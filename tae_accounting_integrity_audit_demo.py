"""
TAE Accounting Integrity Auditor V1

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only audit of portfolio.csv accounting consistency.
"""

from __future__ import annotations

from pathlib import Path

from research_core.performance.accounting_integrity_auditor import (
    ANALYSIS_SAFETY_BANNER,
    DEFAULT_INTEGRITY_JSON_PATH,
    DEFAULT_INTEGRITY_TXT_PATH,
    AccountingIntegrityAuditor,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("portfolio.csv"),
    Path("config/settings.py"),
    Path("dashboard_v2.py"),
    Path("core/trades.py"),
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


def run_accounting_integrity_audit_demo() -> None:
    print("===== TRADING AI — ACCOUNTING INTEGRITY AUDITOR V1 =====")
    print(ANALYSIS_SAFETY_BANNER)
    print("Read-only accounting audit — no portfolio or strategy changes.")
    print("No broker. No execution. No automatic fixes.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    auditor = AccountingIntegrityAuditor()
    report = auditor.audit()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== INTEGRITY AUDIT SUMMARY =====")
    print(f"SELLs audited: {report.sells_audited}")
    print(f"Anomalies found: {report.anomalies_found}")
    print(f"  HIGH: {report.high_severity_count}")
    print(f"  MEDIUM: {report.medium_severity_count}")
    print(f"  LOW: {report.low_severity_count}")
    print(f"Stale snapshot: {report.stale_snapshot_detected}")
    print(f"Focus tickers audited: {len(report.focus_ticker_audits)}")
    print(f"Recommendations (NOT_IMPLEMENTED): {len(report.recommendations)}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/trades.py untouched."
        )
    print(f"JSON saved: {DEFAULT_INTEGRITY_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_INTEGRITY_TXT_PATH}")
    print()


def main() -> None:
    run_accounting_integrity_audit_demo()


if __name__ == "__main__":
    main()
