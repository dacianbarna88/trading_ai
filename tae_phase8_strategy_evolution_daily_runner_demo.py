"""
TAE Phase VIII B6 — Strategy Evolution Daily Runner Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Runs the full Strategy Evolution pipeline — no trade execution.
"""

from __future__ import annotations

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER
from research_core.strategy_evolution.daily_runner import StrategyEvolutionDailyRunner
from research_core.strategy_evolution.daily_runner_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    DailyRunnerReportStore,
)


def run_strategy_evolution_daily_runner_demo() -> None:
    print("===== TAE PHASE VIII B6 — STRATEGY EVOLUTION DAILY RUNNER =====")
    print(SAFETY_BANNER)
    print("Full Strategy Evolution pipeline — read-only, no execution.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    runner = StrategyEvolutionDailyRunner()
    report = runner.run()

    store = DailyRunnerReportStore()
    store.persist(report)
    store.persist_txt(report)

    print(report.format_text())

    print("===== DAILY RUNNER SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Steps succeeded: {sum(1 for s in report.steps if s.succeeded)}/{len(report.steps)}")
    print(f"Top ranked: {report.top_ranked_strategy_id or 'N/A'}")
    print(f"Review candidate: {report.promotion_review_candidate_id or 'None'}")
    print(f"Protected files unchanged: {report.protected_files_unchanged}")
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_strategy_evolution_daily_runner_demo()


if __name__ == "__main__":
    main()
