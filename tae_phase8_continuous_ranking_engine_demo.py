"""
TAE Phase VIII B3 — Continuous Strategy Ranking Engine Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only strategy ranking — no strategy or portfolio changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER
from research_core.strategy_evolution.continuous_ranking_engine import (
    ContinuousStrategyRankingEngine,
)
from research_core.strategy_evolution.continuous_ranking_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    ContinuousStrategyRankingReportStore,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
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


def run_continuous_ranking_engine_demo() -> None:
    print("===== TAE PHASE VIII B3 — CONTINUOUS STRATEGY RANKING ENGINE =====")
    print(SAFETY_BANNER)
    print("Read-only strategy ranking — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    engine = ContinuousStrategyRankingEngine()
    report = engine.rank()

    store = ContinuousStrategyRankingReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== RANKING SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Strategies ranked: {len(report.rankings)}")
    for entry in sorted(report.rankings, key=lambda x: x.rank):
        print(
            f"  #{entry.rank} {entry.candidate_id:32s} "
            f"score={entry.ranking_score:.4f} "
            f"{entry.decision.value}"
        )
    print()
    print(f"Protected files unchanged: {protected_ok}")
    if protected_ok:
        print(
            "  Confirmed: live_bot.py, dashboard_v2.py, config/settings.py, "
            "portfolio.csv, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_continuous_ranking_engine_demo()


if __name__ == "__main__":
    main()
