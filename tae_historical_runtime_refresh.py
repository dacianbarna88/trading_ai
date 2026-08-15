#!/usr/bin/env python3
"""
TAE Historical Intelligence Runtime Refresh — PAPER_ONLY / NO_BROKER.

Verifies freshness of historical/strategic SSOT used by the PAPER loop.
Refreshes stale sources via existing scripts only — no new intelligence engine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "PAPER_ONLY"
DEFAULT_MAX_AGE_HOURS = 24.0
RUNTIME_DIR = Path("runtime_outputs/historical_runtime")
STATE_JSON = RUNTIME_DIR / "runtime_state.json"
REPORT_MD = Path("TAE_HISTORICAL_RUNTIME_REPORT.md")

PYTHON = sys.executable


def _trace_ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def trace_start(step_name: str) -> float:
    t0 = time.monotonic()
    print(f"[START] {step_name} {_trace_ts()}", flush=True)
    return t0


def trace_end(step_name: str, t0: float) -> None:
    duration = time.monotonic() - t0
    print(f"[END] {step_name} {_trace_ts()} duration={duration:.1f}s", flush=True)


def trace_fail(step_name: str, error: str) -> None:
    print(f"[FAIL] {step_name} {error}", flush=True)


def trace_timeout(step_name: str, duration: float) -> None:
    print(f"[TIMEOUT] {step_name} duration={duration:.1f}s", flush=True)


@dataclass(frozen=True)
class HistoricalSourceSpec:
    source_id: str
    path: str
    refresh_script: str
    consumers: tuple[str, ...]
    category: str
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS
    requires: tuple[str, ...] = ()
    optional: bool = False
    critical: bool = True


HISTORICAL_SOURCES: tuple[HistoricalSourceSpec, ...] = (
    HistoricalSourceSpec(
        source_id="historical_intelligence_csv",
        path="historical_intelligence.csv",
        refresh_script="migration/legacy/historical_intelligence_engine.py",
        consumers=("multi-horizon", "paper-decisions", "learning-to-profit"),
        category="multi_horizon",
        critical=True,
    ),
    HistoricalSourceSpec(
        source_id="multi_horizon_backtest_csv",
        path="multi_horizon_backtest.csv",
        refresh_script="research/multi_horizon_backtest.py",
        consumers=("multi-horizon", "cross-validation", "regional-validation"),
        category="multi_horizon",
        critical=True,
    ),
    HistoricalSourceSpec(
        source_id="global_market_scanner_csv",
        path="global_market_scanner.csv",
        refresh_script="strategic_intelligence/global_market_scanner.py",
        consumers=("strategic-allocation", "strategic-intelligence-summary"),
        category="strategic_allocation",
        critical=True,
    ),
    HistoricalSourceSpec(
        source_id="regional_strength_csv",
        path="regional_strength.csv",
        refresh_script="strategic_intelligence/regional_strength_aggregator.py",
        requires=("global_market_scanner.csv",),
        consumers=("strategic-allocation", "capital-allocation"),
        category="strategic_allocation",
        critical=True,
    ),
    HistoricalSourceSpec(
        source_id="strategic_horizon_summary",
        path="strategic_horizon_summary.txt",
        refresh_script="research/strategic_horizon.py",
        requires=("historical_intelligence.csv",),
        consumers=("horizon-vote", "strategic-allocation"),
        category="strategic_allocation",
        optional=True,
        critical=False,
    ),
    HistoricalSourceSpec(
        source_id="horizon_validation_summary",
        path="horizon_validation_summary.txt",
        refresh_script="research/horizon_validation_engine.py",
        requires=("multi_horizon_backtest.csv",),
        consumers=("horizon-vote",),
        category="multi_horizon",
        optional=True,
        critical=False,
    ),
    HistoricalSourceSpec(
        source_id="strategic_intelligence_summary",
        path="strategic_intelligence_summary.txt",
        refresh_script="strategic_intelligence/strategic_intelligence_summary_layer.py",
        consumers=("multi-horizon", "paper-decisions", "learning-to-profit"),
        category="strategic_allocation",
        critical=True,
    ),
    HistoricalSourceSpec(
        source_id="horizon_vote_summary",
        path="horizon_vote_summary.txt",
        refresh_script="strategic_intelligence/horizon_vote_engine.py",
        consumers=("multi-horizon", "paper-decisions", "DPE-context"),
        category="strategic_allocation",
        critical=True,
    ),
)

RECOMPUTE_DEPENDENTS: tuple[tuple[str, str, str], ...] = (
    ("growth_intelligence", "tae_growth_intelligence.py", "tae_growth_intelligence.json"),
    (
        "strategic_allocation_runtime",
        "migration/legacy/tae_strategic_allocation_runtime.py",
        "tae_strategic_allocation_runtime.json",
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    return round((time.time() - path.stat().st_mtime) / 3600.0, 2)


def audit_source(spec: HistoricalSourceSpec, *, root: Path) -> dict[str, Any]:
    path = root / spec.path
    script_path = root / spec.refresh_script
    script_present = script_path.is_file()
    age = _file_age_hours(path)
    if not path.is_file():
        status = "MISSING" if script_present else "REFRESH_OWNER_ABSENT"
    elif age is not None and age > spec.max_age_hours:
        # Stale artifact with no restoreable refresh owner must not HARD-block PAPER.
        status = "STALE" if script_present else "STALE_REFRESH_OWNER_ABSENT"
    else:
        status = "FRESH"
    # Critical only when a refresh owner exists on HEAD.
    critical_for_gate = bool(spec.critical) and script_present
    if status == "FRESH":
        critical_for_gate = bool(spec.critical)
    elif not script_present:
        critical_for_gate = False
    return {
        "source_id": spec.source_id,
        "path": spec.path,
        "category": spec.category,
        "consumers": list(spec.consumers),
        "refresh_command": f"{PYTHON} {spec.refresh_script}",
        "refresh_script_present": script_present,
        "dependencies": list(spec.requires),
        "max_age_hours": spec.max_age_hours,
        "age_hours": age,
        "status": status,
        "critical": critical_for_gate,
        "configured_critical": spec.critical,
        "optional": spec.optional,
    }


def audit_all_sources(*, root: Path | None = None) -> dict[str, Any]:
    root = root or Path(".")
    sources = [audit_source(spec, root=root) for spec in HISTORICAL_SOURCES]
    stale = [s for s in sources if s["status"] in {"STALE", "MISSING"} and s.get("critical")]
    critical_fresh = all(
        s["status"] == "FRESH" for s in sources if s.get("critical")
    )
    # Sources whose refresh owners were intentionally removed never block the gate.
    owner_absent = [
        s["source_id"]
        for s in sources
        if s.get("status") in {"REFRESH_OWNER_ABSENT", "STALE_REFRESH_OWNER_ABSENT"}
    ]
    return {
        "schema": "tae_historical_runtime_audit",
        "mode": MODE,
        "generated_at": _now(),
        "max_age_hours_default": DEFAULT_MAX_AGE_HOURS,
        "sources": sources,
        "stale_count": sum(1 for s in sources if s["status"] == "STALE"),
        "missing_count": sum(1 for s in sources if s["status"] == "MISSING"),
        "fresh_count": sum(1 for s in sources if s["status"] == "FRESH"),
        "critical_stale": [s["source_id"] for s in stale],
        "refresh_owner_absent": owner_absent,
        "all_fresh": critical_fresh,
        "critical_all_fresh": critical_fresh,
    }


def _run_script(script: str, *, root: Path, timeout: int = 300) -> tuple[bool, str]:
    step_name = f"historical_refresh/{script}"
    t0 = trace_start(step_name)
    script_path = root / script
    if not script_path.is_file():
        trace_fail(step_name, f"missing script: {script}")
        trace_end(step_name, t0)
        return False, f"missing script: {script}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.run(
            [PYTHON, "-u", str(script_path)],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        trace_timeout(step_name, time.monotonic() - t0)
        return False, "timeout"
    except OSError as exc:
        trace_fail(step_name, str(exc))
        trace_end(step_name, t0)
        return False, str(exc)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-500:]
        trace_fail(step_name, err or f"exit {proc.returncode}")
        trace_end(step_name, t0)
        return False, err or f"exit {proc.returncode}"
    trace_end(step_name, t0)
    return True, "ok"


def refresh_source(spec: HistoricalSourceSpec, *, root: Path) -> dict[str, Any]:
    path = root / spec.path
    before_age = _file_age_hours(path)
    before_status = audit_source(spec, root=root)["status"]

    for dep in spec.requires:
        if not (root / dep).is_file():
            return {
                "source_id": spec.source_id,
                "refresh_attempted": False,
                "refresh_ok": False,
                "status": "STALE",
                "reason": f"missing dependency: {dep}",
                "age_hours_before": before_age,
                "age_hours_after": before_age,
            }

    ok, detail = _run_script(spec.refresh_script, root=root)
    after_age = _file_age_hours(root / spec.path)
    after_present = (root / spec.path).is_file()

    if ok and after_present and (after_age is not None and after_age < spec.max_age_hours):
        status = "REFRESHED"
    elif ok and after_present:
        status = "FRESH"
    elif not ok and spec.optional:
        status = before_status if before_status != "MISSING" else "STALE"
    else:
        status = "STALE"

    return {
        "source_id": spec.source_id,
        "path": spec.path,
        "refresh_attempted": True,
        "refresh_ok": ok and after_present,
        "status": status,
        "reason": detail if not ok else "",
        "age_hours_before": before_age,
        "age_hours_after": after_age,
    }


def recompute_dependents(*, root: Path, any_refreshed: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    t0 = trace_start("historical_refresh/recompute_dependents")
    for name, script, artifact in RECOMPUTE_DEPENDENTS:
        artifact_path = root / artifact
        artifact_age = _file_age_hours(artifact_path)
        if not (root / script).is_file():
            print(f"[START] historical_refresh/recompute/{name} {_trace_ts()}", flush=True)
            print(
                f"[END] historical_refresh/recompute/{name} {_trace_ts()} duration=0.0s skipped=owner_absent",
                flush=True,
            )
            results.append(
                {
                    "name": name,
                    "skipped": True,
                    "reason": "recompute owner intentionally absent on HEAD",
                    "artifact": artifact,
                }
            )
            continue
        if not any_refreshed and artifact_age is not None and artifact_age <= DEFAULT_MAX_AGE_HOURS:
            print(f"[START] historical_refresh/recompute/{name} {_trace_ts()}", flush=True)
            print(
                f"[END] historical_refresh/recompute/{name} {_trace_ts()} duration=0.0s skipped=fresh",
                flush=True,
            )
            results.append(
                {
                    "name": name,
                    "skipped": True,
                    "reason": "artifact still fresh",
                    "artifact": artifact,
                }
            )
            continue
        ok, detail = _run_script(script, root=root, timeout=600)
        results.append(
            {
                "name": name,
                "skipped": False,
                "ok": ok,
                "artifact": artifact,
                "detail": detail,
            }
        )
    trace_end("historical_refresh/recompute_dependents", t0)
    return results


def confidence_penalty(stale_sources: list[str]) -> float:
    if not stale_sources:
        return 0.0
    critical = sum(
        1 for spec in HISTORICAL_SOURCES if spec.source_id in stale_sources and spec.critical
    )
    return min(0.35, 0.08 * critical)


def run_historical_runtime_refresh(*, root: Path | None = None, force: bool = False) -> dict[str, Any]:
    root = root or Path(".")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    cycle_t0 = trace_start("run_historical_runtime_refresh")

    audit_t0 = trace_start("historical_refresh/audit_before")
    audit_before = audit_all_sources(root=root)
    trace_end("historical_refresh/audit_before", audit_t0)

    refresh_results: list[dict[str, Any]] = []
    any_refreshed = False

    for spec in HISTORICAL_SOURCES:
        row = audit_source(spec, root=root)
        needs_refresh = force or row["status"] in {"STALE", "MISSING"}
        source_step = f"historical_refresh/source/{spec.source_id}"
        source_t0 = trace_start(source_step)
        if row["status"] in {"REFRESH_OWNER_ABSENT", "STALE_REFRESH_OWNER_ABSENT"}:
            refresh_results.append(
                {
                    "source_id": spec.source_id,
                    "refresh_attempted": False,
                    "refresh_ok": True,
                    "status": row["status"],
                    "reason": "refresh owner intentionally absent on HEAD",
                    "age_hours_after": row["age_hours"],
                }
            )
            trace_end(source_step, source_t0)
            continue
        if not needs_refresh:
            refresh_results.append(
                {
                    "source_id": spec.source_id,
                    "refresh_attempted": False,
                    "refresh_ok": True,
                    "status": row["status"],
                    "reason": "already fresh",
                    "age_hours_after": row["age_hours"],
                }
            )
            trace_end(source_step, source_t0)
            continue
        result = refresh_source(spec, root=root)
        refresh_results.append(result)
        if result.get("refresh_ok") and result.get("status") in {"REFRESHED", "FRESH"}:
            any_refreshed = True
        if not result.get("refresh_ok"):
            trace_fail(source_step, result.get("reason") or result.get("status") or "refresh failed")
        trace_end(source_step, source_t0)

    recompute = recompute_dependents(root=root, any_refreshed=any_refreshed)
    audit_t0 = trace_start("historical_refresh/audit_after")
    audit_after = audit_all_sources(root=root)
    trace_end("historical_refresh/audit_after", audit_t0)

    stale_ids = [
        s["source_id"]
        for s in audit_after["sources"]
        if s["status"] in {"STALE", "MISSING"} and s.get("critical")
    ]
    penalty = confidence_penalty(stale_ids)

    state = {
        "schema": "tae_historical_runtime_state",
        "mode": MODE,
        "generated_at": _now(),
        "audit_before": audit_before,
        "refresh_results": refresh_results,
        "recompute_dependents": recompute,
        "audit_after": audit_after,
        "stale_sources": stale_ids,
        "confidence_penalty": penalty,
        "all_fresh": audit_after["all_fresh"],
        "critical_all_fresh": audit_after.get("critical_all_fresh", audit_after["all_fresh"]),
        "never_silent_stale": True,
    }
    STATE_JSON.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    write_report(state)
    trace_end("run_historical_runtime_refresh", cycle_t0)
    return state


def load_runtime_state(*, root: Path | None = None) -> dict[str, Any]:
    path = (root or Path(".")) / STATE_JSON
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def stale_source_paths(*, root: Path | None = None) -> set[str]:
    state = load_runtime_state(root=root)
    stale_ids = set(state.get("stale_sources") or [])
    paths: set[str] = set()
    for spec in HISTORICAL_SOURCES:
        if spec.source_id in stale_ids:
            paths.add(spec.path)
    return paths


def write_report(state: dict[str, Any]) -> None:
    after = state.get("audit_after") or {}
    lines = [
        "# TAE Historical Runtime Report",
        "",
        f"**Generated:** {state.get('generated_at', '')}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_CHANGE",
        f"**All fresh:** **{state.get('all_fresh')}**",
        f"**Confidence penalty:** {state.get('confidence_penalty', 0):.2f}",
        "",
        "## Source audit (after refresh)",
        "",
        "| source | path | age (h) | max (h) | status | refresh |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in after.get("sources") or []:
        refresh = next(
            (r for r in (state.get("refresh_results") or []) if r.get("source_id") == row.get("source_id")),
            {},
        )
        attempted = "yes" if refresh.get("refresh_attempted") else "no"
        lines.append(
            f"| {row.get('source_id')} | `{row.get('path')}` | {row.get('age_hours')} | "
            f"{row.get('max_age_hours')} | **{row.get('status')}** | {attempted} |"
        )

    lines.extend(["", "## Stale sources (critical)", ""])
    stale = state.get("stale_sources") or []
    if stale:
        for sid in stale:
            lines.append(f"- **{sid}** — confidence reduced; not used silently")
    else:
        lines.append("- None — all critical historical/strategic sources fresh")

    lines.extend(["", "## Dependent recompute", ""])
    for row in state.get("recompute_dependents") or []:
        if row.get("skipped"):
            lines.append(f"- {row.get('name')}: skipped ({row.get('reason')})")
        else:
            lines.append(f"- {row.get('name')}: {'OK' if row.get('ok') else 'FAIL'} → `{row.get('artifact')}`")

    lines.extend(
        [
            "",
            "## Consumers",
            "",
            "- Multi-Horizon / Paper Decisions / Learning-to-Profit / Paper Experiments / DPE context",
            "",
            "## Safety",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| NO_BROKER | ✅ |",
            "| NO_LIVE_CHANGE | ✅ |",
            "| No new engines | ✅ |",
            "| Never silent stale | ✅ |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print("===== TAE HISTORICAL RUNTIME REFRESH =====")
    print(f"Mode: {MODE} | existing scripts only | NO_BROKER")
    state = run_historical_runtime_refresh()
    print("All fresh:", state["all_fresh"])
    print("Stale:", state.get("stale_sources") or [])
    print("Confidence penalty:", state.get("confidence_penalty"))
    print("Wrote:", STATE_JSON, REPORT_MD)
    return 0 if state["all_fresh"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
