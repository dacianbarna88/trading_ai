"""TAE CLI — dpe-splitter command (Execution Splitter)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
SPLIT_MD = ROOT / "tae_execution_splitter.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE DPE-SPLITTER — SUMMARY =====")
    if SPLIT_MD.is_file():
        lines = SPLIT_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:48]:
            print(line)
        print("")
        return
    print("dpe-splitter: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DPE-SPLITTER — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no execution or live change")
    print("")

    code = _run_step([sys.executable, "tae_execution_splitter.py"])
    if code != 0:
        print(f"dpe-splitter: splitter failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
