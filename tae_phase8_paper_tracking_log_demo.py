"""
TAE Phase VIII B5 — Paper Tracking Log Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only paper tracking log — no trade execution or strategy changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER
from research_core.strategy_evolution.paper_tracking_log import PaperTrackingLog
from research_core.strategy_evolution.paper_tracking_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    PaperTrackingLogReportStore,
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


def run_paper_tracking_log_demo() -> None:
    print("===== TAE PHASE VIII B5 — PAPER TRACKING LOG =====")
    print(SAFETY_BANNER)
    print("Read-only paper tracking log — no trade execution or strategy changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    log = PaperTrackingLog()
    report = log.build()

    store = PaperTrackingLogReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== TRACKING SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    for entry in report.entries:
        print(
            f"  {entry.candidate_id:32s} "
            f"{entry.tracking_status.value:20s} "
            f"trades={entry.current_trades} need={entry.trades_needed}"
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
    run_paper_tracking_log_demo()


if __name__ == "__main__":
    main()
