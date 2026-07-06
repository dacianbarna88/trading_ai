"""TAE CLI — opportunity command (opportunity cost ledger)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
LEDGER_MD = ROOT / "tae_opportunity_cost_ledger.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE OPPORTUNITY — SUMMARY =====")
    if LEDGER_MD.is_file():
        lines = LEDGER_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:48]:
            print(line)
        print("")
        return
    print("opportunity: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE OPPORTUNITY — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | READ_ONLY | NO_BROKER | no live or advisory change")
    print("")

    code = _run_step([sys.executable, "tae_opportunity_cost_ledger.py"])
    if code != 0:
        print(f"opportunity: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
