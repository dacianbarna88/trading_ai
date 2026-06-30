#!/usr/bin/env python3
"""
TAE Market Open Monitor — observability only.

MODE: OBSERVABILITY + RUNTIME OPS ONLY
NO strategy / BUY / SELL / scoring changes.
"""

from __future__ import annotations

import json
import os
import plistlib
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

PROJECT_DIR = Path(__file__).resolve().parent
SCHEMA = "tae.market_open_monitor.v1"
MODE = "OBSERVABILITY_RUNTIME_OPS_ONLY"

OUTPUT_JSON = PROJECT_DIR / "tae_market_open_monitor.json"
OUTPUT_MD = PROJECT_DIR / "tae_market_open_monitor.md"

BOT_LOG_FRESH_SECONDS = 300
SIGNALS_FRESH_SECONDS = 600
STARTUP_FRESH_HOURS = 48
GUARD_FRESH_HOURS = 6

ARTIFACTS = {
    "market_session_guard_log": PROJECT_DIR / "market_session_guard.log",
    "startup_runner_log": PROJECT_DIR / "startup_runner.log",
    "bot_output_log": PROJECT_DIR / "bot_output.log",
    "bot_status": PROJECT_DIR / "bot_status.txt",
    "bot_pid": PROJECT_DIR / "bot_pid.txt",
    "dashboard_pid": PROJECT_DIR / "dashboard_pid.txt",
    "dashboard_status": PROJECT_DIR / "dashboard_status.txt",
    "live_signals": PROJECT_DIR / "live_signals.csv",
    "portfolio": PROJECT_DIR / "portfolio.csv",
    "tae_live_advisory": PROJECT_DIR / "tae_live_advisory.json",
    "tae_shadow_validation_events": PROJECT_DIR / "tae_shadow_validation_events.csv",
    "tae_full_ecosystem_review": PROJECT_DIR / "tae_full_ecosystem_review.json",
}

PLIST_REPO = PROJECT_DIR / "launchd" / "com.tradingai.startup.plist"
PLIST_INSTALLED = Path.home() / "Library/LaunchAgents/com.tradingai.startup.plist"


