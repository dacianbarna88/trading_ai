"""
TAE Life Demo — Sprint 3.5 Life System

RESEARCH_ONLY | NO_BROKER | NO_EXECUTION

Demonstrates TAE biography: age, generation, journal, milestones,
achievements, timeline, and TAE_STATUS.md generation.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.life import LifeManager

SUMMARY_TXT = "tae_life_summary.txt"
STATUS_MD = "TAE_STATUS.md"


def run_demo() -> LifeManager:
    print("===== TAE LIFE SYSTEM — Sprint 3.5 =====")
    print(RESEARCH_SAFETY_BANNER)
    print("TAE now has a birthday, memory, history, and generation.")
    print()

    life = LifeManager(start_generation=3)
    if life.loaded_from_storage:
        print(f"Loaded prior state from: {life.state_path}")
        print(
            f"  journal={life.journal.count()} milestones={life.milestones.count()} "
            f"timeline={life.timeline.count()} achievements={life.achievements.count_unlocked()}"
        )
    else:
        print(f"No prior state — fresh LifeManager (will persist to {life.state_path})")
    print()

    life.bootstrap_origin_story()
    life.set_current_mission("First Real Organism")

    print(f"Birthday: {life.age.birthday_string()}")
    print(f"Age: {life.age.age_string()}")
    print(f"Generation: {life.generation.current_generation()} — {life.generation.generation_name()}")
    print()

    if life.journal.count() == 0:
        life.record_event(
            "organism_registered",
            "First Organism Created",
            "context_demo_organism registered in ecosystem demo.",
            milestone_importance=9,
        )
        life.record_event(
            "evidence_packet",
            "First Evidence Packet",
            "Synthetic evidence packet published to communication bus.",
            milestone_importance=9,
        )
        life.record_event(
            "collective_decision",
            "First Collective Decision",
            "Collective intelligence produced MEDIUM_CONFIDENCE decision.",
            milestone_importance=9,
        )
        life.record_event(
            "milestone",
            "First Knowledge Graph",
            "Sprint 3 cognitive layer created relational memory.",
            milestone_importance=8,
        )
        life.record_event(
            "curiosity_question",
            "First Curiosity Question",
            "Why does Momentum disagree with Risk in BEAR regimes?",
        )
        life.record_event(
            "self_correction",
            "First Self Correction",
            "Feedback loop adjusted organism trust after collective review.",
        )
        life.record_event(
            "knowledge_item",
            "Knowledge Item Stored",
            "Pattern stored in knowledge core.",
        )
        life.record_event(
            "research_experiment",
            "Cognitive Demo Run",
            "ecosystem_cognitive_demo_v1 executed successfully.",
        )

        life.write_journal_entry(
            todays_mission="Activate TAE Life System and record first biography entry.",
            todays_evolution="Sprint 3.5 Life System born — age, journal, milestones, achievements.",
            new_organisms=["context_demo_organism", "curiosity_organism"],
            major_decisions=[
                "Collective MEDIUM_CONFIDENCE with questioning cognitive status",
                "Life System becomes official TAE biography layer",
            ],
            lessons_learned=[
                "TAE needs persistent history beyond ephemeral CSV outputs.",
                "Curiosity questions reveal where research should go next.",
            ],
            open_questions=[
                "When should Generation 4 (Real Organisms) begin?",
                "Which real research module becomes the first live organism?",
            ],
            next_mission="Wire first real research organism into ecosystem bus.",
        )

        life.promote_generation("Preparing for Real Organisms — Generation 4")
    else:
        print("Demo events already recorded — skipping duplicate seed (loaded from persistence).")
        print()

    print("===== ACHIEVEMENTS UNLOCKED =====")
    for achievement in life.achievements.list_unlocked():
        print(f"  ✓ {achievement.title}")
    print()

    print("===== TIMELINE =====")
    print(life.timeline.format_vertical())
    print()

    summary_content = build_summary(life)
    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(summary_content, encoding="utf-8")

    status_content = life.system_summary()
    persisted_path = life.persist()
    print(f"Saved: {STATUS_MD}")
    print(f"Saved: {summary_path}")
    print(f"Persisted: {persisted_path}")
    print()
    print("===== TAE STATUS (preview) =====")
    print(status_content.split("===== TIMELINE =====")[0])

    return life


def build_summary(life: LifeManager) -> str:
    snapshot = life.daily_snapshot()
    lines = [
        "===== TAE LIFE SYSTEM — Sprint 3.5 Summary =====",
        "",
        RESEARCH_SAFETY_BANNER,
        "",
        "===== BIRTHDAY & AGE =====",
        f"Birthday: {life.age.birthday_string()}",
        f"Age: {life.age.age_string()}",
        f"Days alive: {life.age.days_alive()}",
        "",
        "===== GENERATION =====",
        f"Current: {life.generation.current_generation()} — {life.generation.generation_name()}",
        "History:",
    ]
    for record in life.generation.history():
        lines.append(f"  Gen {record.number}: {record.theme} — {record.description[:60]}")
    lines.extend(
        [
            "",
            "===== METRICS =====",
        ]
    )
    for key, value in snapshot["metrics"].items():
        lines.append(f"  {key}: {value}")
    lines.extend(
        [
            "",
            f"Milestones: {life.milestones.count()}",
            f"Achievements unlocked: {life.achievements.count_unlocked()}",
            f"Journal entries: {life.journal.count()}",
            f"Timeline events: {life.timeline.count()}",
            f"Current mission: {life.current_mission}",
            "",
            "===== MILESTONES =====",
        ]
    )
    for milestone in life.milestones.history():
        lines.append(f"  [{milestone.importance}] {milestone.title} — {milestone.description}")
    lines.extend(["", "===== ACHIEVEMENTS ====="])
    for achievement in life.achievements.list_all():
        status = "UNLOCKED" if achievement.unlocked else f"{achievement.progress_current}/{achievement.progress_target}"
        lines.append(f"  {achievement.title}: {status}")
    lines.extend(["", "===== CURIOSITY / OPEN QUESTIONS ====="])
    latest = life.journal.latest()
    if latest:
        for q in latest.open_questions:
            lines.append(f"  ? {q}")
    lines.extend(
        [
            "",
            "===== TIMELINE =====",
            life.timeline.format_vertical(),
            "",
            "===== LATEST JOURNAL =====",
        ]
    )
    if latest:
        lines.append(latest.format_block())
    lines.extend(
        [
            "We never stop learning.",
            "We never stop moving.",
            "We never stop questioning.",
            "We never stop teaching.",
            "We never stop evolving.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
