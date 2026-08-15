"""TAE CLI — adaptive-deployment (PAPER_ONLY connect orchestrator)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def run(args: list[str] | None = None) -> int:
    print("===== TAE ADAPTIVE-DEPLOYMENT — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | NO_BROKER | live_allowed=false | SSOT=tae_adaptive_deployment")
    print("")
    cmd = [sys.executable, "tae_adaptive_deployment.py"] + list(args or [])
    if not args:
        cmd.append("status")
    return int(subprocess.run(cmd, cwd=ROOT, check=False).returncode)
