"""TAE CLI — adaptive-weights command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE ADAPTIVE-WEIGHTS — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | evidence-driven weights | NO_BROKER | NO_LIVE_PROMOTION")
    print("")
    return int(subprocess.run([sys.executable, "tae_adaptive_paper_weights.py"], cwd=ROOT, check=False).returncode)
