"""
Prioritization report model — Phase V Sprint A1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Structured output for autonomous research prioritization — not execution.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_PRIORITIES_PATH = Path("tae_research_priorities.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_research_priorities"


@dataclass
class ResearchPriorityEntry:
    opportunity_id: str
    source_type: str
    source_id: str
    title: str
    priority_score: float
    rank: int = 0
    why_it_matters: str = ""
    estimated_scientific_value: str = "MEDIUM"
    estimated_effort: str = "MEDIUM"
    suggested_next_action: str = ""
    expected_information_gain: float = 0.0
    scoring_factors: dict[str, float] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "rank": self.rank,
            "priority_score": round(self.priority_score, 2),
            "why_it_matters": self.why_it_matters,
            "estimated_scientific_value": self.estimated_scientific_value,
            "estimated_effort": self.estimated_effort,
            "suggested_next_action": self.suggested_next_action,
            "expected_information_gain": round(self.expected_information_gain, 2),
            "scoring_factors": {k: round(v, 2) for k, v in self.scoring_factors.items()},
            "safety_mode": self.safety_mode,
        }


@dataclass
class PrioritizationReport:
    opportunities_evaluated: int
    top_opportunity_id: str
    highest_information_gain_id: str
    recommended_next_experiment: str
    top_ranking_reason: str
    priorities: list[ResearchPriorityEntry] = field(default_factory=list)
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "opportunities_evaluated": self.opportunities_evaluated,
            "top_opportunity_id": self.top_opportunity_id,
            "highest_information_gain_id": self.highest_information_gain_id,
            "recommended_next_experiment": self.recommended_next_experiment,
            "top_ranking_reason": self.top_ranking_reason,
            "sources_loaded": dict(self.sources_loaded),
            "priorities": [p.to_dict() for p in self.priorities],
        }

    def format_summary(self) -> str:
        lines = [
            "===== TAE RESEARCH PRIORITIZATION REPORT =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Opportunities evaluated: {self.opportunities_evaluated}",
            f"Top priority: {self.top_opportunity_id}",
            f"Highest information gain: {self.highest_information_gain_id}",
            f"Recommended next experiment: {self.recommended_next_experiment}",
            "",
            f"Reason for top ranking: {self.top_ranking_reason}",
            "",
            "Sources loaded:",
        ]
        for name, ok in sorted(self.sources_loaded.items()):
            lines.append(f"  {name}: {'yes' if ok else 'no'}")
        lines.append("")
        lines.append("===== TOP RESEARCH PRIORITIES =====")
        for entry in self.priorities[:10]:
            lines.extend(
                [
                    f"  #{entry.rank} {entry.opportunity_id} (score={entry.priority_score:.1f})",
                    f"    title: {entry.title}",
                    f"    source: {entry.source_type}/{entry.source_id}",
                    f"    why: {entry.why_it_matters[:120]}",
                    f"    scientific value: {entry.estimated_scientific_value} | effort: {entry.estimated_effort}",
                    f"    info gain: {entry.expected_information_gain:.1f}",
                    f"    next action: {entry.suggested_next_action[:120]}",
                    "",
                ]
            )
        lines.append("Prioritization only — does not run experiments or modify discoveries.")
        lines.append("")
        return "\n".join(lines)


class PrioritizationReportStore:
    """JSON persistence for research priorities."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PRIORITIES_PATH
        self._report: PrioritizationReport | None = None

    @property
    def path(self) -> Path:
        return self._path

    def set_report(self, report: PrioritizationReport) -> None:
        self._report = report

    def persist(self, report: PrioritizationReport | None = None) -> Path:
        if report is not None:
            self._report = report
        if self._report is None:
            raise ValueError("No prioritization report to persist.")
        self._path.write_text(
            json.dumps(self._report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path
