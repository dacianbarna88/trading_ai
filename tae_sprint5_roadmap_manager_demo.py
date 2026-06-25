"""
TAE Sprint 5.5 — Research Roadmap Manager

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Structured view of TAE research capabilities and evolution — informational only.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.roadmap import DEFAULT_STATUS_PATH, RoadmapManager
from research_core.life import LifeManager

SUMMARY_TXT = "tae_sprint5_roadmap_manager_summary.txt"


def run_roadmap_demo() -> RoadmapManager:
    print("===== TAE SPRINT 5.5 — RESEARCH ROADMAP MANAGER =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Structured capability roadmap — informational only.")
    print("No broker. No live bot. No order execution.")
    print()

    manager = RoadmapManager()
    status = manager.assess()
    status_path = manager.persist(status)

    print(f"Roadmap assessed: {status.completed_count}/{status.total_capabilities} capabilities complete")
    print(f"Persisted: {status_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Research roadmap — capability evolution tracking")
    if not life.timeline.has_title("Research Roadmap Manager"):
        life.record_event(
            "milestone",
            "Research Roadmap Manager",
            "Sprint 5.5 — structured research capability and phase tracking.",
            milestone_importance=6,
        )
    life.record_event(
        "roadmap",
        "Sprint 5.5 Roadmap Status",
        (
            f"Maturity={status.maturity_level}, "
            f"completion={status.completion_overall_pct:.1f}%, "
            f"completed={status.completed_count}. Informational only."
        ),
        add_timeline=False,
    )
    life.persist()

    report = status.format_report()
    print(report)

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(report + "\n", encoding="utf-8")

    life.status_generator.generate(
        age=life.age,
        generation=life.generation,
        journal=life.journal,
        milestones=life.milestones,
        achievements=life.achievements,
        metrics=life.metrics,
        current_mission=life.current_mission,
    )

    print(f"Saved: {summary_path}")
    print(f"Saved: TAE_STATUS.md")
    print(f"Saved: {DEFAULT_STATUS_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return manager


def main() -> None:
    run_roadmap_demo()


if __name__ == "__main__":
    main()
