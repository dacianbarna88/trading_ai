"""TAE CLI — dpe-collaborative command (Collaborative Paper Executor)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
EXEC_REPORT = ROOT / "runtime_outputs/dpe/paper_collaborative/executor_report.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE DPE-COLLABORATIVE — SUMMARY =====")
    if EXEC_REPORT.is_file():
        lines = EXEC_REPORT.read_text(encoding="utf-8").splitlines()
        for line in lines[:48]:
            print(line)
        print("")
        return
    print("dpe-collaborative: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DPE-COLLABORATIVE — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | SHADOW_ONLY | NO_BROKER | no live portfolio change")
    print("")

    code = _run_step([sys.executable, "tae_dpe_collaborative_executor.py"])
    if code != 0:
        print(f"dpe-collaborative: executor failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
