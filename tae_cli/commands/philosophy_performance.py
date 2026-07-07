"""TAE CLI — philosophy-performance command."""

from __future__ import annotations

from pathlib import Path

from tae_longitudinal_outcome_memory import REPORT_PHILOSOPHY_MD, run_longitudinal_memory

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PHILOSOPHY-PERFORMANCE — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | philosophy evidence | NO_BROKER")
    print("")
    run_longitudinal_memory()
    if REPORT_PHILOSOPHY_MD.is_file():
        print("")
        for line in REPORT_PHILOSOPHY_MD.read_text(encoding="utf-8").splitlines()[:20]:
            print(line)
    return 0
