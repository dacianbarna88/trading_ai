"""
Full Ecosystem Run — Phase X Sprint X.1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Single daily operating command chaining canonical modules in pipeline order.
Reuses existing modules only — no new strategy logic.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from integration_layer import EvidenceIntegrationGate, IntegrationReportStore
from research_core.evidence_engine import EvidenceEngine, EvidenceReportStore
from research_core.governance.daily_intelligence import DailyIntelligenceCollector
from research_core.orchestrator.ecosystem_orchestrator import EcosystemOrchestrator
from research_core.orchestrator.orchestrator_report import EcosystemOrchestratorReportStore
from research_core.runtime.quick_health_report import QuickHealthVerdict
from research_core.runtime.quick_health_wrapper import QuickHealthWrapper
from research_core.runtime.runtime_report import RuntimeFoundationReportStore
from research_core.runtime.workflow_engine import WorkflowEngine
from research_core.strategy_evolution.daily_runner import StrategyEvolutionDailyRunner
from research_core.strategy_evolution.daily_runner_report import DailyRunnerReportStore
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

from research_core.full_ecosystem.full_ecosystem_report import (
    FullEcosystemRunReport,
    FullEcosystemRunVerdict,
    FullEcosystemStepResult,
)

logger = logging.getLogger(__name__)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]

PORTFOLIO_CSV = Path("portfolio.csv")
LIVE_SIGNALS_CSV = Path("live_signals.csv")

CANONICAL_OUTPUTS = [
    "tae_ecosystem_orchestrator.json",
    "tae_ecosystem_inventory_audit.json",
    "tae_evidence_engine_report.json",
    "tae_strategy_evolution_daily_runner.json",
    "tae_candidate_strategy_registry.json",
    "tae_parallel_paper_validation.json",
    "tae_continuous_strategy_ranking.json",
    "tae_strategy_promotion_gate.json",
    "tae_paper_tracking_log.json",
    "tae_strategic_performance_audit.json",
    "tae_accounting_integrity_audit.json",
    "tae_evidence_integration_gate.json",
    "tae_daily_intelligence_report.json",
    "tae_runtime_foundation.json",
    "tae_quick_health_check.json",
]

MODULES_ALREADY_WIRED = [
    "research_core/runtime/quick_health_wrapper.py",
    "research_core/orchestrator/ecosystem_orchestrator.py",
    "research_core/evidence_engine/evidence_registry.py",
    "research_core/strategy_evolution/daily_runner.py",
    "research_core/strategy_evolution/promotion_gate.py",
    "integration_layer/evidence_gate.py",
    "research_core/strategy_evolution/paper_tracking_log.py",
    "research_core/performance/performance_pipeline_integration.py",
    "research_core/governance/daily_intelligence.py",
    "research_core/runtime/workflow_engine.py",
]

MODULES_EXIST_NOT_DAILY_UNTIL_X1 = [
    "tae_phase8_ecosystem_orchestrator_demo.py — superseded by tae_full_ecosystem_run.py",
    "tae_phase8_strategy_evolution_daily_runner_demo.py — superseded by tae_full_ecosystem_run.py",
    "tae_phase9_runtime_foundation_demo.py — superseded by tae_full_ecosystem_run.py",
    "tae_phase5_daily_intelligence_demo.py — superseded by tae_full_ecosystem_run.py",
]


@dataclass
class _StepDef:
    step_number: int
    step_name: str
    module: str
    mode: str
    run: Callable[[], str]
    output_json: str | None = None
    accept_verdicts: frozenset[str] | None = None


class FullEcosystemRunner:
    """Chains canonical TAE modules into one PAPER_ONLY daily operating flow."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._steps: list[FullEcosystemStepResult] = []
        self._generated: list[str] = []
        self._read: list[str] = []
        self._invoked: list[str] = []
        self._read_only: list[str] = []
        self._warnings: list[str] = []
        self._pre_qh_verdict: str | None = None
        self._post_qh_verdict: str | None = None

    def run(self) -> FullEcosystemRunReport:
        before_mtimes = self._snapshot_mtimes()

        for step_def in self._pipeline():
            self._steps.append(self._execute(step_def))

        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)
        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during full ecosystem run")

        portfolio_status = self._portfolio_status()
        live_signals = self._live_signals_freshness()
        open_positions = self._open_positions_summary()
        integration_health = self._integration_health()
        verdict = self._final_verdict(protected_ok)

        return FullEcosystemRunReport(
            verdict=verdict,
            steps=self._steps,
            modules_invoked=list(dict.fromkeys(self._invoked)),
            modules_read_only=list(dict.fromkeys(self._read_only)),
            canonical_reports_generated=list(dict.fromkeys(self._generated)),
            canonical_reports_read=list(dict.fromkeys(self._read)),
            portfolio_status=portfolio_status,
            live_signals_freshness=live_signals,
            open_positions_summary=open_positions,
            integration_health=integration_health,
            quick_health_pre_verdict=self._pre_qh_verdict,
            quick_health_post_verdict=self._post_qh_verdict,
            protected_files_unchanged=protected_ok,
            warnings=list(self._warnings),
            safety_mode=SAFETY_BANNER,
        )

    def _pipeline(self) -> list[_StepDef]:
        return [
            _StepDef(
                1,
                "Quick Health Pre-Check",
                "research_core/runtime/quick_health_wrapper.py",
                "read_only",
                self._run_quick_health_pre,
            ),
            _StepDef(
                2,
                "Ecosystem Orchestrator",
                "research_core/orchestrator/ecosystem_orchestrator.py",
                "invoke",
                self._run_orchestrator,
                "tae_ecosystem_orchestrator.json",
            ),
            _StepDef(
                3,
                "Evidence Engine Refresh",
                "research_core/evidence_engine/evidence_registry.py",
                "invoke",
                self._run_evidence_engine,
                "tae_evidence_engine_report.json",
            ),
            _StepDef(
                4,
                "Strategy Evolution Daily Runner",
                "research_core/strategy_evolution/daily_runner.py",
                "invoke",
                self._run_daily_runner,
                "tae_strategy_evolution_daily_runner.json",
            ),
            _StepDef(
                5,
                "Promotion Gate",
                "research_core/strategy_evolution/promotion_gate.py",
                "read_only",
                self._read_promotion_gate,
                "tae_strategy_promotion_gate.json",
            ),
            _StepDef(
                6,
                "Integration Gate (Post-Promotion)",
                "integration_layer/evidence_gate.py",
                "invoke",
                self._run_integration_gate,
                "tae_evidence_integration_gate.json",
            ),
            _StepDef(
                7,
                "Paper Tracking",
                "research_core/strategy_evolution/paper_tracking_log.py",
                "read_only",
                self._read_paper_tracking,
                "tae_paper_tracking_log.json",
            ),
            _StepDef(
                8,
                "Performance Pipeline",
                "research_core/performance/performance_pipeline_integration.py",
                "read_only",
                self._read_performance_pipeline,
                "tae_strategic_performance_audit.json",
            ),
            _StepDef(
                9,
                "Governance Daily Intelligence",
                "research_core/governance/daily_intelligence.py",
                "invoke",
                self._run_governance,
                "tae_daily_intelligence_report.json",
            ),
            _StepDef(
                10,
                "Runtime Health",
                "research_core/runtime/workflow_engine.py",
                "invoke",
                self._run_runtime,
                "tae_runtime_foundation.json",
            ),
            _StepDef(
                11,
                "Quick Health Post-Check",
                "research_core/runtime/quick_health_wrapper.py",
                "invoke",
                self._run_quick_health_post,
                "tae_quick_health_check.json",
            ),
        ]

    def _execute(self, step_def: _StepDef) -> FullEcosystemStepResult:
        if step_def.mode == "invoke":
            self._invoked.append(step_def.module)
        else:
            self._read_only.append(step_def.module)

        try:
            verdict = step_def.run()
            if step_def.mode == "read_only":
                succeeded = verdict not in {
                    None,
                    "",
                    "NOT_AVAILABLE",
                    "PERFORMANCE_PIPELINE_DEGRADED",
                }
            else:
                succeeded = bool(verdict) and not str(verdict).startswith("BLOCKED")
            if step_def.output_json:
                if step_def.mode == "invoke":
                    self._generated.append(step_def.output_json)
                else:
                    self._read.append(step_def.output_json)
            return FullEcosystemStepResult(
                step_number=step_def.step_number,
                step_name=step_def.step_name,
                module=step_def.module,
                mode=step_def.mode,
                verdict=verdict,
                succeeded=succeeded,
                output_json=step_def.output_json,
            )
        except Exception as exc:
            logger.exception("Full ecosystem step failed: %s", step_def.step_name)
            self._warnings.append(f"{step_def.step_name}: {type(exc).__name__}: {exc}")
            return FullEcosystemStepResult(
                step_number=step_def.step_number,
                step_name=step_def.step_name,
                module=step_def.module,
                mode=step_def.mode,
                verdict=None,
                succeeded=False,
                output_json=step_def.output_json,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _run_quick_health_pre(self) -> str:
        report = QuickHealthWrapper(self._root).run()
        self._pre_qh_verdict = report.verdict.value
        self._read.append("tae_quick_health_check.json")
        if report.warnings:
            for warning in report.warnings:
                if warning not in self._warnings:
                    self._warnings.append(warning)
        return self._pre_qh_verdict

    def _run_orchestrator(self) -> str:
        report = EcosystemOrchestrator(protected_paths=PROTECTED_PATHS).run()
        store = EcosystemOrchestratorReportStore()
        store.persist(report)
        store.persist_txt(report)
        self._generated.extend([
            "tae_ecosystem_inventory_audit.json",
            "tae_evidence_engine_report.json",
            "tae_evidence_integration_gate.json",
        ])
        if not report.protected_files_unchanged:
            self._warnings.append("Orchestrator reported protected files changed")
        return report.verdict.value

    def _run_evidence_engine(self) -> str:
        report = EvidenceEngine().initialize()
        store = EvidenceReportStore()
        store.persist(report)
        store.persist_txt(report)
        return report.verdict.value

    def _run_daily_runner(self) -> str:
        report = StrategyEvolutionDailyRunner(protected_paths=PROTECTED_PATHS).run()
        store = DailyRunnerReportStore()
        store.persist(report)
        store.persist_txt(report)
        self._generated.extend([
            "tae_candidate_strategy_registry.json",
            "tae_parallel_paper_validation.json",
            "tae_continuous_strategy_ranking.json",
            "tae_strategy_promotion_gate.json",
            "tae_paper_tracking_log.json",
            "tae_strategic_performance_audit.json",
            "tae_accounting_integrity_audit.json",
        ])
        if not report.protected_files_unchanged:
            self._warnings.append("Daily runner reported protected files changed")
        return report.verdict.value

    def _read_promotion_gate(self) -> str:
        payload = self._load_json("tae_strategy_promotion_gate.json")
        if not payload:
            return "NOT_AVAILABLE"
        self._read.append("tae_strategy_promotion_gate.json")
        return str(payload.get("verdict", "NOT_AVAILABLE"))

    def _run_integration_gate(self) -> str:
        report = EvidenceIntegrationGate().evaluate()
        store = IntegrationReportStore()
        store.persist(report)
        store.persist_txt(report)
        return report.verdict.value

    def _read_paper_tracking(self) -> str:
        payload = self._load_json("tae_paper_tracking_log.json")
        if not payload:
            return "NOT_AVAILABLE"
        self._read.append("tae_paper_tracking_log.json")
        return str(payload.get("verdict", "NOT_AVAILABLE"))

    def _read_performance_pipeline(self) -> str:
        strategic = self._load_json("tae_strategic_performance_audit.json")
        integrity = self._load_json("tae_accounting_integrity_audit.json")
        self._read.append("tae_strategic_performance_audit.json")
        self._read.append("tae_accounting_integrity_audit.json")
        if strategic and integrity:
            return "PERFORMANCE_PIPELINE_CONNECTED"
        if strategic or integrity:
            return "PERFORMANCE_PIPELINE_PARTIAL"
        return "PERFORMANCE_PIPELINE_DEGRADED"

    def _run_governance(self) -> str:
        report = DailyIntelligenceCollector().generate_and_persist()
        return f"GOVERNANCE_REPORT_{report.report_date}"

    def _run_runtime(self) -> str:
        report = WorkflowEngine(self._root).run()
        store = RuntimeFoundationReportStore()
        store.persist(report)
        store.persist_txt(report)
        self._generated.append("tae_runtime_learning_memory.json")
        if not report.protected_files_unchanged:
            self._warnings.append("Runtime foundation reported protected files changed")
        return report.verdict.value

    def _run_quick_health_post(self) -> str:
        wrapper = QuickHealthWrapper(self._root)
        report = wrapper.run()
        wrapper.persist(report)
        self._post_qh_verdict = report.verdict.value
        if report.warnings:
            for warning in report.warnings:
                if warning not in self._warnings:
                    self._warnings.append(warning)
        return self._post_qh_verdict

    def _integration_health(self) -> dict[str, Any]:
        payload = self._load_json("tae_quick_health_check.json")
        if not payload:
            return {
                "runtime_health": "UNKNOWN",
                "missing_connections": [],
                "integration_backlog": "UNKNOWN",
            }
        missing = payload.get("missing_connections") or []
        if not isinstance(missing, list):
            missing = []
        return {
            "runtime_health": payload.get("runtime_health_status"),
            "missing_connections": missing,
            "integration_backlog": "NONE" if not missing else "PRESENT",
            "orchestrator_verdict": payload.get("orchestrator_verdict"),
            "modules_wired_audit": MODULES_ALREADY_WIRED,
            "prior_demo_entry_points": MODULES_EXIST_NOT_DAILY_UNTIL_X1,
        }

    def _final_verdict(self, protected_ok: bool) -> FullEcosystemRunVerdict:
        if not protected_ok:
            return FullEcosystemRunVerdict.FULL_ECOSYSTEM_RUN_BLOCKED

        critical_steps = {2, 3, 4, 6, 10}
        for step in self._steps:
            if step.step_number in critical_steps and not step.succeeded:
                return FullEcosystemRunVerdict.FULL_ECOSYSTEM_RUN_BLOCKED

        if self._post_qh_verdict == QuickHealthVerdict.TAE_QUICK_HEALTH_NOT_READY.value:
            return FullEcosystemRunVerdict.FULL_ECOSYSTEM_RUN_BLOCKED

        has_warnings = bool(self._warnings)
        invoke_failures = any(
            not step.succeeded for step in self._steps if step.mode == "invoke"
        )
        post_qh_warnings = (
            self._post_qh_verdict
            == QuickHealthVerdict.TAE_QUICK_HEALTH_READY_WITH_WARNINGS.value
        )

        if has_warnings or invoke_failures or post_qh_warnings:
            return FullEcosystemRunVerdict.FULL_ECOSYSTEM_RUN_READY_WITH_WARNINGS

        return FullEcosystemRunVerdict.FULL_ECOSYSTEM_RUN_READY

    def _portfolio_status(self) -> dict[str, Any]:
        path = self._root / PORTFOLIO_CSV
        if not path.is_file():
            return {"status": "missing", "row_count": 0}
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                rows = list(csv.DictReader(handle))
            return {"status": "readable", "row_count": len(rows), "path": str(PORTFOLIO_CSV)}
        except OSError as exc:
            return {"status": "unreadable", "error": str(exc)}

    def _live_signals_freshness(self) -> str | None:
        path = self._root / LIVE_SIGNALS_CSV
        if not path.is_file():
            return "missing"
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
        return f"updated {mtime.isoformat()} ({age_hours:.1f}h ago)"

    def _open_positions_summary(self) -> list[dict[str, Any]]:
        try:
            from research_core.accounting.independent_double_entry import (
                IndependentDoubleEntryVerifier,
            )

            result = IndependentDoubleEntryVerifier().verify()
            return [
                {
                    "ticker": pos.ticker,
                    "shares": round(pos.shares, 4),
                    "market_value": round(pos.market_value, 2),
                    "cost_basis": round(pos.cost_basis, 2),
                }
                for pos in result.open_positions[:20]
            ]
        except Exception as exc:
            logger.debug("Open positions summary unavailable: %s", exc)
            self._warnings.append(f"Open positions summary unavailable: {exc}")
            return []

    def _load_json(self, name: str) -> dict[str, Any] | None:
        path = self._root / name
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in PROTECTED_PATHS:
            full = self._root / path
            if full.is_file():
                out[str(path)] = full.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
