"""TAE CLI — paper-experiments command (Paper Experiment Runner)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
REPORT_MD = ROOT / "TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _print_concise_summary() -> None:
    print("===== TAE PAPER-EXPERIMENTS — SUMMARY =====")
    if REPORT_MD.is_file():
        lines = REPORT_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:50]:
            print(line)
        print("")
        return
    print("paper-experiments: no output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PAPER-EXPERIMENTS — PAPER ONLY =====")
    print("Mode: PAPER_ONLY | READ_ONLY | NO_BROKER | NO_LIVE_CHANGE | no execution")
    print("")

    code = _run_step([sys.executable, "tae_paper_experiment_runner.py"])
    if code != 0:
        print(f"paper-experiments: engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
