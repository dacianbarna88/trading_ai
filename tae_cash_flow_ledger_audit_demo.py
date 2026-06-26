"""
TAE Cash Flow Ledger Audit — Phase VI Sprint B5

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only reconstruction of the Trading AI account from transaction #1 to latest.
"""

from __future__ import annotations

from pathlib import Path

from research_core.accounting import (
    ANALYSIS_SAFETY_BANNER,
    DEFAULT_LEDGER_JSON_PATH,
    DEFAULT_LEDGER_TXT_PATH,
    CashFlowLedgerAuditor,
    RECONCILIATION_FORMULA,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("portfolio.csv"),
    Path("config/settings.py"),
    Path("dashboard_v2.py"),
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


def run_cash_flow_ledger_audit_demo() -> None:
    print("===== TAE CASH FLOW LEDGER AUDIT — PHASE VI B5 =====")
    print(ANALYSIS_SAFETY_BANNER)
    print("Read-only accounting audit — no portfolio or strategy changes.")
    print("No broker. No execution. No automatic fixes.")
    print()
    print(f"Reconciliation formula:")
    print(f"  {RECONCILIATION_FORMULA}")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    auditor = CashFlowLedgerAuditor()
    report = auditor.audit()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== LEDGER AUDIT SUMMARY =====")
    s = report.summary
    print(f"Ledger status: {report.status.value}")
    print(f"Starting Capital: ${s.starting_capital:,.2f}")
    print(f"Deposits: ${s.deposits:,.2f}")
    print(f"Withdrawals: ${s.withdrawals:,.2f}")
    print(f"Realized PnL (all SELLs): ${s.realized_pnl_all_sells:,.2f}")
    print(f"Realized PnL (repairable): ${s.realized_pnl_repairable:,.2f}")
    print(f"Open Unrealized PnL: ${s.open_unrealized_pnl:,.2f}")
    print(f"Total PnL: ${s.total_pnl:,.2f}")
    print(f"Current Cash: ${s.current_cash:,.2f}")
    print(f"Open Market Value: ${s.open_market_value:,.2f}")
    print(f"Final Account Value: ${s.final_account_value:,.2f}")
    print(f"Formula Account Value: ${s.formula_account_value:,.2f}")
    print(f"Reconciliation Difference: ${s.reconciliation_difference:,.2f}")
    print(f"Transactions: {s.transaction_count} (BUY {s.buy_count} / SELL {s.sell_count})")
    print(f"Open positions ({s.open_position_count}): {', '.join(s.open_tickers) or '—'}")
    print()

    failed = [c for c in report.checks if not c.passed and c.severity.value == "ERROR"]
    warnings = [c for c in report.checks if not c.passed and c.severity.value == "WARNING"]
    print(f"Extra checks: {len(failed)} error(s), {len(warnings)} warning(s)")
    if report.first_error:
        fe = report.first_error
        print(
            f"First error: #{fe.index} {fe.timestamp} {fe.ticker} {fe.action} "
            f"— {fe.reason}"
        )
    print()

    print("===== CROSS-CHECKS =====")
    for cc in report.cross_checks:
        if cc.available:
            parts = [f"[{cc.source}]"]
            if cc.account_value is not None:
                parts.append(f"account=${cc.account_value:,.2f}")
            if cc.realized_pnl is not None:
                parts.append(f"realized=${cc.realized_pnl:,.2f}")
            if cc.open_pnl is not None:
                parts.append(f"open=${cc.open_pnl:,.2f}")
            if cc.delta_vs_ledger is not None:
                parts.append(f"delta=${cc.delta_vs_ledger:,.2f}")
            parts.append(cc.notes)
            print("  " + " | ".join(parts))
        else:
            print(f"  [{cc.source}] not available — {cc.notes}")
    print()

    if report.backup_files_found:
        print(f"Portfolio backups found (read-only): {len(report.backup_files_found)}")
        for path in report.backup_files_found:
            print(f"  {path}")
        print()

    print(f"Protected files unchanged: {protected_ok}")
    if protected_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_LEDGER_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_LEDGER_TXT_PATH}")
    print()
    print(f"Ledger {report.status.value}")


def main() -> None:
    run_cash_flow_ledger_audit_demo()


if __name__ == "__main__":
    main()
