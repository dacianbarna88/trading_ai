"""
TAE Sprint 5.4 — Learning Engine

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Transforms experiment history into meta-learning — not trading signals.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.learning import (
    DEFAULT_REPORT_PATH,
    LearningEngine,
    LearningReportStore,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_sprint5_learning_engine_summary.txt"


def run_learning_demo() -> LearningReportStore:
    print("===== TAE SPRINT 5.4 — LEARNING ENGINE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Meta-learning from research history — not trading or execution.")
    print("No broker. No live bot. No order execution.")
    print()

    engine = LearningEngine()
    report = engine.analyze()

    store = LearningReportStore(auto_load=False)
    store.set_report(report)
    report_path = store.persist()

    print(f"Learning report generated: {report_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Learning engine — meta-learning from research history")
    if not life.timeline.has_title("Learning Engine"):
        life.record_event(
            "milestone",
            "Learning Engine",
            "Sprint 5.4 — experiment history transformed into meta-learning.",
            milestone_importance=7,
        )
    life.record_event(
        "meta_learning",
        "Sprint 5.4 Learning Report",
        (
            f"Analyzed {report.experiments_analyzed} experiments; "
            f"confidence={report.learning_confidence:.1f}; "
            f"best_organism={report.best_organism}. Research only."
        ),
        add_timeline=False,
    )
    life.persist()

    summary = report.format_summary()
    print(summary)

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(summary + "\n", encoding="utf-8")

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
    print(f"Saved: {DEFAULT_REPORT_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return store


def main() -> None:
    run_learning_demo()


if __name__ == "__main__":
    main()
