"""Ecosystem-wide state snapshot — no trading metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class EcosystemState:
    """
    Point-in-time view of the living ecosystem.
    """

    generation: int
    active_organisms: list[str]
    knowledge_size: int
    health_score: float
    learning_velocity: float
    packet_count: int
    collective_confidence: float | None
    confidence_level: str | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "active_organisms": self.active_organisms,
            "knowledge_size": self.knowledge_size,
            "health_score": round(self.health_score, 2),
            "learning_velocity": round(self.learning_velocity, 4),
            "packet_count": self.packet_count,
            "collective_confidence": self.collective_confidence,
            "confidence_level": self.confidence_level,
            "timestamp": self.timestamp.isoformat(),
        }


class EcosystemStateTracker:
    """Tracks generation counter and builds state snapshots."""

    def __init__(self) -> None:
        self._generation: int = 0
        self._learning_event_count: int = 0
        self._last_learning_count: int = 0
        self._last_snapshot_time: datetime = datetime.now(timezone.utc)

    def advance_generation(self) -> int:
        self._generation += 1
        return self._generation

    @property
    def generation(self) -> int:
        return self._generation

    def record_learning_events(self, count: int) -> None:
        self._learning_event_count = count

    def learning_velocity(self) -> float:
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_snapshot_time).total_seconds()
        if elapsed <= 0:
            return 0.0
        delta = self._learning_event_count - self._last_learning_count
        velocity = delta / elapsed
        self._last_learning_count = self._learning_event_count
        self._last_snapshot_time = now
        return velocity

    def build_snapshot(
        self,
        active_organisms: list[str],
        knowledge_size: int,
        health_score: float,
        packet_count: int,
        collective_confidence: float | None = None,
        confidence_level: str | None = None,
    ) -> EcosystemState:
        return EcosystemState(
            generation=self._generation,
            active_organisms=list(active_organisms),
            knowledge_size=knowledge_size,
            health_score=health_score,
            learning_velocity=self.learning_velocity(),
            packet_count=packet_count,
            collective_confidence=collective_confidence,
            confidence_level=confidence_level,
        )
