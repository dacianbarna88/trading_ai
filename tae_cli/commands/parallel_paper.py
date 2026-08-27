#!/usr/bin/env python3
"""TAE CLI — parallel-paper commands (start/run-once/health/report/stop)."""

from __future__ import annotations

import json
from typing import Any


def _print(obj: Any) -> None:
    if isinstance(obj, dict):
        print(json.dumps(obj, indent=2, sort_keys=True, default=str))
    else:
        print(obj)


def run_start(_args: list[str] | None = None) -> int:
    """Start persistent runtime only — never runs a decision cycle."""
    from tae_parallel_paper_runtime import bootstrap, health_snapshot, start_runtime

    print("===== TAE PARALLEL-PAPER-START — PERSISTENT RUNTIME =====")
    print("Mode: PAPER_ONLY | NO_BROKER | NO_LIVE | no implicit cycle")
    boot = bootstrap()
    st = start_runtime(spawn_daemon=True)
    if st.get("duplicate"):
        print("DUPLICATE_BLOCKED pid", st.get("pid"))
        _print(st)
        return 2
    if not st.get("ok"):
        _print(st)
        return 1
    h = health_snapshot()
    pid = st.get("pid")
    if pid is None and isinstance(st.get("status"), dict):
        pid = st["status"].get("pid")
    print("bootstrap_ok", boot.get("ok"))
    print("start_ok", st.get("ok"))
    print("pid", pid)
    print("runtime_running", h.get("runtime_running"))
    print("pid_alive", h.get("pid_alive"))
    print("heartbeat_fresh", h.get("heartbeat_fresh"))
    print("overall_status", h.get("overall_status"))
    print("LIVE", h.get("V2_LIVE_ENABLED"))
    return 0 if st.get("ok") and h.get("pid_alive") else 1


def run_once(_args: list[str] | None = None) -> int:
    """Explicit single cycle — not a persistent start."""
    from tae_parallel_paper_runtime import run_cycle

    print("===== TAE PARALLEL-PAPER-RUN-ONCE =====")
    c = run_cycle()
    print("ok", c.get("ok"), "snapshot", c.get("snapshot_id"))
    print(
        "acct_v1",
        c.get("accounting_v1", {}).get("reconciliation_pass"),
        "acct_v2",
        c.get("accounting_v2", {}).get("reconciliation_pass"),
    )
    print("divergences", len(c.get("divergences") or []))
    return 0 if c.get("ok") else 1


def run_health(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_autostart import status_autostart
    from tae_parallel_paper_runtime import health_snapshot

    print("===== TAE PARALLEL-PAPER-HEALTH =====")
    h = health_snapshot()
    h["autostart"] = status_autostart()
    _print(h)
    ok_states = {
        "RUNNING_HEALTHY",
        "RUNNING_HEARTBEAT_STALE",
        "STOPPED_HEALTHY_STATE",
        "STOPPED_CLEAN",
        "STOPPED_STALE_STATE",
        "RUNNING_DEGRADED",
        "DEGRADED_V1",
        "DEGRADED_V2",
        "DEGRADED_ACCOUNTING",
        "HEALTHY",
    }
    return 0 if h.get("overall_status") in ok_states or h.get("status") in ok_states else 1


def run_report(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_reports import generate_daily_report

    print("===== TAE PARALLEL-PAPER-REPORT =====")
    force = bool(_args and "--force" in _args)
    rep = generate_daily_report(force=force)
    print("date", rep.get("date"), "verdict", rep.get("executive_conclusion", {}).get("verdict"))
    print("report", rep.get("paths", {}).get("md"))
    print("accounting", rep.get("accounting_status"))
    return 0 if rep.get("accounting_status") == "PASS" else 1


def run_report_3way(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_reports import generate_three_way_report

    print("===== TAE PARALLEL-PAPER-REPORT-3WAY (V1/V2/V3) =====")
    force = bool(_args and "--force" in _args)
    rep = generate_three_way_report(force=force)
    verdict = rep.get("executive_conclusion", {})
    print("date", rep.get("date"), "arms", rep.get("arms_present"))
    print("verdict", verdict.get("verdict"), "winner", verdict.get("winner"), "ranked", verdict.get("ranked"))
    print("disagreements", rep.get("disagreement_count"))
    print("report", rep.get("paths", {}).get("md"))
    return 0


def run_stop(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_runtime import stop_runtime

    print("===== TAE PARALLEL-PAPER-STOP =====")
    st = stop_runtime(remove_enabled_flag=True)
    _print(st)
    return 0 if st.get("ok") else 1


def run_cycle_cmd(_args: list[str] | None = None) -> int:
    """Alias of run-once for backward compatibility."""
    return run_once(_args)


def run_autostart_install(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_autostart import install_autostart

    print("===== TAE PARALLEL-PAPER-AUTOSTART-INSTALL — PAPER ONLY =====")
    st = install_autostart()
    _print(st)
    return 0 if st.get("ok") else 1


def run_autostart_status(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_autostart import status_autostart

    print("===== TAE PARALLEL-PAPER-AUTOSTART-STATUS =====")
    st = status_autostart()
    _print(st)
    return 0


def run_autostart_remove(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_autostart import remove_autostart

    print("===== TAE PARALLEL-PAPER-AUTOSTART-REMOVE =====")
    st = remove_autostart()
    _print(st)
    return 0 if st.get("ok") else 1
