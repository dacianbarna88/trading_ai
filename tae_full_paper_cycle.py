#!/usr/bin/env python3
"""
TAE Full PAPER Cycle — orchestrates existing intelligence into one closed loop.

PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION
PAPER decisions execute in runtime_outputs/paper_execution/ only.
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
PAPER_EXEC_PORTFOLIO = Path("runtime_outputs/paper_execution/paper_portfolio.json")
PAPER_EXEC_ATTRIBUTION = Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
PAPER_EXEC_TRADES = Path("runtime_outputs/paper_execution/paper_trades.jsonl")
PAPER_EXEC_ORDERS = Path("runtime_outputs/paper_execution/paper_orders.jsonl")
PAPER_MTM_JSON = Path("runtime_outputs/paper_execution/mark_to_market.json")
RULE_LIFECYCLE_JSON = Path("runtime_outputs/paper_execution/rule_lifecycle.json")
ADAPTIVE_WEIGHTS_JSON = Path("runtime_outputs/adaptive_weights/paper_action_weights.json")
PRE_EVOLUTION_DECISIONS = Path("runtime_outputs/paper_decisions/paper_decisions_pre_evolution.json")
PRE_EVOLUTION_WEIGHTS = Path("runtime_outputs/adaptive_weights/paper_action_weights_pre_evolution.json")
EVOLUTION_JSON = Path("runtime_outputs/governance/constitutional_evolution.json")

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
    ("paper_execution", [sys.executable, "tae.py", "paper-execution"]),
    ("paper_mark_to_market", [sys.executable, "tae.py", "paper-mark-to-market"]),
    ("paper_experiments", [sys.executable, "tae.py", "paper-experiments"]),
    ("outcome_memory", [sys.executable, "tae.py", "outcome-memory"]),
    ("adaptive_weights", [sys.executable, "tae.py", "adaptive-weights"]),
    ("dpe_events", [sys.executable, "tae.py", "dpe-events"]),
    ("dpe_splitter", [sys.executable, "tae.py", "dpe-splitter"]),
    ("dpe_competitive", [sys.executable, "tae.py", "dpe-competitive"]),
    ("dpe_collaborative", [sys.executable, "tae.py", "dpe-collaborative"]),
    ("dpe_evaluator", [sys.executable, "tae.py", "dpe-evaluator"]),
    ("dpe_learning", [sys.executable, "tae.py", "dpe-learning"]),
    ("dpe_adaptive", [sys.executable, "tae.py", "dpe-adaptive"]),
    ("strategy_survival", [sys.executable, "tae.py", "strategy-survival"]),
    ("canonical_vs_paper", [sys.executable, "tae.py", "canonical-vs-paper"]),
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
    """True when prior-cycle economic feedback can drive pre-PDE evolution."""
    candidates = (
        root / VALIDATION_JSON,
        root / MEMORY_JSONL,
        root / PAPER_EXEC_ATTRIBUTION,
        root / ADAPTIVE_WEIGHTS_JSON,
        root / PAPER_EXEC_TRADES,
    )
    return any(p.is_file() for p in candidates)


def archive_pre_evolution_snapshot(root: Path, *, kind: str) -> None:
    """Preserve executed-decision / pre-learning weight state for same-cycle evolution proof."""
    if kind == "decisions":
        src = root / DECISIONS_JSON
        if src.is_file():
            dst = root / PRE_EVOLUTION_DECISIONS
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    elif kind == "weights":
        src = root / ADAPTIVE_WEIGHTS_JSON
        if src.is_file():
            dst = root / PRE_EVOLUTION_WEIGHTS
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _decision_index(doc: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _s(row.get("ticker")).upper(): row
        for row in (doc or {}).get("decisions") or []
        if _s(row.get("ticker"))
    }


def _weight_index(doc: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for action, row in ((doc or {}).get("weights") or {}).items():
        out[_s(action).upper()] = _f((row or {}).get("new_weight"), 1.0)
    return out


def compare_constitutional_evolution(
    before_decisions: dict[str, Any] | None,
    after_decisions: dict[str, Any] | None,
    before_weights: dict[str, Any] | None,
    after_weights: dict[str, Any] | None,
) -> dict[str, Any]:
    before_idx = _decision_index(before_decisions)
    after_idx = _decision_index(after_decisions)
    tickers = sorted(set(before_idx) | set(after_idx))
    decision_changes: list[dict[str, Any]] = []
    for ticker in tickers:
        b = before_idx.get(ticker) or {}
        a = after_idx.get(ticker) or {}
        b_action = _s(b.get("action"))
        a_action = _s(a.get("action"))
        b_conf = _f(b.get("confidence"))
        a_conf = _f(a.get("confidence"))
        if b_action != a_action or abs(b_conf - a_conf) >= 0.001:
            decision_changes.append(
                {
                    "ticker": ticker,
                    "action_before": b_action or None,
                    "action_after": a_action or None,
                    "confidence_before": round(b_conf, 4),
                    "confidence_after": round(a_conf, 4),
                }
            )

    bw = _weight_index(before_weights)
    aw = _weight_index(after_weights)
    weight_changes: list[dict[str, Any]] = []
    for action in sorted(set(bw) | set(aw)):
        prev = bw.get(action, 1.0)
        new = aw.get(action, 1.0)
        if abs(new - prev) >= 0.0001:
            weight_changes.append(
                {
                    "action": action,
                    "weight_before": round(prev, 4),
                    "weight_after": round(new, 4),
                    "delta": round(new - prev, 4),
                }
            )

    evolved = bool(decision_changes or weight_changes)
    attribution_doc = _load_json(PAPER_EXEC_ATTRIBUTION) or {}
    return {
        "schema": "tae.constitutional_evolution.v1",
        "mode": MODE,
        "generated_at": _now(),
        "loop_closed": evolved,
        "human_intervention_required": False,
        "decision_changes": decision_changes,
        "weight_changes": weight_changes,
        "decision_change_count": len(decision_changes),
        "weight_change_count": len(weight_changes),
        "attribution_rule_count": len(attribution_doc.get("rules") or {}),
    }


def run_post_learning_evolution(root: Path, step_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-run PDE after economic attribution + weight change; persist evolution evidence."""
    before_decisions = _load_json(root / PRE_EVOLUTION_DECISIONS) or _load_json(root / DECISIONS_JSON)
    before_weights = _load_json(root / PRE_EVOLUTION_WEIGHTS) or _load_json(root / ADAPTIVE_WEIGHTS_JSON)

    print("\n>>> [constitutional_evolution] re-running paper-decisions after learning feedback")
    from tae_paper_decision_engine import main as run_pde

    exit_code = int(run_pde())
    after_decisions = _load_json(root / DECISIONS_JSON) or {}
    after_weights = _load_json(root / ADAPTIVE_WEIGHTS_JSON) or {}

    evolution = compare_constitutional_evolution(
        before_decisions,
        after_decisions,
        before_weights,
        after_weights,
    )
    evolution["pde_exit_code"] = exit_code
    evolution["ok"] = exit_code == 0
    EVOLUTION_JSON.parent.mkdir(parents=True, exist_ok=True)
    EVOLUTION_JSON.write_text(json.dumps(evolution, indent=2) + "\n", encoding="utf-8")

    step_results.append(
        {
            "step": "constitutional_evolution",
            "ok": evolution["ok"],
            "exit_code": exit_code,
            "loop_closed": evolution["loop_closed"],
            "decision_change_count": evolution["decision_change_count"],
            "weight_change_count": evolution["weight_change_count"],
            "output": str(EVOLUTION_JSON),
        }
    )
    print(
        f">>> [constitutional_evolution] loop_closed={evolution['loop_closed']} "
        f"decision_deltas={evolution['decision_change_count']} weight_deltas={evolution['weight_change_count']}"
    )
    return evolution


