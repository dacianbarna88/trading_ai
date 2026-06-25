"""TAE Life System — official biography of the Trading AI Ecosystem."""

from research_core.life.age import TAEAge, TAE_BIRTHDAY
from research_core.life.achievements import Achievement, AchievementTracker
from research_core.life.ecosystem_bridge import BridgeRecordSummary, EcosystemLifeBridge
from research_core.life.generation import GenerationRecord, GenerationTracker, GENERATION_DEFINITIONS
from research_core.life.journal import Journal, JournalEntry
from research_core.life.life_events import LifeEvent
from research_core.life.life_manager import LifeManager
from research_core.life.life_storage import DEFAULT_STATE_PATH, LifeStorage
from research_core.life.milestones import Milestone, MilestoneStore
from research_core.life.status import StatusGenerator
from research_core.life.timeline import Timeline, TimelineEvent

__all__ = [
    "Achievement",
    "AchievementTracker",
    "BridgeRecordSummary",
    "DEFAULT_STATE_PATH",
    "EcosystemLifeBridge",
    "GENERATION_DEFINITIONS",
    "GenerationRecord",
    "GenerationTracker",
    "Journal",
    "JournalEntry",
    "LifeEvent",
    "LifeManager",
    "LifeStorage",
    "Milestone",
    "MilestoneStore",
    "StatusGenerator",
    "TAEAge",
    "TAE_BIRTHDAY",
    "Timeline",
    "TimelineEvent",
]
