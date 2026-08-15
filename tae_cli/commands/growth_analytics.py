"""TAE CLI — growth-analytics command (profit growth analytics SSOT)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
ANALYTICS_MD = ROOT / "tae_profit_growth_analytics.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE GROWTH-ANALYTICS — SUMMARY =====")
    if ANALYTICS_MD.is_file():
        lines = ANALYTICS_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:42]:
            print(line)
        print("")
        return
    print("growth-analytics: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE GROWTH-ANALYTICS — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no live or advisory change")
    print("")

    code = _run_step([sys.executable, "tae_profit_growth_analytics.py"])
    if code != 0:
        print(f"growth-analytics: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
