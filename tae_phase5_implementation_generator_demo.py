"""
TAE Phase V Sprint A7 — Implementation Generator

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Generates patch documentation from evolution artifacts — does not apply patches.
"""

from __future__ import annotations

from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evolution.implementation_patch import (
    DEFAULT_PATCH_JSON_PATH,
    DEFAULT_PATCH_TXT_PATH,
    ImplementationPatchGenerator,
    ImplementationStatus,
    PatchGateStatus,
    format_patch_txt,
    persist_patch_txt,
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


def run_implementation_generator_demo() -> None:
    print("===== TAE PHASE V SPRINT A7 — IMPLEMENTATION GENERATOR =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Patch documentation only — not applied to live code.")
    print("No broker. No execution. Human approval required.")
    print()

    before_mtimes = _snapshot_mtimes(PROTECTED_PATHS)

    generator = ImplementationPatchGenerator()
    result = generator.generate()

    after_mtimes = _snapshot_mtimes(PROTECTED_PATHS)
    live_files_ok = _mtimes_unchanged(before_mtimes, after_mtimes)

    txt_path = persist_patch_txt(result, live_files_unchanged=live_files_ok)
    report = format_patch_txt(result, live_files_unchanged=live_files_ok)
    print(report)

    print("===== GENERATION SUMMARY =====")
    print(f"Recommendations loaded: {result.recommendations_loaded}")
    print(f"Plans loaded: {result.plans_loaded}")
    print(f"Patches generated (this run): {result.patches_generated}")
    print(f"Duplicates skipped (this run): {result.patches_skipped_duplicate}")
    print(f"Total patches persisted: {len(result.patches)}")
    if result.highest_confidence_patch:
        hc = result.highest_confidence_patch
        print(
            f"Highest-confidence patch: {hc.patch_id} "
            f"(confidence={hc.confidence:.1f}, gate={hc.patch_gate_status.value})"
        )
    print(f"Blocked patches: {len(result.blocked_patches)}")
    for patch in result.blocked_patches:
        print(f"  - {patch.patch_id}: {patch.patch_gate_status.value}")

    if result.patches:
        sample = result.patches[0]
        print("Files affected (proposal only):")
        for f in sample.files_affected:
            print(f"  - {f}")

    all_human = all(p.human_approval_required for p in result.patches)
    all_not_impl = all(
        p.implementation_status == ImplementationStatus.NOT_IMPLEMENTED
        for p in result.patches
    )
    print(f"human_approval_required on all: {all_human}")
    print(f"implementation_status NOT_IMPLEMENTED on all: {all_not_impl}")
    print(f"Protected files unchanged: {live_files_ok}")
    if live_files_ok:
        print(
            "  Confirmed: live_bot.py, portfolio.csv, config/settings.py, "
            "dashboard_v2.py, core/entry_filter.py untouched."
        )
    print(f"JSON saved: {DEFAULT_PATCH_JSON_PATH}")
    print(f"TXT saved: {txt_path}")
    print()


def main() -> None:
    run_implementation_generator_demo()


if __name__ == "__main__":
    main()