def run_pre_pde_feedback(root: Path, step_results: list[dict[str, Any]]) -> None:
    if not feedback_artifacts_exist(root):
        print("\n>>> [pre_pde_feedback] skipped — no prior validation/memory artifacts")
        return
    from tae_longitudinal_outcome_memory import run_longitudinal_memory
    from tae_adaptive_paper_weights import run_adaptive_paper_weights
    from tae_rule_survival import run_rule_survival

    print("\n>>> [pre_pde_feedback] refreshing longitudinal memory + adaptive weights + rule survival before paper-decisions")
    mem_result = run_longitudinal_memory()
    mem_idx = mem_result.get("index") or {}
    weights_result = run_adaptive_paper_weights()
    weights_doc = weights_result.get("document") or {}
    survival_result = run_rule_survival(write_report_flag=True)
    survival_doc = survival_result.get("document") or {}
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
    step_results.append(
        {
            "step": "pre_pde_rule_survival",
            "ok": survival_result.get("ok", False),
            "exit_code": 0,
            "rules_classified": len(survival_doc.get("rules") or {}),
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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _trades_today_count() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    count = 0
    for row in _load_jsonl(PAPER_EXEC_TRADES):
        ts = _s(row.get("timestamp") or row.get("executed_at") or row.get("generated_at"))
        if ts.startswith(today):
            count += 1
    return count


def _mark_to_market_status(mtm: dict[str, Any]) -> str:
    live = int(_f(mtm.get("live_price_count")))
    stale = int(_f(mtm.get("stale_price_count")))
    if not mtm:
        return "NOT_RUN"
    if stale == 0 and live > 0:
        return "LIVE"
    if live > 0:
        return "PARTIAL_STALE"
    if stale > 0:
        return "ALL_STALE"
    return "EMPTY"


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
    paper_portfolio = _load_json(PAPER_EXEC_PORTFOLIO) or {}
    paper_attribution = _load_json(PAPER_EXEC_ATTRIBUTION) or {}
    paper_mtm = _load_json(PAPER_MTM_JSON) or {}
    rule_lifecycle = _load_json(RULE_LIFECYCLE_JSON) or {}
    decisions = decisions_doc.get("decisions") or []

    blocked_no_position = sum(
        1 for d in decisions if (d.get("position_discipline") or {}).get("blocked")
    )
    losing_evals = [
        d
        for d in decisions
        if (d.get("loss_discipline") or {}).get("evaluated")
        and _f((d.get("loss_discipline") or {}).get("current_pct")) <= -5.0
    ]
    lifecycle_by_state = rule_lifecycle.get("by_state") or {}

    canonical_value = _f(accounting.get("account_value_corrected") or accounting.get("total_account_value"))
    paper_value = _f(paper_portfolio.get("total_value"))
    rules = paper_attribution.get("rules") or {}
    strengthened = [rid for rid, row in rules.items() if _f(row.get("recommended_influence_delta")) > 0]
    weakened = [rid for rid, row in rules.items() if _f(row.get("recommended_influence_delta")) < 0]
    top_profitable = sorted(
        rules.items(),
        key=lambda x: -_f(x[1].get("avg_actual_pnl")),
    )[:3]
    top_damaging = sorted(
        rules.items(),
        key=lambda x: _f(x[1].get("avg_actual_pnl")),
    )[:3]

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

    from tae_paper_execution import check_paper_profit_integrity, validate_portfolio_reconciliation

    paper_reconciliation = validate_portfolio_reconciliation(paper_portfolio) if paper_portfolio else {"ok": True, "status": "UNKNOWN"}
    profit_integrity = check_paper_profit_integrity(
        portfolio=paper_portfolio,
        accounting=accounting,
        write_report_flag=True,
        update_validation_json=True,
    )
    mtm_status = _mark_to_market_status(paper_mtm)
    broker_flag = bool(paper_portfolio.get("broker_executed")) or bool(paper_portfolio.get("live_money"))
    reconciliation_fail = not paper_reconciliation.get("ok")
    profit_integrity_fail = not profit_integrity.get("ok")
    mtm_all_stale = mtm_status == "ALL_STALE" and len(paper_portfolio.get("positions") or {}) > 0

    if (
        not forbidden_ok
        or infra_fail
        or blocking_failed
        or reconciliation_fail
        or profit_integrity_fail
        or broker_flag
        or mtm_all_stale
    ):
        final_verdict = "BLOCKED_WITH_REASONS"
    elif failed_steps or hist_stale_list or stale_sources or not infra_pass:
        final_verdict = "READY_WITH_WARNINGS"
    else:
        final_verdict = "READY_FOR_PAPER_DAY"

    portfolio = accounting.get("portfolio_summary") or accounting

    switch_accepted = sum(
        1
        for d in decisions
        if d.get("previous_action")
        and d.get("previous_action") != d.get("action")
        and d.get("decision_switch_authorized")
    )
    switch_blocked = sum(
        1
        for d in decisions
        if d.get("previous_action")
        and d.get("previous_action") != d.get("action")
        and not d.get("decision_switch_authorized")
    )
    skipped_switch_exec = sum(
        1 for row in _load_jsonl(PAPER_EXEC_ORDERS) if row.get("status") == "SKIPPED_SWITCH_NOT_AUTHORIZED"
    )

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
        "paper_execution_enabled": True,
        "paper_portfolio_value": _f(paper_portfolio.get("total_value")),
        "paper_portfolio_positions": len(paper_portfolio.get("positions") or {}),
        "paper_execution_rules_tracked": len(paper_attribution.get("rules") or {}),
        "paper_broker_executed": paper_portfolio.get("broker_executed", False),
        "paper_cash": _f(paper_portfolio.get("cash")),
        "paper_realized_pnl": _f(paper_portfolio.get("realized_pnl")),
        "paper_unrealized_pnl": _f(paper_portfolio.get("unrealized_pnl")),
        "paper_total_pnl": _f(paper_portfolio.get("total_pnl")),
        "paper_reconciliation_status": paper_reconciliation.get("status"),
        "paper_reconciliation_ok": paper_reconciliation.get("ok"),
        "profit_integrity_status": profit_integrity.get("status"),
        "profit_integrity_ok": profit_integrity.get("ok"),
        "validation_capital_base": (profit_integrity.get("metrics") or {}).get("validation_capital_base"),
        "profit_vs_capital_base": (profit_integrity.get("metrics") or {}).get("profit_vs_capital_base"),
        "paper_drawdown_pct": paper_portfolio.get("drawdown_pct"),
        "mark_to_market_stale_count": paper_mtm.get("stale_price_count"),
        "mark_to_market_live_count": paper_mtm.get("live_price_count"),
        "mark_to_market_status": _mark_to_market_status(paper_mtm),
        "executed_trades_today": _trades_today_count(),
        "canonical_vs_paper_value_delta": round(paper_value - canonical_value, 4),
        "rules_strengthened": strengthened[:5],
        "rules_weakened": weakened[:5],
        "top_profitable_rules": [{"rule_id": k, "avg_actual_pnl": v.get("avg_actual_pnl")} for k, v in top_profitable],
        "top_damaging_rules": [{"rule_id": k, "avg_actual_pnl": v.get("avg_actual_pnl")} for k, v in top_damaging],
        "top_disabled_rules": (lifecycle_by_state.get("DISABLED") or [])[:5],
        "top_deprecated_rules": (lifecycle_by_state.get("DEPRECATED") or [])[:5],
        "top_trusted_rules": (lifecycle_by_state.get("TRUSTED") or [])[:5],
        "decisions_blocked_no_position": blocked_no_position,
        "losing_positions_evaluated": [
            {
                "ticker": d.get("ticker"),
                "current_pct": (d.get("loss_discipline") or {}).get("current_pct"),
                "action": d.get("action"),
                "preferred": (d.get("loss_discipline") or {}).get("preferred"),
            }
            for d in losing_evals
        ],
        "decision_switch_accepted_count": switch_accepted,
        "decision_switch_blocked_count": switch_blocked,
        "execution_skipped_switch_count": skipped_switch_exec,
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
        "",
        "## PAPER execution intelligence",
        "",
        f"- PAPER portfolio value: **${summary.get('paper_portfolio_value', 0):,.2f}**",
        f"- PAPER cash: **${summary.get('paper_cash', 0):,.2f}**",
        f"- PAPER unrealized PnL: **${summary.get('paper_unrealized_pnl', 0):,.2f}**",
        f"- PAPER realized PnL: **${summary.get('paper_realized_pnl', 0):,.2f}**",
        f"- PAPER total PnL: **${summary.get('paper_total_pnl', 0):,.2f}**",
        f"- PAPER reconciliation: **{summary.get('paper_reconciliation_status')}**",
        f"- Canonical vs PAPER value delta: **${summary.get('canonical_vs_paper_value_delta', 0):,.2f}**",
        f"- Mark-to-market status: **{summary.get('mark_to_market_status')}**",
        f"- Mark-to-market live prices: **{summary.get('mark_to_market_live_count')}**",
        f"- Mark-to-market stale prices: **{summary.get('mark_to_market_stale_count')}**",
        f"- Executed trades today: **{summary.get('executed_trades_today', 0)}**",
        f"- Rules strengthened: `{summary.get('rules_strengthened')}`",
        f"- Rules weakened: `{summary.get('rules_weakened')}`",
        f"- Top profitable rules: `{summary.get('top_profitable_rules')}`",
        f"- Top damaging rules: `{summary.get('top_damaging_rules')}`",
        f"- Top disabled rules: `{summary.get('top_disabled_rules')}`",
        f"- Top deprecated rules: `{summary.get('top_deprecated_rules')}`",
        f"- Top trusted rules: `{summary.get('top_trusted_rules')}`",
        f"- Decisions blocked (no PAPER position): **{summary.get('decisions_blocked_no_position', 0)}**",
        f"- Losing positions evaluated: `{summary.get('losing_positions_evaluated')}`",
        "",
        "## Decision state (anti-churn)",
        "",
        f"- PDE switch authorized: **{summary.get('decision_switch_accepted_count', 0)}**",
        f"- PDE switch blocked: **{summary.get('decision_switch_blocked_count', 0)}**",
        f"- Execution skipped (unauthorized switch): **{summary.get('execution_skipped_switch_count', 0)}**",
        "",
        "## Top PAPER actions (by confidence)",
        "",
        f"- BUY_PAPER: `{summary.get('top_buy_paper')}`",
        f"- SELL_PAPER: `{summary.get('top_sell_paper')}`",
        f"- PROTECT_PAPER: `{summary.get('top_protect_paper')}`",
        f"- ROTATE_PAPER: `{summary.get('top_rotate_paper')}`",
        f"- HOLD_PAPER: `{summary.get('top_hold_paper')}`",
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
    """Delegate to structural governance — single mandatory execution hierarchy."""
    from tae_structural_governance import run_structural_paper_cycle

    exit_code, _state = run_structural_paper_cycle()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
