"""TAE CLI — philosophy command (market philosophy lab)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
LAB_MD = ROOT / "tae_market_philosophy_lab.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE PHILOSOPHY — SUMMARY =====")
    if LAB_MD.is_file():
        lines = LAB_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:52]:
            print(line)
        print("")
        return
    print("philosophy: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PHILOSOPHY — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no live or advisory change")
    print("")

    code = _run_step([sys.executable, "tae_market_philosophy_lab.py"])
    if code != 0:
        print(f"philosophy: lab failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
