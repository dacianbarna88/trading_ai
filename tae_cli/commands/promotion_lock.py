"""TAE CLI — promotion-lock command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PROMOTION-LOCK — Phase 9 =====")
    return int(subprocess.run([sys.executable, "tae_live_promotion_lock.py"], cwd=ROOT, check=False).returncode)
