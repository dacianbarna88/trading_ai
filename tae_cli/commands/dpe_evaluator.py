"""TAE CLI — dpe-evaluator command (Result Evaluator)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
EVAL_MD = ROOT / "runtime_outputs/dpe/result_evaluator/evaluation.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE DPE-EVALUATOR — SUMMARY =====")
    if EVAL_MD.is_file():
        lines = EVAL_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:48]:
            print(line)
        print("")
        return
    print("dpe-evaluator: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE DPE-EVALUATOR — READ ONLY =====")
    print("Mode: READ_ONLY | PAPER_ONLY | no executor or live change")
    print("")

    code = _run_step([sys.executable, "tae_dpe_result_evaluator.py"])
    if code != 0:
        print(f"dpe-evaluator: evaluator failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
