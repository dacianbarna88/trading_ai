"""
TAE Phase V Sprint A1 — Autonomous Research Prioritization

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Prioritizes research opportunities — does not run experiments or modify artifacts.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.autonomy import (
    DEFAULT_PRIORITIES_PATH,
    PrioritizationReportStore,
    ResearchPrioritizer,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_phase5_research_prioritization_summary.txt"


def run_prioritization_demo() -> PrioritizationReportStore:
    print("===== TAE PHASE V SPRINT A1 — RESEARCH PRIORITIZATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Autonomous research ordering — not trading or execution.")
    print("Does not generate hypotheses, run experiments, or modify discoveries.")
    print("No broker. No live bot. No order execution.")
    print()

    prioritizer = ResearchPrioritizer()
    report = prioritizer.prioritize()

    store = PrioritizationReportStore()
    store.set_report(report)
    report_path = store.persist()

    print(f"Evaluated {report.opportunities_evaluated} research opportunity/ies")
    print(f"Persisted: {report_path}")
    print()

    life = LifeManager(start_generation=5)
    life.bootstrap_origin_story()
    life.set_current_mission("Autonomous research prioritization")
    if not life.timeline.has_title("Research Prioritization"):
        life.record_event(
            "milestone",
            "Research Prioritization",
            "Phase V A1 — autonomous ordering of pending research opportunities.",
            milestone_importance=8,
        )
    if report.top_opportunity_id:
        life.record_event(
            "research_prioritization",
            "Phase V A1 Prioritization Run",
            f"Top priority={report.top_opportunity_id}; "
            f"recommended={report.recommended_next_experiment[:80]}. Not execution.",
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
    print(f"Saved: {DEFAULT_PRIORITIES_PATH}")
    print(f"Persisted life state: {life.state_path}")

    return store


def main() -> None:
    run_prioritization_demo()


if __name__ == "__main__":
    main()
