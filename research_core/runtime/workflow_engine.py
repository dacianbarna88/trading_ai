"""
Workflow Engine — Phase IX C2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Safe read-only workflow over canonical JSON state — no live execution.
"""

from __future__ import annotations

import logging
from pathlib import Path

from research_core.runtime.ecosystem_state import EcosystemStateLoader
from research_core.runtime.event_bus import EventBus, RuntimeEventType
from research_core.runtime.learning_memory import LearningMemory
from research_core.runtime.runtime_health import HealthStatus, RuntimeHealth
from research_core.runtime.runtime_report import (
    RuntimeFoundationReport,
    RuntimeFoundationVerdict,
    WorkflowStepResult,
)

logger = logging.getLogger(__name__)

CRITICAL_SOURCES = {
    "tae_ecosystem_orchestrator.json",
    "tae_evidence_engine_report.json",
    "tae_strategy_evolution_daily_runner.json",
}

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]


class WorkflowEngine:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._bus = EventBus()
        self._workflow_steps: list[WorkflowStepResult] = []

    def run(self) -> RuntimeFoundationReport:
        before_mtimes = self._snapshot_mtimes()

        self._bus.emit(
            RuntimeEventType.ECOSYSTEM_STARTED,
            "workflow_engine",
            "OK",
            "Runtime foundation workflow started",
        )

        state = EcosystemStateLoader(self._root).load()
        loaded_count = sum(1 for v in state.sources_loaded.values() if v)
        self._record_step(
            1,
            "Load EcosystemState",
            "OK",
            f"Loaded {loaded_count}/{len(state.sources_loaded)} state sources",
        )
        self._record_step(
            2,
            "Record ECOSYSTEM_STARTED",
            "OK",
            "ECOSYSTEM_STARTED event emitted",
        )
        self._bus.emit(
            RuntimeEventType.STATE_LOADED,
            "ecosystem_state",
            "OK",
            f"{loaded_count} JSON sources loaded",
        )
        self._record_step(
            3,
            "Record STATE_LOADED",
            "OK",
            f"STATE_LOADED event emitted ({loaded_count} sources)",
        )

        evidence_verdict = state.verdicts.get("evidence")
        self._record_step(
            4,
            "Verify Evidence Engine status",
            "OK" if evidence_verdict else "MISSING",
            f"Evidence verdict: {evidence_verdict or 'N/A'}",
        )
        if evidence_verdict:
            self._bus.emit(
                RuntimeEventType.EVIDENCE_REFRESHED,
                "evidence_engine",
                "OK",
                str(evidence_verdict),
            )

        evolution_verdict = state.verdicts.get("strategy_evolution")
        self._record_step(
            5,
            "Verify Strategy Evolution Daily Runner status",
            "OK" if evolution_verdict else "MISSING",
            f"Daily runner verdict: {evolution_verdict or 'N/A'}",
        )
        if evolution_verdict:
            self._bus.emit(
                RuntimeEventType.STRATEGY_EVOLUTION_UPDATED,
                "strategy_evolution",
                "OK",
                str(evolution_verdict),
            )

        ranking_verdict = state.verdicts.get("ranking")
        if ranking_verdict:
            self._bus.emit(
                RuntimeEventType.RANKING_UPDATED,
                "continuous_ranking",
                "OK",
                f"Top: {state.top_ranked_strategy_id or 'N/A'}",
            )

        promotion_verdict = state.verdicts.get("promotion")
        self._record_step(
            6,
            "Verify Promotion Gate status",
            "OK" if promotion_verdict else "MISSING",
            f"Promotion gate: {promotion_verdict or 'N/A'} | "
            f"Review candidate: {state.promotion_review_candidate_id or 'None'}",
        )
        self._bus.emit(
            RuntimeEventType.PROMOTION_CHECKED,
            "promotion_gate",
            "OK" if promotion_verdict else "MISSING",
            f"Candidate: {state.promotion_review_candidate_id or 'None'}",
        )

        tracking_verdict = state.verdicts.get("paper_tracking")
        self._record_step(
            7,
            "Verify Paper Tracking status",
            "OK" if tracking_verdict else "MISSING",
            f"Paper tracking: {tracking_verdict or 'N/A'} | "
            f"{len(state.paper_tracking_needs)} entries",
        )
        self._bus.emit(
            RuntimeEventType.PAPER_TRACKING_UPDATED,
            "paper_tracking",
            "OK" if tracking_verdict else "MISSING",
            f"{len(state.paper_tracking_needs)} tracking entries",
        )

        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)

        health_report = RuntimeHealth(protected_files_unchanged=protected_ok).evaluate(state)
        state.sections["health"] = health_report.to_dict()
        self._record_step(
            8,
            "Run health checks",
            health_report.overall_status,
            f"{len(health_report.checks)} checks, {len(health_report.issues)} issues",
        )
        self._bus.emit(
            RuntimeEventType.HEALTH_CHECK_COMPLETED,
            "runtime_health",
            health_report.overall_status,
            f"Issues: {len(health_report.issues)}",
        )

        memory_builder = LearningMemory()
        memory = memory_builder.build(state, health_report)
        memory_builder.persist(memory)
        self._record_step(
            9,
            "Update learning memory snapshot",
            "OK",
            "tae_runtime_learning_memory.json written",
        )
        self._bus.emit(
            RuntimeEventType.LEARNING_MEMORY_UPDATED,
            "learning_memory",
            "OK",
            f"{len(memory.lessons_learned)} lessons recorded",
        )

        verdict = self._runtime_verdict(state, health_report)
        self._record_step(
            10,
            "Produce runtime report",
            verdict.value,
            "Runtime foundation report complete",
        )
        self._bus.emit(
            RuntimeEventType.ECOSYSTEM_COMPLETED,
            "workflow_engine",
            verdict.value,
            f"Health: {health_report.overall_status}",
        )

        return RuntimeFoundationReport(
            verdict=verdict,
            loaded_state_sources=state.sources_loaded,
            events_emitted=self._bus.to_dict(),
            workflow_steps=sorted(self._workflow_steps, key=lambda s: s.step_number),
            health_status=health_report.overall_status,
            health_checks=[check.to_dict() for check in health_report.checks],
            health_issues=list(health_report.issues),
            learning_memory_summary=memory.to_dict(),
            top_ranked_strategy_id=state.top_ranked_strategy_id,
            top_ranked_strategy_score=state.top_ranked_strategy_score,
            promotion_review_candidate_id=state.promotion_review_candidate_id,
            paper_tracking_needs=state.paper_tracking_needs,
            missing_connections=state.missing_connections,
            conflict_warnings=state.conflict_warnings,
            protected_files_unchanged=protected_ok,
        )

    def _record_step(
        self,
        step_number: int,
        step_name: str,
        status: str,
        message: str,
    ) -> None:
        self._workflow_steps.append(
            WorkflowStepResult(
                step_number=step_number,
                step_name=step_name,
                status=status,
                message=message,
            )
        )

    @staticmethod
    def _runtime_verdict(state, health_report) -> RuntimeFoundationVerdict:
        critical_missing = any(
            not state.sources_loaded.get(src, False) for src in CRITICAL_SOURCES
        )
        if critical_missing or health_report.overall_status == HealthStatus.CRITICAL.value:
            return RuntimeFoundationVerdict.RUNTIME_FOUNDATION_CRITICAL

        if (
            health_report.overall_status == HealthStatus.DEGRADED.value
            and RuntimeHealth.integration_backlog_only(health_report.issues)
        ):
            return (
                RuntimeFoundationVerdict.RUNTIME_FOUNDATION_DEGRADED_WITH_KNOWN_INTEGRATION_BACKLOG
            )

        optional_missing = any(not loaded for loaded in state.sources_loaded.values())
        if optional_missing or health_report.overall_status == HealthStatus.DEGRADED.value:
            return RuntimeFoundationVerdict.RUNTIME_FOUNDATION_DEGRADED

        return RuntimeFoundationVerdict.RUNTIME_FOUNDATION_READY

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
