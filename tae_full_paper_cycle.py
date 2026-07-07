#!/usr/bin/env python3
"""
TAE Full PAPER Cycle — orchestrates existing intelligence into one closed loop.

PAPER_ONLY | READ_ONLY | NO_BROKER | NO_LIVE_CHANGE | NO_EXECUTION
Does NOT modify live_bot.py, portfolio.csv, live_signals.csv, or watchlist.txt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "PAPER_ONLY"
OUTPUT_DIR = Path("runtime_outputs/full_paper_cycle")
SUMMARY_JSON = OUTPUT_DIR / "summary.json"
REPORT_MD = Path("TAE_FULL_PAPER_CYCLE_REPORT.md")

ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")
DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
EXPERIMENTS_JSON = Path("runtime_outputs/learning_to_profit/experiment_results.json")
ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
INFRA_JSON = Path("tae_infrastructure_health.json")
GII_JSON = Path("tae_growth_intelligence.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
PROMOTION_JSON = OUTPUT_DIR / "promotion_gate.json"
MEMORY_JSONL = Path("runtime_outputs/longitudinal_memory/decisions.jsonl")

FORBIDDEN_SNAPSHOT = (
    "live_bot.py",
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
)

FORBIDDEN_GIT_PATHS = FORBIDDEN_SNAPSHOT + (
    "core/",
    "research_core/",
)

CYCLE_STEPS: list[tuple[str, list[str]]] = [
    ("health", [sys.executable, "tae.py", "health"]),
    ("morning_audit", [sys.executable, "tae.py", "morning-audit"]),
    ("learning_profit", [sys.executable, "tae.py", "learning-profit"]),
    ("paper_decisions", [sys.executable, "tae.py", "paper-decisions"]),
    ("paper_experiments", [sys.executable, "tae.py", "paper-experiments"]),
    ("dpe_events", [sys.executable, "tae.py", "dpe-events"]),
    ("dpe_splitter", [sys.executable, "tae.py", "dpe-splitter"]),
    ("dpe_competitive", [sys.executable, "tae.py", "dpe-competitive"]),
    ("dpe_collaborative", [sys.executable, "tae.py", "dpe-collaborative"]),
    ("dpe_evaluator", [sys.executable, "tae.py", "dpe-evaluator"]),
    ("dpe_learning", [sys.executable, "tae.py", "dpe-learning"]),
    ("dpe_adaptive", [sys.executable, "tae.py", "dpe-adaptive"]),
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


def _file_mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.is_file() else None


def forbidden_files_unchanged(before: dict[str, float | None], after: dict[str, float | None]) -> bool:
    """Legacy mtime comparison — prefer check_forbidden_file_safety() for cycle gates."""
    return before == after


def check_forbidden_file_safety(
    root: Path,
    *,
    before_mtimes: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """Block only on real git content diff; report mtime drift separately."""
    before_mtimes = before_mtimes or {}
    after_mtimes = {name: _file_mtime(root / name) for name in FORBIDDEN_SNAPSHOT}
    mtime_drift = bool(before_mtimes) and before_mtimes != after_mtimes

    changed_files: list[str] = []
    diff_text = ""
    git_ok = True
    git_detail = ""

    try:
        diff_result = subprocess.run(
            ["git", "diff", "--", *FORBIDDEN_GIT_PATHS],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        names_result = subprocess.run(
            ["git", "diff", "--name-only", "--", *FORBIDDEN_GIT_PATHS],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if diff_result.returncode != 0 and not (diff_result.stdout or diff_result.stderr):
            git_ok = False
            git_detail = (diff_result.stderr or "git diff failed").strip()
        else:
            diff_text = (diff_result.stdout or "").strip()
            changed_files = [line.strip() for line in (names_result.stdout or "").splitlines() if line.strip()]
    except (OSError, subprocess.TimeoutExpired) as exc:
        git_ok = False
        git_detail = str(exc)

    content_clean = git_ok and not diff_text and not changed_files
    diff_summary = "0 diff lines" if content_clean else diff_text[:500] or f"{len(changed_files)} file(s) changed"

    safety_block_reason = None
    if not git_ok:
        safety_block_reason = f"git diff unavailable: {git_detail}"
    elif not content_clean:
        safety_block_reason = f"forbidden content diff: {', '.join(changed_files) or 'see diff_summary'}"

    note = None
    if mtime_drift and content_clean:
        note = "mtime drift ignored, content diff clean"

    return {
        "forbidden_content_diff_clean": content_clean,
        "forbidden_mtime_drift_detected": mtime_drift,
        "forbidden_files_unchanged": content_clean,
        "safety_status": "PASS" if content_clean else "BLOCKED",
        "safety_block_reason": safety_block_reason,
        "changed_files": changed_files,
        "diff_summary": diff_summary,
        "note": note,
        "git_check_ok": git_ok,
    }


def feedback_artifacts_exist(root: Path) -> bool:
    return (root / VALIDATION_JSON).is_file() or (root / MEMORY_JSONL).is_file()


def run_pre_pde_feedback(root: Path, step_results: list[dict[str, Any]]) -> None:
    if not feedback_artifacts_exist(root):
        print("\n>>> [pre_pde_feedback] skipped — no prior validation/memory artifacts")
        return
    from tae_longitudinal_outcome_memory import run_longitudinal_memory
    from tae_adaptive_paper_weights import run_adaptive_paper_weights

    print("\n>>> [pre_pde_feedback] refreshing longitudinal memory + adaptive weights before paper-decisions")
    mem_result = run_longitudinal_memory()
    mem_idx = mem_result.get("index") or {}
    weights_result = run_adaptive_paper_weights()
    weights_doc = weights_result.get("document") or {}
    step_results.append(
        {
            "step": "pre_pde_longitudinal_memory",
            "ok": mem_result.get("ok", False),
            "exit_code": 0,
            "total_records": mem_idx.get("total_records"),
        }
    )
    step_results.append(
        {
            "step": "pre_pde_adaptive_weights",
            "ok": weights_result.get("ok", False),
            "exit_code": 0,
            "actions_weighted": len(weights_doc.get("weights") or {}),
        }
    )


def run_step(name: str, cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    print(f"\n>>> [{name}] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=False)
    return {"step": name, "command": cmd, "exit_code": int(result.returncode), "ok": result.returncode == 0}


def map_validation_verdict(verdict: str) -> str:
    mapping = {
        "PROMISING": "PROMOTE_TO_LIVE_CANDIDATE",
        "CONTINUE_TESTING": "CONTINUE_PAPER",
        "REJECT": "REJECT",
        "NEEDS_MORE_DATA": "NEEDS_MORE_DATA",
    }
    return mapping.get(verdict, "NEEDS_MORE_DATA")


def build_promotion_gate(validation: dict[str, Any] | None) -> dict[str, Any]:
    recommendations: list[dict[str, Any]] = []
    counts = {"PROMOTE_TO_LIVE_CANDIDATE": 0, "CONTINUE_PAPER": 0, "REJECT": 0, "NEEDS_MORE_DATA": 0}
    for row in (validation or {}).get("results") or []:
        rec = map_validation_verdict(_s(row.get("verdict")))
        counts[rec] = counts.get(rec, 0) + 1
        recommendations.append(
            {
                "ticker": row.get("ticker"),
                "action": row.get("action"),
                "validation_verdict": row.get("verdict"),
                "promotion_recommendation": rec,
                "live_promotion_allowed": False,
                "operator_approval_required": rec == "PROMOTE_TO_LIVE_CANDIDATE",
                "reason": row.get("reason"),
                "horizon_conflict_flag": row.get("horizon_conflict_flag"),
            }
        )
    return {
        "schema": "tae_paper_promotion_gate",
        "mode": MODE,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "recommendation_counts": counts,
        "recommendations": recommendations,
    }


def _s(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def collect_summary(
    step_results: list[dict[str, Any]],
    *,
    forbidden_ok: bool,
    safety: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from tae_historical_runtime_refresh import load_runtime_state

    hist_runtime = load_runtime_state()
    accounting = _load_json(ACCOUNTING_JSON) or {}
    validation = _load_json(VALIDATION_JSON) or {}
    decisions_doc = _load_json(DECISIONS_JSON) or {}
    experiments = _load_json(EXPERIMENTS_JSON) or {}
    adaptive = _load_json(ADAPTIVE_JSON) or {}
    evaluation = _load_json(EVAL_JSON) or {}
    infra = _load_json(INFRA_JSON) or {}
    gii = _load_json(GII_JSON) or {}
    ledger = _load_json(LEDGER_JSON) or {}

    decisions = decisions_doc.get("decisions") or []
    by_action: dict[str, list[dict[str, Any]]] = {}
    for d in decisions:
        by_action.setdefault(d.get("action") or "UNKNOWN", []).append(d)

    def top_action(action: str, n: int = 5) -> list[dict[str, Any]]:
        rows = sorted(by_action.get(action, []), key=lambda x: -_f(x.get("confidence")), reverse=False)
        return [
            {"ticker": r.get("ticker"), "confidence": r.get("confidence"), "horizon_reason": r.get("horizon_reason")}
            for r in rows[:n]
        ]

    val_verdicts = validation.get("verdict_summary") or {}
    horizon_conflicts = sum(1 for r in (validation.get("results") or []) if r.get("horizon_conflict_flag"))
    hist_stale_list = hist_runtime.get("stale_sources") or []
    stale_sources: list[str] = list(hist_stale_list)
    if not hist_runtime.get("all_fresh", True):
        for row in (hist_runtime.get("audit_after") or {}).get("sources") or []:
            if row.get("status") == "STALE":
                stale_sources.append(f"{row.get('path')} ({row.get('age_hours')}h)")

    failed_steps = [s["step"] for s in step_results if not s.get("ok")]
    infra_status = (infra or {}).get("overall_status") or "UNKNOWN"
    infra_pass = infra_status == "PASS"
    infra_fail = infra_status == "FAIL"
    blocking_steps = {"learning_profit", "paper_decisions", "paper_experiments"}
    blocking_failed = [s for s in failed_steps if s in blocking_steps]

    blocked_jobs = _f((evaluation or {}).get("blocked_jobs_count"))
    if not blocked_jobs:
        blocked_jobs = _f((experiments or {}).get("blocked_jobs"))

    promotion_gate = build_promotion_gate(validation)
    from tae_live_promotion_lock import enforce_promotion_gate

    promotion_gate = enforce_promotion_gate(promotion_gate)
    PROMOTION_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROMOTION_JSON.write_text(json.dumps(promotion_gate, indent=2) + "\n", encoding="utf-8")

    safety = safety or {}
    forbidden_ok = bool(safety.get("forbidden_content_diff_clean", forbidden_ok))

    if not forbidden_ok or infra_fail or blocking_failed:
        final_verdict = "BLOCKED_WITH_REASONS"
    elif failed_steps or hist_stale_list or stale_sources or not infra_pass:
        final_verdict = "READY_WITH_WARNINGS"
    else:
        final_verdict = "READY_FOR_PAPER_DAY"

    portfolio = accounting.get("portfolio_summary") or accounting
    return {
        "schema": "tae_full_paper_cycle_summary",
        "version": "v1",
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_live_execution": True,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "step_results": step_results,
        "forbidden_files_unchanged": forbidden_ok,
        "forbidden_content_diff_clean": safety.get("forbidden_content_diff_clean", forbidden_ok),
        "forbidden_mtime_drift_detected": safety.get("forbidden_mtime_drift_detected", False),
        "safety_status": safety.get("safety_status", "PASS" if forbidden_ok else "BLOCKED"),
        "safety_block_reason": safety.get("safety_block_reason"),
        "forbidden_changed_files": safety.get("changed_files") or [],
        "forbidden_diff_summary": safety.get("diff_summary"),
        "forbidden_safety_note": safety.get("note"),
        "portfolio_value": _f(accounting.get("account_value_corrected") or accounting.get("total_account_value")),
        "cash": _f(accounting.get("cash_available")),
        "open_positions": accounting.get("open_positions_count") or len(accounting.get("open_positions") or []),
        "realized_pnl": _f(accounting.get("realized_pnl")),
        "unrealized_pnl": _f(accounting.get("unrealized_pnl")),
        "total_pnl": _f(accounting.get("total_pnl")),
        "top_buy_paper": top_action("BUY_PAPER"),
        "top_sell_paper": top_action("SELL_PAPER"),
        "top_protect_paper": top_action("PROTECT_PAPER"),
        "top_rotate_paper": top_action("ROTATE_PAPER"),
        "top_hold_paper": top_action("HOLD_PAPER"),
        "promising_decisions": val_verdicts.get("PROMISING", 0),
        "continue_decisions": val_verdicts.get("CONTINUE_TESTING", 0),
        "reject_decisions": val_verdicts.get("REJECT", 0),
        "needs_more_data_decisions": val_verdicts.get("NEEDS_MORE_DATA", 0),
        "dpe_winner": evaluation.get("winner") or evaluation.get("preferred_philosophy"),
        "adaptive_philosophy": adaptive.get("preferred_philosophy") or adaptive.get("recommendation"),
        "confidence": adaptive.get("confidence") or evaluation.get("confidence"),
        "capital_efficiency_findings": (gii.get("portfolio") or {}).get("capital_efficiency"),
        "opportunity_cost_total": _f((ledger or {}).get("opportunity_cost_total") or (gii.get("portfolio") or {}).get("opportunity_cost_total")),
        "horizon_conflicts": horizon_conflicts,
        "historical_runtime_all_fresh": hist_runtime.get("critical_all_fresh", hist_runtime.get("all_fresh")),
        "historical_confidence_penalty": hist_runtime.get("confidence_penalty", 0),
        "stale_sources": stale_sources,
        "blocked_jobs": blocked_jobs,
        "infrastructure_status": infra_status,
        "promotion_gate": promotion_gate.get("recommendation_counts"),
        "final_verdict": final_verdict,
        "failed_steps": failed_steps,
    }


def write_report(summary: dict[str, Any]) -> None:
    lines = [
        "# TAE Full PAPER Cycle Report",
        "",
        f"**Generated:** {summary['generated_at']}",
        f"**Mode:** {MODE} — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE",
        f"**Final verdict:** **{summary['final_verdict']}**",
        "",
        "## Portfolio snapshot (read-only accounting)",
        "",
        f"- Portfolio value: **${summary.get('portfolio_value', 0):,.2f}**",
        f"- Cash: **${summary.get('cash', 0):,.2f}**",
        f"- Open positions: **{summary.get('open_positions', 0)}**",
        f"- Total PnL: **${summary.get('total_pnl', 0):,.2f}**",
        "",
        "## PAPER decision highlights",
        "",
        f"- PROMISING: **{summary.get('promising_decisions', 0)}**",
        f"- CONTINUE: **{summary.get('continue_decisions', 0)}**",
        f"- REJECT: **{summary.get('reject_decisions', 0)}**",
        f"- NEEDS_MORE_DATA: **{summary.get('needs_more_data_decisions', 0)}**",
        f"- Horizon conflicts: **{summary.get('horizon_conflicts', 0)}**",
        f"- Historical runtime all fresh: **{summary.get('historical_runtime_all_fresh')}**",
        f"- Historical confidence penalty: **{summary.get('historical_confidence_penalty', 0)}**",
        "",
        "## DPE & adaptive",
        "",
        f"- DPE winner: **{summary.get('dpe_winner')}**",
        f"- Adaptive philosophy: **{summary.get('adaptive_philosophy')}**",
        f"- Confidence: **{summary.get('confidence')}**",
        "",
        "## Promotion gate (live_promotion_allowed=false)",
        "",
        f"- Counts: `{json.dumps(summary.get('promotion_gate') or {})}`",
        "",
        "## Infrastructure & safety",
        "",
        f"- Infrastructure: **{summary.get('infrastructure_status')}**",
        f"- Safety status: **{summary.get('safety_status')}**",
        f"- Forbidden content diff clean: **{summary.get('forbidden_content_diff_clean')}**",
        f"- Forbidden mtime drift detected: **{summary.get('forbidden_mtime_drift_detected')}**",
        f"- Forbidden files unchanged (content): **{summary.get('forbidden_files_unchanged')}**",
    ]
    if summary.get("forbidden_safety_note"):
        lines.append(f"- Note: {summary.get('forbidden_safety_note')}")
    if summary.get("safety_block_reason"):
        lines.append(f"- Safety block reason: **{summary.get('safety_block_reason')}**")
        lines.append(f"- Changed files: `{summary.get('forbidden_changed_files')}`")
    lines.extend(
        [
        f"- Stale sources: {', '.join(summary.get('stale_sources') or []) or 'none flagged'}",
        f"- Failed steps: {', '.join(summary.get('failed_steps') or []) or 'none'}",
        "",
        "## Daily operator command",
        "",
        "```bash",
        "python3 tae.py full-paper-cycle",
        "```",
    ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(".").resolve()
    print("===== TAE FULL PAPER CYCLE =====")
    print(f"Mode: {MODE} | READ_ONLY | NO_BROKER | NO_LIVE_CHANGE | NO_EXECUTION")
    print("")

    before_mtimes = {name: _file_mtime(root / name) for name in FORBIDDEN_SNAPSHOT}

    # Phase P1: historical/strategic freshness before PAPER loop
    from tae_historical_runtime_refresh import run_historical_runtime_refresh

    hist_state = run_historical_runtime_refresh(root=root)
    step_results: list[dict[str, Any]] = [
        {
            "step": "historical_runtime_refresh",
            "ok": hist_state.get("critical_all_fresh", hist_state.get("all_fresh", False)),
            "exit_code": 0,
            "all_fresh": hist_state.get("all_fresh"),
            "critical_all_fresh": hist_state.get("critical_all_fresh", hist_state.get("all_fresh")),
            "stale_sources": hist_state.get("stale_sources"),
            "confidence_penalty": hist_state.get("confidence_penalty"),
        }
    ]

    # Regenerate audit artifacts (Phase 1–3)
    audit_code = subprocess.run([sys.executable, "tae_full_implementation_audit.py"], cwd=root, check=False).returncode

    if audit_code == 0:
        step_results.append({"step": "implementation_audit", "ok": True, "exit_code": 0})
    else:
        step_results.append({"step": "implementation_audit", "ok": False, "exit_code": audit_code})

    exit_code = 0
    for name, cmd in CYCLE_STEPS:
        if name == "paper_decisions":
            run_pre_pde_feedback(root, step_results)
        result = run_step(name, cmd, cwd=root)
        step_results.append(result)
        if not result["ok"] and name in {"health", "learning_profit", "paper_decisions", "paper_experiments"}:
            exit_code = result["exit_code"] or 1

    safety = check_forbidden_file_safety(root, before_mtimes=before_mtimes)
    forbidden_ok = bool(safety["forbidden_content_diff_clean"])
    if not forbidden_ok:
        print(f"ERROR: forbidden file content diff detected: {safety.get('changed_files')}", file=sys.stderr)
        if safety.get("diff_summary"):
            print(f"  diff: {safety.get('diff_summary')[:200]}", file=sys.stderr)
        exit_code = 1
    elif safety.get("note"):
        print(f"NOTE: {safety['note']}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = collect_summary(step_results, forbidden_ok=forbidden_ok, safety=safety)

    from tae_longitudinal_outcome_memory import run_longitudinal_memory

    print("\n>>> [longitudinal_memory] updating canonical PAPER outcome memory")
    mem_result = run_longitudinal_memory()
    mem_idx = mem_result.get("index") or {}

    from tae_adaptive_paper_weights import run_adaptive_paper_weights

    print("\n>>> [adaptive_weights] updating PAPER action weights from evidence")
    weights_result = run_adaptive_paper_weights()
    weights_doc = (weights_result.get("document") or {})

    step_results.append(
        {
            "step": "longitudinal_memory",
            "ok": mem_result.get("ok", False),
            "exit_code": 0,
            "total_records": mem_idx.get("total_records"),
            "new_records": mem_idx.get("new_records"),
            "checkpoints_updated": mem_idx.get("checkpoints_updated"),
        }
    )
    step_results.append(
        {
            "step": "adaptive_weights",
            "ok": weights_result.get("ok", False),
            "exit_code": 0,
            "actions_weighted": len(weights_doc.get("weights") or {}),
        }
    )
    summary["step_results"] = step_results
    summary["longitudinal_memory"] = {
        "total_records": mem_idx.get("total_records"),
        "new_records": mem_idx.get("new_records"),
        "checkpoints_updated": mem_idx.get("checkpoints_updated"),
        "knowledge_count": mem_idx.get("knowledge_count"),
    }
    summary["adaptive_weights"] = {
        "actions_weighted": len(weights_doc.get("weights") or {}),
        "ticker_adjustments": len(weights_doc.get("ticker_weights") or {}),
        "path": "runtime_outputs/adaptive_weights/paper_action_weights.json",
    }

    from tae_live_promotion_lock import run_live_promotion_lock_audit

    lock_report = run_live_promotion_lock_audit(rewrite_gate=True)
    step_results.append({"step": "promotion_lock", "ok": lock_report.get("pass", False), "exit_code": 0})
    summary["promotion_lock"] = {"pass": lock_report.get("pass"), "live_promotion_allowed": False}

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(summary)

    print("\n===== TAE FULL PAPER CYCLE — COMPLETE =====")
    print("Final verdict:", summary["final_verdict"])
    print("Wrote:", SUMMARY_JSON, REPORT_MD, PROMOTION_JSON)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
