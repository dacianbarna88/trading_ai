"""TAE timeline — chronological life story."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TimelineEvent:
    date: str
    title: str
    description: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
        }


class Timeline:
    """Chronological record of TAE history."""

    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def add(self, date: str, title: str, description: str = "") -> TimelineEvent:
        event = TimelineEvent(date=date, title=title, description=description)
        self._events.append(event)
        return event

    def events(self) -> list[TimelineEvent]:
        return sorted(self._events, key=lambda e: e.timestamp)

    def format_vertical(self) -> str:
        sorted_events = self.events()
        if not sorted_events:
            return "Timeline empty."
        lines: list[str] = []
        for event in sorted_events:
            lines.append(event.date)
            lines.append(event.title)
            if event.description:
                lines.append(f"  {event.description}")
            lines.append("↓")
        if lines:
            lines.pop()
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._events)
