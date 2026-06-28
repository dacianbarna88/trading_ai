"""
Ecosystem Orchestrator — Phase VIII B8

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Runs the full read-only ecosystem chain and produces a single daily
ecosystem intelligence report. Reuses existing modules only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from integration_layer import EvidenceIntegrationGate, IntegrationReportStore
from integration_layer.integration_report import IntegrationGateVerdict
from research_core.ecosystem_inventory import EcosystemInventoryAudit, EcosystemInventoryReportStore
from research_core.ecosystem_inventory.inventory_report import InventoryVerdict
from research_core.evidence_engine import EvidenceEngine, EvidenceReportStore
from research_core.evidence_engine.evidence_report import EvidenceEngineVerdict
from research_core.integration_adapters.strategy_adapter import StrategyAdapter
from research_core.orchestrator.orchestrator_report import (
    EcosystemOrchestratorReport,
    OrchestratorStepResult,
    OrchestratorVerdict,
    PaperTrackingSummary,
    PromotionGateSummary,
)

logger = logging.getLogger(__name__)

STRATEGY_STATE_DEGRADED_VERDICT = "STRATEGY_EVOLUTION_STATE_DEGRADED"
STRATEGY_RUNNER_READY_VERDICT = "STRATEGY_EVOLUTION_DAILY_RUNNER_READY"
STRATEGY_RUNNER_PARTIAL_VERDICT = "STRATEGY_EVOLUTION_DAILY_RUNNER_PARTIAL_FAILURE"

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]

INVENTORY_JSON = Path("tae_ecosystem_inventory_audit.json")
EVIDENCE_JSON = Path("tae_evidence_engine_report.json")
INTEGRATION_JSON = Path("tae_evidence_integration_gate.json")
DAILY_RUNNER_JSON = Path("tae_strategy_evolution_daily_runner.json")
PROMOTION_GATE_JSON = Path("tae_strategy_promotion_gate.json")
PAPER_TRACKING_JSON = Path("tae_paper_tracking_log.json")

DO_NOT_REWRITE = [
    "live_bot.py",
    "dashboard_v2.py",
    "config/settings.py",
    "portfolio.csv",
    "core/trades.py",
    "core/portfolio_prices.py",
    "core/portfolio.py",
    "core/entry_filter.py",
    "core/exit_intelligence.py",
    "core/risk.py",
    "core/allocation.py",
    "research_core/strategy_evolution/daily_runner.py",
    "research_core/evidence_engine/evidence_registry.py",
    "research_core/accounting/independent_double_entry.py",
    "integration_layer/evidence_gate.py",
]

FINAL_RECOMMENDATION = (
    "Connect Evidence Engine refresh + Strategy Evolution daily runner + "
    "Integration Gate into one controlled daily process."
)


@dataclass
class _OrchestratorStepDef:
    step_number: int
    step_name: str
    subsystem: str
    run: Callable[[], str]
    expected_verdict: str
    output_json: str | None = None
    output_txt: str | None = None


class EcosystemOrchestrator:
    def __init__(self, protected_paths: list[Path] | None = None) -> None:
        self._protected_paths = protected_paths or PROTECTED_PATHS
        self._inventory_report = None
        self._strategy_state: dict[str, Any] | None = None

    def run(self) -> EcosystemOrchestratorReport:
        before_mtimes = self._snapshot_mtimes()
        steps: list[OrchestratorStepResult] = []

        for step_def in self._executable_steps():
            steps.append(self._run_step(step_def))

        summary_steps = self._summary_steps()
        for step_def in summary_steps:
            steps.append(self._run_summary_step(step_def))

        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)
        all_succeeded = all(step.succeeded for step in steps)

        strategy_state = self._get_strategy_state()
        gate_payload = strategy_state.get("promotion_gate") or {}
        if not isinstance(gate_payload, dict):
            gate_payload = {}
        tracking_payload = strategy_state.get("paper_tracking") or {}
        if not isinstance(tracking_payload, dict):
            tracking_payload = {}

        promotion_summary = self._promotion_gate_summary(gate_payload)
        tracking_summary = self._paper_tracking_summary(tracking_payload)
        missing_connections = self._missing_connections()
        next_impl = self._next_recommended_implementation(missing_connections)

        return EcosystemOrchestratorReport(
            verdict=(
                OrchestratorVerdict.ECOSYSTEM_ORCHESTRATOR_READY
                if all_succeeded
                else OrchestratorVerdict.ECOSYSTEM_ORCHESTRATOR_PARTIAL_FAILURE
            ),
            steps=steps,
            subsystem_verdicts=self._subsystem_verdicts(steps),
            top_ranked_strategy_id=strategy_state.get("top_ranked_strategy_id"),
            top_ranked_strategy_score=strategy_state.get("top_ranked_strategy_score"),
            promotion_review_candidate_id=(
                gate_payload.get("review_candidate_id")
                or strategy_state.get("promotion_review_candidate_id")
            ),
            promotion_gate_summary=promotion_summary,
            paper_tracking_summary=tracking_summary,
            missing_connections=missing_connections,
            do_not_rewrite=list(DO_NOT_REWRITE),
            next_recommended_implementation=next_impl,
            final_ecosystem_recommendation=FINAL_RECOMMENDATION,
            protected_files_unchanged=protected_ok,
            strategy_state_source=strategy_state.get(
                "adapter_path",
                "StrategyAdapter.load_strategy_state_for_orchestrator()",
            ),
            strategy_state_completeness=strategy_state.get("strategy_state_completeness"),
            strategy_adapter_id=strategy_state.get("adapter_id"),
            strategy_contract_validation=strategy_state.get("contract_validation"),
        )

    def _executable_steps(self) -> list[_OrchestratorStepDef]:
        return [
            _OrchestratorStepDef(
                step_number=1,
                step_name="Ecosystem Inventory Audit",
                subsystem="ecosystem_inventory",
                run=self._run_inventory_audit,
                expected_verdict=InventoryVerdict.ECOSYSTEM_INVENTORY_AUDIT_READY.value,
                output_json=INVENTORY_JSON.name,
                output_txt="tae_ecosystem_inventory_audit.txt",
            ),
            _OrchestratorStepDef(
                step_number=2,
                step_name="Evidence Engine Refresh",
                subsystem="evidence_engine",
                run=self._run_evidence_engine,
                expected_verdict=EvidenceEngineVerdict.EVIDENCE_ENGINE_SOURCE_OF_TRUTH_ALIGNED.value,
                output_json=EVIDENCE_JSON.name,
                output_txt="tae_evidence_engine_report.txt",
            ),
            _OrchestratorStepDef(
                step_number=3,
                step_name="Evidence Integration Gate",
                subsystem="integration_gate",
                run=self._run_integration_gate,
                expected_verdict=IntegrationGateVerdict.EVIDENCE_INTEGRATION_GATE_READY.value,
                output_json=INTEGRATION_JSON.name,
                output_txt="tae_evidence_integration_gate.txt",
            ),
            _OrchestratorStepDef(
                step_number=4,
                step_name="Strategy Evolution State (Adapter)",
                subsystem="strategy_evolution",
                run=self._load_strategy_state_via_adapter,
                expected_verdict=STRATEGY_RUNNER_READY_VERDICT,
                output_json=DAILY_RUNNER_JSON.name,
                output_txt="tae_strategy_evolution_daily_runner.txt",
            ),
        ]

    def _summary_steps(self) -> list[_OrchestratorStepDef]:
        return [
            _OrchestratorStepDef(
                step_number=5,
                step_name="Promotion Gate Summary",
                subsystem="promotion_gate",
                run=self._run_promotion_gate_summary,
                expected_verdict="STRATEGY_PROMOTION_GATE_READY",
                output_json=PROMOTION_GATE_JSON.name,
                output_txt="tae_strategy_promotion_gate.txt",
            ),
            _OrchestratorStepDef(
                step_number=6,
                step_name="Paper Tracking Summary",
                subsystem="paper_tracking",
                run=self._run_paper_tracking_summary,
                expected_verdict="PAPER_TRACKING_LOG_READY",
                output_json=PAPER_TRACKING_JSON.name,
                output_txt="tae_paper_tracking_log.txt",
            ),
            _OrchestratorStepDef(
                step_number=7,
                step_name="Missing Connections Summary",
                subsystem="ecosystem_inventory",
                run=self._run_missing_connections_summary,
                expected_verdict=InventoryVerdict.ECOSYSTEM_INVENTORY_AUDIT_READY.value,
                output_json=INVENTORY_JSON.name,
            ),
            _OrchestratorStepDef(
                step_number=8,
                step_name="Final Ecosystem Recommendation",
                subsystem="orchestrator",
                run=lambda: FINAL_RECOMMENDATION,
                expected_verdict=FINAL_RECOMMENDATION,
            ),
        ]

    def _run_step(self, step_def: _OrchestratorStepDef) -> OrchestratorStepResult:
        try:
            verdict = step_def.run()
            succeeded = self._step_succeeded(step_def, verdict)
            return OrchestratorStepResult(
                step_number=step_def.step_number,
                step_name=step_def.step_name,
                subsystem=step_def.subsystem,
                verdict=verdict,
                succeeded=succeeded,
                output_json=step_def.output_json,
                output_txt=step_def.output_txt,
                error=None if succeeded else f"Unexpected verdict: {verdict}",
            )
        except Exception as exc:
            logger.exception("Orchestrator step failed: %s", step_def.step_name)
            return OrchestratorStepResult(
                step_number=step_def.step_number,
                step_name=step_def.step_name,
                subsystem=step_def.subsystem,
                verdict=None,
                succeeded=False,
                output_json=step_def.output_json,
                output_txt=step_def.output_txt,
                error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _step_succeeded(step_def: _OrchestratorStepDef, verdict: str) -> bool:
        if step_def.subsystem == "evidence_engine":
            return verdict in {item.value for item in EvidenceEngineVerdict}
        if step_def.subsystem == "strategy_evolution":
            return verdict in {
                STRATEGY_RUNNER_READY_VERDICT,
                STRATEGY_RUNNER_PARTIAL_VERDICT,
                STRATEGY_STATE_DEGRADED_VERDICT,
            }
        return verdict == step_def.expected_verdict

    def _run_summary_step(self, step_def: _OrchestratorStepDef) -> OrchestratorStepResult:
        try:
            verdict = step_def.run()
            if step_def.step_number == 8:
                succeeded = bool(verdict)
            else:
                succeeded = verdict == step_def.expected_verdict
            return OrchestratorStepResult(
                step_number=step_def.step_number,
                step_name=step_def.step_name,
                subsystem=step_def.subsystem,
                verdict=verdict if step_def.step_number != 8 else "RECOMMENDATION_READY",
                succeeded=succeeded,
                output_json=step_def.output_json,
                output_txt=step_def.output_txt,
                error=None if succeeded else f"Unexpected result: {verdict}",
            )
        except Exception as exc:
            logger.exception("Orchestrator summary step failed: %s", step_def.step_name)
            return OrchestratorStepResult(
                step_number=step_def.step_number,
                step_name=step_def.step_name,
                subsystem=step_def.subsystem,
                verdict=None,
                succeeded=False,
                output_json=step_def.output_json,
                output_txt=step_def.output_txt,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _run_inventory_audit(self) -> str:
        report = EcosystemInventoryAudit().audit()
        EcosystemInventoryReportStore().persist(report)
        EcosystemInventoryReportStore().persist_txt(report)
        self._inventory_report = report
        return report.verdict.value

    @staticmethod
    def _run_evidence_engine() -> str:
        report = EvidenceEngine().initialize()
        store = EvidenceReportStore()
        store.persist(report)
        store.persist_txt(report)
        return report.verdict.value

    @staticmethod
    def _run_integration_gate() -> str:
        report = EvidenceIntegrationGate().evaluate()
        store = IntegrationReportStore()
        store.persist(report)
        store.persist_txt(report)
        return report.verdict.value

    def _get_strategy_state(self) -> dict[str, Any]:
        if self._strategy_state is None:
            self._strategy_state = StrategyAdapter.load_strategy_state_for_orchestrator()
        return self._strategy_state

    def _load_strategy_state_via_adapter(self) -> str:
        state = self._get_strategy_state()
        verdict = state.get("daily_runner_verdict")
        if verdict:
            return str(verdict)
        completeness = state.get("strategy_state_completeness", "DEGRADED")
        if completeness == "DEGRADED":
            return STRATEGY_STATE_DEGRADED_VERDICT
        return STRATEGY_RUNNER_PARTIAL_VERDICT

    def _run_promotion_gate_summary(self) -> str:
        gate = self._get_strategy_state().get("promotion_gate") or {}
        if not isinstance(gate, dict):
            return ""
        return str(gate.get("verdict", ""))

    def _run_paper_tracking_summary(self) -> str:
        tracking = self._get_strategy_state().get("paper_tracking") or {}
        if not isinstance(tracking, dict):
            return ""
        return str(tracking.get("verdict", ""))

    def _run_missing_connections_summary(self) -> str:
        if self._inventory_report is None:
            payload = self._load_json(INVENTORY_JSON)
            if payload:
                return str(payload.get("verdict", ""))
            report = EcosystemInventoryAudit().audit()
            self._inventory_report = report
        return self._inventory_report.verdict.value

    def _missing_connections(self) -> list[str]:
        if self._inventory_report is not None:
            return list(self._inventory_report.missing_connections)
        payload = self._load_json(INVENTORY_JSON)
        if payload and isinstance(payload.get("missing_connections"), list):
            return [str(item) for item in payload["missing_connections"]]
        return []

    @staticmethod
    def _promotion_gate_summary(payload: dict[str, Any]) -> PromotionGateSummary:
        entries = payload.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        return PromotionGateSummary(
            review_candidate_id=payload.get("review_candidate_id"),
            entries=[
                {
                    "candidate_id": entry.get("candidate_id"),
                    "decision": entry.get("decision"),
                    "trades": entry.get("trades"),
                    "ranking_score": entry.get("ranking_score"),
                    "blockers": entry.get("blockers", []),
                    "required_next_step": entry.get("required_next_step"),
                }
                for entry in entries
                if isinstance(entry, dict)
            ],
        )

    @staticmethod
    def _paper_tracking_summary(payload: dict[str, Any]) -> PaperTrackingSummary:
        entries = payload.get("entries", [])
        if not isinstance(entries, list):
            entries = []
        return PaperTrackingSummary(
            entries=[
                {
                    "candidate_id": entry.get("candidate_id"),
                    "tracking_status": entry.get("tracking_status"),
                    "current_trades": entry.get("current_trades"),
                    "trades_needed": entry.get("trades_needed"),
                    "tracking_note": entry.get("tracking_note"),
                    "sample_insufficient": entry.get("sample_insufficient", False),
                }
                for entry in entries
                if isinstance(entry, dict)
                and entry.get("tracking_status") != "BASELINE_REFERENCE"
            ],
        )

    @staticmethod
    def _next_recommended_implementation(missing_connections: list[str]) -> str:
        if missing_connections:
            return (
                "Wire Evidence Engine refresh as pre-step and Integration Gate as post-step "
                "around Strategy Evolution daily runner; address missing connections without "
                "rewriting live execution modules."
            )
        return FINAL_RECOMMENDATION

    @staticmethod
    def _subsystem_verdicts(steps: list[OrchestratorStepResult]) -> dict[str, str | None]:
        verdicts: dict[str, str | None] = {}
        for step in steps:
            if step.step_number <= 4:
                verdicts[step.subsystem] = step.verdict
        return verdicts

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in self._protected_paths:
            if path.is_file():
                out[str(path)] = path.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
