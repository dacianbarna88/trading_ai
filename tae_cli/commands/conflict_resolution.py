"""TAE CLI — conflict-resolution-refresh command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_CONFLICT_RESOLUTION_REPORT.md"


def run(_args: list[str] | None = None) -> int:
    print("===== TAE CONFLICT-RESOLUTION-REFRESH — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | READ_ONLY | NO_BROKER | evidence orchestrator")
    print("")
    code = subprocess.run([sys.executable, "tae_conflict_resolution.py"], cwd=ROOT, check=False).returncode
    if code != 0:
        print(f"conflict-resolution-refresh: failed exit={code}", file=sys.stderr)
        return int(code)
    if REPORT_MD.is_file():
        for line in REPORT_MD.read_text(encoding="utf-8").splitlines()[:25]:
            print(line)
    return 0
