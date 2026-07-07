"""TAE CLI — paper-execution command (PAPER portfolio executor)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_PAPER_EXECUTION_REPORT.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE PAPER-EXECUTION — SUMMARY =====")
    if REPORT_MD.is_file():
        lines = REPORT_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:40]:
            print(line)
        print("")
        return
    print("paper-execution: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PAPER-EXECUTION — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | NO_BROKER | NO_LIVE_MONEY | isolated paper portfolio")
    print("")

    code = _run_step([sys.executable, "tae_paper_execution.py"])
    if code != 0:
        print(f"paper-execution: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
