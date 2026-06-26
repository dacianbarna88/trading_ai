"""
TAE Phase VII — Continuous Strategy Simulation Lab Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only strategy comparison using portfolio.csv — no live changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.simulation_lab import (
    SAFETY_BANNER,
    SimulationLabReportStore,
    StrategySimulationLab,
)
from research_core.simulation_lab.simulation_lab_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
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


def run_simulation_lab_demo() -> None:
    print("===== TAE PHASE VII — CONTINUOUS STRATEGY SIMULATION LAB =====")
    print(SAFETY_BANNER)
    print("Read-only strategy simulation — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    lab = StrategySimulationLab()
    report = lab.run()

    store = SimulationLabReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== SIMULATION LAB SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Baseline PnL: ${report.baseline_total_pnl:,.2f}")
    print(f"Best by total PnL: {report.best_strategy_by_total_pnl}")
    print(f"Best by profit factor: {report.best_strategy_by_profit_factor}")
    print()
    for strategy in report.strategies:
        print(
            f"  {strategy.strategy_id:32s} "
            f"trades={strategy.trades:2d} "
            f"PnL=${strategy.total_pnl:>8,.2f} "
            f"PF={strategy.profit_factor:.4f}"
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
    run_simulation_lab_demo()


if __name__ == "__main__":
    main()
