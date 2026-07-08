"""TAE CLI — dpe-events command (Decision Event Bus)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
BUS_MD = ROOT / "tae_decision_event_bus.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE DPE-EVENTS — SUMMARY =====")
    if BUS_MD.is_file():
        lines = BUS_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:48]:
            print(line)
        print("")
        return
    print("dpe-events: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DPE-EVENTS — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no live or advisory change")
    print("")

    code = _run_step([sys.executable, "tae_decision_event_bus.py"])
    if code != 0:
        print(f"dpe-events: bus failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
