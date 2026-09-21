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


def run_short_margin_once(_args: list[str] | None = None) -> int:
    """Explicit single cycle for the new isolated short/margin arm
    (exp_short_margin). Self-contained — does not touch V1/V2/V3."""
    from tae_parallel_paper_short_margin import run_short_margin_cycle

    print("===== TAE PARALLEL-PAPER-RUN-SHORT-MARGIN-ONCE =====")
    c = run_short_margin_cycle()
    print("arm", c.get("arm"))
    print("account_value", c.get("account_value"), "cash", c.get("cash"))
    print("open_shorts", c.get("open_shorts"), "margin_utilization_pct", c.get("margin_utilization_pct"))
    print("reconciliation_pass", c.get("reconciliation_pass"))
    return 0 if c.get("reconciliation_pass") else 1


def run_mean_reversion_once(_args: list[str] | None = None) -> int:
    """Explicit single cycle for the new isolated mean-reversion arm
    (exp_mean_reversion). Self-contained — does not touch V1/V2/V3/
    exp_short_margin."""
    from tae_parallel_paper_mean_reversion import run_mean_reversion_cycle

    print("===== TAE PARALLEL-PAPER-RUN-MEAN-REVERSION-ONCE =====")
    c = run_mean_reversion_cycle()
    print("arm", c.get("arm"))
    print("account_value", c.get("account_value"), "cash", c.get("cash"))
    print("open_positions", c.get("open_positions"))
    print("reconciliation_pass", c.get("reconciliation_pass"))
    return 0 if c.get("reconciliation_pass") else 1


def run_quality_longterm_once(_args: list[str] | None = None) -> int:
    """Explicit single cycle for the new isolated long-horizon accounting-
    quality arm (exp_quality_longterm). Self-contained — does not touch
    V1/V2/V3/exp_short_margin/exp_mean_reversion. Most hourly invocations
    are mark-to-market only; the real monthly rebalance logic self-gates
    on the arm's own last_rebalance_at timestamp."""
    from tae_parallel_paper_quality_longterm import run_quality_longterm_cycle

    print("===== TAE PARALLEL-PAPER-RUN-QUALITY-LONGTERM-ONCE =====")
    c = run_quality_longterm_cycle()
    print("arm", c.get("arm"), "rebalanced", c.get("rebalanced"))
    print("account_value", c.get("account_value"), "cash", c.get("cash"))
    print("open_positions", c.get("open_positions"))
    print("reconciliation_pass", c.get("reconciliation_pass"))
    return 0 if c.get("reconciliation_pass") else 1


def _retired_autostart_status() -> dict[str, Any]:
    """Status only for the retired com.tradingai.parallel-paper LaunchAgent.

    Bug found 2026-09-21: this used to import a dedicated
    tae_parallel_paper_autostart module, which does not exist on main --
    it only ever existed on an unmerged branch (cursor/x12b-legacy-archive-
    hotfix) -- so every call here raised ModuleNotFoundError. Recreating
    that module is explicitly wrong: tae_canonical_dual_strategy_test.py's
    test_01_no_daemon_module_required() asserts
    tae_parallel_paper_autostart.py must NOT exist, as a guard against
    accidentally restoring the daemon path retired 2026-08-03 (see
    ~/Library/LaunchAgents/disabled_trading_ai/
    com.tradingai.parallel-paper.RETIREMENT_MANIFEST.20260803T164137Z.json
    -- classification RETIRE_LEGACY_ORPHAN, "do_not_accidental_restore":
    true). Real automation today is the shared hourly cron job instead
    (com.tradingai.hourly-refresh -> tae_hourly_refresh.sh ->
    'tae.py parallel-paper-run-once'). This inline helper reports that
    honestly, with no install/remove capability for the retired
    LaunchAgent -- restoring it requires a dedicated sprint per the
    manifest's own restore_prerequisites, not a CLI health check.
    """
    import subprocess
    from pathlib import Path

    hourly_plist = Path.home() / "Library" / "LaunchAgents" / "com.tradingai.hourly-refresh.plist"
    try:
        proc = subprocess.run(["launchctl", "list"], capture_output=True, text=True, check=False)
        hourly_listed = "com.tradingai.hourly-refresh" in (proc.stdout or "")
    except OSError:
        hourly_listed = False
    return {
        "ok": True,
        "retired_label": "com.tradingai.parallel-paper",
        "retired": True,
        "retirement_note": (
            "Dedicated parallel-paper LaunchAgent retired 2026-08-03 "
            "(RETIRE_LEGACY_ORPHAN, do_not_accidental_restore=true). "
            "Automation now runs via the shared hourly cron job "
            "(com.tradingai.hourly-refresh), not a dedicated daemon."
        ),
        "active_automation_label": "com.tradingai.hourly-refresh",
        "active_automation_plist_installed": hourly_plist.is_file(),
        "active_automation_launchctl_listed": hourly_listed,
        "install_supported": False,
        "remove_supported": False,
    }


def run_health(_args: list[str] | None = None) -> int:
    from tae_parallel_paper_runtime import health_snapshot

    print("===== TAE PARALLEL-PAPER-HEALTH =====")
    h = health_snapshot()
    h["autostart"] = _retired_autostart_status()
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
    print("===== TAE PARALLEL-PAPER-AUTOSTART-INSTALL — PAPER ONLY =====")
    st = _retired_autostart_status()
    st["ok"] = False
    st["reason"] = (
        "install is intentionally unsupported: the retired "
        "com.tradingai.parallel-paper LaunchAgent requires a dedicated "
        "sprint + HEAD/main target verification + anti-duplication proof "
        "per its retirement manifest before it can ever come back. Use "
        "the existing com.tradingai.hourly-refresh job instead."
    )
    _print(st)
    return 1


def run_autostart_status(_args: list[str] | None = None) -> int:
    print("===== TAE PARALLEL-PAPER-AUTOSTART-STATUS =====")
    _print(_retired_autostart_status())
    return 0


def run_autostart_remove(_args: list[str] | None = None) -> int:
    print("===== TAE PARALLEL-PAPER-AUTOSTART-REMOVE =====")
    st = _retired_autostart_status()
    st["removed"] = False
    st["reason"] = "Nothing to remove -- the parallel-paper LaunchAgent was already retired/archived 2026-08-03."
    _print(st)
    return 0
