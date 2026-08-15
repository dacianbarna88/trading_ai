"""TAE CLI — paper-mark-to-market command."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_PAPER_MARK_TO_MARKET_REPORT.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    return int(subprocess.run(cmd, cwd=ROOT, check=False).returncode)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PAPER-MARK-TO-MARKET — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | NO_BROKER | live price mark-to-market")
    print("")
    code = _run_step([sys.executable, "-c", "from tae_paper_execution import run_paper_mark_to_market; import sys; r=run_paper_mark_to_market(); sys.exit(0 if r.get('ok') else 1)"])
    if code != 0:
        return code
    if REPORT_MD.is_file():
        print(REPORT_MD.read_text(encoding="utf-8")[:1200])
    return 0
