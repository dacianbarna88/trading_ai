#!/usr/bin/env python3
"""
TAE runtime lifecycle helpers — LaunchAgent KeepAlive ownership for live_bot + dashboard.

Infrastructure only. Does not modify trading economics, BUY/SELL, capital, or ledgers.
Market session still gates executions inside live_bot; process liveness is independent.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

LIVE_BOT_LABEL = "com.tradingai.live-bot"
DASHBOARD_LABEL = "com.tradingai.dashboard"
PARALLEL_LABEL = "com.tradingai.parallel-paper"

LIVE_ENABLED = PROJECT_DIR / "runtime_outputs" / "live_runtime" / "daemon_enabled"
DASHBOARD_ENABLED = PROJECT_DIR / "runtime_outputs" / "dashboard" / "daemon_enabled"


def _domain() -> str:
    return f"gui/{os.getuid()}"


def ensure_keepalive_flags() -> dict[str, bool]:
    """Ensure PathState enable files exist so KeepAlive stays active."""
    LIVE_ENABLED.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_ENABLED.parent.mkdir(parents=True, exist_ok=True)
    created = {}
    for path in (LIVE_ENABLED, DASHBOARD_ENABLED):
        if not path.exists():
            path.write_text("1\n", encoding="utf-8")
            created[str(path)] = True
        else:
            created[str(path)] = False
    return created


def launchd_agent_loaded(label: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", f"{_domain()}/{label}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def launchd_keepalive_active(label: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", f"{_domain()}/{label}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    text = result.stdout or ""
    # PathState KeepAlive shows as keepalive = path / ... or "keep alive = path"
    lowered = text.lower()
    return "keepalive" in lowered or "keep alive" in lowered or "path state" in lowered


def live_bot_lifecycle_owned_by_launchd() -> bool:
    return launchd_agent_loaded(LIVE_BOT_LABEL) and LIVE_ENABLED.exists()


def dashboard_lifecycle_owned_by_launchd() -> bool:
    return launchd_agent_loaded(DASHBOARD_LABEL) and DASHBOARD_ENABLED.exists()


def kickstart_agent(label: str, *, kill: bool = False) -> dict:
    """Ask launchd to (re)start the agent. Prefer non-kill for soft recovery."""
    target = f"{_domain()}/{label}"
    ensure_keepalive_flags()
    subprocess.run(["launchctl", "enable", target], capture_output=True, check=False)
    cmd = ["launchctl", "kickstart"]
    if kill:
        cmd.append("-k")
    cmd.append(target)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "label": label,
        "rc": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "kill": kill,
    }


def ensure_live_bot_via_launchd(*, dry_run: bool = False) -> dict:
    ensure_keepalive_flags()
    if not launchd_agent_loaded(LIVE_BOT_LABEL):
        return {"ok": False, "reason": "agent_not_loaded", "label": LIVE_BOT_LABEL}
    if dry_run:
        return {"ok": True, "reason": "DRY_RUN would kickstart", "label": LIVE_BOT_LABEL}
    return {"ok": True, "reason": "kickstart", **kickstart_agent(LIVE_BOT_LABEL, kill=False)}


def ensure_dashboard_via_launchd(*, dry_run: bool = False) -> dict:
    ensure_keepalive_flags()
    if not launchd_agent_loaded(DASHBOARD_LABEL):
        return {"ok": False, "reason": "agent_not_loaded", "label": DASHBOARD_LABEL}
    if dry_run:
        return {"ok": True, "reason": "DRY_RUN would kickstart", "label": DASHBOARD_LABEL}
    return {"ok": True, "reason": "kickstart", **kickstart_agent(DASHBOARD_LABEL, kill=False)}
