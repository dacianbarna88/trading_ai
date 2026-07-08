"""TAE CLI — dpe-learning command (Learning Engine)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
LEARNING_MD = ROOT / "runtime_outputs/dpe/learning/learning.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE DPE-LEARNING — SUMMARY =====")
    if LEARNING_MD.is_file():
        lines = LEARNING_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:48]:
            print(line)
        print("")
        return
    print("dpe-learning: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DPE-LEARNING — READ ONLY =====")
    print("Mode: READ_ONLY | PAPER_ONLY | append-only learning history")
    print("")

    code = _run_step([sys.executable, "tae_dpe_learning_engine.py"])
    if code != 0:
        print(f"dpe-learning: learning engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
