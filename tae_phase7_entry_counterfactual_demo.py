"""
TAE Phase VII A3 — Entry Decision Counterfactual Analyzer

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only counterfactual analysis of BUY decisions — no strategy or portfolio changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.entry_analysis import (
    CounterfactualEntryAnalyzer,
    EntryAnalysisReportStore,
    SAFETY_BANNER,
)
from research_core.entry_analysis.entry_analysis_report import (
    DEFAULT_ENTRY_JSON_PATH,
    DEFAULT_ENTRY_TXT_PATH,
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


def run_entry_counterfactual_demo() -> None:
    print("===== TAE PHASE VII A3 — ENTRY COUNTERFACTUAL ANALYZER =====")
    print(SAFETY_BANNER)
    print("Read-only counterfactual entry analysis — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    analyzer = CounterfactualEntryAnalyzer()
    report = analyzer.analyze()

    store = EntryAnalysisReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    b = report.baseline
    print("===== COUNTERFACTUAL SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"BUY-uri analizate: {b.buy_count}")
    print(f"Baseline total PnL: ${b.total_pnl:,.2f}")
    print(f"  Realized: ${b.realized_pnl:,.2f} | Open: ${b.open_pnl:,.2f}")
    print(f"Win rate: {b.win_rate:.1f}% | Profit factor: {b.profit_factor:.4f}")
    print(f"Best scenario: {report.best_scenario_id}")
    print(f"Worst scenario: {report.worst_scenario_id}")
    refs = report.external_refs
    if refs.profit_attribution_total_pnl is not None:
        print(
            f"Attribution reference: ${refs.profit_attribution_total_pnl:,.2f} "
            f"(delta ${refs.baseline_delta_vs_attribution:+,.2f})"
        )
    print()
    print("Recomandări (NOT_IMPLEMENTED):")
    for rec in report.recommendations:
        print(f"  [{rec.risk_level.value}] {rec.title} — {rec.implementation_status}")
    print()
    print(f"Protected files unchanged: {protected_ok}")
    if protected_ok:
        print(
            "  Confirmed: live_bot.py, dashboard_v2.py, config/settings.py, "
            "portfolio.csv, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_ENTRY_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_ENTRY_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_entry_counterfactual_demo()


if __name__ == "__main__":
    main()
