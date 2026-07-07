#!/usr/bin/env python3
"""
TAE Full PAPER Cycle Retest — Phase 7 validation orchestrator.

Runs the complete pre-validation command chain and writes a retest report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_MD = Path("TAE_FULL_PAPER_CYCLE_RETEST_REPORT.md")
FORBIDDEN = (
    "live_bot.py",
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "core/",
    "research_core/",
)

COMMANDS: list[tuple[str, list[str]]] = [
    ("historical_refresh", [sys.executable, "tae.py", "historical-refresh"]),
    ("health", [sys.executable, "tae.py", "health"]),
    ("morning_audit", [sys.executable, "tae.py", "morning-audit"]),
    ("learning_profit", [sys.executable, "tae.py", "learning-profit"]),
    ("paper_decisions", [sys.executable, "tae.py", "paper-decisions"]),
    ("paper_experiments", [sys.executable, "tae.py", "paper-experiments"]),
    ("outcome_memory", [sys.executable, "tae.py", "outcome-memory"]),
    ("adaptive_weights", [sys.executable, "tae.py", "adaptive-weights"]),
    ("strategy_survival", [sys.executable, "tae.py", "strategy-survival"]),
    ("long_term_learning", [sys.executable, "tae.py", "long-term-learning"]),
    ("philosophy_performance", [sys.executable, "tae.py", "philosophy-performance"]),
    ("full_paper_cycle", [sys.executable, "tae.py", "full-paper-cycle"]),
    ("promotion_lock", [sys.executable, "tae_live_promotion_lock.py"]),
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.is_file() else None


def run_step(name: str, cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    print(f"\n>>> [{name}] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, check=False)
    return {"step": name, "command": cmd, "exit_code": int(result.returncode), "ok": result.returncode == 0}


def forbidden_diff(before: dict[str, float | None], after: dict[str, float | None]) -> bool:
    return before == after


def evaluate_verdict(results: list[dict[str, Any]], *, forbidden_ok: bool) -> tuple[str, list[str]]:
    blockers: list[str] = []
    summary = _load_json(Path("runtime_outputs/full_paper_cycle/summary.json")) or {}
    infra = _load_json(Path("tae_infrastructure_health.json")) or {}
    hist = _load_json(Path("runtime_outputs/historical_runtime/runtime_state.json")) or {}

    if not forbidden_ok:
        blockers.append("forbidden file mutation detected")
    if infra.get("overall_status") == "FAIL":
        blockers.append("infrastructure FAIL")
    if not (_load_json(Path("runtime_outputs/paper_decisions/decision_validation_results.json"))):
        blockers.append("missing decision validation")
    if not Path("runtime_outputs/longitudinal_memory/decisions.jsonl").is_file():
        blockers.append("missing longitudinal memory")
    if not Path("runtime_outputs/adaptive_weights/paper_action_weights.json").is_file():
        blockers.append("missing adaptive weights")

    stale = hist.get("stale_sources") or summary.get("stale_sources") or []
    critical_stale = [s for s in stale if "critical" in str(s).lower() or "historical_intelligence" in str(s)]
    if critical_stale:
        blockers.append(f"critical stale sources: {critical_stale[:3]}")

    gate = _load_json(Path("runtime_outputs/full_paper_cycle/promotion_gate.json")) or {}
    if gate.get("live_promotion_allowed") is True:
        blockers.append("live_promotion_allowed=true in promotion gate")

    failed = [r["step"] for r in results if not r.get("ok")]
    critical_failed = [s for s in failed if s in {"paper_decisions", "paper_experiments", "full_paper_cycle", "outcome_memory", "adaptive_weights"}]
    if critical_failed:
        blockers.append(f"critical step failures: {critical_failed}")

    if blockers:
        if any("infrastructure FAIL" in b or "forbidden" in b for b in blockers):
            return "BLOCKED_WITH_REASONS", blockers
        return "READY_WITH_WARNINGS", blockers
    return summary.get("final_verdict") or "READY_FOR_PAPER_DAY", blockers


def write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# TAE Full PAPER Cycle Retest Report",
        "",
        f"**Generated:** {payload['generated_at']}",
        f"**Final verdict:** **{payload['final_verdict']}**",
        "",
        "## Command results",
        "",
        "| step | ok | exit |",
        "| --- | --- | --- |",
    ]
    for row in payload["step_results"]:
        lines.append(f"| {row['step']} | {row.get('ok')} | {row.get('exit_code')} |")
    lines.extend(
        [
            "",
            "## Checks",
            "",
            f"- Forbidden files unchanged: **{payload.get('forbidden_ok')}**",
            f"- Adaptive weights present: **{payload.get('adaptive_weights_present')}**",
            f"- Outcome memory records: **{payload.get('memory_records')}**",
            f"- Infrastructure: **{payload.get('infrastructure_status')}**",
            f"- Autostart: **{payload.get('autostart_readiness')}**",
            "",
            "## Blockers / warnings",
            "",
        ]
    )
    blockers = payload.get("blockers") or []
    lines.extend(f"- {b}" for b in blockers) if blockers else lines.append("- none")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(".").resolve()
    print("===== TAE FULL PAPER CYCLE RETEST =====")
    before = {name: _mtime(root / name) for name in FORBIDDEN if not name.endswith("/")}
    results: list[dict[str, Any]] = []
    for name, cmd in COMMANDS:
        results.append(run_step(name, cmd, cwd=root))
    after = {name: _mtime(root / name) for name in FORBIDDEN if not name.endswith("/")}
    forbidden_ok = forbidden_diff(before, after)

    weights = _load_json(Path("runtime_outputs/adaptive_weights/paper_action_weights.json"))
    memory = _load_json(Path("runtime_outputs/longitudinal_memory/memory_index.json"))
    infra = _load_json(Path("tae_infrastructure_health.json")) or {}
    verdict, blockers = evaluate_verdict(results, forbidden_ok=forbidden_ok)

    payload = {
        "generated_at": _now(),
        "step_results": results,
        "forbidden_ok": forbidden_ok,
        "final_verdict": verdict,
        "blockers": blockers,
        "adaptive_weights_present": bool(weights),
        "memory_records": (memory or {}).get("total_records"),
        "infrastructure_status": infra.get("overall_status"),
        "autostart_readiness": infra.get("autostart_readiness"),
    }
    write_report(payload)
    print("\nRetest verdict:", verdict)
    print("Wrote:", REPORT_MD)
    return 0 if verdict in {"READY_FOR_PAPER_DAY", "READY_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
