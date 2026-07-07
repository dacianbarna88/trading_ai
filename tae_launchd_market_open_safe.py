#!/usr/bin/env python3
"""
TAE LaunchAgent-safe market-open launcher — infrastructure only.

Invoked by com.tradingai.market-open via framework Python (not venv).
macOS launchd cannot execute Desktop .sh files (TCC exit 126); Python entry works.
Manual operator use: /bin/bash tae_launchd_market_open_safe.sh
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LOG_FILE = PROJECT_DIR / "tae_launchd_market_open_safe.log"
ERR_FILE = PROJECT_DIR / "tae_launchd_market_open_safe.err.log"
FRAMEWORK_PYTHON = Path("/Library/Frameworks/Python.framework/Versions/3.14/bin/python3")


def _ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _log(msg: str) -> None:
    line = f"[{_ts()}] {msg}"
    _append(LOG_FILE, line)
    print(line)


def _log_err(msg: str) -> None:
    line = f"[{_ts()}] {msg}"
    _append(ERR_FILE, line)
    print(line, file=sys.stderr)


def _run(label: str, cmd: list[str]) -> int:
    _log(f"CMD [{label}]: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), check=False)
    _log(f"EXIT_CODE [{label}]: {result.returncode}")
    return int(result.returncode)


def _pgrep_lines(pattern: str) -> list[str]:
    result = subprocess.run(
        ["pgrep", "-fl", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if pattern == "live_bot.py":
        return [line for line in lines if "live_bot.py" in line and "pgrep" not in line]
    if "streamlit run dashboard_v2.py" in pattern:
        return [line for line in lines if "streamlit run dashboard_v2.py" in line and "pgrep" not in line]
    return lines


def _pgrep_count(pattern: str) -> int:
    return len(_pgrep_lines(pattern))


def _resolve_python() -> Path:
    if FRAMEWORK_PYTHON.is_file() and os.access(FRAMEWORK_PYTHON, os.X_OK):
        return FRAMEWORK_PYTHON
    return Path(sys.executable)


def _xattr(path: Path) -> str:
    result = subprocess.run(["xattr", "-l", str(path)], capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr or "").strip() or "none"


def main() -> int:
    os.chdir(PROJECT_DIR)
    os.environ["PATH"] = "/Library/Frameworks/Python.framework/Versions/3.14/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    os.environ["TAE_SCHEDULER_SOURCE"] = "launchd"

    python = _resolve_python()
    _log("===== TAE LAUNCHD MARKET OPEN SAFE (python entry) =====")
    _log(f"whoami={os.getenv('USER')} pid={os.getpid()} ppid={os.getppid()}")
    _log(f"pwd={PROJECT_DIR}")
    _log(f"PYTHON={python} version={sys.version.split()[0]}")
    _log(f"python_xattr={_xattr(python)}")
    venv = PROJECT_DIR / "venv/bin/python3"
    if venv.is_file():
        _log(f"venv_xattr={_xattr(venv)}")

    bot_count = _pgrep_count("live_bot.py")
    dash_count = _pgrep_count("streamlit run dashboard_v2.py")
    _log(f"pre_run bot_count={bot_count} dashboard_count={dash_count}")

    if (PROJECT_DIR / "awake_guard.sh").is_file():
        _run("awake_guard", ["/bin/bash", str(PROJECT_DIR / "awake_guard.sh")])

    bot_count = _pgrep_count("live_bot.py")
    if bot_count > 1:
        _log_err(f"WARN duplicate live_bot count={bot_count} — not starting another")
    elif bot_count == 0:
        ec = _run("bot_controller_start", [str(python), str(PROJECT_DIR / "bot_controller.py"), "start", "--force"])
        if ec != 0:
            _log_err(f"ERROR bot_controller start exit={ec}")
            return 78
    else:
        _log("SKIP live_bot already running")

    dash_count = _pgrep_count("streamlit run dashboard_v2.py")
    if dash_count > 1:
        _log_err(f"WARN duplicate dashboard count={dash_count}")
    elif dash_count == 0:
        ec = _run(
            "bot_controller_dashboard",
            [str(python), str(PROJECT_DIR / "bot_controller.py"), "start-dashboard", "--force"],
        )
        if ec != 0:
            _log_err(f"ERROR bot_controller start-dashboard exit={ec}")
            return 78
    else:
        _log("SKIP dashboard already running")

    optional = (
        ("market_open_intelligence", [str(python), str(PROJECT_DIR / "tae_market_open_intelligence_runner.py")]),
        ("morning_update", [str(python), str(PROJECT_DIR / "morning_update.py")]),
        ("daily_intelligence", [str(python), str(PROJECT_DIR / "daily_intelligence_runner.py")]),
        ("market_session_guard", [str(python), str(PROJECT_DIR / "market_session_guard.py")]),
    )
    for label, cmd in optional:
        if not Path(cmd[1]).is_file():
            continue
        if label == "market_open_intelligence" and _pgrep_count("tae_market_open_intelligence_runner.py"):
            _log("SKIP intelligence runner already running")
            continue
        ec = _run(label, cmd)
        if ec != 0:
            _log_err(f"WARN {label} exit={ec} — non-fatal")

    bot_count = _pgrep_count("live_bot.py")
    dash_count = _pgrep_count("streamlit run dashboard_v2.py")
    _log(f"post_run bot_count={bot_count} dashboard_count={dash_count}")

    for name in ("bot_status.txt", "dashboard_status.txt", "bot_pid.txt", "dashboard_pid.txt"):
        path = PROJECT_DIR / name
        _log(f"{name}={path.read_text(encoding='utf-8').strip() if path.is_file() else 'MISSING'}")

    proc = subprocess.run(["pgrep", "-fl", "live_bot.py"], capture_output=True, text=True, check=False)
    _log(f"pgrep live_bot: {(proc.stdout or 'none').strip()}")
    proc = subprocess.run(
        ["pgrep", "-fl", "streamlit run dashboard_v2.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    _log(f"pgrep dashboard: {(proc.stdout or 'none').strip()}")

    bot_lines = _pgrep_lines("live_bot.py")
    dash_lines = _pgrep_lines("streamlit run dashboard_v2.py")
    bot_count = len(bot_lines)
    dash_count = len(dash_lines)

    if bot_count > 1:
        _log_err(f"FAIL duplicate live_bot count={bot_count}")
        return 78
    if bot_count < 1:
        _log_err("FAIL live_bot not running")
        return 78
    if dash_count < 1:
        _log_err("FAIL dashboard not running")
        return 78

    _log("RESULT: PASS — bot and dashboard running")
    _log("===== END TAE LAUNCHD MARKET OPEN SAFE =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
