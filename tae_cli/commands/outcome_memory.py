"""TAE CLI — outcome-memory command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE OUTCOME-MEMORY — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | canonical longitudinal storage | NO_BROKER")
    print("")
    return int(subprocess.run([sys.executable, "tae_longitudinal_outcome_memory.py"], cwd=ROOT, check=False).returncode)
