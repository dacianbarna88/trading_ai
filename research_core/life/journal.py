"""TAE journal — daily biography entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class JournalEntry:
    date: str
    age: str
    generation: int
    todays_mission: str
    todays_evolution: str
    new_organisms: list[str] = field(default_factory=list)
    major_decisions: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    next_mission: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "age": self.age,
            "generation": self.generation,
            "todays_mission": self.todays_mission,
            "todays_evolution": self.todays_evolution,
            "new_organisms": self.new_organisms,
            "major_decisions": self.major_decisions,
            "lessons_learned": self.lessons_learned,
            "open_questions": self.open_questions,
            "next_mission": self.next_mission,
            "timestamp": self.timestamp.isoformat(),
        }

    def format_block(self) -> str:
        lines = [
            f"--- Journal Entry: {self.date} ---",
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Age: {self.age}",
            f"Generation: {self.generation}",
            f"Today's Mission: {self.todays_mission}",
            f"Today's Evolution: {self.todays_evolution}",
            f"New Organisms: {', '.join(self.new_organisms) or 'None'}",
            f"Major Decisions: {'; '.join(self.major_decisions) or 'None'}",
            f"Lessons Learned: {'; '.join(self.lessons_learned) or 'None'}",
            f"Open Questions: {'; '.join(self.open_questions) or 'None'}",
            f"Next Mission: {self.next_mission}",
            "",
        ]
        return "\n".join(lines)


class Journal:
    """Automatic journal for TAE life story."""

    def __init__(self) -> None:
        self._entries: list[JournalEntry] = []

    def add_entry(
        self,
        age_string: str,
        generation: int,
        todays_mission: str,
        todays_evolution: str,
        new_organisms: list[str] | None = None,
        major_decisions: list[str] | None = None,
        lessons_learned: list[str] | None = None,
        open_questions: list[str] | None = None,
        next_mission: str = "",
    ) -> JournalEntry:
        now = datetime.now(timezone.utc)
        entry = JournalEntry(
            date=now.strftime("%Y-%m-%d"),
            age=age_string,
            generation=generation,
            todays_mission=todays_mission,
            todays_evolution=todays_evolution,
            new_organisms=new_organisms or [],
            major_decisions=major_decisions or [],
            lessons_learned=lessons_learned or [],
            open_questions=open_questions or [],
            next_mission=next_mission,
            timestamp=now,
        )
        self._entries.append(entry)
        return entry

    def latest(self) -> JournalEntry | None:
        return self._entries[-1] if self._entries else None

    def all_entries(self) -> list[JournalEntry]:
        return list(self._entries)

    def count(self) -> int:
        return len(self._entries)
