"""
TAE Phase IV Sprint D6 — Cross-Regime & Multi-Horizon Validation

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.validation import (
    DEFAULT_REPORT_PATH,
    CrossRegimeValidator,
    CrossValidationReportStore,
)
from research_core.life import LifeManager

SUMMARY_TXT = "tae_phase4_cross_validation_summary.txt"


def run_cross_validation_demo() -> CrossValidationReportStore:
    print("===== TAE PHASE IV SPRINT D6 — CROSS-VALIDATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Regime / horizon / region robustness — not trading.")
    print("No broker. No live bot. No order execution.")
    print()

    validator = CrossRegimeValidator()
    report = validator.validate_all()

    store = CrossValidationReportStore()
    store.set_report(report)
    report_path = store.persist()

    print(f"Validation complete — {report.candidates_analyzed} candidate(s)")
    print(f"Persisted: {report_path}")
    print()

    life = LifeManager(start_generation=4)
    life.bootstrap_origin_story()
    life.set_current_mission("Cross-regime validation — knowledge candidate robustness")
    if not life.timeline.has_title("Cross-Regime Validation"):
        life.record_event(
            "milestone",
            "Cross-Regime Validation",
            "Phase IV D6 — knowledge candidates validated across regimes and horizons.",
            milestone_importance=7,
        )
    life.record_event(
        "validation",
        "Phase IV D6 Cross-Validation",
        (
            f"Analyzed {report.candidates_analyzed} candidates; "
            f"most_robust={report.most_robust_candidate_id}. Research only."
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
    run_cross_validation_demo()


if __name__ == "__main__":
    main()
