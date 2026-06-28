"""
Runtime Health — Phase IX C2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from research_core.runtime.ecosystem_state import EcosystemState, STATE_SOURCES

CRITICAL_SOURCES = {
    "tae_ecosystem_orchestrator.json",
    "tae_evidence_engine_report.json",
    "tae_strategy_evolution_daily_runner.json",
}

CANONICAL_MODULES = {
    "research_core/accounting/independent_double_entry.py",
    "research_core/evidence_engine/evidence_registry.py",
    "research_core/strategy_evolution/daily_runner.py",
    "integration_layer/evidence_gate.py",
    "research_core/orchestrator/ecosystem_orchestrator.py",
}


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


@dataclass
class HealthCheck:
    check_id: str
    status: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class RuntimeHealthReport:
    overall_status: str
    checks: list[HealthCheck]
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "checks": [check.to_dict() for check in self.checks],
            "issues": list(self.issues),
        }


class RuntimeHealth:
    def __init__(self, protected_files_unchanged: bool = True) -> None:
        self._protected_files_unchanged = protected_files_unchanged

    def evaluate(self, state: EcosystemState) -> RuntimeHealthReport:
        checks: list[HealthCheck] = []
        issues: list[str] = []

        checks.append(self._check_required_json(state, issues))
        checks.append(self._check_subsystem_verdicts(state, issues))
        checks.append(self._check_protected_files(issues))
        checks.append(self._check_promotion_gate_bypass(state, issues))
        checks.append(self._check_canonical_modules(state, issues))
        checks.append(self._check_missing_connections(state, issues))
        checks.append(self._check_top_ranked_strategy(state, issues))
        checks.append(self._check_paper_tracking(state, issues))
        checks.append(self._check_performance_pipeline(state, issues))
        checks.append(self._check_evidence_gap_registration(state, issues))
        checks.append(self._check_regional_validation_integration(state, issues))

        statuses = [check.status for check in checks]
        if HealthStatus.CRITICAL.value in statuses or any(
            not state.sources_loaded.get(src, False) for src in CRITICAL_SOURCES
        ):
            overall = HealthStatus.CRITICAL.value
        elif HealthStatus.DEGRADED.value in statuses:
            overall = HealthStatus.DEGRADED.value
        else:
            overall = HealthStatus.HEALTHY.value

        return RuntimeHealthReport(
            overall_status=overall,
            checks=checks,
            issues=issues,
        )

    def _check_required_json(
        self,
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        missing = [
            filename
            for filename in STATE_SOURCES.values()
            if not state.sources_loaded.get(filename, False)
        ]
        critical_missing = [f for f in missing if f in CRITICAL_SOURCES]
        if critical_missing:
            issues.append(f"Critical JSON missing: {', '.join(critical_missing)}")
            return HealthCheck(
                check_id="required_json",
                status=HealthStatus.CRITICAL.value,
                message=f"Missing critical sources: {critical_missing}",
            )
        if missing:
            issues.append(f"Optional JSON missing: {', '.join(missing)}")
            return HealthCheck(
                check_id="required_json",
                status=HealthStatus.DEGRADED.value,
                message=f"Missing optional sources: {missing}",
            )
        return HealthCheck(
            check_id="required_json",
            status=HealthStatus.HEALTHY.value,
            message="All state JSON sources loaded",
        )

    def _check_subsystem_verdicts(
        self,
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        required = ("evidence", "strategy_evolution", "promotion", "paper_tracking")
        missing_verdicts = [key for key in required if not state.verdicts.get(key)]
        if missing_verdicts:
            issues.append(f"Missing subsystem verdicts: {missing_verdicts}")
            return HealthCheck(
                check_id="subsystem_verdicts",
                status=HealthStatus.DEGRADED.value,
                message=f"Missing verdicts: {missing_verdicts}",
            )
        return HealthCheck(
            check_id="subsystem_verdicts",
            status=HealthStatus.HEALTHY.value,
            message="Core subsystem verdicts present",
        )

    def _check_protected_files(self, issues: list[str]) -> HealthCheck:
        if not self._protected_files_unchanged:
            issues.append("Protected live files may have changed during runtime")
            return HealthCheck(
                check_id="protected_files",
                status=HealthStatus.CRITICAL.value,
                message="Protected files not confirmed unchanged",
            )
        return HealthCheck(
            check_id="protected_files",
            status=HealthStatus.HEALTHY.value,
            message="Protected files unchanged",
        )

    @staticmethod
    def _check_promotion_gate_bypass(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        review = state.promotion_review_candidate_id
        promotion_verdict = state.verdicts.get("promotion")
        if review and promotion_verdict != "STRATEGY_PROMOTION_GATE_READY":
            issues.append(f"Promotion candidate {review} without gate ready verdict")
            return HealthCheck(
                check_id="promotion_gate_bypass",
                status=HealthStatus.CRITICAL.value,
                message="Promotion candidate bypasses gate",
            )
        if review:
            return HealthCheck(
                check_id="promotion_gate_bypass",
                status=HealthStatus.DEGRADED.value,
                message=f"Review candidate present: {review}",
            )
        return HealthCheck(
            check_id="promotion_gate_bypass",
            status=HealthStatus.HEALTHY.value,
            message="No promotion candidate bypassing gate",
        )

    @staticmethod
    def _check_canonical_modules(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        interconnection = state.sections.get("interconnection")
        if not interconnection:
            issues.append("Interconnection map not loaded — canonical modules unverified")
            return HealthCheck(
                check_id="canonical_modules",
                status=HealthStatus.DEGRADED.value,
                message="Interconnection map missing",
            )
        canonical_paths = {
            item.get("canonical_module")
            for item in interconnection.get("canonical_module_map", [])
            if isinstance(item, dict)
        }
        missing = CANONICAL_MODULES - {p for p in canonical_paths if p}
        if missing:
            issues.append(f"Canonical modules missing from map: {sorted(missing)}")
            return HealthCheck(
                check_id="canonical_modules",
                status=HealthStatus.DEGRADED.value,
                message=f"Missing canonical entries: {sorted(missing)}",
            )
        return HealthCheck(
            check_id="canonical_modules",
            status=HealthStatus.HEALTHY.value,
            message="All canonical modules present in interconnection map",
        )

    @staticmethod
    def _check_missing_connections(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        if state.missing_connections:
            for connection in state.missing_connections:
                issues.append(f"Integration backlog: {connection}")
            return HealthCheck(
                check_id="missing_connections",
                status=HealthStatus.DEGRADED.value,
                message=(
                    f"{len(state.missing_connections)} integration backlog "
                    "degradation reason(s)"
                ),
            )
        return HealthCheck(
            check_id="missing_connections",
            status=HealthStatus.HEALTHY.value,
            message="No missing connections documented",
        )

    @staticmethod
    def integration_backlog_only(issues: list[str]) -> bool:
        return bool(issues) and all(
            issue.startswith("Integration backlog:") for issue in issues
        )

    @staticmethod
    def _check_top_ranked_strategy(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        if not state.top_ranked_strategy_id:
            issues.append("Top ranked strategy unavailable")
            return HealthCheck(
                check_id="top_ranked_strategy",
                status=HealthStatus.DEGRADED.value,
                message="Top ranked strategy not available",
            )
        return HealthCheck(
            check_id="top_ranked_strategy",
            status=HealthStatus.HEALTHY.value,
            message=f"Top ranked: {state.top_ranked_strategy_id}",
        )

    @staticmethod
    def _check_paper_tracking(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        if not state.paper_tracking_needs:
            issues.append("Paper tracking needs unavailable")
            return HealthCheck(
                check_id="paper_tracking",
                status=HealthStatus.DEGRADED.value,
                message="Paper tracking needs not available",
            )
        return HealthCheck(
            check_id="paper_tracking",
            status=HealthStatus.HEALTHY.value,
            message=f"{len(state.paper_tracking_needs)} paper tracking entries",
        )

    @staticmethod
    def _check_performance_pipeline(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        strategic_loaded = state.sources_loaded.get(
            "tae_strategic_performance_audit.json", False
        )
        integrity_loaded = state.sources_loaded.get(
            "tae_accounting_integrity_audit.json", False
        )
        pipeline_verdict = state.verdicts.get("performance_pipeline")

        if not strategic_loaded:
            issues.append("Performance pipeline: strategic performance audit JSON missing")
            return HealthCheck(
                check_id="performance_pipeline",
                status=HealthStatus.DEGRADED.value,
                message="Strategic performance audit not available",
            )
        if not integrity_loaded:
            issues.append("Performance pipeline: accounting integrity audit JSON missing")
            return HealthCheck(
                check_id="performance_pipeline",
                status=HealthStatus.DEGRADED.value,
                message="Accounting integrity audit not available (optional stage output)",
            )
        msg = "Performance pipeline stage connected via canonical JSON"
        if pipeline_verdict:
            msg = f"{msg} | pipeline report: {pipeline_verdict}"
        return HealthCheck(
            check_id="performance_pipeline",
            status=HealthStatus.HEALTHY.value,
            message=msg,
        )

    @staticmethod
    def _check_evidence_gap_registration(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        evidence_section = state.sections.get("evidence") or {}
        gap_reg = evidence_section.get("evidence_gap_registration")
        gap_status = state.verdicts.get("evidence_gap_registration")

        if not isinstance(gap_reg, dict) or not gap_reg.get("evidence_gap_registered"):
            issues.append("Evidence gap not registered in Evidence Registry refresh")
            return HealthCheck(
                check_id="evidence_gap_registration",
                status=HealthStatus.DEGRADED.value,
                message="Evidence gap feeder not registered in evidence engine report",
            )

        status = str(gap_reg.get("evidence_gap_status", gap_status or ""))
        if status == "EVIDENCE_GAP_REGISTERED_MISSING_REPORT":
            return HealthCheck(
                check_id="evidence_gap_registration",
                status=HealthStatus.HEALTHY.value,
                message=(
                    "Evidence gap registered in registry — source report missing "
                    "(EVIDENCE_GAP_REGISTERED_MISSING_REPORT)"
                ),
            )

        warning_count = gap_reg.get("evidence_gap_warning_count", 0)
        return HealthCheck(
            check_id="evidence_gap_registration",
            status=HealthStatus.HEALTHY.value,
            message=(
                f"Evidence gap registered via {gap_reg.get('evidence_gap_source_report')} "
                f"| warnings={warning_count}"
            ),
        )

    @staticmethod
    def _check_regional_validation_integration(
        state: EcosystemState,
        issues: list[str],
    ) -> HealthCheck:
        promotion_section = state.sections.get("promotion") or {}
        regional_reg = promotion_section.get("regional_validation_registration")
        regional_status = state.verdicts.get("regional_validation_integration")

        if not isinstance(regional_reg, dict) or not regional_reg.get(
            "regional_validation_registered"
        ):
            issues.append(
                "Regional validation not registered in Promotion Gate refresh"
            )
            return HealthCheck(
                check_id="regional_validation_integration",
                status=HealthStatus.DEGRADED.value,
                message="Regional validation feeder not registered in promotion gate report",
            )

        status = str(regional_reg.get("regional_validation_status", regional_status or ""))
        if status == "REGIONAL_VALIDATION_REGISTERED_MISSING_REPORT":
            return HealthCheck(
                check_id="regional_validation_integration",
                status=HealthStatus.HEALTHY.value,
                message=(
                    "Regional validation registered in promotion gate — source report "
                    "missing (REGIONAL_VALIDATION_REGISTERED_MISSING_REPORT)"
                ),
            )

        return HealthCheck(
            check_id="regional_validation_integration",
            status=HealthStatus.HEALTHY.value,
            message=(
                f"Regional validation registered via "
                f"{regional_reg.get('regional_validation_source')} "
                f"| refresh={regional_reg.get('regional_validation_last_refresh')}"
            ),
        )
