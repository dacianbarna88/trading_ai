"""
TAE Phase VI Sprint B5 — Regional Validation Gap Closure (kn_d5_00002)

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Attempts Europe/UK regional validation using existing project data.
Reports NOT_AVAILABLE when hypothesis-linked CSVs are missing — no estimation.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.regional_validation import (
    DEFAULT_REGIONAL_JSON_PATH,
    DEFAULT_REGIONAL_TXT_PATH,
    RegionalGapClosureAnalyzer,
    TARGET_CANDIDATE_ID,
)
from research_core.regional_validation.regional_validation_report import ReadinessProjection

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


def run_regional_validation_demo() -> None:
    print("===== TAE PHASE VI SPRINT B5 — REGIONAL VALIDATION GAP CLOSURE =====")
    print(RESEARCH_SAFETY_BANNER)
    print(f"Focus candidate: {TARGET_CANDIDATE_ID}")
    print("Read-only regional validation — no strategy, portfolio, or trading changes.")
    print("No broker. No execution. No patch apply. No estimation of missing data.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    analyzer = RegionalGapClosureAnalyzer()
    report = analyzer.analyze()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_summary())

    print("===== REGIONAL VALIDATION DEMO SUMMARY =====")
    print(f"Candidate analyzed: {report.candidate_id}")
    print(f"Hypothesis: {report.source_hypothesis_id}")
    print()
    print("Regional datasets found:")
    hypothesis_linked = [
        d for d in report.datasets_found if d.kind.value == "HYPOTHESIS_LINKED"
    ]
    reference = [
        d for d in report.datasets_found if d.kind.value == "REFERENCE_ONLY"
    ]
    if hypothesis_linked:
        for ds in hypothesis_linked:
            print(f"  • {ds.path} [{ds.region}] rows={ds.row_count}")
    else:
        print("  (none — no hypothesis-linked Europe/UK ensemble CSV)")
    if reference:
        print("Reference/context datasets:")
        for ds in reference:
            print(f"  • {ds.path} — {ds.notes}")
    print()
    print("Regional datasets missing:")
    seen_paths: set[str] = set()
    for ds in report.datasets_missing:
        if ds.path in seen_paths:
            continue
        seen_paths.add(ds.path)
        print(f"  • {ds.path} [{ds.region}]")
    print()
    print(f"Validations completed: {report.validations_completed}")
    print(f"Validations NOT_AVAILABLE: {report.validations_not_available}")
    print()
    print("Slice status:")
    for sl in report.slice_results:
        print(f"  {sl.slice_id}: {sl.status}")
    print()
    can_advance = report.readiness_projection != ReadinessProjection.NOT_READY
    print(
        f"Readiness can move toward READY_FOR_SANDBOX_REVIEW: "
        f"{'YES' if can_advance else 'NO'}"
    )
    print(f"Projection: {report.readiness_projection.value}")
    print(f"Rationale: {report.readiness_rationale}")
    print()
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, dashboard_v2.py, config/settings.py, "
            "portfolio.csv, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_REGIONAL_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_REGIONAL_TXT_PATH}")
    print()


def main() -> None:
    run_regional_validation_demo()


if __name__ == "__main__":
    main()
