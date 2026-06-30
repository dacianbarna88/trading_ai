#!/usr/bin/env python3
"""
TAE Market Session Guard — start bot/dashboard when any market session is open.

RUNTIME_OPS_ONLY | PAPER_ONLY | NO_BROKER
Default: live startup (DRY_RUN=False). Use --dry-run or env DRY_RUN=1 to simulate.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LOG_FILE = PROJECT_DIR / "market_session_guard.log"

sys.path.insert(0, str(PROJECT_DIR))

from research_core.runtime.dry_run_config import dry_run_diagnostics, resolve_dry_run


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def pgrep_pattern(pattern: str) -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    pids: list[int] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def ensure_awake_guard(*, dry_run: bool, dry_run_source: str) -> str:
    awake_script = PROJECT_DIR / "awake_guard.sh"
    if not awake_script.exists():
        log(f"ACTION=AWAKE_GUARD SKIPPED reason=missing script path={awake_script}")
        return "missing script"

    if dry_run:
        return f"DRY_RUN would run awake_guard.sh source={dry_run_source}"

    result = subprocess.run(
        ["/bin/bash", str(awake_script)],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        log(f"ACTION=AWAKE_GUARD ERROR code={result.returncode} stderr={stderr}")
        return f"error code={result.returncode}"
    return "awake_guard invoked"


def _format_start_result(label: str, detail: dict) -> str:
    parts = [
        f"{label}={detail.get('message', '')}",
        f"PID={detail.get('pid')}",
        f"PID_ALIVE={detail.get('pid_alive')}",
        f"PGREP={detail.get('pgrep_pids')}",
        f"CMD={detail.get('command')}",
    ]
    if detail.get("failure_reason"):
        parts.append(f"FAIL={detail['failure_reason']}")
    return " | ".join(str(p) for p in parts if p)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TAE market session guard")
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Log startup actions without starting bot/dashboard",
    )
    args = parser.parse_args(argv)

    os.chdir(PROJECT_DIR)

    dry_run, dry_run_source = resolve_dry_run(
        (["--dry-run"] if args.dry_run else []) + (argv or sys.argv[1:])
    )

    from bot_controller import (
        get_bot_start_command,
        get_dashboard_status,
        get_status,
        start_bot_verified,
        start_dashboard_verified,
    )
    from markets.market_hours import any_market_open, get_market_statuses, get_open_markets

    statuses = get_market_statuses()
    open_markets = get_open_markets()
    closed_markets = [name for name, is_open in statuses.items() if not is_open]
    markets_open = any_market_open()
    bot_status = get_status()
    dashboard_status = get_dashboard_status()

    bot_action = "NONE"
    dashboard_action = "NONE"
    bot_result = ""
    dashboard_result = ""
    awake_result = ""
    start_reason = "NONE"

    log(
        "INVOKED scheduler={scheduler} pid={pid}".format(
            scheduler=os.getenv("TAE_SCHEDULER_SOURCE", "manual"),
            pid=os.getpid(),
        )
    )
    log(
        "CONFIG DRY_RUN={dry_run} DRY_RUN_SOURCE={source} ENV={env}".format(
            dry_run=dry_run,
            source=dry_run_source,
            env=dry_run_diagnostics(),
        )
    )

    if markets_open:
        start_reason = "market_session_open"
        awake_result = ensure_awake_guard(dry_run=dry_run, dry_run_source=dry_run_source)

        if bot_status != "RUNNING":
            bot_action = "START"
            if dry_run:
                bot_result = (
                    f"DRY_RUN would start bot source={dry_run_source} "
                    f"cmd={get_bot_start_command()}"
                )
            else:
                detail = start_bot_verified()
                bot_result = _format_start_result("BOT", detail)
                bot_status = get_status()
                if not detail.get("pid_alive"):
                    log(f"START_BOT_VERIFY_FAILED {_format_start_result('BOT', detail)}")

        if dashboard_status != "RUNNING":
            dashboard_action = "START"
            if dry_run:
                dashboard_result = f"DRY_RUN would start dashboard source={dry_run_source}"
            else:
                detail = start_dashboard_verified()
                dashboard_result = _format_start_result("DASHBOARD", detail)
                dashboard_status = get_dashboard_status()
    else:
        start_reason = "all_markets_closed"

    log(
        "OPEN=[{open}] CLOSED=[{closed}] BOT={bot} DASHBOARD={dashboard} "
        "BOT_ACTION={bot_action} DASHBOARD_ACTION={dashboard_action} "
        "START_REASON={start_reason} AWAKE={awake} BOT_RESULT={bot_result} "
        "DASHBOARD_RESULT={dashboard_result} DRY_RUN={dry_run} DRY_RUN_SOURCE={source} SCHEDULER={scheduler}".format(
            open=",".join(open_markets) if open_markets else "NONE",
            closed=",".join(closed_markets) if closed_markets else "NONE",
            bot=bot_status,
            dashboard=dashboard_status,
            bot_action=bot_action,
            dashboard_action=dashboard_action,
            start_reason=start_reason,
            awake=awake_result or "NONE",
            bot_result=bot_result or "NONE",
            dashboard_result=dashboard_result or "NONE",
            dry_run=dry_run,
            source=dry_run_source,
            scheduler=os.getenv("TAE_SCHEDULER_SOURCE", "manual"),
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR {exc}")
        raise SystemExit(1) from exc
