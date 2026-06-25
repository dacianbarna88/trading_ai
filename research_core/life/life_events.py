"""TAE life event record — single biography event."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LifeEvent:
    event_type: str
    title: str
    detail: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
