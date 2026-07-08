"""TAE CLI — dpe-adaptive command (Adaptive Philosophy Selector)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
ADAPTIVE_MD = ROOT / "runtime_outputs/dpe/adaptive/adaptive.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE DPE-ADAPTIVE — SUMMARY =====")
    if ADAPTIVE_MD.is_file():
        lines = ADAPTIVE_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:40]:
            print(line)
        print("")
        return
    print("dpe-adaptive: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DPE-ADAPTIVE — READ ONLY =====")
    print("Mode: READ_ONLY | PAPER_ONLY | no learning or live change")
    print("")

    code = _run_step([sys.executable, "tae_dpe_adaptive_selector.py"])
    if code != 0:
        print(f"dpe-adaptive: selector failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
