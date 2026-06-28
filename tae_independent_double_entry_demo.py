"""
TAE Independent Double-Entry Verification — Phase VI Sprint B6

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Standalone FIFO verifier — no reuse of existing accounting helpers for calculation.
"""

from __future__ import annotations

from pathlib import Path

from research_core.accounting.independent_double_entry import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    SAFETY_BANNER,
    IndependentDoubleEntryVerifier,
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


def run_independent_double_entry_demo() -> None:
    print("===== TAE INDEPENDENT DOUBLE-ENTRY VERIFICATION — PHASE VI B6 =====")
    print(SAFETY_BANNER)
    print("Verificare contabilă independentă — fără reutilizare helpers existenți.")
    print("No broker. No execution. No portfolio modifications.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    verifier = IndependentDoubleEntryVerifier()
    result = verifier.verify()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(result.format_text())

    print("===== REZUMAT DEMO =====")
    print(f"Verdict: {result.verdict.value}")
    print(f"Cash independent:           ${result.independent_cash:,.2f}")
    print(f"PnL realizat (FIFO):        ${result.independent_realized_pnl:,.2f}")
    print(f"Valoare piață deschisă:     ${result.independent_open_market_value:,.2f}")
    print(f"PnL nerealizat deschis:     ${result.independent_open_unrealized_pnl:,.2f}")
    print(f"Valoare cont independentă:  ${result.independent_account_value:,.2f}")
    print(f"PnL total:                  ${result.independent_total_pnl:,.2f}")
    print(f"Delta reconciliere internă: ${result.internal_reconciliation_delta:,.2f}")
    if result.existing_ledger_account_value is not None:
        print(
            f"Ledger B5:                  ${result.existing_ledger_account_value:,.2f} "
            f"(delta ${result.delta_vs_existing_ledger:,.2f})"
        )
    if result.dashboard_account_value is not None:
        print(
            f"Dashboard:                  ${result.dashboard_account_value:,.2f} "
            f"(delta ${result.delta_vs_dashboard_expected:,.2f})"
        )
    print(f"Poziții deschise:           {len(result.open_positions)}")
    print(f"SELL-uri procesate:         {result.closed_trades_count}")
    if result.first_mismatch:
        m = result.first_mismatch
        print(f"Prima neconcordanță:        #{m.row_num} {m.timestamp} {m.ticker} — {m.reason}")
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
    print(result.verdict.value)


def main() -> None:
    run_independent_double_entry_demo()


if __name__ == "__main__":
    main()
