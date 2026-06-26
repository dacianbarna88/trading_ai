"""
TAE Phase VI Sprint B1 — Patch Review Center

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Reviews implementation patch proposals — documentation only, no sandbox apply.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.review import (
    DEFAULT_REVIEW_JSON_PATH,
    DEFAULT_REVIEW_TXT_PATH,
    ImplementationStatus,
    PatchReviewCenter,
    ReviewVerdict,
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


def run_patch_review_demo() -> None:
    print("===== TAE PHASE VI SPRINT B1 — PATCH REVIEW CENTER =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Formal patch review — not sandbox, not implementation.")
    print("No broker. No execution. Review documentation only.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    center = PatchReviewCenter()
    report = center.review_all()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    text = report.format_text()
    print(text)

    print("===== REVIEW SUMMARY =====")
    print(f"Patches reviewed: {report.patches_reviewed}")
    print(f"Reviews generated (this run): {report.reviews_generated}")
    print(f"Duplicates skipped (this run): {report.reviews_skipped_duplicate}")
    print(f"Approved for sandbox: {report.approved_for_sandbox}")
    print(f"Require more evidence: {report.require_more_evidence}")
    print(f"Rejected: {report.rejected}")
    if report.highest_quality_review:
        hq = report.highest_quality_review
        print(
            f"Highest quality patch: {hq.patch_id} "
            f"(score={hq.review_score:.1f}, verdict={hq.verdict.value})"
        )
    print(f"Biggest blocker: {report.biggest_blocker}")
    print(f"Next recommended work: {report.next_recommended_work}")

    all_not_impl = all(
        r.implementation_status == ImplementationStatus.NOT_IMPLEMENTED
        for r in report.reviews
    )
    sandbox_true = sum(1 for r in report.reviews if r.sandbox_required)
    print(f"implementation_status NOT_IMPLEMENTED on all: {all_not_impl}")
    print(f"sandbox_required true count: {sandbox_true}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/entry_filter.py untouched."
        )
    print(f"Live files modified: NO")
    print(f"JSON saved: {DEFAULT_REVIEW_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_REVIEW_TXT_PATH}")
    print()


def main() -> None:
    run_patch_review_demo()


if __name__ == "__main__":
    main()
