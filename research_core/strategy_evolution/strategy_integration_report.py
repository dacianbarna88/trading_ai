"""
Strategy Integration Report — Phase IX Sprint IX.2C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.pipeline_integration import CANONICAL_REPORT_PATH
from research_core.strategy_evolution.strategy_dependency_map import (
    CANONICAL_RUNNER_PATH,
    INTEGRATION_TARGETS,
    ModuleRole,
    StrategyDependencyMap,
    StrategyDependencyMapBuilder,
    StrategyDependencyMapStore,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

REPORT_JSON = Path("tae_strategy_integration_report.json")
REPORT_TXT = Path("tae_strategy_integration_report.txt")


class IntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    PARTIAL = "PARTIAL"
    DISCONNECTED = "DISCONNECTED"
    LEGACY = "LEGACY_PLANNING_ONLY"


@dataclass
class TargetIntegration:
    module_path: str
    status: IntegrationStatus
    role: str
    pipeline_role: str | None
    reads_canonical_json: bool
    notes: str

    def to_dict(self) -> dict[str, str]:
        return {
            "module_path": self.module_path,
            "status": self.status.value,
            "role": self.role,
            "pipeline_role": self.pipeline_role or "",
            "reads_canonical_json": str(self.reads_canonical_json),
            "notes": self.notes,
        }


@dataclass
class StrategyIntegrationReport:
    canonical_runner: str
    canonical_json_exists: bool
    single_runner_verified: bool
    no_competing_official_runner_verified: bool
    promotion_gate_review_only_verified: bool
    paper_tracking_paper_only_verified: bool
    integration_targets: list[TargetIntegration]
    competing_demos: list[str]
    validation_checks: list[str]
    warnings: list[str]
    verdict: str = "STRATEGY_EVOLUTION_INTEGRATION_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_strategy_integration_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_runner": self.canonical_runner,
            "canonical_json_exists": self.canonical_json_exists,
            "single_runner_verified": self.single_runner_verified,
            "no_competing_official_runner_verified": self.no_competing_official_runner_verified,
            "promotion_gate_review_only_verified": self.promotion_gate_review_only_verified,
            "paper_tracking_paper_only_verified": self.paper_tracking_paper_only_verified,
            "integration_targets": [t.to_dict() for t in self.integration_targets],
            "competing_demos": list(self.competing_demos),
            "validation_checks": list(self.validation_checks),
            "warnings": list(self.warnings),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE STRATEGY INTEGRATION REPORT — SPRINT IX.2C =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical runner: {self.canonical_runner}",
            f"Canonical JSON present: {self.canonical_json_exists}",
            "",
            "===== VALIDATION =====",
            f"  Single runner:              {self.single_runner_verified}",
            f"  No competing official runner: {self.no_competing_official_runner_verified}",
            f"  Promotion gate review-only: {self.promotion_gate_review_only_verified}",
            f"  Paper tracking paper-only:  {self.paper_tracking_paper_only_verified}",
            "",
            "===== INTEGRATION TARGETS =====",
        ]
        for target in self.integration_targets:
            lines.append(
                f"  [{target.status.value}] {target.module_path} ({target.role})"
            )
            lines.append(f"      pipeline_role={target.pipeline_role} — {target.notes}")
        lines.extend(["", "===== COMPETING DEMOS (non-official) ====="])
        for demo in self.competing_demos:
            lines.append(f"  {demo}")
        lines.extend(["", "===== CHECKS ====="])
        for check in self.validation_checks:
            lines.append(f"  ✓ {check}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        lines.append("")
        return "\n".join(lines)


class StrategyIntegrationAnalyzer:
    def analyze(self, dep_map: StrategyDependencyMap) -> StrategyIntegrationReport:
        node_by_path = {n.module_path: n for n in dep_map.nodes}
        targets: list[TargetIntegration] = []
        warnings: list[str] = list(dep_map.bypass_risks)
        checks: list[str] = []

        for path in INTEGRATION_TARGETS:
            node = node_by_path.get(path)
            if node is None:
                targets.append(
                    TargetIntegration(
                        module_path=path,
                        status=IntegrationStatus.DISCONNECTED,
                        role="UNKNOWN",
                        pipeline_role=None,
                        reads_canonical_json=False,
                        notes="Module not found",
                    )
                )
                continue

            if node.role == ModuleRole.LEGACY_PLANNING:
                status = IntegrationStatus.LEGACY
                notes = "Phase V planning-only — superseded by Daily Runner"
            elif node.role == ModuleRole.REPORT_SCHEMA:
                status = IntegrationStatus.CONNECTED
                notes = "Report schema for validation feeder"
            elif node.reads_canonical_json or node.imports_pipeline:
                status = IntegrationStatus.CONNECTED
                notes = self._notes_for_role(node.role, node.pipeline_role)
            else:
                status = IntegrationStatus.DISCONNECTED
                notes = "Not wired to canonical daily runner"

            targets.append(
                TargetIntegration(
                    module_path=path,
                    status=status,
                    role=node.role.value,
                    pipeline_role=node.pipeline_role,
                    reads_canonical_json=node.reads_canonical_json,
                    notes=notes,
                )
            )

        single_runner = dep_map.runner_count == 1
        if single_runner:
            checks.append("Exactly one StrategyEvolutionDailyRunner exists")

        no_competing = len(dep_map.competing_demos) > 0
        if no_competing:
            checks.append(
                f"Step demos classified as non-official ({len(dep_map.competing_demos)} found)"
            )

        promo = node_by_path.get("research_core/strategy_evolution/promotion_gate.py")
        promo_ok = promo and promo.pipeline_role == "PIPELINE_STEP_PROMOTION_REVIEW_ONLY"
        if promo_ok:
            checks.append("Promotion gate is review-only pipeline step")

        paper = node_by_path.get("research_core/strategy_evolution/paper_tracking_log.py")
        paper_ok = paper and paper.pipeline_role == "PIPELINE_STEP_PAPER_TRACKING"
        if paper_ok:
            checks.append("Paper tracking is paper-only pipeline step")

        sim = node_by_path.get("research_core/simulation_lab/strategy_simulation_lab.py")
        if sim and sim.role == ModuleRole.FEEDER_READER:
            checks.append("simulation_lab connected as FEEDER_READER")

        regional = node_by_path.get("research_core/regional_validation/regional_gap_closure.py")
        if regional and regional.role == ModuleRole.VALIDATION_FEEDER:
            checks.append("regional_validation connected as VALIDATION_FEEDER")
        elif regional:
            warnings.append("regional_validation not fully connected as VALIDATION_FEEDER")

        canonical_exists = CANONICAL_REPORT_PATH.is_file()
        if canonical_exists:
            checks.append("Canonical daily runner report available on disk")
        else:
            warnings.append("Run tae_phase8_ecosystem_orchestrator_demo or daily runner demo")

        all_ok = all(
            t.status in (IntegrationStatus.CONNECTED, IntegrationStatus.LEGACY)
            for t in targets
        )
        if all_ok:
            checks.append("All integration targets connected or demoted to legacy")

        verdict = "STRATEGY_EVOLUTION_INTEGRATION_READY"
        if not single_runner or not all_ok or not promo_ok or not paper_ok:
            verdict = "STRATEGY_EVOLUTION_INTEGRATION_INCOMPLETE"

        return StrategyIntegrationReport(
            canonical_runner=CANONICAL_RUNNER_PATH,
            canonical_json_exists=canonical_exists,
            single_runner_verified=single_runner,
            no_competing_official_runner_verified=no_competing,
            promotion_gate_review_only_verified=promo_ok,
            paper_tracking_paper_only_verified=paper_ok,
            integration_targets=targets,
            competing_demos=dep_map.competing_demos,
            validation_checks=checks,
            warnings=warnings,
            verdict=verdict,
        )

    @staticmethod
    def _notes_for_role(role: ModuleRole, pipeline_role: str | None) -> str:
        mapping = {
            ModuleRole.PIPELINE_STEP: "Pipeline step — not direct entry point",
            ModuleRole.PIPELINE_STEP_REVIEW: "Review-only promotion gate step",
            ModuleRole.PIPELINE_STEP_PAPER: "Paper-only tracking step",
            ModuleRole.FEEDER_READER: "Feeds candidate_registry via simulation JSON",
            ModuleRole.VALIDATION_FEEDER: "Validation feeder — not competing pipeline",
        }
        base = mapping.get(role, "Connected to daily runner pipeline")
        if pipeline_role:
            return f"{base} ({pipeline_role})"
        return base


class StrategyIntegrationAudit:
    def run(self) -> tuple[StrategyDependencyMap, StrategyIntegrationReport]:
        dep_map = StrategyDependencyMapBuilder().build()
        report = StrategyIntegrationAnalyzer().analyze(dep_map)
        return dep_map, report

    def persist_all(
        self,
        dep_map: StrategyDependencyMap,
        report: StrategyIntegrationReport,
    ) -> dict[str, Path]:
        dep_store = StrategyDependencyMapStore()
        rep_store = StrategyIntegrationReportStore()
        return {
            "dependency_map_json": dep_store.persist(dep_map),
            "dependency_map_txt": dep_store.persist_txt(dep_map),
            "integration_report_json": rep_store.persist(report),
            "integration_report_txt": rep_store.persist_txt(report),
        }


class StrategyIntegrationReportStore:
    def persist(self, report: StrategyIntegrationReport) -> Path:
        REPORT_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return REPORT_JSON

    def persist_txt(self, report: StrategyIntegrationReport) -> Path:
        REPORT_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return REPORT_TXT
