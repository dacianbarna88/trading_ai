"""
TAE Phase V Sprint A5 — Governance & Daily Intelligence

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Executive daily report summarizing the entire TAE ecosystem.
Read-only — no live bot, config, portfolio, or strategy changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.governance import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    DailyIntelligenceCollector,
)

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


def run_daily_intelligence_demo() -> None:
    print("===== TAE PHASE V SPRINT A5 — DAILY INTELLIGENCE =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Executive governance report — read-only aggregation.")
    print("No broker. No execution. No live bot or config changes.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    collector = DailyIntelligenceCollector()
    report = collector.generate_and_persist()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    text_report = report.format_text()
    print(text_report)

    print("===== OUTPUT =====")
    print(f"JSON saved: {DEFAULT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_TXT_PATH}")
    print(f"Report date: {report.report_date}")
    print(f"Executive summary lines: {len(report.executive_summary)}")
    print(f"Critical issues: {len(report.critical_issues)}")
    print(f"Live trading files unchanged: {live_files_ok}")
    if live_files_ok:
        print("  Confirmed: live_bot.py, portfolio.csv, config/settings.py, dashboard_v2.py untouched.")
    print()


def main() -> None:
    run_daily_intelligence_demo()


if __name__ == "__main__":
    main()
