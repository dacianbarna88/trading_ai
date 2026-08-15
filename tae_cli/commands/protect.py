"""TAE CLI — protect command (shadow profit decision pipeline)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
COMMITTEE_MD = ROOT / "tae_profit_decision_committee.md"
LEARNING_MD = ROOT / "tae_profit_committee_learning.md"
CONTEXT_MD = ROOT / "tae_profit_context_engine.md"
CONTEXT_LEARNING_MD = ROOT / "tae_profit_context_learning.md"
GOVERNOR_MD = ROOT / "tae_profit_decision_governor.md"
JSON_OUTPUT = ROOT / "tae_profit_decision_committee.json"

PIPELINE = [
    [sys.executable, "tae_profit_protection_shadow.py"],
    [sys.executable, "tae_profit_intelligence_brain.py"],
    [sys.executable, "tae_profit_memory_engine.py"],
    [sys.executable, "tae_profit_decision_committee.py"],
    [sys.executable, "tae_profit_committee_learning.py"],
    [sys.executable, "tae_profit_context_engine.py"],
    [sys.executable, "tae_profit_decision_governor.py"],
]


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE PROTECT — FINAL SUMMARY =====")
    if GOVERNOR_MD.is_file():
        print("--- Profit Decision Governor (v1) ---")
        lines = GOVERNOR_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:28]:
            print(line)
        print("")
    if CONTEXT_MD.is_file():
        print("--- Profit Context Engine (v2 adaptive) ---")
        lines = CONTEXT_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:32]:
            print(line)
        print("")
    if CONTEXT_LEARNING_MD.is_file():
        print("--- Context Learning Weights ---")
        lines = CONTEXT_LEARNING_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:18]:
            print(line)
        print("")
    if LEARNING_MD.is_file():
        print("--- Committee Learning ---")
        lines = LEARNING_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:20]:
            print(line)
        print("")
    if COMMITTEE_MD.is_file():
        print("--- Committee weighted view ---")
        lines = COMMITTEE_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:18]:
            print(line)
        print("")
        return
    if JSON_OUTPUT.is_file():
        import json

        data = json.loads(JSON_OUTPUT.read_text(encoding="utf-8"))
        summary = data.get("global_summary") or {}
        print("===== TAE PROTECT (concise) =====")
        print("Final verdict:", summary.get("final_verdict"))
        print("Tickers:", summary.get("total_tickers"))
        print("Avg score:", summary.get("average_protection_score"))
        for row in (summary.get("top_5_highest_protection_score") or [])[:5]:
            print(
                f"  {row.get('ticker')}: {row.get('protection_score')} → "
                f"{row.get('final_committee_recommendation')}"
            )
        print("")
        return
    print("protect: no committee output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PROTECT — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | NO_BROKER | no live orders")
    print("")

    for cmd in PIPELINE:
        code = _run_step(cmd)
        if code != 0:
            print(f"protect: step failed ({cmd[1]}) exit={code}", file=sys.stderr)
            return code

    print("")
    _print_concise_summary()
    return 0
