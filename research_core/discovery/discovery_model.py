"""
Discovery model — Phase IV Sprint D1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

A Discovery is an unexpected statistical relationship worth future research —
NOT a BUY/SELL signal or a hypothesis.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER


class DiscoveryStatus(str, Enum):
    NEW = "NEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONVERTED = "CONVERTED"
    LINKED = "LINKED"
    VALIDATED = "VALIDATED"
    DISMISSED = "DISMISSED"
    ARCHIVED = "ARCHIVED"


class DiscoveryCategory(str, Enum):
    HIGH_PERFORMING_CLUSTER = "HIGH_PERFORMING_CLUSTER"
    CROSS_REGIME_ANOMALY = "CROSS_REGIME_ANOMALY"
    ORGANISM_DOMINANCE = "ORGANISM_DOMINANCE"
    FORWARD_RETURN_ANOMALY = "FORWARD_RETURN_ANOMALY"


@dataclass
class Discovery:
    discovery_id: str
    title: str
    description: str
    evidence: str
    confidence: float
    novelty_score: float
    source_experiments: list[str]
    suggested_next_step: str
    status: DiscoveryStatus = DiscoveryStatus.NEW
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safety_mode: str = RESEARCH_SAFETY_BANNER
    category: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(100.0, float(self.confidence)))
        self.novelty_score = max(0.0, min(100.0, float(self.novelty_score)))
        if isinstance(self.status, str):
            self.status = DiscoveryStatus(self.status)
        if not self.fingerprint:
            self.fingerprint = self.build_fingerprint()

    def build_fingerprint(self) -> str:
        raw = f"{self.category}|{self.title}".lower().strip()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_id": self.discovery_id,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 2),
            "novelty_score": round(self.novelty_score, 2),
            "source_experiments": list(self.source_experiments),
            "suggested_next_step": self.suggested_next_step,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "safety_mode": self.safety_mode,
            "category": self.category,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Discovery | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            status_raw = str(data.get("status", DiscoveryStatus.NEW.value))
            try:
                status = DiscoveryStatus(status_raw)
            except ValueError:
                status = DiscoveryStatus.NEW

            experiments = data.get("source_experiments", [])
            if not isinstance(experiments, list):
                experiments = []

            discovery = cls(
                discovery_id=str(data["discovery_id"]),
                title=str(data.get("title", "")),
                description=str(data.get("description", "")),
                evidence=str(data.get("evidence", "")),
                confidence=float(data.get("confidence", 0)),
                novelty_score=float(data.get("novelty_score", 0)),
                source_experiments=[str(e) for e in experiments],
                suggested_next_step=str(data.get("suggested_next_step", "")),
                status=status,
                created_at=dt,
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                category=str(data.get("category", "")),
                fingerprint=str(data.get("fingerprint", "")),
            )
            return discovery
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.discovery_id} | {self.title} | "
            f"conf={self.confidence:.1f} novelty={self.novelty_score:.1f} "
            f"[{self.status.value}]"
        )
