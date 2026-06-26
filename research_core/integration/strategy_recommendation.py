"""
Strategy recommendation model — Phase V Sprint A3

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Human-review strategy recommendations — not trading signals or execution.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_RECOMMENDATIONS_PATH = Path("tae_strategy_recommendations.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategy_recommendations"


class RecommendationType(str, Enum):
    PROMOTE_RESEARCH_WEIGHT = "PROMOTE_RESEARCH_WEIGHT"
    KEEP_UNDER_OBSERVATION = "KEEP_UNDER_OBSERVATION"
    REQUIRE_MORE_VALIDATION = "REQUIRE_MORE_VALIDATION"
    BLOCK_FROM_TRADING = "BLOCK_FROM_TRADING"


class ImplementationStatus(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"


@dataclass
class StrategyRecommendation:
    recommendation_id: str
    source_candidate_id: str
    source_hypothesis_id: str
    title: str
    recommendation_type: RecommendationType
    confidence: float
    evidence_summary: str
    validation_summary: str
    risk_notes: str
    human_approval_required: bool = True
    implementation_status: ImplementationStatus = ImplementationStatus.NOT_IMPLEMENTED
    safety_mode: str = RESEARCH_SAFETY_BANNER
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.recommendation_type, str):
            self.recommendation_type = RecommendationType(self.recommendation_type)
        if isinstance(self.implementation_status, str):
            self.implementation_status = ImplementationStatus(self.implementation_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "source_candidate_id": self.source_candidate_id,
            "source_hypothesis_id": self.source_hypothesis_id,
            "title": self.title,
            "recommendation_type": self.recommendation_type.value,
            "confidence": round(self.confidence, 2),
            "evidence_summary": self.evidence_summary,
            "validation_summary": self.validation_summary,
            "risk_notes": self.risk_notes,
            "human_approval_required": self.human_approval_required,
            "implementation_status": self.implementation_status.value,
            "safety_mode": self.safety_mode,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyRecommendation | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            rec_type = str(data.get("recommendation_type", RecommendationType.KEEP_UNDER_OBSERVATION.value))
            try:
                recommendation_type = RecommendationType(rec_type)
            except ValueError:
                recommendation_type = RecommendationType.KEEP_UNDER_OBSERVATION

            impl = str(data.get("implementation_status", ImplementationStatus.NOT_IMPLEMENTED.value))
            try:
                implementation_status = ImplementationStatus(impl)
            except ValueError:
                implementation_status = ImplementationStatus.NOT_IMPLEMENTED

            return cls(
                recommendation_id=str(data["recommendation_id"]),
                source_candidate_id=str(data.get("source_candidate_id", "")),
                source_hypothesis_id=str(data.get("source_hypothesis_id", "")),
                title=str(data.get("title", "")),
                recommendation_type=recommendation_type,
                confidence=float(data.get("confidence", 0)),
                evidence_summary=str(data.get("evidence_summary", "")),
                validation_summary=str(data.get("validation_summary", "")),
                risk_notes=str(data.get("risk_notes", "")),
                human_approval_required=bool(data.get("human_approval_required", True)),
                implementation_status=implementation_status,
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                created_at=dt,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.recommendation_id} | {self.recommendation_type.value} | "
            f"confidence={self.confidence:.1f} | {self.source_candidate_id}"
        )


@dataclass
class IntegrationResult:
    candidates_analyzed: int
    recommendations_generated: int
    recommendations_skipped_duplicate: int
    recommendations: list[StrategyRecommendation]
    highest_confidence: StrategyRecommendation | None
    blocked_or_validation: list[StrategyRecommendation]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "candidates_analyzed": self.candidates_analyzed,
            "recommendations_generated": self.recommendations_generated,
            "recommendations_skipped_duplicate": self.recommendations_skipped_duplicate,
            "highest_confidence_id": (
                self.highest_confidence.recommendation_id if self.highest_confidence else ""
            ),
            "sources_loaded": dict(self.sources_loaded),
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def format_report(self) -> str:
        lines = [
            "===== TAE STRATEGY RECOMMENDATIONS =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Candidates analyzed: {self.candidates_analyzed}",
            f"Recommendations generated (this run): {self.recommendations_generated}",
            f"Duplicates skipped (this run): {self.recommendations_skipped_duplicate}",
            f"Total recommendations in store: {len(self.recommendations)}",
            "",
            "Sources loaded:",
        ]
        for name, ok in sorted(self.sources_loaded.items()):
            lines.append(f"  {name}: {'yes' if ok else 'no'}")
        lines.append("")

        if self.highest_confidence:
            lines.append("Highest-confidence recommendation:")
            lines.append(f"  {self.highest_confidence.summary_line()}")
            lines.append(f"  title: {self.highest_confidence.title[:100]}")
            lines.append("")

        blocked = [
            r for r in self.recommendations
            if r.recommendation_type in (
                RecommendationType.BLOCK_FROM_TRADING,
                RecommendationType.REQUIRE_MORE_VALIDATION,
            )
        ]
        lines.append(
            f"Blocked / needs validation: {len(blocked)} recommendation(s)"
        )
        for rec in blocked:
            lines.append(f"  - {rec.recommendation_id}: {rec.recommendation_type.value}")
        lines.append("")

        lines.append("All recommendations:")
        for rec in self.recommendations:
            lines.append(f"  {rec.summary_line()}")
            lines.append(
                f"    human_approval_required={rec.human_approval_required} "
                f"implementation_status={rec.implementation_status.value}"
            )
        lines.append("")
        lines.append(
            "Research-to-human-review layer only — does not modify live trading."
        )
        lines.append("")
        return "\n".join(lines)


class StrategyRecommendationsStore:
    """JSON persistence for strategy recommendations — stdlib only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_RECOMMENDATIONS_PATH
        self._recommendations: dict[str, StrategyRecommendation] = {}
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    def list_all(self) -> list[StrategyRecommendation]:
        return sorted(self._recommendations.values(), key=lambda r: r.created_at)

    def get(self, recommendation_id: str) -> StrategyRecommendation | None:
        return self._recommendations.get(recommendation_id)

    def has_candidate(self, source_candidate_id: str) -> bool:
        return any(
            r.source_candidate_id == source_candidate_id for r in self._recommendations.values()
        )

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Recommendations unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict):
            return False
        if payload.get("schema") != SCHEMA_NAME:
            return False

        items = payload.get("recommendations", [])
        if not isinstance(items, list):
            return False

        self._recommendations.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            rec = StrategyRecommendation.from_dict(item)
            if rec is not None:
                self._recommendations[rec.recommendation_id] = rec
        return True

    def merge_new(self, recommendations: list[StrategyRecommendation]) -> tuple[int, int]:
        """Add recommendations; skip duplicate recommendation_id or source_candidate_id."""
        added = 0
        skipped = 0
        for rec in recommendations:
            if rec.recommendation_id in self._recommendations:
                skipped += 1
                continue
            if self.has_candidate(rec.source_candidate_id):
                skipped += 1
                continue
            self._recommendations[rec.recommendation_id] = rec
            added += 1
        return added, skipped

    def persist(self, result: IntegrationResult | None = None) -> Path:
        if result is not None:
            payload = result.to_dict()
            payload["recommendations"] = [r.to_dict() for r in self.list_all()]
        else:
            payload = {
                "version": SCHEMA_VERSION,
                "schema": SCHEMA_NAME,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_mode": RESEARCH_SAFETY_BANNER,
                "recommendations": [r.to_dict() for r in self.list_all()],
            }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path
