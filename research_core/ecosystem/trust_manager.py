"""Per-organism trust evolution — separate from confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TrustEvent:
    timestamp: datetime
    delta: float
    reason: str
    trust_after: float


class TrustManager:
    """
    Manages trust scores for registered organisms.
    Trust evolves from ecosystem feedback — not from single-run confidence.
    """

    DEFAULT_TRUST: float = 50.0

    def __init__(self) -> None:
        self._trust: dict[str, float] = {}
        self._history: dict[str, list[TrustEvent]] = {}

    def register(self, organism_name: str, initial: float | None = None) -> float:
        level = initial if initial is not None else self.DEFAULT_TRUST
        self._trust[organism_name] = max(0.0, min(100.0, level))
        self._history.setdefault(organism_name, [])
        return self._trust[organism_name]

    def current(self, organism_name: str) -> float:
        if organism_name not in self._trust:
            return self.register(organism_name)
        return self._trust[organism_name]

    def increase(self, organism_name: str, amount: float, reason: str) -> float:
        return self._apply(organism_name, amount, reason)

    def decrease(self, organism_name: str, amount: float, reason: str) -> float:
        return self._apply(organism_name, -amount, reason)

    def history(self, organism_name: str) -> list[TrustEvent]:
        return list(self._history.get(organism_name, []))

    def distribution(self) -> dict[str, float]:
        return dict(self._trust)

    def _apply(self, organism_name: str, delta: float, reason: str) -> float:
        if organism_name not in self._trust:
            self.register(organism_name)
        new_level = max(0.0, min(100.0, self._trust[organism_name] + delta))
        self._trust[organism_name] = new_level
        self._history[organism_name].append(
            TrustEvent(
                timestamp=datetime.now(timezone.utc),
                delta=delta,
                reason=reason,
                trust_after=new_level,
            )
        )
        return new_level
