"""
TAE Phase V Sprint A3 — Knowledge Integration Layer

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Bridges research knowledge to human-review strategy recommendations.
Does not modify live bot, config, portfolio, or execution logic.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.integration import (
    DEFAULT_RECOMMENDATIONS_PATH,
    ImplementationStatus,
    KnowledgeIntegrator,
    RecommendationType,
)

SUMMARY_TXT = "tae_phase5_knowledge_integration_summary.txt"

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("portfolio.csv"),
    Path("config/settings.py"),
    Path("dashboard_v2.py"),
]


def _snapshot_mtimes(paths: list[Path]) -> dict[str, float]:
    out: dict[str, float] = {}
    for path in paths:
        if path.is_file():
            out[str(path)] = path.stat().st_mtime
    return out


def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
    for key, mtime in before.items():
        if key not in after or after[key] != mtime:
            return False
    return True


def run_integration_demo() -> None:
    print("===== TAE PHASE V SPRINT A3 — KNOWLEDGE INTEGRATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Research-to-human-review bridge — not trading signals or execution.")
    print("No broker. No live bot changes. Human approval required.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    integrator = KnowledgeIntegrator()
    result = integrator.integrate()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    report = result.format_report()
    print(report)

    print("===== INTEGRATION SUMMARY =====")
    print(f"Candidates analyzed: {result.candidates_analyzed}")
    print(f"Recommendations generated (this run): {result.recommendations_generated}")
    print(f"Duplicates skipped (this run): {result.recommendations_skipped_duplicate}")
    print(f"Total recommendations persisted: {len(result.recommendations)}")
    if result.highest_confidence:
        hc = result.highest_confidence
        print(
            f"Highest-confidence: {hc.recommendation_id} "
            f"({hc.recommendation_type.value}, confidence={hc.confidence:.1f})"
        )
    blocked = [
        r for r in result.recommendations
        if r.recommendation_type in (
            RecommendationType.BLOCK_FROM_TRADING,
            RecommendationType.REQUIRE_MORE_VALIDATION,
        )
    ]
    print(f"Blocked / needs validation: {len(blocked)}")
    for rec in blocked:
        print(f"  - {rec.recommendation_id}: {rec.recommendation_type.value}")

    all_human = all(r.human_approval_required for r in result.recommendations)
    all_not_impl = all(
        r.implementation_status == ImplementationStatus.NOT_IMPLEMENTED
        for r in result.recommendations
    )
    print(f"human_approval_required on all: {all_human}")
    print(f"implementation_status NOT_IMPLEMENTED on all: {all_not_impl}")
    print(f"Output saved: {DEFAULT_RECOMMENDATIONS_PATH}")
    print(f"Live trading files unchanged: {live_files_ok}")
    if not live_files_ok:
        print("  WARNING: protected file mtimes changed — investigate.")
    else:
        print("  Confirmed: live_bot.py, portfolio.csv, config/settings.py, dashboard_v2.py untouched.")
    print()

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(report + "\n", encoding="utf-8")
    print(f"Saved: {summary_path}")


def main() -> None:
    run_integration_demo()


if __name__ == "__main__":
    main()
