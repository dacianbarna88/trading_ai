"""TAE CLI — strategy-survival command."""

from __future__ import annotations

from pathlib import Path

from tae_longitudinal_outcome_memory import REPORT_SURVIVAL_MD, run_longitudinal_memory

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE STRATEGY-SURVIVAL — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | checkpoint survival | NO_BROKER")
    print("")
    run_longitudinal_memory()
    if REPORT_SURVIVAL_MD.is_file():
        print("")
        for line in REPORT_SURVIVAL_MD.read_text(encoding="utf-8").splitlines()[:25]:
            print(line)
    return 0
