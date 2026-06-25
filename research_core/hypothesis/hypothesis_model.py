"""
TAE Hypothesis model — Sprint 5.0

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

A hypothesis is a research object for later testing — NOT a trade order or signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SAFETY_MODE = "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class HypothesisStatus(str, Enum):
    UNTESTED = "UNTESTED"
    QUEUED = "QUEUED"
    TESTING = "TESTING"
    TESTED = "TESTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


@dataclass
class Hypothesis:
    """
    Explicit research hypothesis derived from council / organism outputs.
    Not a BUY/SELL instruction — subject to future experiment validation.
    """

    hypothesis_id: str
    title: str
    source_cycle: str
    source_organisms: list[str]
    conditions: dict[str, Any]
    prediction: str
    horizon: str
    confidence: float
    rationale: str
    status: HypothesisStatus = HypothesisStatus.UNTESTED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safety_mode: str = SAFETY_MODE

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(100.0, float(self.confidence)))
        if isinstance(self.status, str):
            self.status = HypothesisStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "source_cycle": self.source_cycle,
            "source_organisms": list(self.source_organisms),
            "conditions": dict(self.conditions),
            "prediction": self.prediction,
            "horizon": self.horizon,
            "confidence": round(self.confidence, 2),
            "rationale": self.rationale,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "safety_mode": self.safety_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hypothesis | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            status_raw = str(data.get("status", HypothesisStatus.UNTESTED.value))
            try:
                status = HypothesisStatus(status_raw)
            except ValueError:
                status = HypothesisStatus.UNTESTED

            conditions = data.get("conditions", {})
            if not isinstance(conditions, dict):
                conditions = {}

            organisms = data.get("source_organisms", [])
            if not isinstance(organisms, list):
                organisms = []

            return cls(
                hypothesis_id=str(data["hypothesis_id"]),
                title=str(data.get("title", "")),
                source_cycle=str(data.get("source_cycle", "")),
                source_organisms=[str(o) for o in organisms],
                conditions=conditions,
                prediction=str(data.get("prediction", "")),
                horizon=str(data.get("horizon", "")),
                confidence=float(data.get("confidence", 0)),
                rationale=str(data.get("rationale", "")),
                status=status,
                created_at=dt,
                safety_mode=str(data.get("safety_mode", SAFETY_MODE)),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.hypothesis_id}: {self.title} "
            f"[{self.status.value}] conf={self.confidence:.1f} horizon={self.horizon}"
        )
