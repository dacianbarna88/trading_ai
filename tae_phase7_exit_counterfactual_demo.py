"""
TAE Phase VII A2 — Exit Decision Counterfactual Analyzer

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only counterfactual analysis of SELL decisions — no strategy or portfolio changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.exit_analysis import (
    CounterfactualExitAnalyzer,
    ExitAnalysisReportStore,
    SAFETY_BANNER,
)
from research_core.exit_analysis.exit_analysis_report import (
    DEFAULT_EXIT_JSON_PATH,
    DEFAULT_EXIT_TXT_PATH,
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


def run_exit_counterfactual_demo() -> None:
    print("===== TAE PHASE VII A2 — EXIT COUNTERFACTUAL ANALYZER =====")
    print(SAFETY_BANNER)
    print("Read-only counterfactual exit analysis — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    analyzer = CounterfactualExitAnalyzer()
    report = analyzer.analyze()

    store = ExitAnalysisReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    primary = next(
        (h for h in report.horizon_aggregates if h.horizon_days == report.primary_horizon_days),
        None,
    )
    print("===== COUNTERFACTUAL SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"SELL-uri analizate: {report.sells_analyzed}")
    print(f"Cu date preț: {report.sells_with_price_data}")
    if primary:
        print(f"Total extra profit (+{primary.horizon_days}d): ${primary.total_extra_profit:,.2f}")
        print(f"Medie extra return (+{primary.horizon_days}d): {primary.avg_extra_return_pct:+.4f}%")
        print(f"Median extra return (+{primary.horizon_days}d): {primary.median_extra_return_pct:+.4f}%")
        print(f"% îmbunătățit dacă așteptat: {primary.pct_improved:.1f}%")
        print(f"% mai rău dacă așteptat: {primary.pct_worse:.1f}%")
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
    print(f"JSON saved: {DEFAULT_EXIT_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_EXIT_TXT_PATH}")
    print()
    print(report.verdict.value)


def main() -> None:
    run_exit_counterfactual_demo()


if __name__ == "__main__":
    main()
