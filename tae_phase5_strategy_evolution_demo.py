"""
TAE Phase V Sprint A4 — Strategy Evolution Manager

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Converts eligible strategy recommendations into auditable evolution plans.
Does not modify live bot, config, portfolio, or execution logic.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evolution import (
    DEFAULT_EVOLUTION_NOTICE_PATH,
    DEFAULT_EVOLUTION_PLAN_PATH,
    EvolutionPlanResult,
    ImplementationStatus,
    ProposedChangeType,
    StrategyEvolutionManager,
)

SUMMARY_TXT = "tae_phase5_strategy_evolution_summary.txt"

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


def run_evolution_demo() -> EvolutionPlanResult:
    print("===== TAE PHASE V SPRINT A4 — STRATEGY EVOLUTION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Evolution plans for human review — not live config or execution.")
    print("No broker. No live bot changes. Human approval required.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    manager = StrategyEvolutionManager()
    result = manager.generate_plans()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    report = result.format_report()
    print(report)

    notice = result.format_human_notice(live_files_unchanged=live_files_ok)
    notice_path = result.write_human_notice(live_files_unchanged=live_files_ok)

    print("===== HUMAN REVIEW NOTICE =====")
    print(notice)

    print("===== EVOLUTION SUMMARY =====")
    print(f"Recommendations loaded: {result.recommendations_loaded}")
    print(f"Plans generated (this run): {result.plans_generated}")
    print(f"Duplicates skipped (this run): {result.plans_skipped_duplicate}")
    print(f"Total plans persisted: {len(result.plans)}")
    print(
        f"Blocked recommendations (BLOCK_FROM_TRADING): {result.recommendations_blocked}"
    )
    print(
        f"Plans requiring validation gate: {len(result.validation_gated_plans)}"
    )
    if result.highest_confidence_plan:
        hc = result.highest_confidence_plan
        print(
            f"Highest-confidence plan: {hc.plan_id} "
            f"({hc.proposed_change_type.value}, confidence={hc.confidence:.1f})"
        )
    print(f"Files protected / unchanged: {live_files_ok}")
    if live_files_ok:
        print("  Confirmed: live_bot.py, portfolio.csv, config/settings.py, dashboard_v2.py untouched.")
    else:
        print("  WARNING: protected file mtimes changed — investigate.")

    all_human = all(p.human_approval_required for p in result.plans)
    all_not_impl = all(
        p.implementation_status == ImplementationStatus.NOT_IMPLEMENTED
        for p in result.plans
    )
    print(f"human_approval_required on all: {all_human}")
    print(f"implementation_status NOT_IMPLEMENTED on all: {all_not_impl}")
    print(f"Output saved: {DEFAULT_EVOLUTION_PLAN_PATH}")
    print(f"Notice saved: {notice_path}")
    print()

    summary_path = Path(SUMMARY_TXT)
    summary_path.write_text(report + "\n", encoding="utf-8")
    print(f"Saved: {summary_path}")

    return result


def main() -> None:
    run_evolution_demo()


if __name__ == "__main__":
    main()
