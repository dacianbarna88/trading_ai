"""
Roadmap manager — Sprint 5.5 structured research capability evolution view.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Informational roadmap status — not trading or execution logic.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.roadmap.capability_registry import (
    CapabilityRecord,
    CapabilityRegistry,
    CapabilityStatus,
    PHASE_ORDER,
    RoadmapPhase,
)

logger = logging.getLogger(__name__)

DEFAULT_STATUS_PATH = Path("tae_roadmap_status.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_roadmap_status"

MATURITY_EMERGING = "Emerging"
MATURITY_DEVELOPING = "Developing"
MATURITY_MATURING = "Maturing"
MATURITY_ADVANCED = "Advanced"
MATURITY_MATURE = "Mature"


@dataclass
class PhaseSummary:
    phase: str
    completed_count: int
    planned_count: int
    partial_count: int
    total_count: int
    completion_pct: float
    capabilities: list[CapabilityRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "completed_count": self.completed_count,
            "planned_count": self.planned_count,
            "partial_count": self.partial_count,
            "total_count": self.total_count,
            "completion_pct": round(self.completion_pct, 2),
            "capabilities": [c.to_dict() for c in self.capabilities],
        }


@dataclass
class RoadmapStatus:
    maturity_level: str
    completion_overall_pct: float
    capabilities_completed: list[str]
    capabilities_planned: list[str]
    capabilities_partial: list[str]
    phase_summaries: list[PhaseSummary]
    suggested_next_priorities: list[str]
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_capabilities: int = 0
    completed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "maturity_level": self.maturity_level,
            "completion_overall_pct": round(self.completion_overall_pct, 2),
            "total_capabilities": self.total_capabilities,
            "completed_count": self.completed_count,
            "capabilities_completed": list(self.capabilities_completed),
            "capabilities_planned": list(self.capabilities_planned),
            "capabilities_partial": list(self.capabilities_partial),
            "phases": [p.to_dict() for p in self.phase_summaries],
            "suggested_next_priorities": list(self.suggested_next_priorities),
        }

    def format_report(self) -> str:
        lines = [
            "===== TAE RESEARCH ROADMAP STATUS =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Current maturity level: {self.maturity_level}",
            f"Overall completion: {self.completion_overall_pct:.1f}%",
            f"Capabilities completed: {self.completed_count} / {self.total_capabilities}",
            "",
            "===== COMPLETION BY PHASE =====",
        ]
        for phase in self.phase_summaries:
            lines.append(
                f"  {phase.phase}: {phase.completion_pct:.1f}% "
                f"({phase.completed_count} completed, "
                f"{phase.planned_count} planned, "
                f"{phase.partial_count} partial / {phase.total_count} total)"
            )
        lines.append("")
        lines.append("===== CAPABILITIES COMPLETED =====")
        if self.capabilities_completed:
            for name in self.capabilities_completed:
                lines.append(f"  ✓ {name}")
        else:
            lines.append("  (none)")
        lines.append("")
        lines.append("===== CAPABILITIES PLANNED =====")
        if self.capabilities_planned:
            for name in self.capabilities_planned:
                lines.append(f"  ○ {name}")
        else:
            lines.append("  (none)")
        if self.capabilities_partial:
            lines.append("")
            lines.append("===== CAPABILITIES PARTIAL =====")
            for name in self.capabilities_partial:
                lines.append(f"  ~ {name}")
        lines.append("")
        lines.append("===== SUGGESTED NEXT RESEARCH PRIORITIES =====")
        for idx, priority in enumerate(self.suggested_next_priorities, start=1):
            lines.append(f"  {idx}. {priority}")
        lines.append("")
        lines.append("Informational only — not trading signals or execution authorization.")
        lines.append("")
        return "\n".join(lines)


class RoadmapManager:
    """
    Maintains structured view of TAE research capabilities and evolution.
    Sprint 5.5 — informational roadmap, no broker or execution paths.
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        status_path: Path | None = None,
    ) -> None:
        self._registry = registry or CapabilityRegistry()
        self._status_path = status_path or DEFAULT_STATUS_PATH

    @property
    def status_path(self) -> Path:
        return self._status_path

    def assess(self) -> RoadmapStatus:
        records = self._registry.detect_all()
        grouped = self._registry.by_phase(records)

        phase_summaries: list[PhaseSummary] = []
        for phase in PHASE_ORDER:
            phase_records = grouped.get(phase.value, [])
            completed = sum(1 for r in phase_records if r.status == CapabilityStatus.COMPLETED)
            planned = sum(1 for r in phase_records if r.status == CapabilityStatus.PLANNED)
            partial = sum(1 for r in phase_records if r.status == CapabilityStatus.PARTIAL)
            total = len(phase_records)
            completion_pct = (completed / total * 100.0) if total else 0.0
            phase_summaries.append(
                PhaseSummary(
                    phase=phase.value,
                    completed_count=completed,
                    planned_count=planned,
                    partial_count=partial,
                    total_count=total,
                    completion_pct=completion_pct,
                    capabilities=phase_records,
                )
            )

        completed_names = [r.name for r in records if r.status == CapabilityStatus.COMPLETED]
        planned_names = [r.name for r in records if r.status == CapabilityStatus.PLANNED]
        partial_names = [r.name for r in records if r.status == CapabilityStatus.PARTIAL]

        total = len(records)
        completed_count = len(completed_names)
        overall_pct = (completed_count / total * 100.0) if total else 0.0
        maturity = self._maturity_level(overall_pct)

        priorities = self._suggest_priorities(phase_summaries, records)

        return RoadmapStatus(
            maturity_level=maturity,
            completion_overall_pct=overall_pct,
            capabilities_completed=completed_names,
            capabilities_planned=planned_names,
            capabilities_partial=partial_names,
            phase_summaries=phase_summaries,
            suggested_next_priorities=priorities,
            total_capabilities=total,
            completed_count=completed_count,
        )

    def persist(self, status: RoadmapStatus | None = None) -> Path:
        if status is None:
            status = self.assess()
        try:
            self._status_path.write_text(
                json.dumps(status.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to persist roadmap status: %s", exc)
            raise
        return self._status_path

    def load_status(self) -> RoadmapStatus | None:
        if not self._status_path.is_file():
            return None
        try:
            raw = self._status_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Roadmap status unreadable: %s", exc)
            return None

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return None

        phases_raw = payload.get("phases", [])
        phase_summaries: list[PhaseSummary] = []
        if isinstance(phases_raw, list):
            for item in phases_raw:
                if not isinstance(item, dict):
                    continue
                caps_raw = item.get("capabilities", [])
                caps: list[CapabilityRecord] = []
                if isinstance(caps_raw, list):
                    for cap in caps_raw:
                        if not isinstance(cap, dict):
                            continue
                        try:
                            status_val = CapabilityStatus(cap.get("status", "PLANNED"))
                        except ValueError:
                            status_val = CapabilityStatus.PLANNED
                        caps.append(
                            CapabilityRecord(
                                capability_id=str(cap.get("capability_id", "")),
                                name=str(cap.get("name", "")),
                                phase=str(cap.get("phase", "")),
                                sprint=str(cap.get("sprint", "")),
                                description=str(cap.get("description", "")),
                                status=status_val,
                                module_paths=list(cap.get("module_paths", [])),
                                demo_paths=list(cap.get("demo_paths", [])),
                                artifacts_found=list(cap.get("artifacts_found", [])),
                                missing_artifacts=list(cap.get("missing_artifacts", [])),
                            )
                        )
                phase_summaries.append(
                    PhaseSummary(
                        phase=str(item.get("phase", "")),
                        completed_count=int(item.get("completed_count", 0)),
                        planned_count=int(item.get("planned_count", 0)),
                        partial_count=int(item.get("partial_count", 0)),
                        total_count=int(item.get("total_count", 0)),
                        completion_pct=float(item.get("completion_pct", 0)),
                        capabilities=caps,
                    )
                )

        generated = payload.get("generated_at")
        if generated:
            dt = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        return RoadmapStatus(
            maturity_level=str(payload.get("maturity_level", "")),
            completion_overall_pct=float(payload.get("completion_overall_pct", 0)),
            capabilities_completed=list(payload.get("capabilities_completed", [])),
            capabilities_planned=list(payload.get("capabilities_planned", [])),
            capabilities_partial=list(payload.get("capabilities_partial", [])),
            phase_summaries=phase_summaries,
            suggested_next_priorities=list(payload.get("suggested_next_priorities", [])),
            generated_at=dt,
            total_capabilities=int(payload.get("total_capabilities", 0)),
            completed_count=int(payload.get("completed_count", 0)),
        )

    def _maturity_level(self, overall_pct: float) -> str:
        if overall_pct >= 90.0:
            return MATURITY_MATURE
        if overall_pct >= 75.0:
            return MATURITY_ADVANCED
        if overall_pct >= 50.0:
            return MATURITY_MATURING
        if overall_pct >= 25.0:
            return MATURITY_DEVELOPING
        return MATURITY_EMERGING

    def _suggest_priorities(
        self,
        phase_summaries: list[PhaseSummary],
        records: list[CapabilityRecord],
    ) -> list[str]:
        priorities: list[str] = []

        for phase_summary in phase_summaries:
            incomplete = [
                c
                for c in phase_summary.capabilities
                if c.status in (CapabilityStatus.PLANNED, CapabilityStatus.PARTIAL)
            ]
            for cap in incomplete:
                priorities.append(
                    f"[{cap.phase}] {cap.name}: {cap.description} (research only)"
                )

        partial_intel = [
            r for r in records
            if r.status == CapabilityStatus.PARTIAL
            and r.phase == RoadmapPhase.INTELLIGENCE.value
        ]
        for cap in partial_intel:
            missing = ", ".join(cap.missing_artifacts[:3])
            if missing:
                priorities.append(
                    f"Restore missing artifacts for {cap.name}: {missing}"
                )

        if not any(
            p.phase == RoadmapPhase.SCIENTIFIC_DISCOVERY.value
            and p.completed_count > 0
            for p in phase_summaries
        ):
            priorities.append(
                "Begin Scientific Discovery phase: cross-regime experiment matrix "
                "on existing BULL cohort hypotheses (no execution)."
            )

        if RoadmapPhase.INTELLIGENCE.value in {
            r.phase for r in records if r.status == CapabilityStatus.COMPLETED
        }:
            priorities.append(
                "Run full Sprint 5 pipeline cycle: hypothesis → experiment → "
                "ranking → knowledge candidate → learning report."
            )

        priorities.append(
            "Maintain RESEARCH_ONLY / PAPER_ONLY discipline — broker and execution remain last."
        )

        return priorities[:8]
