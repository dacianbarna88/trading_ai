#!/usr/bin/env python3
"""
TAE Sprint X.10C — Scanner Refresh Orchestrator

RUNTIME DATA REFRESH ONLY | NO_BROKER | NO_EXECUTION | NO_STRATEGY_CHANGE
Does NOT modify live_bot.py, watchlist.txt, or execute trades.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REFRESH_MODE = "RUNTIME_DATA_REFRESH_ONLY"
NO_EXECUTION = True
DEFAULT_ROOT = Path(".")
LOG_FILE = "tae_scanner_refresh.log"
OUTPUT_JSON = "tae_scanner_refresh.json"
OUTPUT_MD = "tae_scanner_refresh.md"

PYTHON = sys.executable


@dataclass
class StepSpec:
    name: str
    command: list[str]
    artifact: str | None = None
    requires_artifacts: tuple[str, ...] = ()
    skip_if_missing_inputs: bool = True
    needs_pythonpath: bool = False
    critical: bool = False


@dataclass
class StepResult:
    name: str
    command: str
    status: str
    runtime_seconds: float
    artifact: str | None = None
    row_count: int | None = None
    freshness_hours: float | None = None
    artifact_mtime: str | None = None
    errors: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_line(message: str, root: Path) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line)
    with (root / LOG_FILE).open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _artifact_meta(root: Path, rel_path: str | None) -> dict[str, Any]:
    if not rel_path:
        return {}
    path = root / rel_path
    if not path.is_file():
        return {"present": False, "path": rel_path}
    stat = path.stat()
    age_hours = (time.time() - stat.st_mtime) / 3600.0
    row_count: int | None = None
    if path.suffix.lower() == ".csv":
        try:
            with path.open(encoding="utf-8", errors="replace", newline="") as handle:
                row_count = sum(1 for _ in csv.DictReader(handle))
        except OSError:
            row_count = None
    return {
        "present": True,
        "path": rel_path,
        "row_count": row_count,
        "freshness_hours": round(age_hours, 4),
        "artifact_mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _tail(text: str, limit: int = 1200) -> str:
    text = text or ""
    return text[-limit:]


def _build_steps(root: Path) -> list[StepSpec]:
    return [
        StepSpec(
            name="global_market_scanner",
            command=[PYTHON, str(root / "strategic_intelligence/global_market_scanner.py")],
            artifact="global_market_scanner.csv",
            critical=True,
        ),
        StepSpec(
            name="regional_strength_aggregator",
            command=[PYTHON, str(root / "strategic_intelligence/regional_strength_aggregator.py")],
            artifact="regional_strength.csv",
            requires_artifacts=("global_market_scanner.csv",),
        ),
        StepSpec(
            name="sector_rotation_scanner",
            command=[PYTHON, str(root / "sector_intelligence/sector_rotation_scanner.py")],
            artifact="sector_rotation.csv",
        ),
        StepSpec(
            name="us_market_scanner",
            command=[
                PYTHON,
                "-c",
                "from research.market_scanner import run_market_scanner; run_market_scanner(write_watchlist=False)",
            ],
            artifact="watchlist_candidates.csv",
            needs_pythonpath=True,
            critical=True,
        ),
        StepSpec(
            name="multi_market_scanner",
            command=[PYTHON, str(root / "research/multi_market_scanner.py")],
            artifact="multi_market_candidates.csv",
            needs_pythonpath=True,
            critical=True,
        ),
        StepSpec(
            name="global_candidates",
            command=[PYTHON, str(root / "research/global_candidates.py")],
            artifact="global_candidates.csv",
            requires_artifacts=("multi_market_candidates.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="global_opportunity_ranking",
            command=[PYTHON, str(root / "research/global_opportunity_ranking.py")],
            artifact="global_opportunity_ranking.csv",
            requires_artifacts=("global_candidates.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="historical_results_analysis",
            command=[PYTHON, str(root / "tae_historical_results_analysis_demo.py")],
            artifact="tae_historical_results_analysis.json",
            requires_artifacts=("tae_historical_execution.json",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="strategy_evolution_daily_runner",
            command=[PYTHON, str(root / "tae_phase8_strategy_evolution_daily_runner_demo.py")],
            artifact="tae_continuous_strategy_ranking.json",
            needs_pythonpath=True,
        ),
        StepSpec(
            name="live_signals_historical_enrich",
            command=[PYTHON, str(root / "tae_live_signals_historical_enrich.py")],
            artifact="tae_live_signals_historical_enrich.json",
            requires_artifacts=("live_signals.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="research_runtime",
            command=[PYTHON, str(root / "tae_research_runtime.py")],
            artifact="tae_research_runtime.json",
            needs_pythonpath=True,
        ),
        StepSpec(
            name="live_signals_research_enrich",
            command=[PYTHON, str(root / "tae_live_signals_research_enrich.py")],
            artifact="tae_live_signals_research_enrich.json",
            requires_artifacts=("live_signals.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="committee_runtime",
            command=[PYTHON, str(root / "tae_committee_runtime.py")],
            artifact="tae_committee_runtime.json",
            needs_pythonpath=True,
        ),
        StepSpec(
            name="live_signals_committee_enrich",
            command=[PYTHON, str(root / "tae_live_signals_committee_enrich.py")],
            artifact="tae_live_signals_committee_enrich.json",
            requires_artifacts=("live_signals.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="learning_runtime",
            command=[PYTHON, str(root / "tae_learning_runtime.py")],
            artifact="tae_learning_runtime.json",
            needs_pythonpath=True,
        ),
        StepSpec(
            name="strategic_allocation_runtime",
            command=[PYTHON, str(root / "tae_strategic_allocation_runtime.py")],
            artifact="tae_strategic_allocation_runtime.json",
            needs_pythonpath=True,
        ),
        StepSpec(
            name="live_signals_allocation_enrich",
            command=[PYTHON, str(root / "tae_live_signals_allocation_enrich.py")],
            artifact="tae_live_signals_allocation_enrich.json",
            requires_artifacts=("live_signals.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="meta_intelligence_runtime",
            command=[PYTHON, str(root / "tae_meta_intelligence_runtime.py")],
            artifact="tae_meta_intelligence_runtime.json",
            needs_pythonpath=True,
        ),
        StepSpec(
            name="live_signals_meta_enrich",
            command=[PYTHON, str(root / "tae_live_signals_meta_enrich.py")],
            artifact="tae_live_signals_meta_enrich.json",
            requires_artifacts=("live_signals.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="unified_runtime",
            command=[PYTHON, str(root / "tae_unified_runtime.py")],
            artifact="tae_unified_runtime.json",
            requires_artifacts=("live_signals.csv",),
            needs_pythonpath=True,
        ),
        StepSpec(
            name="candidate_queue_builder",
            command=[PYTHON, str(root / "tae_candidate_queue_builder.py")],
            artifact="tae_candidate_queue.json",
            requires_artifacts=("tae_unified_runtime.json",),
        ),
        StepSpec(
            name="watchlist_proposal",
            command=[PYTHON, str(root / "tae_watchlist_proposal.py")],
            artifact="tae_watchlist_proposal.json",
        ),
        StepSpec(
            name="actionable_signal_audit",
            command=[PYTHON, str(root / "tae_actionable_signal_audit.py")],
            artifact="tae_actionable_signal_audit.json",
        ),
    ]


def _run_step(root: Path, spec: StepSpec) -> StepResult:
    command_str = " ".join(spec.command)
    started = time.monotonic()

    for required in spec.requires_artifacts:
        if not (root / required).is_file():
            reason = f"Missing required input: {required}"
            _log_line(f"SKIP {spec.name}: {reason}", root)
            return StepResult(
                name=spec.name,
                command=command_str,
                status="SKIPPED",
                runtime_seconds=round(time.monotonic() - started, 3),
                artifact=spec.artifact,
                errors=reason,
            )

    env = os.environ.copy()
    if spec.needs_pythonpath:
        env["PYTHONPATH"] = str(root)

    _log_line(f"START {spec.name}: {command_str}", root)
    try:
        completed = subprocess.run(
            spec.command,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _log_line(f"FAIL {spec.name}: timeout after 900s", root)
        return StepResult(
            name=spec.name,
            command=command_str,
            status="FAIL",
            runtime_seconds=round(time.monotonic() - started, 3),
            artifact=spec.artifact,
            errors="Step timed out after 900 seconds",
        )
    except OSError as exc:
        _log_line(f"FAIL {spec.name}: {exc}", root)
        return StepResult(
            name=spec.name,
            command=command_str,
            status="FAIL",
            runtime_seconds=round(time.monotonic() - started, 3),
            artifact=spec.artifact,
            errors=str(exc),
        )

    runtime = round(time.monotonic() - started, 3)
    meta = _artifact_meta(root, spec.artifact)
    artifact_ok = bool(meta.get("present"))

    if completed.returncode != 0:
        status = "FAIL"
        err = _tail(completed.stderr or completed.stdout)
        _log_line(f"FAIL {spec.name} rc={completed.returncode}", root)
        return StepResult(
            name=spec.name,
            command=command_str,
            status=status,
            runtime_seconds=runtime,
            artifact=spec.artifact,
            row_count=meta.get("row_count"),
            freshness_hours=meta.get("freshness_hours"),
            artifact_mtime=meta.get("artifact_mtime"),
            errors=err or f"Exit code {completed.returncode}",
            stdout_tail=_tail(completed.stdout),
            stderr_tail=_tail(completed.stderr),
        )

    if spec.artifact and not artifact_ok:
        status = "FAIL"
        err = "Command succeeded but expected artifact was not produced"
        _log_line(f"FAIL {spec.name}: {err}", root)
    else:
        status = "OK"
        _log_line(
            f"OK {spec.name} runtime={runtime}s rows={meta.get('row_count')} artifact={spec.artifact}",
            root,
        )

    return StepResult(
        name=spec.name,
        command=command_str,
        status=status,
        runtime_seconds=runtime,
        artifact=spec.artifact,
        row_count=meta.get("row_count"),
        freshness_hours=meta.get("freshness_hours"),
        artifact_mtime=meta.get("artifact_mtime"),
        errors="" if status == "OK" else err,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _load_json_summary(root: Path, filename: str) -> dict[str, Any]:
    path = root / filename
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _final_verdict(results: list[StepResult]) -> str:
    statuses = {r.status for r in results}
    if any(r.status == "FAIL" and r.name in {"global_market_scanner", "multi_market_scanner"} for r in results):
        return "FAIL"
    if "FAIL" in statuses:
        return "WARNING"
    if all(s in {"OK", "SKIPPED"} for s in (r.status for r in results)):
        return "OK"
    return "WARNING"


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TAE Scanner Refresh",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** {report['final_verdict']}",
        f"**Total runtime:** {report['total_runtime_seconds']}s",
        "",
        "## Steps",
        "",
        "| Step | Status | Runtime (s) | Artifact | Rows | Freshness (h) |",
        "|------|--------|-------------|----------|------|---------------|",
    ]
    for step in report.get("steps") or []:
        lines.append(
            f"| {step['name']} | {step['status']} | {step['runtime_seconds']} | "
            f"{step.get('artifact') or '—'} | {step.get('row_count', '—')} | "
            f"{step.get('freshness_hours', '—')} |"
        )

    downstream = report.get("downstream") or {}
    lines.extend(
        [
            "",
            "## Downstream",
            "",
            f"- Candidate queue action: **{downstream.get('candidate_queue_action', 'NO_DATA')}**",
            f"- Promotion eligible: **{downstream.get('promotion_eligible_count', 'NO_DATA')}**",
            f"- Watchlist proposal recommended additions: **{downstream.get('watchlist_proposal_recommended_count', 'NO_DATA')}**",
            f"- Watchlist proposal queue action: **{downstream.get('watchlist_proposal_queue_action', 'NO_DATA')}**",
            "",
            "## Governance",
            "",
            "- Does **NOT** write `watchlist.txt`",
            "- Does **NOT** auto-promote watchlist",
            "- Does **NOT** modify live_bot BUY/SELL logic",
        ]
    )
    failed = [s for s in report.get("steps") or [] if s.get("status") == "FAIL"]
    if failed:
        lines.extend(["", "## Failures", ""])
        for step in failed:
            lines.append(f"### {step['name']}")
            lines.append(f"- Command: `{step['command']}`")
            if step.get("errors"):
                lines.append(f"- Error: {step['errors'][:500]}")
    return "\n".join(lines) + "\n"


def run_refresh(root: Path | str = DEFAULT_ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    started = time.monotonic()
    _log_line("===== TAE SCANNER REFRESH START =====", root)

    steps = _build_steps(root)
    results: list[StepResult] = []

    for spec in steps:
        result = _run_step(root, spec)
        results.append(result)

    total_runtime = round(time.monotonic() - started, 3)
    verdict = _final_verdict(results)

    queue = _load_json_summary(root, "tae_candidate_queue.json")
    proposal = _load_json_summary(root, "tae_watchlist_proposal.json")
    queue_summary = queue.get("summary") or {}
    proposal_summary = proposal.get("summary") or {}

    artifacts_refreshed = [
        {
            "artifact": r.artifact,
            **_artifact_meta(root, r.artifact),
        }
        for r in results
        if r.artifact and r.status == "OK"
    ]

    report = {
        "schema": "tae.scanner_refresh.v1",
        "mode": REFRESH_MODE,
        "live_trading_impact": "NONE",
        "generated_at": _utc_now_iso(),
        "final_verdict": verdict,
        "total_runtime_seconds": total_runtime,
        "watchlist_txt_written": False,
        "steps": [asdict(r) for r in results],
        "artifacts_refreshed": artifacts_refreshed,
        "downstream": {
            "candidate_queue_action": queue_summary.get("recommended_action"),
            "promotion_eligible_count": queue_summary.get("promotion_eligible_count"),
            "watchlist_proposal_recommended_count": proposal_summary.get(
                "recommended_additions_count"
            ),
            "watchlist_proposal_queue_action": proposal_summary.get(
                "candidate_queue_recommended_action"
            ),
        },
        "step_counts": {
            "ok": sum(1 for r in results if r.status == "OK"),
            "fail": sum(1 for r in results if r.status == "FAIL"),
            "skipped": sum(1 for r in results if r.status == "SKIPPED"),
        },
    }

    (root / OUTPUT_JSON).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (root / OUTPUT_MD).write_text(_render_markdown(report), encoding="utf-8")

    _log_line(
        f"===== TAE SCANNER REFRESH END verdict={verdict} runtime={total_runtime}s "
        f"ok={report['step_counts']['ok']} fail={report['step_counts']['fail']} "
        f"skipped={report['step_counts']['skipped']} =====",
        root,
    )
    return report


def main() -> int:
    root = Path(".")
    report = run_refresh(root)

    print("===== TAE SCANNER REFRESH =====")
    print(f"Verdict: {report['final_verdict']}")
    print(f"Total runtime: {report['total_runtime_seconds']}s")
    print(
        f"Steps: OK={report['step_counts']['ok']} "
        f"FAIL={report['step_counts']['fail']} "
        f"SKIPPED={report['step_counts']['skipped']}"
    )
    for step in report["steps"]:
        print(
            f"  - {step['name']}: {step['status']} ({step['runtime_seconds']}s) "
            f"artifact={step.get('artifact') or '—'} rows={step.get('row_count', '—')}"
        )
    downstream = report.get("downstream") or {}
    print(f"Candidate queue action: {downstream.get('candidate_queue_action')}")
    print(
        f"Watchlist proposal recommended additions: "
        f"{downstream.get('watchlist_proposal_recommended_count')}"
    )
    print(f"Output: {OUTPUT_JSON}, {OUTPUT_MD}, {LOG_FILE}")
    return 0 if report["final_verdict"] in {"OK", "WARNING"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
