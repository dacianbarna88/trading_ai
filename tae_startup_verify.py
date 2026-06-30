#!/usr/bin/env python3
"""
TAE Startup Verify — runs startup chain and aggregates monitor + ecosystem review.

OBSERVABILITY + RUNTIME OPS ONLY
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SCHEMA = "tae.startup_verify.v1"
OUTPUT_JSON = PROJECT_DIR / "tae_startup_verify.json"
OUTPUT_MD = PROJECT_DIR / "tae_startup_verify.md"

MONITOR_JSON = PROJECT_DIR / "tae_market_open_monitor.json"
ECOSYSTEM_JSON = PROJECT_DIR / "tae_full_ecosystem_review.json"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def build_verify_report(
    *,
    startup_rc: int,
    monitor_rc: int,
    review_rc: int,
) -> dict:
    monitor = _load_json(MONITOR_JSON)
    ecosystem = _load_json(ECOSYSTEM_JSON)
    market = monitor.get("market") or {}
    any_open = market.get("any_open")
    proc = monitor.get("process") or {}
    bot_effective = proc.get("bot_effective", "UNKNOWN")
    dash_effective = proc.get("dashboard_effective", "UNKNOWN")
    dry_run = monitor.get("dry_run") or {}
    sleep_wake = monitor.get("sleep_wake_readiness") or {}

    startup_works = startup_rc == 0
    if any_open is True:
        bot_expected = "RUNNING"
        bot_ok = bot_effective == "RUNNING"
        normal_stopped = False
    else:
        bot_expected = "STOPPED"
        bot_ok = bot_effective == "STOPPED"
        normal_stopped = True

    if startup_works and monitor_rc in (0, 1) and review_rc == 0:
        if any_open is True and not bot_ok:
            verdict = "FAIL"
        elif monitor.get("verdict") == "WARNING":
            verdict = "WARNING"
        elif normal_stopped:
            verdict = "PASS"
        else:
            verdict = monitor.get("verdict", "PASS")
    else:
        verdict = "FAIL"

    next_actions: list[str] = []
    if normal_stopped:
        next_actions.append("All markets closed — bot STOPPED is expected. Wait for market open.")
    elif not bot_ok:
        next_actions.append("Market open — start bot: python3 bot_controller.py start-bot")
    if sleep_wake.get("verdict") != "READY":
        next_actions.append("Install autostart: ./install_autostart.sh")
    if not dry_run.get("is_live_mode"):
        next_actions.append("Unset DRY_RUN env; wrappers should use live default.")
    if not next_actions:
        next_actions.append("No action — startup chain healthy.")

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "startup_command_works": startup_works,
        "exit_codes": {
            "startup_runner": startup_rc,
            "market_open_monitor": monitor_rc,
            "ecosystem_review": review_rc,
        },
        "all_markets_closed": any_open is False,
        "bot_stopped_expected": normal_stopped,
        "bot_expected": bot_expected,
        "bot_actual": bot_effective,
        "bot_ok": bot_ok,
        "dashboard_expected": "RUNNING" if any_open else "STOPPED or optional",
        "dashboard_actual": dash_effective,
        "dry_run": dry_run,
        "sleep_wake_readiness": sleep_wake,
        "monitor_verdict": monitor.get("verdict"),
        "ecosystem_verdict": (ecosystem.get("J_final_verdict") or {}).get("ecosystem_verdict")
        or ecosystem.get("Final_Verdict")
        or ecosystem.get("verdict"),
        "next_action": next_actions[0],
        "next_actions": next_actions,
        "monitor_summary": {
            "session_guard_last": (monitor.get("session_guard") or {}).get("last_run_timestamp"),
            "startup_runner_last": (monitor.get("startup_runner") or {}).get("last_timestamp"),
        },
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# TAE Startup Verify",
        "",
        f"**Verdict:** {report['verdict']}",
        f"**Startup command works:** {report['startup_command_works']}",
        "",
        "## Results",
        "",
        f"- All markets closed: **{report['all_markets_closed']}**",
        f"- Bot stopped expected: **{report['bot_stopped_expected']}**",
        f"- Bot expected/actual: **{report['bot_expected']}** / **{report['bot_actual']}**",
        f"- Dashboard actual: **{report['dashboard_actual']}**",
        f"- DRY_RUN live mode: **{report['dry_run'].get('is_live_mode')}** (source={report['dry_run'].get('source')})",
        f"- Monitor verdict: **{report['monitor_verdict']}**",
        f"- Ecosystem verdict: **{report['ecosystem_verdict']}**",
        "",
        f"**Next action:** {report['next_action']}",
        "",
        "## Exit codes",
        "",
    ]
    for key, value in report["exit_codes"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Sleep / Wake Readiness", ""])
    for key, value in report["sleep_wake_readiness"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def print_summary(report: dict) -> None:
    print("===== TAE STARTUP VERIFY =====")
    print(f"Startup works: {report['startup_command_works']}")
    print(f"Markets closed: {report['all_markets_closed']} | bot expected={report['bot_expected']} actual={report['bot_actual']}")
    print(f"DRY_RUN live: {report['dry_run'].get('is_live_mode')} source={report['dry_run'].get('source')}")
    print(f"Verdict: {report['verdict']}")
    print(f"Next: {report['next_action']}")


def main() -> int:
    if len(sys.argv) >= 4:
        startup_rc = int(sys.argv[1])
        monitor_rc = int(sys.argv[2])
        review_rc = int(sys.argv[3])
    else:
        startup_rc = monitor_rc = review_rc = 0

    report = build_verify_report(
        startup_rc=startup_rc,
        monitor_rc=monitor_rc,
        review_rc=review_rc,
    )
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    print_summary(report)
    return 0 if report["verdict"] in {"PASS", "WARNING"} else 1


if __name__ == "__main__":
    sys.exit(main())
