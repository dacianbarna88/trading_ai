"""TAE CLI — portfolio-protect command (portfolio-level profit governor)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
GOVERNOR_JSON = ROOT / "tae_profit_decision_governor.json"
GOVERNOR_SCRIPT = ROOT / "tae_profit_decision_governor.py"
CONTEXT_JSON = ROOT / "tae_profit_context_engine.json"
COMMITTEE_JSON = ROOT / "tae_profit_decision_committee.json"
PORTFOLIO_MD = ROOT / "tae_portfolio_profit_governor.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _needs_governor_refresh() -> bool:
    if not GOVERNOR_JSON.is_file():
        return True
    gov_mtime = GOVERNOR_JSON.stat().st_mtime
    for path in (CONTEXT_JSON, COMMITTEE_JSON):
        if path.is_file() and path.stat().st_mtime > gov_mtime:
            return True
    return False


def _print_concise_summary() -> None:
    print("===== TAE PORTFOLIO-PROTECT — SUMMARY =====")
    if PORTFOLIO_MD.is_file():
        lines = PORTFOLIO_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:36]:
            print(line)
        print("")
        return
    print("portfolio-protect: no portfolio governor output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE PORTFOLIO-PROTECT — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | NO_BROKER | no live orders")
    print("")

    if _needs_governor_refresh():
        code = _run_step([sys.executable, str(GOVERNOR_SCRIPT.name)])
        if code != 0:
            print(f"portfolio-protect: governor step failed exit={code}", file=sys.stderr)
            return code
    else:
        print(">>> skip tae_profit_decision_governor.py (output fresh)")
        print("")

    code = _run_step([sys.executable, "tae_portfolio_profit_governor.py"])
    if code != 0:
        print(f"portfolio-protect: portfolio governor failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
