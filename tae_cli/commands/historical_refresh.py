"""TAE CLI — historical-refresh command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_HISTORICAL_RUNTIME_REPORT.md"


def run(_args: list[str] | None = None) -> int:
    print("===== TAE HISTORICAL-REFRESH — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | existing scripts | NO_BROKER | no live change")
    print("")

    result = subprocess.run([sys.executable, "tae_historical_runtime_refresh.py"], cwd=ROOT, check=False)
    if REPORT_MD.is_file():
        print("")
        for line in REPORT_MD.read_text(encoding="utf-8").splitlines()[:30]:
            print(line)
    return int(result.returncode)
