"""
Runtime Event Bus — Phase IX C2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RuntimeEventType(str, Enum):
    ECOSYSTEM_STARTED = "ECOSYSTEM_STARTED"
    STATE_LOADED = "STATE_LOADED"
    EVIDENCE_REFRESHED = "EVIDENCE_REFRESHED"
    STRATEGY_EVOLUTION_UPDATED = "STRATEGY_EVOLUTION_UPDATED"
    RANKING_UPDATED = "RANKING_UPDATED"
    PROMOTION_CHECKED = "PROMOTION_CHECKED"
    PAPER_TRACKING_UPDATED = "PAPER_TRACKING_UPDATED"
    HEALTH_CHECK_COMPLETED = "HEALTH_CHECK_COMPLETED"
    LEARNING_MEMORY_UPDATED = "LEARNING_MEMORY_UPDATED"
    ECOSYSTEM_COMPLETED = "ECOSYSTEM_COMPLETED"


@dataclass
class RuntimeEvent:
    event_type: RuntimeEventType
    source: str
    status: str
    payload_summary: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "source": self.source,
            "status": self.status,
            "payload_summary": self.payload_summary,
        }


class EventBus:
    def __init__(self) -> None:
        self._events: list[RuntimeEvent] = []

    def emit(
        self,
        event_type: RuntimeEventType,
        source: str,
        status: str,
        payload_summary: str,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_type=event_type,
            source=source,
            status=status,
            payload_summary=payload_summary,
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> list[RuntimeEvent]:
        return list(self._events)

    def to_dict(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]
