"""TAE CLI — paper-cycle-retest command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PAPER-CYCLE-RETEST — Phase 7 =====")
    return int(subprocess.run([sys.executable, "tae_full_paper_cycle_retest.py"], cwd=ROOT, check=False).returncode)
