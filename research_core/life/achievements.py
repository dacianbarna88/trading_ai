"""TAE achievements — unlockable ecosystem accomplishments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Achievement:
    id: str
    title: str
    description: str
    unlocked: bool = False
    unlocked_at: datetime | None = None
    progress_current: int = 0
    progress_target: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "unlocked": self.unlocked,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "progress_current": self.progress_current,
            "progress_target": self.progress_target,
        }


ACHIEVEMENT_DEFINITIONS: list[tuple[str, str, str, int]] = [
    ("first_organism", "First Organism", "First organism registered in TAE.", 1),
    ("first_evidence_packet", "First Evidence Packet", "First evidence packet published.", 1),
    ("evidence_packets_100", "100 Evidence Packets", "One hundred evidence packets processed.", 100),
    ("knowledge_items_1000", "1000 Knowledge Items", "One thousand knowledge items stored.", 1000),
    ("research_hours_100", "100 Research Hours", "One hundred research hours logged.", 100),
    ("first_self_correction", "First Self Correction", "First feedback-driven self correction.", 1),
    ("first_curiosity_question", "First Curiosity Question", "Curiosity organism asked first question.", 1),
    ("first_discovery_accepted", "First Discovery Accepted", "First discovery accepted into knowledge core.", 1),
    ("life_system_born", "Life System Born", "TAE Life System officially activated.", 1),
    ("first_journal_entry", "First Journal Entry", "First journal entry recorded.", 1),
    ("first_milestone", "First Milestone", "First milestone recorded.", 1),
]


class AchievementTracker:
    """Tracks unlockable achievements and progress counters."""

    def __init__(self) -> None:
        self._achievements: dict[str, Achievement] = {}
        for aid, title, desc, target in ACHIEVEMENT_DEFINITIONS:
            self._achievements[aid] = Achievement(
                id=aid,
                title=title,
                description=desc,
                progress_target=target,
            )

    def unlock(self, achievement_id: str) -> Achievement | None:
        achievement = self._achievements.get(achievement_id)
        if achievement is None:
            return None
        if not achievement.unlocked:
            achievement.unlocked = True
            achievement.unlocked_at = datetime.now(timezone.utc)
            achievement.progress_current = achievement.progress_target
        return achievement

    def is_unlocked(self, achievement_id: str) -> bool:
        achievement = self._achievements.get(achievement_id)
        return achievement.unlocked if achievement else False

    def list_all(self) -> list[Achievement]:
        return list(self._achievements.values())

    def list_unlocked(self) -> list[Achievement]:
        return [a for a in self._achievements.values() if a.unlocked]

    def progress(self, achievement_id: str, current: int) -> Achievement | None:
        achievement = self._achievements.get(achievement_id)
        if achievement is None:
            return None
        achievement.progress_current = min(current, achievement.progress_target)
        if achievement.progress_current >= achievement.progress_target:
            self.unlock(achievement_id)
        return achievement

    def increment(self, achievement_id: str, amount: int = 1) -> Achievement | None:
        achievement = self._achievements.get(achievement_id)
        if achievement is None:
            return None
        return self.progress(achievement_id, achievement.progress_current + amount)

    def count_unlocked(self) -> int:
        return sum(1 for a in self._achievements.values() if a.unlocked)

    def restore_from(self, achievements_data: list[dict[str, Any]]) -> None:
        """Merge persisted achievement progress without duplicating unlocks."""
        for item in achievements_data:
            if not isinstance(item, dict):
                continue
            achievement_id = item.get("id")
            if not achievement_id or achievement_id not in self._achievements:
                continue
            achievement = self._achievements[achievement_id]
            progress_current = int(item.get("progress_current", achievement.progress_current))
            progress_target = int(item.get("progress_target", achievement.progress_target))
            achievement.progress_target = progress_target
            achievement.progress_current = min(progress_current, progress_target)
            if item.get("unlocked"):
                if not achievement.unlocked:
                    achievement.unlocked = True
                    achievement.unlocked_at = _parse_unlocked_at(item.get("unlocked_at"))
                    achievement.progress_current = achievement.progress_target
            elif achievement.progress_current >= achievement.progress_target:
                self.unlock(achievement_id)


def _parse_unlocked_at(value: Any) -> datetime | None:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
