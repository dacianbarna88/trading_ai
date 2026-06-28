"""
Performance Pipeline Integration Report — Phase IX Sprint IX.5A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.performance.performance_dependency_map import (
    PerformanceDependencyMap,
    PerformanceDependencyMapBuilder,
    PerformanceDependencyMapStore,
)
from research_core.performance.performance_pipeline_integration import (
    INTEGRITY_REPORT_PATH,
    MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER,
    PIPELINE_ORDER,
    STRATEGIC_REPORT_PATH,
    is_daily_runner_performance_wired,
    pipeline_reference,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

REPORT_JSON = Path("tae_performance_pipeline_report.json")
REPORT_TXT = Path("tae_performance_pipeline_report.txt")


class PipelineConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    PARTIAL = "PARTIAL"
    DISCONNECTED = "DISCONNECTED"
    BYPASS = "BYPASS"


@dataclass
class PerformancePipelineReport:
    safety_banner: str
    inventory_summary: dict[str, int]
    pipeline_diagram: list[str]
    integration_diagram: list[str]
    pipeline_reference: dict[str, Any]
    dependency_map_verdict: str
    strategic_json_exists: bool
    integrity_json_exists: bool
    runtime_connected: bool
    quick_health_connected: bool
    evidence_registry_consumer_ready: bool
    warnings: list[str]
    remaining_backlog: list[str]
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_performance_pipeline_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "inventory_summary": dict(self.inventory_summary),
            "pipeline_diagram": list(self.pipeline_diagram),
            "integration_diagram": list(self.integration_diagram),
            "pipeline_reference": dict(self.pipeline_reference),
            "dependency_map_verdict": self.dependency_map_verdict,
            "strategic_json_exists": self.strategic_json_exists,
            "integrity_json_exists": self.integrity_json_exists,
            "runtime_connected": self.runtime_connected,
            "quick_health_connected": self.quick_health_connected,
            "evidence_registry_consumer_ready": self.evidence_registry_consumer_ready,
            "warnings": list(self.warnings),
            "remaining_backlog": list(self.remaining_backlog),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE PERFORMANCE PIPELINE REPORT — SPRINT IX.5A =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== INVENTORY SUMMARY =====",
        ]
        for cls, count in self.inventory_summary.items():
            lines.append(f"  {cls}: {count}")
        lines.extend(["", "===== PIPELINE DIAGRAM ====="])
        for row in self.pipeline_diagram:
            lines.append(f"  {row}")
        lines.extend(["", "===== INTEGRATION DIAGRAM ====="])
        for row in self.integration_diagram:
            lines.append(f"  {row}")
        lines.extend([
            "",
            f"Strategic JSON ({STRATEGIC_REPORT_PATH.name}): "
            f"{'OK' if self.strategic_json_exists else 'MISSING'}",
            f"Integrity JSON ({INTEGRITY_REPORT_PATH.name}): "
            f"{'OK' if self.integrity_json_exists else 'MISSING'}",
            f"Runtime connected: {self.runtime_connected}",
            f"Quick health connected: {self.quick_health_connected}",
            f"Evidence registry consumer ready: {self.evidence_registry_consumer_ready}",
            "",
            "===== WARNINGS =====",
        ])
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  • {w}")
        else:
            lines.append("  none")
        lines.extend(["", "===== REMAINING BACKLOG ====="])
        if self.remaining_backlog:
            for item in self.remaining_backlog:
                lines.append(f"  • {item}")
        else:
            lines.append("  none")
        lines.append("")
        return "\n".join(lines)


class PerformancePipelineAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(self, protected_ok: bool) -> tuple[PerformanceDependencyMap, PerformancePipelineReport]:
        dep_map = PerformanceDependencyMapBuilder(self._root).build()
        pipe_ref = pipeline_reference(self._root)
        warnings: list[str] = []
        backlog: list[str] = list(dep_map.direct_runtime_bypasses)

        strategic_exists = STRATEGIC_REPORT_PATH.is_file()
        integrity_exists = INTEGRITY_REPORT_PATH.is_file()
        daily_runner_wired = is_daily_runner_performance_wired(self._root)
        if not daily_runner_wired:
            backlog.append(MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER)
        if not strategic_exists:
            warnings.append(
                f"Missing {STRATEGIC_REPORT_PATH.name} — run tae_strategic_performance_audit_demo.py"
            )
        if not integrity_exists:
            warnings.append(
                f"Missing {INTEGRITY_REPORT_PATH.name} — run tae_accounting_integrity_audit_demo.py"
            )

        runtime_connected = self._runtime_connected()
        quick_health_connected = self._quick_health_connected()
        if not runtime_connected:
            backlog.append("EcosystemStateLoader missing performance pipeline sources")
        if not quick_health_connected:
            backlog.append("QuickHealth missing performance pipeline status")

        evidence_ready = strategic_exists and integrity_exists
        if not evidence_ready:
            backlog.append(
                "Evidence Registry should consume performance JSON via pipeline boundary "
                "(evidence_registry.py protected — document-only until future sprint)"
            )

        inv_summary: dict[str, int] = {}
        for item in dep_map.inventory:
            cls = item["classification"]
            inv_summary[cls] = inv_summary.get(cls, 0) + 1

        pipeline_diagram = self._pipeline_diagram()
        integration_diagram = self._integration_diagram(pipe_ref, dep_map)

        if dep_map.duplicate_engine_candidates:
            for dup in dep_map.duplicate_engine_candidates:
                warnings.append(dup)

        if not protected_ok:
            verdict = "PERFORMANCE_PIPELINE_FAILED_PROTECTED_FILE_MODIFIED"
        elif (
            daily_runner_wired
            and strategic_exists
            and runtime_connected
            and quick_health_connected
            and MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER not in backlog
        ):
            verdict = "PERFORMANCE_PIPELINE_INTEGRATION_COMPLETE"
        else:
            verdict = "PERFORMANCE_PIPELINE_PARTIALLY_CONNECTED"

        report = PerformancePipelineReport(
            safety_banner=SAFETY_BANNER,
            inventory_summary=inv_summary,
            pipeline_diagram=pipeline_diagram,
            integration_diagram=integration_diagram,
            pipeline_reference=pipe_ref,
            dependency_map_verdict=dep_map.verdict,
            strategic_json_exists=strategic_exists,
            integrity_json_exists=integrity_exists,
            runtime_connected=runtime_connected,
            quick_health_connected=quick_health_connected,
            evidence_registry_consumer_ready=evidence_ready,
            warnings=warnings,
            remaining_backlog=backlog,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )
        return dep_map, report

    def persist_all(
        self,
        dep_map: PerformanceDependencyMap,
        report: PerformancePipelineReport,
    ) -> dict[str, Path]:
        dep_store = PerformanceDependencyMapStore()
        paths = {
            "dependency_map_json": dep_store.persist(dep_map, self._root),
            "dependency_map_txt": dep_store.persist_txt(dep_map, self._root),
            "pipeline_report_json": self._root / REPORT_JSON,
            "pipeline_report_txt": self._root / REPORT_TXT,
        }
        paths["pipeline_report_json"].write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths["pipeline_report_txt"].write_text(report.format_text() + "\n", encoding="utf-8")
        return paths

    @staticmethod
    def _pipeline_diagram() -> list[str]:
        return [
            "Market",
            "  → Evidence Engine",
            "  → Simulation Lab",
            "  → Strategy Evolution",
            "  → Promotion Gate",
            "  → Paper Tracking",
            "  → Performance Pipeline  ← IX.5A canonical stage",
            "  → Evidence Registry",
            "  → Runtime",
            "  → Quick Health",
        ]

    @staticmethod
    def _integration_diagram(
        pipe_ref: dict[str, Any],
        dep_map: PerformanceDependencyMap,
    ) -> list[str]:
        lines = [
            "  → Paper Tracking (tae_paper_tracking_log.json)",
            "  ↓",
            "  → Performance Pipeline (daily runner step 6 — canonical JSON reference)",
            "  ↓",
            f"Strategic Performance ({STRATEGIC_REPORT_PATH.name})",
            f"  module: {pipe_ref.get('canonical_strategic_module')}",
            "  ↓",
            f"Accounting Integrity ({INTEGRITY_REPORT_PATH.name})",
            f"  module: {pipe_ref.get('canonical_integrity_module')} via AccountingAdapter",
            "  ↓",
            "Evidence Registry (future consumer — JSON boundary)",
            "  ↓",
            "Runtime (EcosystemStateLoader + RuntimeHealth)",
            "  ↓",
            "Quick Health (via runtime + tae_performance_pipeline_report.json)",
        ]
        for consumer in dep_map.runtime_consumers[:4]:
            lines.append(f"  consumer: {consumer}")
        return lines

    def _runtime_connected(self) -> bool:
        path = self._root / "research_core/runtime/ecosystem_state.py"
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8", errors="replace")
        return STRATEGIC_REPORT_PATH.name in text and "strategic_performance" in text

    def _quick_health_connected(self) -> bool:
        path = self._root / "research_core/runtime/quick_health_wrapper.py"
        if not path.is_file():
            return False
        text = path.read_text(encoding="utf-8", errors="replace")
        return "performance_pipeline" in text


def protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def verify_protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file() or full.stat().st_mtime != mtime:
            return False
    return True
