"""
TAE Life JSON persistence — Sprint 3.7

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | ANALYSIS_ONLY

Persists journal, milestones, achievements, timeline, and recorded events.
No external dependencies — stdlib json only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from research_core.life.generation import GenerationRecord
from research_core.life.journal import JournalEntry
from research_core.life.life_events import LifeEvent
from research_core.life.milestones import Milestone
from research_core.life.timeline import TimelineEvent

if TYPE_CHECKING:
    from research_core.life.life_manager import LifeManager

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("tae_life_state.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_life_state"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _life_event_to_dict(event: LifeEvent) -> dict[str, Any]:
    return {
        "event_type": event.event_type,
        "title": event.title,
        "detail": event.detail,
        "timestamp": event.timestamp.isoformat(),
    }


def _life_event_from_dict(data: dict[str, Any]) -> LifeEvent | None:
    try:
        timestamp = _parse_datetime(data.get("timestamp"))
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return LifeEvent(
            event_type=str(data["event_type"]),
            title=str(data["title"]),
            detail=str(data.get("detail", "")),
            timestamp=timestamp,
        )
    except (KeyError, TypeError):
        return None


class LifeStorage:
    """JSON file persistence for TAE Life state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_STATE_PATH

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def save(self, manager: LifeManager) -> Path:
        payload = self._serialize(manager)
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return self._path

    def load_into(self, manager: LifeManager) -> bool:
        if not self.exists():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("TAE life state unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict):
            logger.warning("TAE life state invalid root type in %s", self._path)
            return False

        if payload.get("schema") != SCHEMA_NAME:
            logger.warning("TAE life state schema mismatch in %s", self._path)
            return False

        try:
            self._deserialize(manager, payload)
            manager._loaded_from_storage = True
            manager._storage_path = self._path
            return True
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("TAE life state deserialize failed (%s): %s", self._path, exc)
            return False

    def _serialize(self, manager: LifeManager) -> dict[str, Any]:
        generation_history = []
        for record in manager.generation.history():
            generation_history.append(
                {
                    "number": record.number,
                    "name": record.name,
                    "theme": record.theme,
                    "started_at": record.started_at.isoformat(),
                    "description": record.description,
                }
            )

        achievements = [achievement.to_dict() for achievement in manager.achievements.list_all()]
        journal = [entry.to_dict() for entry in manager.journal.all_entries()]
        milestones = [milestone.to_dict() for milestone in manager.milestones.history()]
        timeline = [event.to_dict() for event in manager.timeline.events()]
        events = [_life_event_to_dict(event) for event in manager.events()]

        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "origin_bootstrapped": manager.origin_bootstrapped,
            "current_mission": manager.current_mission,
            "metrics": dict(manager.metrics),
            "generation": {
                "current": manager.generation.current_generation(),
                "history": generation_history,
            },
            "events": events,
            "journal": journal,
            "milestones": milestones,
            "achievements": achievements,
            "timeline": timeline,
        }

    def _deserialize(self, manager: LifeManager, payload: dict[str, Any]) -> None:
        manager._origin_bootstrapped = bool(payload.get("origin_bootstrapped", False))
        manager._current_mission = str(payload.get("current_mission", manager._current_mission))

        metrics = payload.get("metrics", {})
        if isinstance(metrics, dict):
            for key in manager._metrics:
                if key in metrics:
                    manager._metrics[key] = int(metrics[key])

        generation_data = payload.get("generation", {})
        if isinstance(generation_data, dict):
            history: list[GenerationRecord] = []
            for item in generation_data.get("history", []):
                if not isinstance(item, dict):
                    continue
                started_at = _parse_datetime(item.get("started_at"))
                if started_at is None:
                    started_at = datetime(2026, 6, 25, tzinfo=timezone.utc)
                history.append(
                    GenerationRecord(
                        number=int(item["number"]),
                        name=str(item.get("name", f"Generation {item['number']}")),
                        theme=str(item.get("theme", "")),
                        started_at=started_at,
                        description=str(item.get("description", "")),
                    )
                )
            current = int(generation_data.get("current", manager.generation.current_generation()))
            manager.generation.restore(current, history)

        manager._events = []
        for item in payload.get("events", []):
            if not isinstance(item, dict):
                continue
            event = _life_event_from_dict(item)
            if event is not None:
                manager._events.append(event)

        manager.journal._entries = []
        for item in payload.get("journal", []):
            if not isinstance(item, dict):
                continue
            timestamp = _parse_datetime(item.get("timestamp")) or datetime.now(timezone.utc)
            manager.journal._entries.append(
                JournalEntry(
                    date=str(item.get("date", "")),
                    age=str(item.get("age", "")),
                    generation=int(item.get("generation", 3)),
                    todays_mission=str(item.get("todays_mission", "")),
                    todays_evolution=str(item.get("todays_evolution", "")),
                    new_organisms=list(item.get("new_organisms", [])),
                    major_decisions=list(item.get("major_decisions", [])),
                    lessons_learned=list(item.get("lessons_learned", [])),
                    open_questions=list(item.get("open_questions", [])),
                    next_mission=str(item.get("next_mission", "")),
                    timestamp=timestamp,
                )
            )

        manager.milestones._milestones = []
        for item in payload.get("milestones", []):
            if not isinstance(item, dict):
                continue
            timestamp = _parse_datetime(item.get("timestamp")) or datetime.now(timezone.utc)
            milestone = Milestone(
                title=str(item.get("title", "")),
                date=str(item.get("date", "")),
                age=str(item.get("age", "")),
                generation=int(item.get("generation", 3)),
                description=str(item.get("description", "")),
                importance=int(item.get("importance", 5)),
                timestamp=timestamp,
            )
            manager.milestones._milestones.append(milestone)

        achievements_data = payload.get("achievements", [])
        if isinstance(achievements_data, list):
            manager.achievements.restore_from(achievements_data)

        manager.timeline._events = []
        for item in payload.get("timeline", []):
            if not isinstance(item, dict):
                continue
            timestamp = _parse_datetime(item.get("timestamp")) or datetime.now(timezone.utc)
            manager.timeline._events.append(
                TimelineEvent(
                    date=str(item.get("date", "")),
                    title=str(item.get("title", "")),
                    description=str(item.get("description", "")),
                    timestamp=timestamp,
                )
            )
