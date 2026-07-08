"""TAE CLI — decision-state-refresh command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_DECISION_STATE_REPORT.md"


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DECISION-STATE-REFRESH — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | READ_ONLY builder | NO_BROKER")
    print("")
    code = subprocess.run([sys.executable, "tae_decision_state.py"], cwd=ROOT, check=False).returncode
    if code != 0:
        print(f"decision-state-refresh: failed exit={code}", file=sys.stderr)
        return int(code)
    if REPORT_MD.is_file():
        for line in REPORT_MD.read_text(encoding="utf-8").splitlines()[:20]:
            print(line)
    return 0
