"""TAE CLI — long-term-learning command."""

from __future__ import annotations

from pathlib import Path

from tae_longitudinal_outcome_memory import REPORT_LEARNING_MD, run_longitudinal_memory

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE LONG-TERM-LEARNING — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | evidence aggregation | NO_BROKER")
    print("")
    run_longitudinal_memory()
    if REPORT_LEARNING_MD.is_file():
        print("")
        for line in REPORT_LEARNING_MD.read_text(encoding="utf-8").splitlines()[:30]:
            print(line)
    return 0
