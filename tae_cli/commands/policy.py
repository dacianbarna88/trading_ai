"""TAE CLI — policy command (adaptive profit policy engine)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
PORTFOLIO_GOV_JSON = ROOT / "tae_portfolio_profit_governor.json"
PORTFOLIO_GOV_SCRIPT = ROOT / "tae_portfolio_profit_governor.py"
PDG_JSON = ROOT / "tae_profit_decision_governor.json"
POLICY_MD = ROOT / "tae_adaptive_profit_policy_engine.md"


def _run_step(cmd: list[str]) -> int:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    return int(result.returncode)


def _needs_portfolio_refresh() -> bool:
    if not PORTFOLIO_GOV_JSON.is_file():
        return True
    ppg_mtime = PORTFOLIO_GOV_JSON.stat().st_mtime
    if PDG_JSON.is_file() and PDG_JSON.stat().st_mtime > ppg_mtime:
        return True
    return False


def _print_concise_summary() -> None:
    print("===== TAE POLICY — SUMMARY =====")
    if POLICY_MD.is_file():
        lines = POLICY_MD.read_text(encoding="utf-8").splitlines()
        for line in lines[:40]:
            print(line)
        print("")
        return
    print("policy: no adaptive policy output found", file=sys.stderr)


def run(_args: list[str] | None = None) -> int:
    print("===== TAE POLICY — SHADOW ONLY =====")
    print("Mode: SHADOW_ONLY | NO_BROKER | no live or advisory change")
    print("")

    if _needs_portfolio_refresh():
        code = _run_step([sys.executable, str(PORTFOLIO_GOV_SCRIPT.name)])
        if code != 0:
            print(f"policy: portfolio governor step failed exit={code}", file=sys.stderr)
            return code
    else:
        print(">>> skip tae_portfolio_profit_governor.py (output fresh)")
        print("")

    code = _run_step([sys.executable, "tae_adaptive_profit_policy_engine.py"])
    if code != 0:
        print(f"policy: adaptive policy engine failed exit={code}", file=sys.stderr)
        return code

    print("")
    _print_concise_summary()
    return 0
