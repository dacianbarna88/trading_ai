"""
TAE Phase VI Sprint B4 — Research Confidence Recalibration

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Recalibrates TAE confidence after accounting integrity fix — read-only analysis.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.recalibration import (
    DEFAULT_RECALIBRATION_JSON_PATH,
    DEFAULT_RECALIBRATION_TXT_PATH,
    ConfidenceRecalibrator,
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


def run_confidence_recalibration_demo() -> None:
    print("===== TAE PHASE VI SPRINT B4 — CONFIDENCE RECALIBRATION =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Read-only recalibration — no strategy, portfolio, or trading changes.")
    print("No broker. No execution. No patch apply.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    recalibrator = ConfidenceRecalibrator()
    report = recalibrator.recalibrate()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    print(report.format_summary())

    eco = report.ecosystem
    ac = report.accounting_comparison
    print("===== RECALIBRATION DEMO SUMMARY =====")
    print(f"Sources loaded: {sum(report.sources_loaded.values())}/{len(report.sources_loaded)}")
    print(f"Candidates recalibrated: {len(report.candidates)}")
    print(f"Legacy realized PnL: {ac.legacy_realized_pnl:,.2f}")
    print(f"Corrected realized PnL: {ac.corrected_realized_pnl:,.2f}")
    print(f"PnL delta: {ac.realized_pnl_delta:+,.2f}")
    print(f"Legacy HIGH anomalies: {ac.legacy_high_severity_anomalies}")
    print(f"Corrected HIGH anomalies: {ac.corrected_high_severity_anomalies}")
    print(f"Conclusions affected by accounting: {ac.conclusions_affected}")
    print()
    print(f"Average confidence: {eco.average_old_confidence:.2f} → "
          f"{eco.average_recalibrated_confidence:.2f} "
          f"(delta {eco.average_confidence_delta:+.2f})")
    print(f"Ranking changed: {eco.ranking_changed}")
    print(f"Top candidate before: {eco.top_candidate_before}")
    print(f"Top candidate after: {eco.top_candidate_after}")
    print(f"kn_d5_00002 remains top: {eco.top_candidate_unchanged and eco.top_candidate_after == 'kn_d5_00002'}")
    print()
    print("Per-candidate recalibration:")
    for cand in sorted(report.candidates, key=lambda c: c.rank_after):
        print(
            f"  {cand.candidate_id} | rank {cand.rank_before}→{cand.rank_after} | "
            f"conf {cand.old_confidence:.1f}→{cand.recalibrated_confidence:.1f} "
            f"({cand.confidence_stability.value}) | "
            f"readiness={cand.recalibrated_readiness} | "
            f"requires_review={cand.requires_review}"
        )
    print()
    print(f"All implementation NOT_READY: {eco.all_implementation_not_ready}")
    print(f"Europe/UK gaps block all: {all(c.validation_gaps_remain for c in report.candidates)}")
    print(f"Recommendations REQUIRE_REVIEW: {eco.recommendations_requiring_review}")
    print(f"Patches still blocked: {eco.patches_still_blocked}")
    print(f"Evolution plans gated: {eco.evolution_plans_still_gated}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, dashboard_v2.py, config/settings.py, "
            "portfolio.csv, core/trades.py, core/portfolio_prices.py untouched."
        )
    print(f"JSON saved: {DEFAULT_RECALIBRATION_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_RECALIBRATION_TXT_PATH}")
    print()


def main() -> None:
    run_confidence_recalibration_demo()


if __name__ == "__main__":
    main()
