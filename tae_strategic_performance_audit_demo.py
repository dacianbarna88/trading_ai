"""
TAE Strategic Performance Auditor V1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only portfolio performance audit — no execution or strategy changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.performance import (
    ANALYSIS_SAFETY_BANNER,
    DEFAULT_AUDIT_JSON_PATH,
    DEFAULT_AUDIT_TXT_PATH,
    StrategicPerformanceAuditor,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("portfolio.csv"),
    Path("config/settings.py"),
    Path("dashboard_v2.py"),
    Path("core/entry_filter.py"),
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


def run_strategic_performance_audit_demo() -> None:
    print("===== TRADING AI — STRATEGIC PERFORMANCE AUDITOR V1 =====")
    print(ANALYSIS_SAFETY_BANNER)
    print("Read-only analysis — no strategy or trading changes.")
    print("No broker. No execution. No automatic fixes.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    auditor = StrategicPerformanceAuditor()
    audit = auditor.audit()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(audit.format_text())

    print("===== AUDIT SUMMARY =====")
    print(f"Candidates/open positions: {audit.portfolio_activity.open_positions}")
    print(f"Total gaps/anomalies: {len(audit.anomalies)}")
    print(f"Last 2 days realized PnL: {audit.performance.last_2_days_realized_pnl:,.2f}")
    print(f"Root cause hypotheses: {len(audit.root_cause_hypotheses)}")
    print(f"Recommendations: {len(audit.recommendations)}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/entry_filter.py untouched."
        )
    print(f"JSON saved: {DEFAULT_AUDIT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_AUDIT_TXT_PATH}")
    print()


def main() -> None:
    run_strategic_performance_audit_demo()


if __name__ == "__main__":
    main()
