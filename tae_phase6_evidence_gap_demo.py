"""
TAE Phase VI Sprint B3 — Evidence Gap Analyzer

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Transforms evidence history into a research roadmap — planning only.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evidence_gap import (
    DEFAULT_GAP_JSON_PATH,
    DEFAULT_GAP_TXT_PATH,
    EvidenceGapAnalyzer,
)

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("portfolio.csv"),
    Path("config/settings.py"),
    Path("dashboard_v2.py"),
    Path("core/entry_filter.py"),
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


def run_evidence_gap_demo() -> None:
    print("===== TAE PHASE VI SPRINT B3 — EVIDENCE GAP ANALYZER =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Research roadmap only — no strategy or trading changes.")
    print("No broker. No execution. No patch apply.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    analyzer = EvidenceGapAnalyzer()
    report = analyzer.analyze()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    text = report.format_text()
    print(text)

    print("===== GAP ANALYZER SUMMARY =====")
    print(f"Candidates analyzed: {report.candidates_analyzed}")
    print(f"Total gaps: {report.total_gaps}")
    print(f"Gaps created (this run): {report.gaps_created}")
    print(f"Gaps updated (this run): {report.gaps_updated}")
    print(
        f"Highest information gain: {report.highest_information_gain_candidate_id} "
        f"({report.highest_information_gain:.1f})"
    )
    print(
        f"Most blocked candidate: {report.most_blocked_candidate_id} "
        f"({report.most_blocked_gap_count} gaps)"
    )
    print(f"Easiest candidate to unblock: {report.easiest_unblock_candidate_id}")
    print(
        f"Candidates potentially ready after gap closure: "
        f"{report.candidates_ready_after_closure}"
    )
    print("Recommended research order:")
    for idx, cid in enumerate(report.recommended_research_order, start=1):
        print(f"  {idx}. {cid}")

    all_impl_blocked = all(not a.implementation_allowed for a in report.analyses)
    print(f"All implementation_allowed=False: {all_impl_blocked}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/entry_filter.py untouched."
        )
    print(f"JSON saved: {DEFAULT_GAP_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_GAP_TXT_PATH}")
    print()


def main() -> None:
    run_evidence_gap_demo()


if __name__ == "__main__":
    main()
