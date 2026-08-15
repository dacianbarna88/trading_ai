"""TAE CLI — paper-decisions command (Paper Decision Engine)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_PAPER_DECISION_ENGINE_REPORT.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE PAPER-DECISIONS — SUMMARY =====")
    if REPORT_MD.is_file():
        lines = REPORT_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:50]:
            print(line)
        print("")
        return
    print("paper-decisions: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PAPER-DECISIONS — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | READ_ONLY | NO_BROKER | NO_EXECUTION | NO_LIVE_CHANGE")
    print("")

    code = _run_step([sys.executable, "tae_paper_decision_engine.py"])
    if code != 0:
        print(f"paper-decisions: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
