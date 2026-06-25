"""TAE milestones — landmark events in ecosystem history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Milestone:
    title: str
    date: str
    age: str
    generation: int
    description: str
    importance: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "date": self.date,
            "age": self.age,
            "generation": self.generation,
            "description": self.description,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat(),
        }


class MilestoneStore:
    """Records major moments in TAE biography."""

    PREDEFINED: list[tuple[str, str, int]] = [
        ("TAE Born", "Trading AI Ecosystem officially born.", 10),
        ("First Organism", "First organism architecture defined.", 9),
        ("First Collective Decision", "Collective intelligence produced first decision.", 9),
        ("First Knowledge Graph", "Knowledge graph foundation created.", 8),
        ("First Walk Forward PASS", "Walk-forward validation passed in research.", 8),
        ("First Production Candidate", "Edge marked for human review.", 9),
        ("Life System Born", "TAE Life System Sprint 3.5 — official biography begins.", 10),
    ]

    def __init__(self) -> None:
        self._milestones: list[Milestone] = []

    def add(
        self,
        title: str,
        date: str,
        age: str,
        generation: int,
        description: str,
        importance: int = 5,
    ) -> Milestone:
        milestone = Milestone(
            title=title,
            date=date,
            age=age,
            generation=generation,
            description=description,
            importance=importance,
        )
        self._milestones.append(milestone)
        return milestone

    def history(self) -> list[Milestone]:
        return sorted(self._milestones, key=lambda m: m.timestamp)

    def latest(self) -> Milestone | None:
        if not self._milestones:
            return None
        return max(self._milestones, key=lambda m: m.timestamp)

    def count(self) -> int:
        return len(self._milestones)

    def titles(self) -> list[str]:
        return [m.title for m in self._milestones]
