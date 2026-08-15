"""TAE CLI — lightweight status command (stdlib only)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(".")


def _run(cmd: list[str], *, timeout: float = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _git_branch() -> str:
    if shutil.which("git") is None:
        return "GIT_UNAVAILABLE"
    result = _run(["git", "branch", "--show-current"])
    if result.returncode != 0:
        return "UNKNOWN"
    return (result.stdout or "").strip() or "UNKNOWN"


def _git_latest_commit() -> str:
    if shutil.which("git") is None:
        return "GIT_UNAVAILABLE"
    result = _run(["git", "log", "-1", "--oneline"])
    if result.returncode != 0:
        return "UNKNOWN"
    return (result.stdout or "").strip() or "UNKNOWN"


def _git_clean() -> str:
    if shutil.which("git") is None:
        return "GIT_UNAVAILABLE"
    result = _run(["git", "status", "--short"])
    if result.returncode != 0:
        return "UNKNOWN"
    return "CLEAN" if not (result.stdout or "").strip() else "DIRTY"


def _process_running(pattern: str) -> bool:
    if shutil.which("pgrep") is None:
        return False
    try:
        result = _run(["pgrep", "-fl", pattern], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if not (result.stdout or "").strip():
        return False
    if pattern == "live_bot.py":
        return any("live_bot.py" in line for line in result.stdout.splitlines())
    return True


def _dashboard_running() -> bool:
    if _process_running("streamlit") or _process_running("dashboard_v2"):
        return True
    if shutil.which("lsof") is None:
        return False
    for port in (8501, 8502, 8503):
        try:
            result = _run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and (result.stdout or "").strip():
            return True
    return False


def run(_args: list[str] | None = None) -> int:
    branch = _git_branch()
    commit = _git_latest_commit()
    git_state = _git_clean()
    bot = "yes" if _process_running("live_bot.py") else "no"
    dashboard = "yes" if _dashboard_running() else "no"

    print("===== TAE STATUS =====")
    print(f"current git branch: {branch}")
    print(f"latest commit: {commit}")
    print(f"git dirty / clean: {git_state}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"bot running yes/no: {bot}")
    print(f"dashboard running yes/no: {dashboard}")
    print("")
    return 0
