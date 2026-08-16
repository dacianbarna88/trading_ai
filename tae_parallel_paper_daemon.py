#!/usr/bin/env python3
"""
Parallel PAPER daemon — PAPER_ONLY, no LIVE, no broker.

Single-instance via flock. Session-aware cycles. End-of-day report once/day.
Controlled by enabled-flag file for LaunchAgent PathState KeepAlive.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tae_parallel_paper_config import load_parallel_paper_config, paths
from tae_parallel_paper_reports import generate_daily_report
from tae_parallel_paper_runtime import (
    _atomic_write_json,
    _now,
    acquire_lock,
    bootstrap,
    health_snapshot,
    release_lock,
    run_cycle,
)

STOP_REQUESTED = False


def _log(msg: str) -> None:
    p = paths()
    line = f"{_now()} {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    for name in ("daemon_log", "log"):
        log = p[name]
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(line)


def enabled_flag_path() -> Path:
    return paths()["root"] / "daemon_enabled"


def set_enabled(on: bool) -> None:
    flag = enabled_flag_path()
    flag.parent.mkdir(parents=True, exist_ok=True)
    if on:
        flag.write_text("1\n", encoding="utf-8")
    elif flag.is_file():
        try:
            flag.unlink()
        except OSError:
            pass


def is_enabled() -> bool:
    return enabled_flag_path().is_file()


def _tz_now(cfg: dict[str, Any]) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(str(cfg.get("TIMEZONE") or "Europe/Bucharest")))
    except Exception:
        return datetime.now()


def session_allows_cycle(cfg: dict[str, Any]) -> bool:
    """Weekday Europe/Bucharest, 08:00–23:25 (covers EU/UK/US close window)."""
    now = _tz_now(cfg)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 8 * 60 <= minutes <= 23 * 60 + 25


def should_run_daily_report(cfg: dict[str, Any]) -> bool:
    now = _tz_now(cfg)
    if now.weekday() >= 5:
        return False
    report_hm = str(cfg.get("DAILY_REPORT_TIME") or "22:30")
    try:
        hh, mm = [int(x) for x in report_hm.split(":")[:2]]
    except ValueError:
        hh, mm = 22, 30
    if (now.hour, now.minute) < (hh, mm):
        return False
    day = now.date().isoformat()
    p = paths()
    stamp = p["reports"] / f".daily_report_done_{day}"
    if stamp.is_file():
        return False
    return True


def mark_report_done(day: str) -> None:
    p = paths()
    p["reports"].mkdir(parents=True, exist_ok=True)
    (p["reports"] / f".daily_report_done_{day}").write_text(_now() + "\n", encoding="utf-8")


def _handle_sig(_signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    _log(f"signal {_signum} — stop requested")


def write_runtime_status(*, running: bool, pid: int | None, extra: dict[str, Any] | None = None) -> None:
    p = paths()
    payload = {
        "schema": "tae.parallel_paper.runtime_status.v1",
        "running": running,
        "pid": pid,
        "updated_at": _now(),
        "V2_LIVE_ENABLED": False,
        "V2_CANONICAL_PAPER_ENABLED": False,
        "daemon": True,
        "enabled_flag": is_enabled(),
    }
    if extra:
        payload.update(extra)
    _atomic_write_json(p["runtime_status"], payload)
    _atomic_write_json(p["status"], payload)
    if pid and running:
        p["pid"].write_text(str(pid) + "\n", encoding="utf-8")


def write_heartbeat(
    *,
    pid: int,
    interval_sec: int,
    last_cycle_at: str | None,
    session_active: bool,
    extra: dict[str, Any] | None = None,
) -> None:
    p = paths()
    next_at = (
        datetime.now(timezone.utc) + timedelta(seconds=max(1, int(interval_sec)))
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "schema": "tae.parallel_paper.heartbeat.v1",
        "pid": pid,
        "updated_at": _now(),
        "last_heartbeat": _now(),
        "last_cycle_at": last_cycle_at,
        "next_cycle_expected_at": next_at,
        "session_active": session_active,
        "interval_sec": interval_sec,
        "V2_LIVE_ENABLED": False,
    }
    if extra:
        payload.update(extra)
    _atomic_write_json(p["heartbeat"], payload)


def _market_open_state_path() -> Path:
    return paths()["root"] / "market_open_monitor_state.json"


def _load_open_markets_state() -> set[str]:
    path = _market_open_state_path()
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    open_list = raw.get("open_markets") if isinstance(raw, dict) else None
    if not isinstance(open_list, list):
        return set()
    return {str(x).upper() for x in open_list}


def _save_open_markets_state(open_markets: list[str]) -> None:
    path = _market_open_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(
        path,
        {
            "schema": "tae.parallel_paper.market_open_monitor.v1",
            "updated_at": _now(),
            "open_markets": sorted(open_markets),
        },
    )


def _log_market_open_cycle_summary(result: dict[str, Any], newly_open: list[str]) -> None:
    """Append MARKET_OPEN readiness summary to existing parallel paper logs."""
    marks_valid = 0
    marks_stale = 0
    marks_closed = 0
    snap_id = result.get("snapshot_id")
    if snap_id:
        snap_path = paths()["snapshots"] / f"{snap_id}.json"
        if snap_path.is_file():
            try:
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
                for _t, m in (snap.get("marks") or {}).items():
                    fr = str((m or {}).get("mark_freshness") or "").upper()
                    if fr in {"STALE", "MARK_STALE", "INVALID", "MARK_UNAVAILABLE", "UNAVAILABLE"}:
                        marks_stale += 1
                    elif fr in {"MARKET_CLOSED", "MARKET_CLOSED_VALID_PREVIOUS_CLOSE"}:
                        marks_closed += 1
                        marks_valid += 1
                    elif (m or {}).get("mark_price") not in (None, "", 0, 0.0):
                        marks_valid += 1
            except (OSError, json.JSONDecodeError, TypeError):
                pass
    v1_ok = bool(result.get("v1_ok")) and bool(
        (result.get("accounting_v1") or {}).get("reconciliation_pass")
    )
    v2_ok = bool(result.get("v2_ok")) and bool(
        (result.get("accounting_v2") or {}).get("reconciliation_pass")
    )
    v1_decs = result.get("v1_decisions") or []
    v2_decs = result.get("v2_decisions") or []
    v1_exec = sum(1 for d in v1_decs if d.get("executor_called") or d.get("executed"))
    v2_exec = sum(1 for d in v2_decs if d.get("executor_called") or d.get("executed"))
    _log(
        "MARKET_OPEN markets={markets} "
        "V1_CYCLE_{v1} V2_CYCLE_{v2} "
        "VALID_PRICES={valid} STALE_PRICES={stale} MARKET_CLOSED_PRICES={closed} "
        "DECISIONS=v1:{d1}/v2:{d2} EXECUTIONS=v1:{e1}/v2:{e2} "
        "RECONCILIATION=v1:{r1}/v2:{r2}".format(
            markets=",".join(newly_open) if newly_open else "NONE",
            v1="OK" if v1_ok else "FAILED",
            v2="OK" if v2_ok else "FAILED",
            valid=marks_valid,
            stale=marks_stale,
            closed=marks_closed,
            d1=len(v1_decs),
            d2=len(v2_decs),
            e1=v1_exec,
            e2=v2_exec,
            r1="PASS" if (result.get("accounting_v1") or {}).get("reconciliation_pass") else "FAIL",
            r2="PASS" if (result.get("accounting_v2") or {}).get("reconciliation_pass") else "FAIL",
        )
    )


def daemon_loop(*, interval_sec: int = 300, once: bool = False) -> int:
    global STOP_REQUESTED
    cfg = load_parallel_paper_config()
    if not cfg.get("PARALLEL_PAPER_ENABLED"):
        _log("PARALLEL_PAPER_DISABLED — exit")
        return 1
    if not is_enabled():
        _log("daemon_enabled flag absent — exit (autostart PathState)")
        return 0

    interval_sec = int(cfg.get("RUNTIME_INTERVAL_SEC") or interval_sec or 300)
    bootstrap(cfg)
    p = paths()
    try:
        lock_fh = acquire_lock(p["lock"])
    except RuntimeError:
        _log("DUPLICATE_PARALLEL_PAPER_RUNTIME — exit")
        return 2

    pid = os.getpid()
    last_cycle_at: str | None = None
    write_runtime_status(running=True, pid=pid, extra={"started_at": _now(), "interval_sec": interval_sec})
    write_heartbeat(pid=pid, interval_sec=interval_sec, last_cycle_at=None, session_active=False)
    _log(f"daemon started pid={pid} LIVE=false interval={interval_sec}s")

    signal.signal(signal.SIGTERM, _handle_sig)
    signal.signal(signal.SIGINT, _handle_sig)

    rc = 0
    try:
        while not STOP_REQUESTED and is_enabled():
            cfg = load_parallel_paper_config()
            interval_sec = int(cfg.get("RUNTIME_INTERVAL_SEC") or interval_sec or 300)
            try:
                in_session = session_allows_cycle(cfg)
                try:
                    from markets.market_hours import get_open_markets

                    current_open = [
                        m for m in get_open_markets() if m in {"EU", "UK", "US"}
                    ]
                except Exception:
                    current_open = []
                prev_open = _load_open_markets_state()
                newly_open = sorted(set(current_open) - prev_open)
                if in_session:
                    _log("session OK — run_cycle")
                    result = run_cycle(cfg=cfg)
                    last_cycle_at = _now()
                    _log(
                        f"cycle ok={result.get('ok')} "
                        f"v1_acct={result.get('accounting_v1', {}).get('reconciliation_pass')} "
                        f"v2_acct={result.get('accounting_v2', {}).get('reconciliation_pass')} "
                        f"divs={len(result.get('divergences') or [])}"
                    )
                    if newly_open:
                        _log_market_open_cycle_summary(result, newly_open)
                else:
                    _log("outside session — heartbeat only")

                _save_open_markets_state(current_open)
                if should_run_daily_report(cfg) or (
                    cfg.get("DAILY_REPORT_ENABLED")
                    and not in_session
                    and _tz_now(cfg).hour >= 22
                ):
                    day = _tz_now(cfg).date().isoformat()
                    _log(f"daily report for {day}")
                    rep = generate_daily_report(date=day, cfg=cfg, force=False)
                    mark_report_done(day)
                    _log(
                        f"report verdict={rep.get('executive_conclusion', {}).get('verdict')} "
                        f"acct={rep.get('accounting_status')}"
                    )

                write_heartbeat(
                    pid=pid,
                    interval_sec=interval_sec,
                    last_cycle_at=last_cycle_at,
                    session_active=in_session,
                )
                h = health_snapshot(cfg)
                write_runtime_status(
                    running=True,
                    pid=pid,
                    extra={
                        "last_heartbeat": _now(),
                        "last_cycle_at": last_cycle_at,
                        "next_cycle_expected_at": (
                            datetime.now(timezone.utc) + timedelta(seconds=interval_sec)
                        )
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "health_status": h.get("overall_status") or h.get("status"),
                        "V2_ACTIVATION_SCOPE": cfg.get("V2_ACTIVATION_SCOPE"),
                        "interval_sec": interval_sec,
                    },
                )
            except Exception as exc:
                rc = 1
                _log(f"ERROR {exc}\n{traceback.format_exc()[-1500:]}")
                err = p["root"] / "daemon_errors.jsonl"
                with err.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": _now(), "error": str(exc)}) + "\n")
                write_heartbeat(
                    pid=pid,
                    interval_sec=interval_sec,
                    last_cycle_at=last_cycle_at,
                    session_active=False,
                    extra={"last_error": str(exc)},
                )

            if once:
                break
            for _ in range(max(1, int(interval_sec))):
                if STOP_REQUESTED or not is_enabled():
                    break
                time.sleep(1)
    finally:
        write_runtime_status(running=False, pid=None, extra={"stopped_at": _now()})
        if p["pid"].is_file():
            try:
                p["pid"].unlink()
            except OSError:
                pass
        release_lock(lock_fh)
        _log("daemon stopped cleanly")
    return rc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TAE Parallel PAPER daemon (PAPER_ONLY)")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--ensure-enabled", action="store_true", help="create enabled flag then run")
    args = parser.parse_args(argv)
    if args.ensure_enabled:
        set_enabled(True)
    return daemon_loop(interval_sec=args.interval, once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
