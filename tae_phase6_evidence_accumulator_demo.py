"""
TAE Phase VI Sprint B2 — Evidence Accumulator

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Persistent evidence history for knowledge candidates — tracking only.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evidence_history import (
    DEFAULT_HISTORY_JSON_PATH,
    DEFAULT_HISTORY_TXT_PATH,
    EvidenceAccumulator,
    ImplementationReadiness,
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


def run_evidence_accumulator_demo() -> None:
    print("===== TAE PHASE VI SPRINT B2 — EVIDENCE ACCUMULATOR =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Evidence tracking only — no strategy or trading changes.")
    print("No broker. No execution. No patch apply.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    accumulator = EvidenceAccumulator()
    report = accumulator.accumulate()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    text = report.format_text()
    print(text)

    print("===== ACCUMULATOR SUMMARY =====")
    print(f"Candidates analyzed: {report.candidates_analyzed}")
    print(f"Dossiers created (this run): {report.dossiers_created}")
    print(f"Dossiers updated (this run): {report.dossiers_updated}")
    print(f"Top evidence score: {report.top_evidence_score:.1f}")
    print(f"Weakest evidence score: {report.weakest_evidence_score:.1f}")
    print(f"Candidates ready for sandbox review: {report.sandbox_ready_count}")
    print(f"Candidates blocked (NOT_READY): {report.blocked_count}")
    print("Main blockers:")
    for b in report.main_blockers:
        print(f"  - {b}")

    all_not_ready = all(
        d.implementation_readiness == ImplementationReadiness.NOT_READY
        for d in report.dossiers
    )
    europe_block = any(
        "Europe/UK" in b for d in report.dossiers for b in d.blockers
    )
    print(f"All implementation_readiness NOT_READY: {all_not_ready}")
    print(f"Europe/UK blocker present: {europe_block}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/entry_filter.py untouched."
        )
    print(f"JSON saved: {DEFAULT_HISTORY_JSON_PATH}")
    print(f"TXT saved: {DEFAULT_HISTORY_TXT_PATH}")
    print()


def main() -> None:
    run_evidence_accumulator_demo()


if __name__ == "__main__":
    main()
