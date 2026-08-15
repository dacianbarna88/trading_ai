"""TAE CLI — 30-day-paper-validation command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE 30-DAY-PAPER-VALIDATION — Phase 8 =====")
    return int(subprocess.run([sys.executable, "tae_30_day_paper_validation.py"], cwd=ROOT, check=False).returncode)
