"""
Cross-validation report model — Phase IV Sprint D6

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
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

DEFAULT_REPORT_PATH = Path("tae_cross_validation_report.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_cross_validation_report"
NOT_AVAILABLE = "NOT_AVAILABLE"


def _serialize_metric(value: float | None) -> str | float:
    if value is None:
        return NOT_AVAILABLE
    return round(value, 4)


@dataclass
class DimensionSlice:
    label: str
    sample_size: int = 0
    accuracy: float | None = None
    avg_forward_return: float | None = None
    status: str = NOT_AVAILABLE

    def to_dict(self) -> dict[str, Any]:
        acc = self.accuracy
        ret = self.avg_forward_return
        return {
            "label": self.label,
            "sample_size": self.sample_size,
            "accuracy": _serialize_metric(acc if self.sample_size > 0 else None),
            "avg_forward_return": _serialize_metric(ret if self.sample_size > 0 else None),
            "status": self.status,
        }


@dataclass
class CandidateValidationResult:
    candidate_id: str
    source_hypothesis_id: str
    title: str
    regime_consistency: float | None
    horizon_consistency: float | None
    regional_consistency: float | None
    robustness_score: float
    confidence_adjustment: float
    validation_notes: str
    regime_slices: dict[str, DimensionSlice] = field(default_factory=dict)
    horizon_slices: dict[str, DimensionSlice] = field(default_factory=dict)
    region_slices: dict[str, DimensionSlice] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_hypothesis_id": self.source_hypothesis_id,
            "title": self.title,
            "regime_consistency": _serialize_metric(self.regime_consistency),
            "horizon_consistency": _serialize_metric(self.horizon_consistency),
            "regional_consistency": _serialize_metric(self.regional_consistency),
            "robustness_score": round(self.robustness_score, 2),
            "confidence_adjustment": round(self.confidence_adjustment, 2),
            "validation_notes": self.validation_notes,
            "regime_slices": {k: v.to_dict() for k, v in self.regime_slices.items()},
            "horizon_slices": {k: v.to_dict() for k, v in self.horizon_slices.items()},
            "region_slices": {k: v.to_dict() for k, v in self.region_slices.items()},
        }


@dataclass
class CrossValidationReport:
    candidates_analyzed: int
    most_robust_candidate_id: str
    weakest_candidate_id: str
    cross_regime_consistency_summary: str | float
    cross_horizon_consistency_summary: str | float
    cross_region_consistency_summary: str | float
    recommended_follow_up_research: list[str]
    candidate_results: list[CandidateValidationResult] = field(default_factory=list)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_sources: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "candidates_analyzed": self.candidates_analyzed,
            "most_robust_candidate_id": self.most_robust_candidate_id,
            "weakest_candidate_id": self.weakest_candidate_id,
            "cross_regime_consistency_summary": (
                self.cross_regime_consistency_summary
                if isinstance(self.cross_regime_consistency_summary, str)
                else round(self.cross_regime_consistency_summary, 2)
            ),
            "cross_horizon_consistency_summary": (
                self.cross_horizon_consistency_summary
                if isinstance(self.cross_horizon_consistency_summary, str)
                else round(self.cross_horizon_consistency_summary, 2)
            ),
            "cross_region_consistency_summary": (
                self.cross_region_consistency_summary
                if isinstance(self.cross_region_consistency_summary, str)
                else round(self.cross_region_consistency_summary, 2)
            ),
            "recommended_follow_up_research": list(self.recommended_follow_up_research),
            "data_sources": dict(self.data_sources),
            "candidate_results": [c.to_dict() for c in self.candidate_results],
        }

    def format_summary(self) -> str:
        lines = [
            "===== TAE CROSS-VALIDATION REPORT =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Knowledge candidates analyzed: {self.candidates_analyzed}",
            f"Most robust candidate: {self.most_robust_candidate_id}",
            f"Weakest candidate: {self.weakest_candidate_id}",
            f"Cross-regime consistency: {self.cross_regime_consistency_summary}",
            f"Cross-horizon consistency: {self.cross_horizon_consistency_summary}",
            f"Cross-region consistency: {self.cross_region_consistency_summary}",
            "",
            "Data sources:",
        ]
        for name, ok in sorted(self.data_sources.items()):
            lines.append(f"  {name}: {'loaded' if ok else 'missing'}")
        lines.append("")
        for result in self.candidate_results:
            lines.append(
                f"  {result.candidate_id} | robustness={result.robustness_score:.1f} "
                f"| regime={_serialize_metric(result.regime_consistency)} "
                f"| horizon={_serialize_metric(result.horizon_consistency)} "
                f"| region={_serialize_metric(result.regional_consistency)}"
            )
            lines.append(f"    {result.title[:80]}")
            lines.append(f"    notes: {result.validation_notes[:120]}")
        lines.append("")
        lines.append("Recommended follow-up research:")
        for idx, item in enumerate(self.recommended_follow_up_research, start=1):
            lines.append(f"  {idx}. {item}")
        lines.append("")
        return "\n".join(lines)


class CrossValidationReportStore:
    """JSON persistence for cross-validation reports."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_REPORT_PATH
        self._report: CrossValidationReport | None = None

    @property
    def path(self) -> Path:
        return self._path

    def set_report(self, report: CrossValidationReport) -> None:
        self._report = report

    def persist(self, report: CrossValidationReport | None = None) -> Path:
        if report is not None:
            self._report = report
        if self._report is None:
            raise ValueError("No cross-validation report to persist.")
        self._path.write_text(
            json.dumps(self._report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path
