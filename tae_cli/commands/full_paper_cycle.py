"""TAE CLI — full-paper-cycle command (complete PAPER closed loop)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_FULL_PAPER_CYCLE_REPORT.md"


def run(_args: list[str] | None = None) -> int:
    print("===== TAE FULL-PAPER-CYCLE — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | READ_ONLY | NO_BROKER | NO_LIVE_CHANGE | no execution")
    print("")

    result = subprocess.run([sys.executable, "tae_full_paper_cycle.py"], cwd=ROOT, check=False)
    code = int(result.returncode)

    if REPORT_MD.is_file():
        print("")
        print("===== TAE FULL-PAPER-CYCLE — SUMMARY =====")
        for line in REPORT_MD.read_text(encoding="utf-8").splitlines()[:35]:
            print(line)
        print("")

    return code