def _file_age_seconds(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        return round(time.time() - path.stat().st_mtime, 1)
    except OSError:
        return None


def _read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse_log_timestamp(line: str) -> datetime | None:
    match = re.match(r"\[(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})\]", line)
    if not match:
        return None
    try:
        return datetime.strptime(
            f"{match.group(1)} {match.group(2)}:{match.group(3)}:{match.group(4)}",
            "%Y-%m-%d %H:%M:%S",
        )
    except ValueError:
        return None


def _parse_kv_line(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in line.split():
        if "=" in token:
            key, _, value = token.partition("=")
            out[key.lower()] = value
    # multi-word values from log format KEY=[...] 
    open_match = re.search(r"OPEN=\[([^\]]*)\]", line)
    if open_match:
        out["open"] = open_match.group(1)
    closed_match = re.search(r"CLOSED=\[([^\]]*)\]", line)
    if closed_match:
        out["closed"] = closed_match.group(1)
    source_match = re.search(r"DRY_RUN_SOURCE=(\S+)", line)
    if source_match:
        out["dry_run_source"] = source_match.group(1)
    return out


def _last_matching_lines(path: Path, pattern: str, limit: int = 5) -> list[str]:
    text = _read_text(path)
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matched = [line for line in lines if re.search(pattern, line)]
    return matched[-limit:]


def _last_startup_runner_run(log_path: Path) -> dict[str, Any]:
    text = _read_text(log_path)
    if not text:
        return {"ran": False, "last_timestamp": None, "age_hours": None}
    blocks = text.split("===== TRADING AI STARTUP RUNNER =====")
    if len(blocks) < 2:
        return {"ran": False, "last_timestamp": None, "age_hours": None}
    last_block = blocks[-1]
    ts_match = re.search(r"Timestamp:\s*(.+)", last_block)
    ts_raw = ts_match.group(1).strip() if ts_match else None
    age_hours = None
    if ts_raw:
        try:
            parsed = datetime.strptime(ts_raw, "%a %b %d %H:%M:%S %Z %Y")
        except ValueError:
            try:
                parsed = datetime.strptime(ts_raw, "%a %b %d %H:%M:%S %Y")
            except ValueError:
                parsed = None
        if parsed:
            age_hours = round((datetime.now() - parsed).total_seconds() / 3600, 2)
    return {
        "ran": True,
        "last_timestamp": ts_raw,
        "age_hours": age_hours,
        "recent_within_48h": age_hours is not None and age_hours <= STARTUP_FRESH_HOURS,
        "last_block_excerpt": last_block.strip()[:400],
    }


def _parse_guard_log(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if not text:
        return {"present": False}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    config_lines = [line for line in lines if "CONFIG DRY_RUN=" in line]
    session_lines = [line for line in lines if "OPEN=[" in line and "START_REASON=" in line]
    last_config = config_lines[-1] if config_lines else None
    last_session = session_lines[-1] if session_lines else lines[-1] if lines else None

    config_parsed: dict[str, str] = {}
    if last_config:
        for part in last_config.split():
            if part.startswith("DRY_RUN="):
                config_parsed["dry_run"] = part.split("=", 1)[1]
            elif part.startswith("DRY_RUN_SOURCE="):
                config_parsed["dry_run_source"] = part.split("=", 1)[1]

    session_parsed = _parse_kv_line(last_session) if last_session else {}
    last_ts = _parse_log_timestamp(last_session) if last_session else None
    age_hours = None
    if last_ts:
        age_hours = round((datetime.now() - last_ts).total_seconds() / 3600, 2)

    return {
        "present": True,
        "last_config_line": last_config,
        "last_session_line": last_session,
        "config": config_parsed,
        "session": session_parsed,
        "last_run_timestamp": last_ts.isoformat(sep=" ") if last_ts else None,
        "age_hours": age_hours,
        "recent_within_6h": age_hours is not None and age_hours <= GUARD_FRESH_HOURS,
    }


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid(path: Path) -> int | None:
    text = _read_text(path)
    if not text:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def _pgrep(pattern: str) -> list[int]:
    for cmd in (["pgrep", "-f", pattern], ["/usr/bin/pgrep", "-f", pattern]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return [int(x) for x in proc.stdout.strip().splitlines() if x.strip().isdigit()]
    return []


def _port_open(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


def _market_state() -> dict[str, Any]:
    try:
        from markets.market_hours import any_market_open, get_market_statuses, get_open_markets

        statuses = get_market_statuses()
        open_markets = get_open_markets()
        return {
            "any_open": any_market_open(),
            "open_markets": open_markets,
            "closed_markets": [k for k, v in statuses.items() if not v],
            "statuses": statuses,
        }
    except Exception as exc:
        return {"any_open": None, "error": str(exc)}


def _shadow_events_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "count": 0, "age_seconds": None}
    text = _read_text(path) or ""
    lines = [line for line in text.splitlines() if line.strip()]
    count = max(0, len(lines) - 1)
    return {
        "present": True,
        "count": count,
        "age_seconds": _file_age_seconds(path),
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _cron_has_guard() -> bool | None:
    try:
        proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
    except OSError:
        return None
    if proc.returncode != 0:
        return False
    return "market_session_guard" in (proc.stdout or "")


def _plist_run_at_load(path: Path) -> bool | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            data = plistlib.load(handle)
        return bool(data.get("RunAtLoad"))
    except Exception:
        pass
    try:
        tree = ElementTree.parse(path)
        root = tree.getroot()
        for key_el in root.iter("key"):
            if key_el.text == "RunAtLoad":
                sibling = key_el.getnext() if hasattr(key_el, "getnext") else None
                if sibling is not None and sibling.tag == "true":
                    return True
                if sibling is not None and sibling.tag == "false":
                    return False
    except Exception:
        return None
    return None


def _sleep_wake_readiness() -> dict[str, Any]:
    scripts = {
        "startup_runner_executable": PROJECT_DIR / "startup_runner.sh",
        "awake_guard_executable": PROJECT_DIR / "awake_guard.sh",
        "market_guard_executable": PROJECT_DIR / "market_session_guard.sh",
    }
    exec_status = {
        key: path.is_file() and os.access(path, os.X_OK)
        for key, path in scripts.items()
    }
    startup_log = _last_startup_runner_run(ARTIFACTS["startup_runner_log"])
    guard_log = _parse_guard_log(ARTIFACTS["market_session_guard_log"])

    readiness_checks = [
        exec_status["startup_runner_executable"],
        exec_status["awake_guard_executable"],
        exec_status["market_guard_executable"],
        PLIST_REPO.is_file(),
    ]
    installed_startup = PLIST_INSTALLED.is_file()
    installed_guard = (Path.home() / "Library/LaunchAgents/com.tradingai.market-session-guard.plist").is_file()
    run_at_load = _plist_run_at_load(PLIST_INSTALLED) or _plist_run_at_load(PLIST_REPO)
    guard_plist = Path.home() / "Library/LaunchAgents/com.tradingai.market-session-guard.plist"
    guard_interval = None
    if guard_plist.is_file():
        try:
            with guard_plist.open("rb") as handle:
                pdata = plistlib.load(handle)
            guard_interval = pdata.get("StartInterval")
        except Exception:
            guard_interval = None

    if all(readiness_checks) and installed_startup and installed_guard and run_at_load:
        verdict = "READY"
    elif all(readiness_checks) and installed_startup:
        verdict = "WARNING"
    else:
        verdict = "NOT_READY"

    return {
        "launchagent_repo_present": PLIST_REPO.is_file(),
        "launchagent_startup_installed": installed_startup,
        "launchagent_guard_installed": installed_guard,
        "launchagent_guard_start_interval_seconds": guard_interval,
        "launchagent_installed_path": str(PLIST_INSTALLED) if installed_startup else None,
        "run_at_load": run_at_load,
        "cron_has_market_guard": _cron_has_guard(),
        **exec_status,
        "last_startup_runner_time": startup_log.get("last_timestamp"),
        "last_startup_runner_age_hours": startup_log.get("age_hours"),
        "last_session_guard_time": guard_log.get("last_run_timestamp"),
        "last_session_guard_age_hours": guard_log.get("age_hours"),
        "verdict": verdict,
        "note": (
            "Sleep/wake cannot be simulated; chain checks LaunchAgent, executables, "
            "and recent startup/guard log timestamps."
        ),
    }


def _explain_dashboard_without_bot(
    market_open: bool,
    guard: dict[str, Any],
    bot_status: str,
    dashboard_status: str,
) -> str | None:
    if dashboard_status != "RUNNING" or bot_status == "RUNNING":
        return None
    session = guard.get("session") or {}
    config = guard.get("config") or {}
    reasons: list[str] = []
    if not market_open:
        reasons.append("all markets closed — bot start skipped by session guard")
    if session.get("start_reason") == "all_markets_closed":
        reasons.append("last guard START_REASON=all_markets_closed")
    dry_run = config.get("dry_run") or session.get("dry_run")
    if dry_run and dry_run.lower() in {"true", "1"}:
        reasons.append(f"DRY_RUN active (source={config.get('dry_run_source', 'unknown')})")
    if session.get("bot_action") == "START" and "DRY_RUN would start bot" in (session.get("bot_result") or ""):
        reasons.append("guard logged DRY_RUN would start bot")
    if session.get("bot") == "STOPPED" and session.get("bot_action") == "NONE":
        reasons.append("guard did not attempt bot start")
    return "; ".join(reasons) if reasons else "dashboard running independently of bot (manual or prior session)"


def _compute_verdict(ctx: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    notes: list[str] = []
    market_open = ctx["market"]["any_open"] is True
    bot_running = ctx["process"]["bot_effective"] == "RUNNING"
    dashboard_running = ctx["process"]["dashboard_effective"] == "RUNNING"
    dry_run_false = ctx["dry_run"]["is_live_mode"]
    signals_recent = ctx["signals"]["recent"]
    bot_log_recent = ctx["bot_log"]["recent"]
    x9 = ctx["x9"]
    guard = ctx["guard"]
    startup = ctx["startup"]
    readiness = ctx["sleep_wake_readiness"]["verdict"]

    if ctx["market"]["any_open"] is None:
        return "WARNING", ["market hours module error"], notes

    if not market_open:
        notes.append("All markets closed — bot STOPPED expected.")
        if bot_running:
            warnings.append("Bot process running while all markets closed (manual start?)")
        if not dry_run_false:
            warnings.append("DRY_RUN not live mode while markets closed")
        if readiness != "READY":
            warnings.append(f"sleep_wake_readiness={readiness}")
        if warnings:
            return "WARNING", warnings, notes
        return "WAITING_FOR_MARKET_OPEN", warnings, notes

    # Market open
    if not dry_run_false:
        warnings.append(f"DRY_RUN not live: source={ctx['dry_run']['source']}")

    if not bot_running:
        warnings.append("Market open but bot not RUNNING")
        if ctx.get("dashboard_bot_explanation"):
            notes.append(ctx["dashboard_bot_explanation"])
        return "FAIL", warnings, notes

    if not bot_log_recent and not signals_recent:
        warnings.append("Bot RUNNING but bot_output.log and live_signals.csv not recent")

    if bot_running and not signals_recent:
        warnings.append("Bot RUNNING but live_signals.csv stale")

    if market_open and bot_running and x9.get("warning_after_open"):
        warnings.append("X.9 ledger has no events after market open / BUY evaluation window")

    if x9.get("ok_before_open"):
        notes.append("X.9 empty before market open: OK")

    if warnings:
        return "WARNING", warnings, notes
    return "PASS", warnings, notes


def build_monitor_report(root: Path | None = None) -> dict[str, Any]:
    root = root or PROJECT_DIR
    paths = {key: root / ARTIFACTS[key].name for key in ARTIFACTS}

    market = _market_state()
    guard = _parse_guard_log(paths["market_session_guard_log"])
    startup = _last_startup_runner_run(paths["startup_runner_log"])

    bot_pid = _read_pid(paths["bot_pid"])
    dash_pid = _read_pid(paths["dashboard_pid"])
    bot_pgrep = _pgrep("live_bot.py")
    dash_pgrep = _pgrep("streamlit run dashboard_v2.py")
    bot_pid_alive = bool(bot_pid and _pid_alive(bot_pid))
    dash_pid_alive = bool(dash_pid and _pid_alive(dash_pid))
    dash_port = _port_open(8501)

    bot_status_file = (_read_text(paths["bot_status"]) or "UNKNOWN").strip()
    dash_status_file = (_read_text(paths["dashboard_status"]) or "UNKNOWN").strip()

    bot_log_age = _file_age_seconds(paths["bot_output_log"])
    signals_age = _file_age_seconds(paths["live_signals"])
    bot_log_recent = bot_log_age is not None and bot_log_age <= BOT_LOG_FRESH_SECONDS
    signals_recent = signals_age is not None and signals_age <= SIGNALS_FRESH_SECONDS

    bot_effective = "RUNNING" if (bot_pid_alive or bot_pgrep) else (
        "RUNNING" if bot_log_recent or signals_recent else bot_status_file.upper()
    )
    dash_effective = "RUNNING" if (dash_port or dash_pid_alive or dash_pgrep) else dash_status_file.upper()

    config = guard.get("config") or {}
    session = guard.get("session") or {}
    dry_run_val = config.get("dry_run") or session.get("dry_run", "")
    dry_run_source = config.get("dry_run_source") or session.get("dry_run_source", "unknown")
    is_live_mode = str(dry_run_val).lower() in {"false", "0", ""}

    x9_path = paths["tae_shadow_validation_events"]
    x9 = _shadow_events_summary(x9_path)
    market_open = market.get("any_open") is True
    x9_ok_before = not market_open and x9["count"] == 0
    x9_warning_after = market_open and bot_effective == "RUNNING" and x9["count"] == 0

    advisory = _load_json(paths["tae_live_advisory"]) or {}
    ecosystem = _load_json(paths["tae_full_ecosystem_review"]) or {}

    dashboard_bot_explanation = _explain_dashboard_without_bot(
        market_open, guard, bot_effective, dash_effective
    )

    sleep_wake = _sleep_wake_readiness()

    answers = {
        "1_system_started_after_wake": startup.get("recent_within_48h", False),
        "2_startup_runner_ran": startup.get("ran", False),
        "3_market_session_guard_ran": guard.get("present", False) and guard.get("recent_within_6h", False),
        "4_dry_run_false": is_live_mode,
        "5_market_open_checks": {
            "bot_started": bot_effective == "RUNNING" if market_open else None,
            "dashboard_started": dash_effective == "RUNNING" if market_open else None,
            "pid_alive": bot_pid_alive if market_open else None,
            "bot_output_recent": bot_log_recent if market_open else None,
            "live_signals_recent": signals_recent if market_open else None,
            "x9_recent": (x9.get("age_seconds") or 99999) <= SIGNALS_FRESH_SECONDS if market_open else None,
        },
        "6_all_markets_closed": {
            "stopped_expected": not market_open and bot_effective == "STOPPED",
            "readiness_ready": (ecosystem.get("Market_Readiness") or {}).get("verdict") == "READY"
            or not market_open,
        },
        "7_dashboard_without_bot_explanation": dashboard_bot_explanation,
        "8_bot_fail_if_open_and_stopped": market_open and bot_effective != "RUNNING",
        "9_bot_running_no_signals_warning": bot_effective == "RUNNING" and not signals_recent,
        "10_x9_empty_before_open_ok": x9_ok_before or (not market_open and x9["count"] == 0),
        "11_x9_empty_after_buy_eval_warning": x9_warning_after,
    }

    ctx = {
        "market": market,
        "guard": guard,
        "startup": startup,
        "dry_run": {
            "value": dry_run_val,
            "source": dry_run_source,
            "is_live_mode": is_live_mode,
        },
        "process": {
            "bot_effective": bot_effective,
            "dashboard_effective": dash_effective,
        },
        "signals": {"recent": signals_recent, "age_seconds": signals_age},
        "bot_log": {"recent": bot_log_recent, "age_seconds": bot_log_age},
        "x9": {
            "count": x9["count"],
            "present": x9["present"],
            "ok_before_open": x9_ok_before,
            "warning_after_open": x9_warning_after,
        },
        "sleep_wake_readiness": sleep_wake,
        "dashboard_bot_explanation": dashboard_bot_explanation,
    }

    verdict, warnings, notes = _compute_verdict(ctx)

    return {
        "schema": SCHEMA,
        "mode": MODE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "warnings": warnings,
        "notes": notes,
        "answers": answers,
        "market": market,
        "dry_run": ctx["dry_run"],
        "session_guard": guard,
        "startup_runner": startup,
        "process": {
            "bot_status_file": bot_status_file,
            "bot_effective": bot_effective,
            "bot_pid": bot_pid,
            "bot_pid_alive": bot_pid_alive,
            "bot_pgrep_pids": bot_pgrep,
            "dashboard_status_file": dash_status_file,
            "dashboard_effective": dash_effective,
            "dashboard_pid": dash_pid,
            "dashboard_pid_alive": dash_pid_alive,
            "dashboard_pgrep_pids": dash_pgrep,
            "dashboard_port_8501_open": dash_port,
        },
        "artifacts": {
            key: {
                "path": str(paths[key]),
                "present": paths[key].is_file(),
                "age_seconds": _file_age_seconds(paths[key]),
            }
            for key in paths
        },
        "signals": {
            "live_signals_age_seconds": signals_age,
            "live_signals_recent": signals_recent,
            "fresh_threshold_seconds": SIGNALS_FRESH_SECONDS,
        },
        "bot_log": {
            "age_seconds": bot_log_age,
            "recent": bot_log_recent,
            "fresh_threshold_seconds": BOT_LOG_FRESH_SECONDS,
        },
        "x9_ledger": x9,
        "advisory": {
            "present": bool(advisory),
            "action": advisory.get("action"),
            "blocks_new_buy": advisory.get("blocks_new_buy"),
        },
        "ecosystem_review": {
            "present": bool(ecosystem),
            "market_readiness": (ecosystem.get("Market_Readiness") or {}).get("verdict"),
        },
        "sleep_wake_readiness": sleep_wake,
        "dashboard_without_bot_explanation": dashboard_bot_explanation,
    }


def render_markdown(report: dict[str, Any]) -> str:
    proc = report["process"]
    market = report["market"]
    lines = [
        "# TAE Market Open Monitor",
        "",
        f"**Verdict:** {report['verdict']}",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Market open: **{market.get('open_markets', [])}**",
        f"- Bot: **{proc['bot_effective']}** (pid={proc['bot_pid']}, alive={proc['bot_pid_alive']})",
        f"- Dashboard: **{proc['dashboard_effective']}** (port8501={proc['dashboard_port_8501_open']})",
        f"- DRY_RUN live mode: **{report['dry_run']['is_live_mode']}** (source={report['dry_run']['source']})",
        f"- Session guard last run: {report['session_guard'].get('last_run_timestamp')}",
        f"- Startup runner last run: {report['startup_runner'].get('last_timestamp')}",
        "",
        "## Q&A",
        "",
    ]
    for key, value in report["answers"].items():
        lines.append(f"- **{key}**: {value}")

    if report.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for item in report["warnings"]:
            lines.append(f"- {item}")

    if report.get("notes"):
        lines.extend(["", "## Notes", ""])
        for item in report["notes"]:
            lines.append(f"- {item}")

    lines.extend(["", "## Sleep / Wake Readiness", ""])
    for key, value in report["sleep_wake_readiness"].items():
        lines.append(f"- {key}: {value}")

    return "\n".join(lines) + "\n"


def print_terminal_summary(report: dict[str, Any]) -> None:
    proc = report["process"]
    market = report["market"]
    x9 = report["x9_ledger"]
    guard = report["session_guard"]
    print("===== TAE MARKET OPEN MONITOR =====")
    print(f"Session guard: last={guard.get('last_run_timestamp')} reason={guard.get('session', {}).get('start_reason', 'UNKNOWN')}")
    print(f"DRY_RUN: live_mode={report['dry_run']['is_live_mode']} source={report['dry_run']['source']}")
    print(f"Bot: {proc['bot_effective']} pid={proc['bot_pid']} alive={proc['bot_pid_alive']} pgrep={proc['bot_pgrep_pids']}")
    print(f"Dashboard: {proc['dashboard_effective']} port8501={proc['dashboard_port_8501_open']}")
    open_mkts = market.get("open_markets") or []
    print(f"Market: open={open_mkts if open_mkts else 'NONE'} any_open={market.get('any_open')}")
    sig = report["signals"]
    print(f"Signals: recent={sig['live_signals_recent']} age_s={sig['live_signals_age_seconds']}")
    print(f"X.9: present={x9['present']} count={x9['count']} age_s={x9.get('age_seconds')}")
    print(f"Verdict: {report['verdict']}")
    if report.get("dashboard_without_bot_explanation"):
        print(f"Note: {report['dashboard_without_bot_explanation']}")


def main() -> int:
    report = build_monitor_report()
    OUTPUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    print_terminal_summary(report)
    return 0 if report["verdict"] in {"PASS", "WAITING_FOR_MARKET_OPEN"} else 1


if __name__ == "__main__":
    sys.exit(main())
