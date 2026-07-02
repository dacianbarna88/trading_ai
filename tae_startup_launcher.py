#!/usr/bin/env python3
"""
TAE startup launcher for LaunchAgent — avoids macOS TCC blocking bash .sh on Desktop.

Infrastructure only. Does not modify trading logic.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON_BIN = PROJECT_DIR / "venv" / "bin" / "python3"
LOG_FILE = PROJECT_DIR / "startup_runner.log"
AWAKE_PID_FILE = PROJECT_DIR / "awake_guard.pid"
AWAKE_LOG = PROJECT_DIR / "awake_guard.log"


def log(lines: list[str], *, echo_stdout: bool = False) -> None:
    text = "\n".join(lines) + "\n"
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(text)
    if echo_stdout:
        print(text, end="")


def pgrep_count(pattern: str) -> int:
    result = subprocess.run(
        ["pgrep", "-f", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def ensure_awake_guard() -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"[{timestamp}] AWAKE GUARD (launcher)"]
    if AWAKE_PID_FILE.is_file():
        old_pid = AWAKE_PID_FILE.read_text(encoding="utf-8").strip()
        if old_pid and subprocess.run(["ps", "-p", old_pid], capture_output=True, check=False).returncode == 0:
            lines.append(f"Already running PID: {old_pid}")
            with AWAKE_LOG.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            return
        AWAKE_PID_FILE.unlink(missing_ok=True)
        lines.append(f"Stale PID removed: {old_pid}")
    proc = subprocess.Popen(
        ["caffeinate", "-d", "-i", "-m"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    AWAKE_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    lines.extend([f"Started caffeinate PID: {proc.pid}", "Status: ACTIVE"])
    with AWAKE_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run_market_session_guard(guard_args: list[str]) -> None:
    python = PYTHON_BIN if PYTHON_BIN.is_file() and os.access(PYTHON_BIN, os.X_OK) else Path(sys.executable)
    cmd = [str(python), str(PROJECT_DIR / "market_session_guard.py"), *guard_args]
    subprocess.run(cmd, cwd=str(PROJECT_DIR), check=False)


def main() -> int:
    os.chdir(PROJECT_DIR)
    for key in ("DRY_RUN", "TAE_DRY_RUN", "MARKET_GUARD_DRY_RUN"):
        os.environ.pop(key, None)

    guard_args: list[str] = []
    if os.getenv("STARTUP_DRY_RUN", "0") == "1" or "--dry-run" in sys.argv[1:]:
        guard_args.append("--dry-run")

    scheduler = os.getenv("TAE_SCHEDULER_SOURCE", "manual")
    header = [
        "",
        "===== TRADING AI STARTUP RUNNER =====",
        f"Timestamp: {datetime.now()}",
        f"Reason: {scheduler}_startup",
        f"PROJECT_DIR: {PROJECT_DIR}",
        "Launcher: tae_startup_launcher.py",
        "DRY_RUN: disabled (live startup default)",
        f"GUARD_ARGS: {' '.join(guard_args) if guard_args else 'none'}",
        "",
        "[1/3] Starting Awake Guard...",
    ]
    ensure_awake_guard()
    header.append("OK")
    header.extend(["", "[2/3] Market Session Guard pre-check..."])

    bot_running = pgrep_count("live_bot.py") > 0
    dash_running = pgrep_count("streamlit run dashboard_v2.py") > 0
    if bot_running:
        header.append("STARTUP: live_bot already running")
    if dash_running:
        header.append("STARTUP: dashboard already running")

    if bot_running and dash_running:
        header.append("STARTUP: skipping market_session_guard (bot and dashboard already up)")
    else:
        if not bot_running:
            header.append("STARTUP: starting live_bot via market_session_guard")
        if not dash_running:
            header.append("STARTUP: starting dashboard via market_session_guard")
        run_market_session_guard(guard_args)

    header.extend(["", "[3/3] Startup status..."])
    for name, label in (("bot_pid.txt", "Bot PID"), ("bot_status.txt", "Bot Status"), ("dashboard_status.txt", "Dashboard Status")):
        path = PROJECT_DIR / name
        header.append(f"{label}: {path.read_text(encoding='utf-8').strip() if path.is_file() else 'MISSING'}")
    header.extend(
        [
            "",
            "Mode: ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
            "===== STARTUP COMPLETE =====",
        ]
    )
    log(header, echo_stdout=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
