"""TAE CLI — winner command (winner lifecycle profiler)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
PROFILER_MD = ROOT / "tae_winner_lifecycle_profiler.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE WINNER — SUMMARY =====")
    if PROFILER_MD.is_file():
        lines = PROFILER_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:52]:
            print(line)
        print("")
        return
    print("winner: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE WINNER — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no live or advisory change")
    print("")

    code = _run_step([sys.executable, "tae_winner_lifecycle_profiler.py"])
    if code != 0:
        print(f"winner: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
