"""
Evidence Integration Report — Phase IX Sprint IX.2B

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.evidence_engine.evidence_dependency_map import (
    CANONICAL_REGISTRY_PATH,
    EvidenceDependencyMap,
    EvidenceDependencyMapBuilder,
    EvidenceDependencyMapStore,
    INTEGRATION_GATE_PATH,
    INTEGRATION_TARGETS,
    ModuleRole,
)
from research_core.evidence_engine.evidence_registry import CANONICAL_REPORT_PATH
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

REPORT_JSON = Path("tae_evidence_integration_report.json")
REPORT_TXT = Path("tae_evidence_integration_report.txt")


class IntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    PARTIAL = "PARTIAL"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class TargetIntegration:
    module_path: str
    status: IntegrationStatus
    role: str
    reads_canonical_json: bool
    imports_registry: bool
    notes: str

    def to_dict(self) -> dict[str, str]:
        return {
            "module_path": self.module_path,
            "status": self.status.value,
            "role": self.role,
            "reads_canonical_json": str(self.reads_canonical_json),
            "imports_registry": str(self.imports_registry),
            "notes": self.notes,
        }


@dataclass
class EvidenceIntegrationReport:
    canonical_registry: str
    canonical_json_exists: bool
    single_registry_verified: bool
    integration_gate_verified: bool
    no_duplicate_engine_verified: bool
    integration_targets: list[TargetIntegration]
    validation_checks: list[str]
    warnings: list[str]
    verdict: str = "EVIDENCE_INTEGRATION_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_evidence_integration_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_registry": self.canonical_registry,
            "canonical_json_exists": self.canonical_json_exists,
            "single_registry_verified": self.single_registry_verified,
            "integration_gate_verified": self.integration_gate_verified,
            "no_duplicate_engine_verified": self.no_duplicate_engine_verified,
            "integration_targets": [t.to_dict() for t in self.integration_targets],
            "validation_checks": list(self.validation_checks),
            "warnings": list(self.warnings),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE EVIDENCE INTEGRATION REPORT — SPRINT IX.2B =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical registry: {self.canonical_registry}",
            f"Canonical JSON present: {self.canonical_json_exists}",
            "",
            "===== VALIDATION =====",
            f"  Single registry:        {self.single_registry_verified}",
            f"  Integration gate:       {self.integration_gate_verified}",
            f"  No duplicate engine:    {self.no_duplicate_engine_verified}",
            "",
            "===== INTEGRATION TARGETS =====",
        ]
        for target in self.integration_targets:
            lines.append(f"  [{target.status.value}] {target.module_path} ({target.role})")
            lines.append(f"      {target.notes}")
        lines.extend(["", "===== CHECKS ====="])
        for check in self.validation_checks:
            lines.append(f"  ✓ {check}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        lines.append("")
        return "\n".join(lines)


class EvidenceIntegrationAnalyzer:
    def analyze(self, dep_map: EvidenceDependencyMap) -> EvidenceIntegrationReport:
        node_by_path = {n.module_path: n for n in dep_map.nodes}
        targets: list[TargetIntegration] = []
        warnings: list[str] = list(dep_map.bypass_risks)
        checks: list[str] = []

        role_notes = {
            ModuleRole.VIEW_READER: "VIEW_ONLY — reads canonical registry JSON",
            ModuleRole.FEEDER_READER: "FEEDER/READER — not source of truth",
            ModuleRole.REPORT_SERIALIZER: "Serializes Evidence Registry state",
            ModuleRole.RECORD_MODEL: "Record model — fed by accumulator",
        }

        for path in INTEGRATION_TARGETS:
            node = node_by_path.get(path)
            if node is None:
                targets.append(
                    TargetIntegration(
                        module_path=path,
                        status=IntegrationStatus.DISCONNECTED,
                        role="UNKNOWN",
                        reads_canonical_json=False,
                        imports_registry=False,
                        notes="Module not found",
                    )
                )
                continue

            if node.reads_canonical_json or node.imports_registry:
                status = IntegrationStatus.CONNECTED
            else:
                status = IntegrationStatus.DISCONNECTED

            if node.role == ModuleRole.RECORD_MODEL:
                status = IntegrationStatus.CONNECTED
                note = "Schema layer for accumulator dossiers"
            else:
                note = role_notes.get(node.role, "Connected to evidence pipeline")

            if node.has_competing_registry and path != CANONICAL_REGISTRY_PATH:
                status = IntegrationStatus.DISCONNECTED
                note = "Competing EvidenceRegistry detected"

            targets.append(
                TargetIntegration(
                    module_path=path,
                    status=status,
                    role=node.role.value,
                    reads_canonical_json=node.reads_canonical_json,
                    imports_registry=node.imports_registry,
                    notes=note,
                )
            )

        single_registry = dep_map.registry_count == 1
        if single_registry:
            checks.append("Exactly one EvidenceRegistry class exists")

        gate_ok = dep_map.integration_gate_reads_canonical
        if gate_ok:
            checks.append("Integration gate reads tae_evidence_engine_report.json only")

        no_dup = dep_map.registry_count == 1
        if no_dup:
            checks.append("No duplicate evidence engine created")

        canonical_exists = CANONICAL_REPORT_PATH.is_file()
        if canonical_exists:
            checks.append("Canonical evidence engine report available on disk")
        else:
            warnings.append("Run tae_phase7_evidence_engine_demo.py to materialize canonical JSON")

        all_connected = all(t.status == IntegrationStatus.CONNECTED for t in targets)
        if all_connected:
            checks.append("All integration targets connected to Evidence Registry")

        if node := node_by_path.get("research_core/evidence_gap/evidence_gap.py"):
            if node.role == ModuleRole.VIEW_READER:
                checks.append("evidence_gap classified as VIEW_READER")

        if node := node_by_path.get("research_core/evidence_history/evidence_accumulator.py"):
            if node.role == ModuleRole.FEEDER_READER:
                checks.append("evidence_accumulator classified as FEEDER_READER")

        verdict = "EVIDENCE_INTEGRATION_READY"
        if not single_registry or not gate_ok or not all_connected:
            verdict = "EVIDENCE_INTEGRATION_INCOMPLETE"

        return EvidenceIntegrationReport(
            canonical_registry=CANONICAL_REGISTRY_PATH,
            canonical_json_exists=canonical_exists,
            single_registry_verified=single_registry,
            integration_gate_verified=gate_ok,
            no_duplicate_engine_verified=no_dup,
            integration_targets=targets,
            validation_checks=checks,
            warnings=warnings,
            verdict=verdict,
        )


EXCLUDE_META = {
    "research_core/evidence_engine/evidence_dependency_map.py",
    "research_core/evidence_engine/evidence_integration_report.py",
}


class EvidenceIntegrationAudit:
    def run(self) -> tuple[EvidenceDependencyMap, EvidenceIntegrationReport]:
        dep_map = EvidenceDependencyMapBuilder().build()
        report = EvidenceIntegrationAnalyzer().analyze(dep_map)
        return dep_map, report

    def persist_all(
        self,
        dep_map: EvidenceDependencyMap,
        report: EvidenceIntegrationReport,
    ) -> dict[str, Path]:
        dep_store = EvidenceDependencyMapStore()
        rep_store = EvidenceIntegrationReportStore()
        return {
            "dependency_map_json": dep_store.persist(dep_map),
            "dependency_map_txt": dep_store.persist_txt(dep_map),
            "integration_report_json": rep_store.persist(report),
            "integration_report_txt": rep_store.persist_txt(report),
        }


class EvidenceIntegrationReportStore:
    def persist(self, report: EvidenceIntegrationReport) -> Path:
        REPORT_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return REPORT_JSON

    def persist_txt(self, report: EvidenceIntegrationReport) -> Path:
        REPORT_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return REPORT_TXT
