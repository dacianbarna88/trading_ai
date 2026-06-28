"""
Runtime Foundation report — Phase IX C2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH = Path("tae_runtime_foundation.json")
DEFAULT_TXT_PATH = Path("tae_runtime_foundation.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_runtime_foundation"


class RuntimeFoundationVerdict(str, Enum):
    RUNTIME_FOUNDATION_READY = "RUNTIME_FOUNDATION_READY"
    RUNTIME_FOUNDATION_DEGRADED = "RUNTIME_FOUNDATION_DEGRADED"
    RUNTIME_FOUNDATION_DEGRADED_WITH_KNOWN_INTEGRATION_BACKLOG = (
        "RUNTIME_FOUNDATION_DEGRADED_WITH_KNOWN_INTEGRATION_BACKLOG"
    )
    RUNTIME_FOUNDATION_CRITICAL = "RUNTIME_FOUNDATION_CRITICAL"


@dataclass
class WorkflowStepResult:
    step_number: int
    step_name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class RuntimeFoundationReport:
    verdict: RuntimeFoundationVerdict
    loaded_state_sources: dict[str, bool]
    events_emitted: list[dict[str, Any]]
    workflow_steps: list[WorkflowStepResult]
    health_status: str
    health_checks: list[dict[str, Any]]
    health_issues: list[str]
    learning_memory_summary: dict[str, Any]
    top_ranked_strategy_id: str | None
    top_ranked_strategy_score: float | None
    promotion_review_candidate_id: str | None
    paper_tracking_needs: list[dict[str, Any]]
    missing_connections: list[str]
    conflict_warnings: list[dict[str, Any]]
    protected_files_unchanged: bool
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "loaded_state_sources": dict(self.loaded_state_sources),
            "events_emitted": list(self.events_emitted),
            "workflow_steps": [step.to_dict() for step in self.workflow_steps],
            "health_status": self.health_status,
            "health_checks": list(self.health_checks),
            "health_issues": list(self.health_issues),
            "health_issue_count": len(self.health_issues),
            "learning_memory_summary": dict(self.learning_memory_summary),
            "top_ranked_strategy_id": self.top_ranked_strategy_id,
            "top_ranked_strategy_score": self.top_ranked_strategy_score,
            "promotion_review_candidate_id": self.promotion_review_candidate_id,
            "paper_tracking_needs": list(self.paper_tracking_needs),
            "missing_connections": list(self.missing_connections),
            "conflict_warnings": list(self.conflict_warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE TRADING AI OS RUNTIME FOUNDATION — FAZA IX C2 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Health: {self.health_status}",
            f"Issues: {len(self.health_issues)}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== LOADED STATE SOURCES =====",
        ]
        for name, loaded in self.loaded_state_sources.items():
            lines.append(f"  {name}: {'OK' if loaded else 'MISSING'}")
        lines.extend(["", "===== WORKFLOW STEPS ====="])
        for step in self.workflow_steps:
            lines.append(
                f"{step.step_number}. {step.step_name} [{step.status}] {step.message}"
            )
        lines.extend(["", "===== EVENTS ====="])
        for event in self.events_emitted:
            lines.append(
                f"  {event.get('event_type')} | {event.get('source')} | "
                f"{event.get('status')} | {event.get('payload_summary')}"
            )
        lines.extend([
            "",
            "===== ECOSYSTEM INTELLIGENCE =====",
            f"Top ranked strategy: {self.top_ranked_strategy_id or 'N/A'}",
        ])
        if self.top_ranked_strategy_score is not None:
            lines.append(f"Top ranking score: {self.top_ranked_strategy_score:.4f}")
        lines.append(
            f"Promotion review candidate: {self.promotion_review_candidate_id or 'None'}"
        )
        lines.extend(["", "Paper tracking needs:"])
        for need in self.paper_tracking_needs:
            lines.append(
                f"  {need.get('candidate_id')}: {need.get('tracking_status')} | "
                f"need={need.get('trades_needed')}"
            )
        lines.extend(["", "===== HEALTH ISSUES ====="])
        if self.health_issues:
            for issue in self.health_issues:
                lines.append(f"  - {issue}")
        else:
            lines.append("  none")
        lines.extend(["", "Missing connections:"])
        for conn in self.missing_connections:
            lines.append(f"  - {conn}")
        lines.extend(["", "Lessons learned:"])
        for lesson in self.learning_memory_summary.get("lessons_learned", []):
            lines.append(f"  - {lesson}")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "ANALYSIS ONLY — NO EXECUTION",
            "Runtime foundation is read-only — no trade execution.",
            "",
        ])
        return "\n".join(lines)


class RuntimeFoundationReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: RuntimeFoundationReport) -> Path:
        self._json_path.write_text(
            json.dumps(
                report.to_dict(),
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: RuntimeFoundationReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
