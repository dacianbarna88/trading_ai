#!/usr/bin/env python3
"""
TAE INFRA-1 — Lightweight Quick Health Check

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Standalone read-only health check using Python standard library only.
Does not import research_core or pandas.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import deque
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(".")
REPORT_JSON = ROOT / "tae_quick_health_check.json"
REPORT_TXT = ROOT / "tae_quick_health_check.txt"
SCHEMA_NAME = "tae_quick_health_check"

KEY_FILES = (
    "live_bot.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
)

LOG_FILES = (
    "bot_output.log",
    "market_open_runner.log",
    "startup_runner.log",
    "dashboard_output.log",
)

DASHBOARD_PORTS = (8501, 8502, 8503)
LOG_TAIL_LINES = 200
TIMESTAMP_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _now_iso() -> str:
    return _now_local().isoformat()


def _run(cmd: list[str], *, cwd: Path = ROOT, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _process_detected(pattern: str) -> bool:
    if shutil.which("pgrep") is None:
        return False
    try:
        result = _run(["pgrep", "-fl", pattern], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if not (result.stdout or "").strip():
        return False
    # Avoid matching unrelated processes that merely contain substring "live_bot"
    if pattern == "live_bot.py":
        return any("live_bot.py" in line for line in result.stdout.splitlines())
    return True


def _dashboard_port_status() -> int | None:
    if shutil.which("lsof") is None:
        return None
    for port in DASHBOARD_PORTS:
        try:
            result = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and (result.stdout or "").strip():
            return port
    return None


def _file_status(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {"exists": False, "size_bytes": None, "modified": None, "age_hours": None}
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).astimezone()
    age_hours = (_now_local() - mtime).total_seconds() / 3600
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "modified": mtime.isoformat(),
        "age_hours": round(age_hours, 1),
    }


def _read_log_tail(path: Path, max_lines: int = LOG_TAIL_LINES) -> list[str]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return list(deque(handle, maxlen=max_lines))
    except OSError:
        return []


def _latest_timestamp_line(lines: list[str]) -> str | None:
    for line in reversed(lines):
        match = TIMESTAMP_RE.search(line)
        if match:
            return match.group(1)
    return None


def _activity_is_today(timestamp_text: str | None, today: date) -> bool:
    if not timestamp_text:
        return False
    try:
        parsed = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return parsed.date() == today


def _find_latest_matching(lines: list[str], needle: str) -> str | None:
    for line in reversed(lines):
        if needle in line:
            return line.strip()
    return None


def _autostart_evidence(today: date) -> dict[str, object]:
    startup_lines = _read_log_tail(ROOT / "startup_runner.log", max_lines=500)
    market_lines = _read_log_tail(ROOT / "market_open_runner.log", max_lines=500)

    startup_complete = _find_latest_matching(startup_lines, "STARTUP COMPLETE")
    market_activity = _find_latest_matching(market_lines, "Market") or (
        market_lines[-1].strip() if market_lines else None
    )

    startup_today = False
    for line in reversed(startup_lines):
        if "Timestamp:" in line:
            match = re.search(r"Timestamp:\s*(\d{4}-\d{2}-\d{2})", line)
            if match:
                try:
                    startup_today = date.fromisoformat(match.group(1)) == today
                except ValueError:
                    pass
            break

    present = bool(startup_complete) or bool(market_lines)
    today_evidence = startup_today or any(
        f"{today.isoformat()}" in line for line in startup_lines[-50:]
    ) or any(f"{today.isoformat()}" in line for line in market_lines[-50:])

    return {
        "startup_complete_line": startup_complete,
        "startup_today": startup_today,
        "market_open_latest": market_activity,
        "present": present,
        "today": today_evidence,
    }


def _git_status() -> dict[str, str]:
    if shutil.which("git") is None:
        return {"classification": "GIT_UNAVAILABLE", "short": "GIT_UNAVAILABLE"}
    try:
        result = _run(["git", "status", "--short"], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {"classification": "GIT_ERROR", "short": "GIT_ERROR"}
    if result.returncode != 0:
        return {"classification": "NOT_A_REPOSITORY", "short": "NOT_A_REPOSITORY"}
    output = (result.stdout or "").strip()
    if not output:
        return {"classification": "CLEAN", "short": "CLEAN"}
    compact = output.replace("\n", "; ")[:500]
    return {"classification": "DIRTY", "short": compact}


def _compute_verdict(
    *,
    bot_running: bool,
    activity_today: bool,
    autostart_today: bool,
    git_classification: str,
) -> str:
    if not bot_running or not activity_today:
        return "NOT_READY"
    if not autostart_today or git_classification == "DIRTY":
        return "WARNING"
    return "READY"


def _format_text(report: dict[str, object]) -> str:
    lines = [
        "===== TAE QUICK HEALTH CHECK =====",
        "",
        f"timestamp: {report['timestamp']}",
        "",
        "process status:",
        f"  python: {report['python_executable']} ({report['python_version']})",
        f"  live_bot: {report['process_status']['live_bot']}",
        f"  streamlit/dashboard: {report['process_status']['dashboard']}",
        "",
        "key file status:",
    ]
    for name, status in report["key_files"].items():
        exists = "OK" if status["exists"] else "MISSING"
        lines.append(f"  {name}: {exists}")
    lines.extend(["", "log status:"])
    for name, status in report["log_files"].items():
        if not status["exists"]:
            lines.append(f"  {name}: MISSING")
        else:
            lines.append(
                f"  {name}: {status['size_bytes']} bytes, "
                f"modified {status['modified']} ({status['age_hours']}h ago)"
            )
    lines.extend([
        "",
        "recent activity:",
        f"  latest_timestamp: {report['recent_activity']['latest_timestamp'] or 'none'}",
        f"  activity_today: {report['recent_activity']['activity_today']}",
        "",
        "market/advisory evidence:",
        f"  market_sessions_open: {report['evidence']['market_sessions_open'] or 'none'}",
        f"  buy_executat: {report['evidence']['buy_executat'] or 'none'}",
        f"  tae_live_advisory: {report['evidence']['tae_live_advisory'] or 'none'}",
        "",
        "git status:",
        f"  classification: {report['git']['classification']}",
        f"  detail: {report['git']['short']}",
        "",
        f"final verdict: {report['verdict']}",
        "",
        "Read-only lightweight health check — no bot start/stop, no execution.",
        "",
    ])
    return "\n".join(lines)


def run_health_check() -> dict[str, object]:
    today = _now_local().date()
    bot_running = _process_detected("live_bot.py")
    dashboard_port = _dashboard_port_status()
    streamlit_running = _process_detected("streamlit") or _process_detected("dashboard_v2")
    if dashboard_port or streamlit_running:
        dashboard_status = (
            f"RUNNING (port {dashboard_port})" if dashboard_port else "RUNNING (process detected)"
        )
    else:
        dashboard_status = "NOT DETECTED"

    key_files = {name: _file_status(ROOT / name) for name in KEY_FILES}
    log_files = {name: _file_status(ROOT / name) for name in LOG_FILES}

    bot_tail = _read_log_tail(ROOT / "bot_output.log")
    latest_ts = _latest_timestamp_line(bot_tail)
    activity_today = _activity_is_today(latest_ts, today)

    evidence = {
        "market_sessions_open": _find_latest_matching(bot_tail, "Market sessions OPEN"),
        "buy_executat": _find_latest_matching(bot_tail, "BUY executat"),
        "tae_live_advisory": _find_latest_matching(bot_tail, "TAE Live Advisory"),
    }

    autostart = _autostart_evidence(today)
    git = _git_status()
    verdict = _compute_verdict(
        bot_running=bot_running,
        activity_today=activity_today,
        autostart_today=bool(autostart["today"]),
        git_classification=git["classification"],
    )

    return {
        "version": 2,
        "schema": SCHEMA_NAME,
        "timestamp": _now_iso(),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "process_status": {
            "live_bot": "RUNNING" if bot_running else "NOT DETECTED",
            "dashboard": dashboard_status,
        },
        "key_files": key_files,
        "log_files": log_files,
        "recent_activity": {
            "lines_scanned": len(bot_tail),
            "latest_timestamp": latest_ts,
            "activity_today": activity_today,
        },
        "evidence": evidence,
        "autostart": autostart,
        "git": git,
        "verdict": verdict,
    }


def persist(report: dict[str, object]) -> tuple[Path, Path]:
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    REPORT_TXT.write_text(_format_text(report) + "\n", encoding="utf-8")
    return REPORT_JSON, REPORT_TXT


def main() -> int:
    report = run_health_check()
    json_path, txt_path = persist(report)
    print(_format_text(report))
    print(f"Reports: {json_path}, {txt_path}")
    return 1 if report["verdict"] == "NOT_READY" else 0


if __name__ == "__main__":
    sys.exit(main())
