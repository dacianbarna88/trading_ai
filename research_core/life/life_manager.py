"""TAE Life Manager — central orchestrator for ecosystem biography."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.life.age import TAEAge, TAE_BIRTHDAY
from research_core.life.achievements import AchievementTracker
from research_core.life.generation import GenerationTracker
from research_core.life.journal import Journal
from research_core.life.life_events import LifeEvent
from research_core.life.life_storage import DEFAULT_STATE_PATH, LifeStorage
from research_core.life.milestones import MilestoneStore
from research_core.life.status import StatusGenerator
from research_core.life.timeline import Timeline


class LifeManager:
    """
    Central orchestrator for TAE biography:
    age, journal, milestones, achievements, timeline, status.
    """

    def __init__(
        self,
        start_generation: int = 3,
        status_path: Path | None = None,
        state_path: Path | None = None,
        auto_load: bool = True,
    ) -> None:
        self.age = TAEAge(TAE_BIRTHDAY)
        self.generation = GenerationTracker(start_generation=start_generation)
        self.journal = Journal()
        self.milestones = MilestoneStore()
        self.achievements = AchievementTracker()
        self.timeline = Timeline()
        self.status_generator = StatusGenerator(status_path)
        self._metrics: dict[str, int] = {
            "organisms": 0,
            "knowledge_items": 0,
            "validated_discoveries": 0,
            "evidence_packets": 0,
            "collective_decisions": 0,
            "research_experiments": 0,
        }
        self._current_mission = "Birth of Collective Intelligence"
        self._events: list[LifeEvent] = []
        self._origin_bootstrapped = False
        self._loaded_from_storage = False
        self._storage_path = state_path or DEFAULT_STATE_PATH
        self._storage = LifeStorage(self._storage_path)

        if auto_load:
            self._loaded_from_storage = self._storage.load_into(self)

    @property
    def origin_bootstrapped(self) -> bool:
        return self._origin_bootstrapped

    @property
    def loaded_from_storage(self) -> bool:
        return self._loaded_from_storage

    @property
    def state_path(self) -> Path:
        return self._storage_path

    @property
    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)

    def events(self) -> list[LifeEvent]:
        return list(self._events)

    def persist(self) -> Path:
        """Write current life state to JSON."""
        path = self._storage.save(self)
        self._loaded_from_storage = True
        return path

    def bootstrap_origin_story(self) -> bool:
        """Seed timeline and milestones for TAE origin (Sprint 3.5). Idempotent."""
        if self._origin_bootstrapped:
            return False

        birth_date = self.age.birthday_string()
        origin_timeline = [
            ("TAE Born", "Trading AI Ecosystem officially born."),
            ("Foundation Created", "TAE 1.0 philosophy and architecture."),
            ("Collective Intelligence Created", "Sprint 2 nervous system."),
            ("Cognitive Layer Created", "Sprint 3 active cognition."),
            ("Life System Born", "Sprint 3.5 — official biography begins."),
        ]
        for title, detail in origin_timeline:
            if not self.timeline.has_title(title):
                self.timeline.add(birth_date, title, detail)

        age_str = self.age.age_one_line()
        gen = self.generation.current_generation()
        for title, desc, importance in MilestoneStore.PREDEFINED[:3]:
            if not self.milestones.has_title(title):
                self.milestones.add(title, birth_date, age_str, gen, desc, importance)
        if not self.milestones.has_title("Life System Born"):
            self.milestones.add(
                "Life System Born",
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                age_str,
                gen,
                "TAE Life System Sprint 3.5 activated.",
                10,
            )

        self.achievements.unlock("life_system_born")
        self.achievements.unlock("first_organism")
        self.achievements.unlock("first_milestone")
        self._origin_bootstrapped = True
        return True

    def record_event(
        self,
        event_type: str,
        title: str,
        detail: str = "",
        add_timeline: bool = True,
        milestone_importance: int = 5,
    ) -> LifeEvent:
        event = LifeEvent(event_type=event_type, title=title, detail=detail)
        self._events.append(event)
        date_str = event.timestamp.strftime("%Y-%m-%d")
        age_str = self.age.age_one_line()
        gen = self.generation.current_generation()

        if add_timeline:
            self.timeline.add(date_str, title, detail)

        if event_type == "milestone":
            self.milestones.add(title, date_str, age_str, gen, detail, milestone_importance)
            self.achievements.unlock("first_milestone")

        if event_type == "achievement":
            for achievement in self.achievements.list_all():
                if achievement.title == title or achievement.id == title:
                    self.achievements.unlock(achievement.id)
                    break

        if event_type == "organism_registered":
            self._metrics["organisms"] += 1
            self.achievements.unlock("first_organism")

        if event_type == "evidence_packet":
            self._metrics["evidence_packets"] += 1
            self.achievements.increment("first_evidence_packet")
            self.achievements.increment("evidence_packets_100")

        if event_type == "collective_decision":
            self._metrics["collective_decisions"] += 1

        if event_type == "knowledge_item":
            self._metrics["knowledge_items"] += 1
            self.achievements.increment("knowledge_items_1000")

        if event_type == "curiosity_question":
            self.achievements.unlock("first_curiosity_question")

        if event_type == "self_correction":
            self.achievements.unlock("first_self_correction")

        if event_type == "discovery_accepted":
            self._metrics["validated_discoveries"] += 1
            self.achievements.unlock("first_discovery_accepted")

        if event_type == "research_experiment":
            self._metrics["research_experiments"] += 1

        return event

    def set_current_mission(self, mission: str) -> None:
        self._current_mission = mission

    @property
    def current_mission(self) -> str:
        return self._current_mission

    def promote_generation(self, reason: str = "") -> int:
        record = self.generation.promote_generation(reason)
        self.record_event(
            "generation_promoted",
            f"Generation {record.number}: {record.theme}",
            record.description,
        )
        return record.number

    def write_journal_entry(
        self,
        todays_mission: str,
        todays_evolution: str,
        new_organisms: list[str] | None = None,
        major_decisions: list[str] | None = None,
        lessons_learned: list[str] | None = None,
        open_questions: list[str] | None = None,
        next_mission: str = "",
    ) -> None:
        entry = self.journal.add_entry(
            age_string=self.age.age_one_line(),
            generation=self.generation.current_generation(),
            todays_mission=todays_mission,
            todays_evolution=todays_evolution,
            new_organisms=new_organisms,
            major_decisions=major_decisions,
            lessons_learned=lessons_learned,
            open_questions=open_questions,
            next_mission=next_mission,
        )
        self.achievements.unlock("first_journal_entry")
        self.record_event("journal_entry", f"Journal: {entry.date}", entry.todays_mission)

    def daily_snapshot(self) -> dict[str, Any]:
        return {
            "birthday": self.age.birthday_string(),
            "age": self.age.age_one_line(),
            "age_days": self.age.current_age_days(),
            "age_hours": self.age.current_age_hours(),
            "generation": self.generation.to_dict(),
            "metrics": dict(self._metrics),
            "milestones": self.milestones.count(),
            "achievements_unlocked": self.achievements.count_unlocked(),
            "journal_entries": self.journal.count(),
            "timeline_events": self.timeline.count(),
            "current_mission": self._current_mission,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def system_summary(self) -> str:
        status = self.status_generator.generate(
            age=self.age,
            generation=self.generation,
            journal=self.journal,
            milestones=self.milestones,
            achievements=self.achievements,
            metrics=self._metrics,
            current_mission=self._current_mission,
        )
        parts = [
            status,
            "",
            "===== TIMELINE =====",
            self.timeline.format_vertical(),
            "",
        ]
        latest_journal = self.journal.latest()
        if latest_journal:
            parts.append(latest_journal.format_block())
        return "\n".join(parts)

    def update_metrics(self, **kwargs: int) -> None:
        for key, value in kwargs.items():
            if key in self._metrics:
                self._metrics[key] = value
