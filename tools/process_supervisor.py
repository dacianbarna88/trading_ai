#!/usr/bin/env python3
"""
TAE OPS 1 — Process Supervisor

Infrastructure only. Stdlib only.
Validates bot_pid.txt / bot_status.txt against live process state.
No broker. No execution. No trading or research logic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "bot_pid.txt"
STATUS_FILE = PROJECT_ROOT / "bot_status.txt"
HEALTH_FILE = PROJECT_ROOT / "process_health.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid_file() -> int | None:
    if not PID_FILE.is_file():
        return None
    try:
        raw = PID_FILE.read_text(encoding="utf-8").strip()
        return int(raw)
    except (OSError, ValueError):
        return None


def _remove_pid_file() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _write_status(status: str) -> None:
    STATUS_FILE.write_text(status + "\n", encoding="utf-8")


def _write_health(payload: dict) -> None:
    HEALTH_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _collect_stats(pid: int) -> dict[str, object]:
    """Best-effort CPU, memory, and uptime via ps (stdlib subprocess)."""
    stats: dict[str, object] = {"pid": pid}
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "etime=,%cpu=,%mem="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            if len(parts) >= 3:
                stats["uptime"] = parts[0]
                stats["cpu"] = round(float(parts[1]), 2)
                stats["memory"] = round(float(parts[2]), 2)
            elif len(parts) == 2:
                stats["cpu"] = round(float(parts[0]), 2)
                stats["memory"] = round(float(parts[1]), 2)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return stats


def _handle_stale_pid() -> str:
    _remove_pid_file()
    _write_status("STOPPED")
    payload = {
        "status": "STOPPED",
        "reason": "stale pid removed",
        "checked_at": _utc_now(),
    }
    _write_health(payload)
    return "STALE_PID_REMOVED"


def supervise() -> str:
    """Run one supervision cycle. Returns CLI status token."""
    os.chdir(PROJECT_ROOT)
    checked_at = _utc_now()
    pid = _read_pid_file()

    if pid is None:
        if PID_FILE.is_file():
            return _handle_stale_pid()

        _write_status("STOPPED")
        payload = {
            "status": "STOPPED",
            "reason": "no pid file",
            "checked_at": checked_at,
        }
        _write_health(payload)
        return "STOPPED"

    if not _pid_alive(pid):
        return _handle_stale_pid()

    stats = _collect_stats(pid)
    _write_status("RUNNING")
    payload: dict[str, object] = {
        "status": "RUNNING",
        "pid": pid,
        "checked_at": checked_at,
    }
    for key in ("cpu", "memory", "uptime"):
        if key in stats:
            payload[key] = stats[key]

    _write_health(payload)
    return "RUNNING"


def main() -> int:
    result = supervise()
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
