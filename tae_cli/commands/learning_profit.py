"""TAE CLI — learning-profit command (Learning-to-Profit Bridge)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_LEARNING_TO_PROFIT_BRIDGE_REPORT.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE LEARNING-PROFIT — SUMMARY =====")
    if REPORT_MD.is_file():
        lines = REPORT_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:55]:
            print(line)
        print("")
        return
    print("learning-profit: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE LEARNING-PROFIT — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | READ_ONLY | NO_BROKER | no live promotion | no execution")
    print("")

    code = _run_step([sys.executable, "tae_learning_to_profit_bridge.py"])
    if code != 0:
        print(f"learning-profit: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
