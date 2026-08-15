#!/usr/bin/env python3
"""
Canonical PAPER learning runtime — orchestration only.

Reuses existing:
  run_longitudinal_memory → run_adaptive_paper_weights → run_rule_survival

Does NOT: execute LIVE, mutate live portfolio, promote to LIVE, invent challengers,
or replace the Paper Decision Engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_learning_persistence import (
    LearningLockBusy,
    atomic_write_json,
    atomic_write_text,
    default_lock_path,
    learning_state_lock,
    load_json_safe,
)

MODE = "PAPER_ONLY"
SCHEMA_STATUS = "tae.canonical_learning.runtime_status.v1"
SCHEMA_HEARTBEAT = "tae.canonical_learning.heartbeat.v1"
SCHEMA_LAST = "tae.canonical_learning.last_applied.v1"

# Heartbeat stale if older than 3× default interval
DEFAULT_INTERVAL_SEC = 900
HEARTBEAT_STALE_SEC = DEFAULT_INTERVAL_SEC * 3
MAX_RETRIES = 3
BACKOFF_BASE_SEC = 5.0

FORBIDDEN_LIVE_MARKERS = (
    "portfolio.csv",
    "live_bot.py",
    "machine_live_promotion_allowed",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _root() -> Path:
    env = os.environ.get("TAE_CANONICAL_LEARNING_ROOT")
    if env:
        return Path(env)
    return Path("runtime_outputs/canonical_learning")


def paths(root: Path | None = None) -> dict[str, Path]:
    r = Path(root) if root is not None else _root()
    return {
        "root": r,
        "lock": r / "learning_state.lock",
        "pid": r / "canonical_learning.pid",
        "status": r / "runtime_status.json",
        "heartbeat": r / "heartbeat.json",
        "last_applied": r / "last_applied.json",
        "applied_events": r / "applied_events.jsonl",
        "log": r / "canonical_learning.log",
        "daemon_enabled": r / "daemon_enabled",
        "cycle_ledger": r / "cycle_ledger.jsonl",
    }


def log_line(msg: str, *, root: Path | None = None) -> None:
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)
    line = f"{_now()} {msg}\n"
    with p["log"].open("a", encoding="utf-8") as fh:
        fh.write(line)


def paper_safety_guard(*, allow_live_mutation: bool = False) -> dict[str, Any]:
    """Hard PAPER-only guard for this runtime."""
    violations: list[str] = []
    if allow_live_mutation:
        violations.append("live_mutation_requested")
    if os.environ.get("TAE_FORCE_LIVE_LEARNING") == "1":
        violations.append("TAE_FORCE_LIVE_LEARNING=1")
    # Never flip promotion lock from this runtime
    live_flag = os.environ.get("TAE_MACHINE_LIVE_PROMOTION_ALLOWED", "").lower()
    if live_flag in {"1", "true", "yes"}:
        violations.append("env_machine_live_promotion_allowed")
    ok = not violations
    return {
        "ok": ok,
        "paper_only": True,
        "live_mutation_allowed": False,
        "violations": violations,
        "mode": MODE,
    }


def feedback_inputs(project_root: Path | None = None) -> dict[str, Path]:
    root = Path(project_root) if project_root is not None else Path(".")
    return {
        "validation": root / "runtime_outputs/paper_decisions/decision_validation_results.json",
        "memory_jsonl": root / "runtime_outputs/longitudinal_memory/decisions.jsonl",
        "attribution": root / "runtime_outputs/paper_execution/rule_outcome_attribution.json",
        "weights": root / "runtime_outputs/adaptive_weights/paper_action_weights.json",
        "trades": root / "runtime_outputs/paper_execution/paper_trades.jsonl",
        "knowledge": root / "runtime_outputs/longitudinal_memory/knowledge.json",
        "lifecycle": root / "runtime_outputs/paper_execution/rule_lifecycle.json",
    }


def feedback_artifacts_exist(project_root: Path | None = None) -> bool:
    paths_map = feedback_inputs(project_root)
    keys = ("validation", "memory_jsonl", "attribution", "weights", "trades")
    return any(paths_map[k].is_file() for k in keys)


def _file_fingerprint(path: Path) -> str:
    if not path.is_file():
        return "missing"
    try:
        data = path.read_bytes()
    except OSError:
        return "unreadable"
    return hashlib.sha256(data).hexdigest()[:16]


def compute_input_fingerprint(project_root: Path | None = None) -> str:
    """Fingerprint of external learning inputs (excludes learning-owned memory writes)."""
    inp = feedback_inputs(project_root)
    parts = [
        f"validation={_file_fingerprint(inp['validation'])}",
        f"attribution={_file_fingerprint(inp['attribution'])}",
        f"trades={_file_fingerprint(inp['trades'])}",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_learning_ssot(project_root: Path | None = None) -> dict[str, Any]:
    """Detect corruption in learning SSOT without mutating."""
    inp = feedback_inputs(project_root)
    errors: list[str] = []
    for key in ("weights", "knowledge", "lifecycle"):
        path = inp[key]
        if not path.is_file():
            continue
        _data, err = load_json_safe(path)
        if err:
            errors.append(f"{key}:{err}")
    return {"ok": not errors, "errors": errors}


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k
            not in {
                "generated_at",
                "updated_at",
                "cycle_id",
                "last_cycle_id",
                "timestamp",
            }
        }
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


def content_fingerprint(doc: dict[str, Any] | None) -> str:
    stable = json.dumps(_strip_volatile(doc or {}), sort_keys=True, default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def load_last_applied(root: Path | None = None) -> dict[str, Any]:
    p = paths(root)["last_applied"]
    data, err = load_json_safe(p)
    if err or not isinstance(data, dict):
        return {}
    return data


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def write_status(payload: dict[str, Any], *, root: Path | None = None) -> None:
    p = paths(root)
    base = {
        "schema": SCHEMA_STATUS,
        "paper_only": True,
        "live_mutation_allowed": False,
        "mode": MODE,
        "updated_at": _now(),
    }
    base.update(payload)
    atomic_write_json(p["status"], base)


def write_heartbeat(
    *,
    pid: int | None,
    interval_sec: int = DEFAULT_INTERVAL_SEC,
    session_active: bool = False,
    extra: dict[str, Any] | None = None,
    root: Path | None = None,
) -> None:
    p = paths(root)
    payload = {
        "schema": SCHEMA_HEARTBEAT,
        "pid": pid,
        "updated_at": _now(),
        "last_heartbeat": _now(),
        "interval_sec": interval_sec,
        "session_active": session_active,
        "paper_only": True,
        "live_mutation_allowed": False,
    }
    if extra:
        payload.update(extra)
    atomic_write_json(p["heartbeat"], payload)


def write_pid(pid: int, *, root: Path | None = None) -> None:
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)
    atomic_write_text(p["pid"], f"{pid}\n")


def clear_pid(*, root: Path | None = None) -> None:
    p = paths(root)
    if p["pid"].is_file():
        try:
            p["pid"].unlink()
        except OSError:
            pass


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def pid_is_canonical_learning(pid: int | None) -> bool:
    """True only if pid is alive AND its command line is our learning daemon."""
    if not pid_alive(pid):
        return False
    assert pid is not None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    cmd = (result.stdout or "").strip()
    return "tae_canonical_learning" in cmd


def read_pid(*, root: Path | None = None) -> int | None:
    p = paths(root)
    if not p["pid"].is_file():
        return None
    try:
        return int(p["pid"].read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def resolve_learning_pid(*, root: Path | None = None) -> int | None:
    """Return PID only when it matches the learning daemon; clear stale foreign PIDs."""
    existing = read_pid(root=root)
    if existing is None:
        return None
    if pid_is_canonical_learning(existing):
        return existing
    # Stale or foreign PID (e.g. recycled system pid) — reclaim
    clear_pid(root=root)
    return None


def session_window_active(*, tz_name: str = "Europe/Bucharest") -> bool:
    """Multi-market host window (not US-only). Weekday 08:00–23:25 local."""
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now = datetime.now()
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 8 * 60 <= minutes <= 23 * 60 + 25


def any_tracked_market_open() -> bool:
    try:
        from markets.market_hours import any_market_open

        return bool(any_market_open())
    except Exception:
        return False


def _empty_status() -> dict[str, Any]:
    return {
        "runtime_running": False,
        "pid": None,
        "last_cycle_started_at": None,
        "last_cycle_completed_at": None,
        "last_successful_learning_at": None,
        "last_cycle_id": None,
        "last_outcomes_evaluated": 0,
        "last_learning_updates_applied": 0,
        "last_duplicates_skipped": 0,
        "last_error": None,
        "consecutive_failures": 0,
        "heartbeat_fresh": False,
        "paper_only": True,
        "live_mutation_allowed": False,
        "last_result": None,
    }


def status_snapshot(*, root: Path | None = None) -> dict[str, Any]:
    p = paths(root)
    data, err = load_json_safe(p["status"])
    base = _empty_status()
    if isinstance(data, dict):
        base.update({k: data.get(k, base.get(k)) for k in base})
        base.update({k: v for k, v in data.items() if k not in base})
    hb, hb_err = load_json_safe(p["heartbeat"])
    heartbeat_fresh = False
    if isinstance(hb, dict) and hb.get("last_heartbeat"):
        try:
            ts = str(hb["last_heartbeat"]).replace("Z", "+00:00")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
            heartbeat_fresh = age <= HEARTBEAT_STALE_SEC
        except Exception:
            heartbeat_fresh = False
    pid = read_pid(root=root)
    running = bool(pid_alive(pid))
    base["runtime_running"] = running
    base["pid"] = pid if running else None
    base["heartbeat_fresh"] = heartbeat_fresh
    base["paper_only"] = True
    base["live_mutation_allowed"] = False
    if err:
        base["status_read_error"] = err
    if hb_err:
        base["heartbeat_read_error"] = hb_err
    return base


def health_snapshot(*, root: Path | None = None) -> dict[str, Any]:
    st = status_snapshot(root=root)
    safety = paper_safety_guard()
    ssot = validate_learning_ssot()
    overall = "HEALTHY"

    if not safety["ok"]:
        overall = "PAPER_SAFETY_VIOLATION"
    elif not ssot["ok"]:
        overall = "STATE_CORRUPTION"
    elif st.get("last_result") == "CYCLE_FAILED" or (
        st.get("consecutive_failures", 0) and not st.get("runtime_running")
    ):
        if st.get("last_error"):
            overall = "CYCLE_FAILED"
    elif st.get("runtime_running") and not st.get("heartbeat_fresh"):
        overall = "STALE_HEARTBEAT"
    elif st.get("last_result") == "NO_ELIGIBLE_OUTCOMES" and st.get("runtime_running"):
        overall = "RUNNING_NO_ELIGIBLE_OUTCOMES"
    elif st.get("last_result") == "DUPLICATE_SKIPPED" and st.get("runtime_running"):
        overall = "RUNNING_NO_ELIGIBLE_OUTCOMES"
    elif st.get("runtime_running") and st.get("heartbeat_fresh"):
        overall = "HEALTHY"
    elif not st.get("runtime_running") and st.get("last_error") is None:
        overall = "HEALTHY"
    elif st.get("last_error"):
        overall = "CYCLE_FAILED"

    st["overall_status"] = overall
    st["safety"] = safety
    st["ssot_validation"] = ssot
    st["feedback_artifacts_exist"] = feedback_artifacts_exist()
    return st


def run_canonical_learning_cycle(
    *,
    project_root: Path | None = None,
    runtime_root: Path | None = None,
    source: str = "learning-runtime-cycle",
    write_reports: bool = False,
    force: bool = False,
    blocking_lock: bool = False,
) -> dict[str, Any]:
    """
    Single canonical learning mutation cycle.

    Applies longitudinal + adaptive weights + rule survival at most once
    per distinct input_fingerprint (unless force=True recomputes and still
    skips write when content unchanged).
    """
    project_root = Path(project_root) if project_root is not None else Path(".")
    runtime_root = Path(runtime_root) if runtime_root is not None else _root()
    p = paths(runtime_root)
    p["root"].mkdir(parents=True, exist_ok=True)

    cycle_id = f"CLR-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    started = _now()
    safety = paper_safety_guard()
    if not safety["ok"]:
        result = {
            "ok": False,
            "cycle_id": cycle_id,
            "result": "PAPER_SAFETY_VIOLATION",
            "safety": safety,
            "learning_updates_applied": 0,
            "duplicates_skipped": 0,
            "outcomes_evaluated": 0,
        }
        _record_cycle_end(runtime_root, result, started=started, error="PAPER_SAFETY_VIOLATION")
        return result

    ssot = validate_learning_ssot(project_root)
    if not ssot["ok"]:
        result = {
            "ok": False,
            "cycle_id": cycle_id,
            "result": "STATE_CORRUPTION",
            "ssot_validation": ssot,
            "learning_updates_applied": 0,
            "duplicates_skipped": 0,
            "outcomes_evaluated": 0,
        }
        _record_cycle_end(runtime_root, result, started=started, error=";".join(ssot["errors"]))
        return result

    if not feedback_artifacts_exist(project_root):
        result = {
            "ok": True,
            "cycle_id": cycle_id,
            "result": "NO_ELIGIBLE_OUTCOMES",
            "reason": "no_feedback_artifacts",
            "learning_updates_applied": 0,
            "duplicates_skipped": 0,
            "outcomes_evaluated": 0,
            "source": source,
        }
        _record_cycle_end(runtime_root, result, started=started, error=None)
        return result

    input_fp = compute_input_fingerprint(project_root)
    last = load_last_applied(runtime_root)
    if not force and last.get("input_fingerprint") == input_fp and last.get("applied"):
        result = {
            "ok": True,
            "cycle_id": cycle_id,
            "result": "DUPLICATE_SKIPPED",
            "reason": "identical_input_fingerprint",
            "input_fingerprint": input_fp,
            "prior_cycle_id": last.get("cycle_id"),
            "learning_updates_applied": 0,
            "duplicates_skipped": 1,
            "outcomes_evaluated": int(last.get("outcomes_evaluated") or 0),
            "source": source,
        }
        _record_cycle_end(runtime_root, result, started=started, error=None)
        return result

    write_status(
        {
            **status_snapshot(root=runtime_root),
            "last_cycle_started_at": started,
            "last_cycle_id": cycle_id,
            "runtime_running": status_snapshot(root=runtime_root).get("runtime_running"),
        },
        root=runtime_root,
    )

    try:
        with learning_state_lock(p["lock"], blocking=blocking_lock):
            # Re-check fingerprint under lock
            input_fp = compute_input_fingerprint(project_root)
            last = load_last_applied(runtime_root)
            if not force and last.get("input_fingerprint") == input_fp and last.get("applied"):
                result = {
                    "ok": True,
                    "cycle_id": cycle_id,
                    "result": "DUPLICATE_SKIPPED",
                    "reason": "identical_input_fingerprint_under_lock",
                    "input_fingerprint": input_fp,
                    "learning_updates_applied": 0,
                    "duplicates_skipped": 1,
                    "outcomes_evaluated": int(last.get("outcomes_evaluated") or 0),
                    "source": source,
                }
                _record_cycle_end(runtime_root, result, started=started, error=None)
                return result

            from tae_longitudinal_outcome_memory import run_longitudinal_memory
            from tae_adaptive_paper_weights import run_adaptive_paper_weights
            from tae_rule_survival import run_rule_survival

            # Snapshot prior content fingerprints
            inp = feedback_inputs(project_root)
            prior_weights, _ = load_json_safe(inp["weights"])
            prior_knowledge, _ = load_json_safe(inp["knowledge"])
            prior_lifecycle, _ = load_json_safe(inp["lifecycle"])
            prior_fps = {
                "weights": content_fingerprint(prior_weights if isinstance(prior_weights, dict) else {}),
                "knowledge": content_fingerprint(prior_knowledge if isinstance(prior_knowledge, dict) else {}),
                "lifecycle": content_fingerprint(prior_lifecycle if isinstance(prior_lifecycle, dict) else {}),
            }

            mem = run_longitudinal_memory(write_reports_flag=write_reports)
            weights = run_adaptive_paper_weights(write_report_flag=write_reports)
            survival = run_rule_survival(write_report_flag=write_reports)

            new_weights = weights.get("document") if isinstance(weights, dict) else None
            new_knowledge, _ = load_json_safe(inp["knowledge"])
            new_lifecycle = survival.get("document") if isinstance(survival, dict) else None
            new_fps = {
                "weights": content_fingerprint(new_weights if isinstance(new_weights, dict) else {}),
                "knowledge": content_fingerprint(new_knowledge if isinstance(new_knowledge, dict) else {}),
                "lifecycle": content_fingerprint(new_lifecycle if isinstance(new_lifecycle, dict) else {}),
            }

            changed = [k for k in prior_fps if prior_fps[k] != new_fps[k]]
            updates_applied = len(changed)
            duplicates_skipped = 0 if updates_applied else 1

            outcomes = 0
            if isinstance(mem, dict):
                idx = mem.get("index") or {}
                outcomes = int(idx.get("total_records") or 0)

            applied_row = {
                "schema": SCHEMA_LAST,
                "cycle_id": cycle_id,
                "learning_event_id": f"LE-{input_fp[:12]}",
                "input_fingerprint": input_fp,
                "content_fingerprints": new_fps,
                "changed": changed,
                "applied": True,
                "updates_applied": updates_applied,
                "outcomes_evaluated": outcomes,
                "source": source,
                "at": _now(),
                "paper_only": True,
                "live_mutation_allowed": False,
            }
            atomic_write_json(p["last_applied"], applied_row)
            append_jsonl(p["applied_events"], applied_row)

            result = {
                "ok": bool(mem.get("ok", True) and weights.get("ok", True) and survival.get("ok", True)),
                "cycle_id": cycle_id,
                "result": "LEARNING_UPDATES_APPLIED" if updates_applied else "DUPLICATE_SKIPPED",
                "input_fingerprint": input_fp,
                "changed": changed,
                "learning_updates_applied": updates_applied,
                "duplicates_skipped": duplicates_skipped,
                "outcomes_evaluated": outcomes,
                "source": source,
                "steps": {
                    "longitudinal": {"ok": mem.get("ok", True), "total_records": outcomes},
                    "adaptive_weights": {"ok": weights.get("ok", True)},
                    "rule_survival": {"ok": survival.get("ok", True)},
                },
            }
            _record_cycle_end(runtime_root, result, started=started, error=None)
            log_line(
                f"cycle {cycle_id} result={result['result']} updates={updates_applied} source={source}",
                root=runtime_root,
            )
            return result
    except LearningLockBusy as exc:
        result = {
            "ok": False,
            "cycle_id": cycle_id,
            "result": "DUPLICATE_RUNTIME",
            "error": str(exc),
            "learning_updates_applied": 0,
            "duplicates_skipped": 0,
            "outcomes_evaluated": 0,
            "source": source,
        }
        _record_cycle_end(runtime_root, result, started=started, error=str(exc))
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "cycle_id": cycle_id,
            "result": "CYCLE_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "learning_updates_applied": 0,
            "duplicates_skipped": 0,
            "outcomes_evaluated": 0,
            "source": source,
        }
        _record_cycle_end(runtime_root, result, started=started, error=result["error"])
        log_line(f"cycle {cycle_id} FAILED {result['error']}", root=runtime_root)
        return result


def _record_cycle_end(
    runtime_root: Path,
    result: dict[str, Any],
    *,
    started: str,
    error: str | None,
) -> None:
    prev = status_snapshot(root=runtime_root)
    failures = int(prev.get("consecutive_failures") or 0)
    if result.get("ok"):
        failures = 0
    else:
        failures += 1
    completed = _now()
    payload = {
        "runtime_running": prev.get("runtime_running"),
        "pid": prev.get("pid"),
        "last_cycle_started_at": started,
        "last_cycle_completed_at": completed,
        "last_cycle_id": result.get("cycle_id"),
        "last_outcomes_evaluated": result.get("outcomes_evaluated", 0),
        "last_learning_updates_applied": result.get("learning_updates_applied", 0),
        "last_duplicates_skipped": result.get("duplicates_skipped", 0),
        "last_error": error,
        "consecutive_failures": failures,
        "last_result": result.get("result"),
        "paper_only": True,
        "live_mutation_allowed": False,
    }
    if result.get("ok") and result.get("learning_updates_applied", 0) > 0:
        payload["last_successful_learning_at"] = completed
    elif prev.get("last_successful_learning_at"):
        payload["last_successful_learning_at"] = prev.get("last_successful_learning_at")
    write_status(payload, root=runtime_root)
    append_jsonl(
        paths(runtime_root)["cycle_ledger"],
        {"at": completed, "started": started, **{k: result.get(k) for k in ("cycle_id", "result", "ok", "source")}},
    )


def start_runtime(*, spawn_daemon: bool = True, interval_sec: int = DEFAULT_INTERVAL_SEC) -> dict[str, Any]:
    """Enable flag + optionally spawn daemon. Never runs an implicit learning cycle."""
    safety = paper_safety_guard()
    if not safety["ok"]:
        return {"ok": False, "result": "PAPER_SAFETY_VIOLATION", "safety": safety}

    root = _root()
    p = paths(root)
    p["root"].mkdir(parents=True, exist_ok=True)

    existing = resolve_learning_pid(root=root)
    if existing is not None:
        return {
            "ok": False,
            "duplicate": True,
            "result": "DUPLICATE_RUNTIME",
            "pid": existing,
        }

    p["daemon_enabled"].write_text("1\n", encoding="utf-8")
    if not spawn_daemon:
        write_status(
            {
                **_empty_status(),
                "runtime_running": False,
                "enabled_flag": True,
                "note": "enabled_without_spawn",
            },
            root=root,
        )
        return {"ok": True, "spawned": False, "enabled": True}

    import subprocess
    import sys

    cmd = [
        sys.executable,
        str(Path("tae_canonical_learning_daemon.py").resolve()),
        "--interval",
        str(int(interval_sec)),
        "--ensure-enabled",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(Path(".").resolve()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    time.sleep(0.4)
    alive = pid_alive(proc.pid)
    write_pid(proc.pid, root=root)
    write_status(
        {
            **_empty_status(),
            "runtime_running": alive,
            "pid": proc.pid if alive else None,
            "enabled_flag": True,
            "spawned_at": _now(),
        },
        root=root,
    )
    write_heartbeat(pid=proc.pid if alive else None, interval_sec=interval_sec, session_active=session_window_active(), root=root)
    return {"ok": alive, "spawned": True, "pid": proc.pid, "duplicate": False}


def stop_runtime(*, remove_enabled_flag: bool = True) -> dict[str, Any]:
    root = _root()
    p = paths(root)
    pid = read_pid(root=root)
    if remove_enabled_flag and p["daemon_enabled"].is_file():
        try:
            p["daemon_enabled"].unlink()
        except OSError:
            pass
    if pid and pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            return {"ok": False, "error": str(exc), "pid": pid}
        # wait briefly
        for _ in range(20):
            if not pid_alive(pid):
                break
            time.sleep(0.1)
    clear_pid(root=root)
    write_status(
        {
            **status_snapshot(root=root),
            "runtime_running": False,
            "pid": None,
            "enabled_flag": False,
            "stopped_at": _now(),
        },
        root=root,
    )
    return {"ok": True, "stopped_pid": pid}


def recover_stale_lock(*, root: Path | None = None) -> dict[str, Any]:
    """
    Safe stale lock recovery: only clears pid file when process is dead.
    Does not delete lock file inode (flock releases on process death).
    """
    runtime_root = Path(root) if root is not None else _root()
    pid = read_pid(root=runtime_root)
    if pid and pid_alive(pid):
        return {"ok": False, "result": "DUPLICATE_RUNTIME", "pid": pid}
    if pid and not pid_alive(pid):
        clear_pid(root=runtime_root)
        return {"ok": True, "result": "STALE_PID_CLEARED", "cleared_pid": pid}
    return {"ok": True, "result": "NO_STALE_LOCK"}
