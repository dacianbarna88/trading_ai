"""
TAE Phase VIII B2 — Parallel Paper Validator Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only parallel paper validation — no strategy or portfolio changes.
"""

from __future__ import annotations

from pathlib import Path

from research_core.strategy_evolution.candidate_report import SAFETY_BANNER
from research_core.strategy_evolution.parallel_paper_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    ParallelPaperValidationReportStore,
)
from research_core.strategy_evolution.parallel_paper_validator import ParallelPaperValidator

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


def run_parallel_paper_validator_demo() -> None:
    print("===== TAE PHASE VIII B2 — PARALLEL PAPER VALIDATOR =====")
    print(SAFETY_BANNER)
    print("Read-only parallel validation — no strategy or portfolio changes.")
    print("No broker. No execution. No BUY/SELL instructions.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    validator = ParallelPaperValidator()
    report = validator.validate()

    store = ParallelPaperValidationReportStore()
    store.persist(report)
    store.persist_txt(report)

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    protected_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_text())

    print("===== VALIDATION SUMMARY =====")
    print(f"Verdict: {report.verdict.value}")
    print(f"Candidates validated: {len(report.validations)}")
    for result in report.validations:
        print(
            f"  {result.candidate_id:32s} "
            f"{result.validation_status.value:26s} "
            f"PnL=${result.total_pnl:>8,.2f} trades={result.trades}"
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
    run_parallel_paper_validator_demo()


if __name__ == "__main__":
    main()
