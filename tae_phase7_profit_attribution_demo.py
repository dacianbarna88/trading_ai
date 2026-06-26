"""
TAE Phase VII A1 — Profit Attribution Engine

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only mathematical explanation of net profit (~+$330) despite many trades.
"""

from __future__ import annotations

from pathlib import Path

from research_core.profit_attribution import (
    DEFAULT_ATTRIBUTION_JSON_PATH,
    DEFAULT_ATTRIBUTION_TXT_PATH,
    ProfitAttributionEngine,
    SAFETY_BANNER,
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


def run_profit_attribution_demo() -> None:
    print("===== TAE PHASE VII A1 — PROFIT ATTRIBUTION ENGINE =====")
    print(SAFETY_BANNER)
    print("Read-only profit attribution — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    engine = ProfitAttributionEngine()
    report = engine.analyze()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    c = report.core
    print("===== ATTRIBUTION SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Gross profit:        ${c.gross_profit:,.2f}")
    print(f"Gross loss:            ${abs(c.gross_loss):,.2f}")
    print(f"Net realized:          ${c.net_realized_profit:,.2f}")
    print(f"Open unrealized:       ${c.open_unrealized_pnl:,.2f}")
    print(f"Total PnL:             ${c.total_pnl:,.2f}")
    print(f"Win rate:              {c.win_rate:.2f}%")
    print(f"Profit factor:         {c.profit_factor:.4f}")
    print(f"Expectancy/trade:      ${c.expectancy_per_trade:,.2f}")
    print(f"Closed SELL count:     {c.closed_trade_count}")
    print()
    print("Top 3 explanation bullets:")
    for bullet in report.mathematical_explanation[:3]:
        print(f"  • {bullet}")
    print()
    print(f"Protected files unchanged: {protected_ok}")
    if protected_ok:
        print(
            "  Confirmed: live_bot.py, dashboard_v2.py, config/settings.py, "
            "portfolio.csv, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_ATTRIBUTION_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_ATTRIBUTION_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_profit_attribution_demo()


if __name__ == "__main__":
    main()
