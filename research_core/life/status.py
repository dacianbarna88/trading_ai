"""TAE_STATUS.md generator — living status document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_core.life.age import TAEAge
from research_core.life.achievements import AchievementTracker
from research_core.life.generation import GenerationTracker
from research_core.life.journal import Journal
from research_core.life.milestones import MilestoneStore

PHILOSOPHY_LINES: list[str] = [
    "Research before Execution",
    "Evidence before Opinion",
    "Validation before Trust",
    "Knowledge before Profit",
]

DEFAULT_STATUS_PATH = Path("TAE_STATUS.md")


def compute_health_label(
    organisms: int,
    knowledge_items: int,
    milestones: int,
) -> str:
    score = organisms + knowledge_items // 10 + milestones
    if score >= 15:
        return "Excellent"
    if score >= 8:
        return "Good"
    if score >= 3:
        return "Growing"
    return "Nascent"


def compute_learning_velocity(journal_count: int, achievements_unlocked: int) -> str:
    total = journal_count + achievements_unlocked
    if total >= 10:
        return "Accelerating"
    if total >= 5:
        return "Growing"
    if total >= 1:
        return "Emerging"
    return "Waiting"


class StatusGenerator:
    """Builds TAE_STATUS.md from life system state."""

    def __init__(self, output_path: Path | None = None) -> None:
        self._path = output_path or DEFAULT_STATUS_PATH

    def generate(
        self,
        age: TAEAge,
        generation: GenerationTracker,
        journal: Journal,
        milestones: MilestoneStore,
        achievements: AchievementTracker,
        metrics: dict[str, Any],
        current_mission: str,
    ) -> str:
        gen_info = generation.current_generation_info()
        theme = gen_info.theme if gen_info else generation.generation_name()
        health = compute_health_label(
            metrics.get("organisms", 0),
            metrics.get("knowledge_items", 0),
            milestones.count(),
        )
        velocity = compute_learning_velocity(journal.count(), achievements.count_unlocked())

        lines = [
            "===================================",
            "Trading AI Ecosystem",
            "===================================",
            "",
            "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
            "",
            f"Birthday: {age.birthday_string()}",
            f"Age: {age.age_one_line()}",
            f"Generation: {generation.current_generation()} ({theme})",
            f"Current Mission: {current_mission}",
            "",
            f"Organisms: {metrics.get('organisms', 0)}",
            f"Knowledge Items: {metrics.get('knowledge_items', 0)}",
            f"Validated Discoveries: {metrics.get('validated_discoveries', 0)}",
            f"Evidence Packets: {metrics.get('evidence_packets', 0)}",
            f"Collective Decisions: {metrics.get('collective_decisions', 0)}",
            f"Research Experiments: {metrics.get('research_experiments', 0)}",
            f"Git Milestones: {milestones.count()}",
            f"Book Chapters: {journal.count()}",
            f"Achievements Unlocked: {achievements.count_unlocked()}",
            "",
            f"Health: {health}",
            f"Learning Velocity: {velocity}",
            "",
            "Current Philosophy:",
        ]
        for line in PHILOSOPHY_LINES:
            lines.append(f"  {line}")
        lines.extend(["", "===================================", ""])
        content = "\n".join(lines)
        self._path.write_text(content, encoding="utf-8")
        return content

    @property
    def path(self) -> Path:
        return self._path
