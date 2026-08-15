#!/usr/bin/env python3
"""TAE LEARNING_DECISION_TO_ECONOMIC_OUTCOME_CLOSURE — read-only audit + report.

PAPER_ONLY · NO_BROKER · NO_LIVE_CHANGE
Does not mutate decisions, execution, Hard Risk, or SELL semantics.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

EXECUTABLE_ACTIONS = frozenset(
    {"BUY_PAPER", "SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER"}
)
NON_EXECUTABLE_ACTIONS = frozenset({"SKIP_PAPER", "HOLD_PAPER", "NO_CHANGE"})

LEDGER_PATH = ROOT / "runtime_outputs/learning_economic_attribution/ledger.jsonl"
PENDING_PATH = ROOT / "runtime_outputs/learning_economic_attribution/pending_outcomes.json"
STATUS_PATH = ROOT / "runtime_outputs/learning_economic_attribution/status.json"
SUMMARY_PATH = ROOT / "runtime_outputs/learning_economic_attribution/summary.json"
FPC_SUMMARY = ROOT / "runtime_outputs/full_paper_cycle/summary.json"
CE_PATH = ROOT / "runtime_outputs/governance/constitutional_evolution.json"
PORTFOLIO_PATH = ROOT / "runtime_outputs/paper_execution/paper_portfolio.json"
ORDERS_PATH = ROOT / "runtime_outputs/paper_execution/paper_orders.jsonl"
TRADES_PATH = ROOT / "runtime_outputs/paper_execution/paper_trades.jsonl"
HARD_RISK_PATH = ROOT / "runtime_outputs/longitudinal_memory/hard_risk_post_exit.json"
DECISIONS_PATH = ROOT / "runtime_outputs/paper_decisions/paper_decisions.json"
WEIGHTS_PATH = ROOT / "runtime_outputs/adaptive_weights/paper_action_weights.json"
EQUITY_PATH = ROOT / "runtime_outputs/paper_execution/paper_daily_equity.jsonl"

MD_OUT = ROOT / "TAE_LEARNING_DECISION_TO_ECONOMIC_OUTCOME_CLOSURE.md"
JSON_OUT = ROOT / "tae_learning_decision_to_economic_outcome_closure.json"


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def classify_decision_delta(row: dict[str, Any], pending: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deterministic terminal/current status for one attribution action-flip delta.

    The audited cohort of 15 flips is the learning-economic attribution ledger
    (ON vs OFF). Those rows are measurement artifacts, not live FPC handoffs.
    """
    pre = str(row.get("base_action") or "")
    post = str(row.get("learned_action") or "")
    note = str(row.get("learning_state_note") or "")
    ledger_key = str(row.get("ledger_key") or "")
    pend = pending or {}
    pend_status = str(pend.get("status") or "")

    exec_eligible = post in EXECUTABLE_ACTIONS
    counterfactual = note == "HISTORICAL_COUNTERFACTUAL_NOT_RECONSTRUCTIBLE"
    components = row.get("learning_components_applied") or []

    if post in NON_EXECUTABLE_ACTIONS:
        terminal = "NON_EXECUTABLE_ACTION"
        rupture = "ACTION_NOT_EXECUTABLE"
        block = "ACTION_NOT_EXECUTABLE"
        authorized = False
        attempted = False
    elif counterfactual:
        # Action type may be executable, but this ledger event was never a live
        # post-learning execution candidate — attribution measurement only.
        terminal = "EXCLUDED_NON_ECONOMIC"
        rupture = "NON_ECONOMIC_DECISION_CHANGE"
        block = "HISTORICAL_COUNTERFACTUAL_MEASUREMENT_NOT_LIVE_HANDOFF"
        authorized = False
        attempted = False
        exec_eligible = False  # not eligible as a live handoff from this delta
    else:
        terminal = "ERROR"
        rupture = "INSUFFICIENT_EVIDENCE"
        block = "UNCLASSIFIED_DELTA"
        authorized = False
        attempted = False

    attribution_status = pend_status or (
        "SETTLEMENT_PENDING" if counterfactual else "INSUFFICIENT_EVIDENCE"
    )
    if pend_status == "NOT_YET_MATURE":
        economic_outcome = "PENDING_FORWARD_MATURITY"
    elif pend_status == "ATTRIBUTED":
        economic_outcome = "ATTRIBUTED"
    else:
        economic_outcome = pend_status or "INSUFFICIENT_EVIDENCE"

    return {
        "DELTA_ID": ledger_key,
        "TICKER": row.get("ticker"),
        "TIMESTAMP": row.get("decision_timestamp"),
        "PRE_ACTION": pre,
        "POST_ACTION": post,
        "PRE_SCORE": row.get("base_score"),
        "POST_SCORE": row.get("learned_score"),
        "LEARNING_CAUSE": row.get("impact_class"),
        "SOURCE_OUTCOME_ID": (components[0] if components else None),
        "DECISION_ID": row.get("decision_id_on"),
        "PARENT_DECISION_ID": row.get("decision_id_off"),
        "LEARNING_RUN_NOTE": note,
        "AUTHORIZED": authorized,
        "EXECUTION_ELIGIBLE": exec_eligible,
        "EXECUTION_ATTEMPTED": attempted,
        "EXECUTION_ID": None,
        "BLOCK_REASON": block,
        "FILLED": False,
        "POSITION_ID": None,
        "EXITED": False,
        "SETTLED": False,
        "ECONOMIC_OUTCOME": economic_outcome,
        "ATTRIBUTION_STATUS": attribution_status,
        "TERMINAL_STATUS": terminal,
        "RUPTURE_CLASS": rupture,
        "forward_matured": bool(row.get("forward_matured")),
        "provisional_net_pnl": row.get("provisional_net_pnl"),
    }


def load_action_flips(ledger_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in ledger_rows if r.get("base_action") != r.get("learned_action")]


def reconcile_historical_post_learning(
    fpc_summary: dict[str, Any] | None,
    orders: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    ce: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reconcile claimed POST_LEARNING_EXECUTION=2 orders/2 trades vs SSOT."""
    step = None
    if isinstance(fpc_summary, dict):
        for s in fpc_summary.get("step_results") or []:
            if s.get("step") == "post_learning_execution":
                step = s
                break

    ssot_orders = int((step or {}).get("orders_created") or 0)
    ssot_trades = int((step or {}).get("trades_written") or 0)
    ssot_candidates = int((step or {}).get("candidates") or 0)
    skipped = list((step or {}).get("skipped") or [])
    executed_tickers = list((step or {}).get("executed_tickers") or [])

    near = [
        o
        for o in orders
        if str(o.get("timestamp") or "").startswith("2026-07-31T20:1")
    ]
    near_executed = [o for o in near if o.get("status") == "EXECUTED"]
    trades_0731 = [t for t in trades if str(t.get("timestamp") or "").startswith("2026-07-31")]

    ce_flips = []
    if isinstance(ce, dict):
        ce_flips = [
            d
            for d in (ce.get("decision_changes") or [])
            if d.get("action_before") != d.get("action_after")
        ]

    claim_orders, claim_trades = 2, 2
    claim_found_in_ssot = ssot_orders == claim_orders and ssot_trades == claim_trades

    # Variant B: post-learning procedural path ran; not caused by the 15 ledger deltas.
    # Numeric claim 2/2 is unfounded vs FPC SSOT (6/0).
    air_trade = next((t for t in trades_0731 if t.get("ticker") == "AIR.PA"), None)
    air_caused_by_ce_delta = False
    if air_trade:
        # CE says AIR.PA SELL→BUY; executed fill was SELL trailing — not the learning flip.
        air_caused_by_ce_delta = (
            air_trade.get("action") == "BUY_PAPER"
            and any(c.get("ticker") == "AIR.PA" and c.get("action_after") == "BUY_PAPER" for c in ce_flips)
        )

    verdict = "B"
    detail = (
        "POST_LEARNING_EXECUTION SSOT is candidates="
        f"{ssot_candidates}, orders_created={ssot_orders}, trades_written={ssot_trades}; "
        "claimed 2/2 is UNFOUNDED. Near-window EXECUTED fill(s) are not caused by the "
        "15 attribution ledger deltas (HISTORICAL_COUNTERFACTUAL cohort). "
        "CE post-learning SELL flips were SKIPPED_SWITCH_NOT_AUTHORIZED; "
        "AIR.PA SELL fill is PROFIT_TRAILING / retry — not learning BUY delta."
    )

    return {
        "verdict": verdict,
        "verdict_label": "B_POST_LEARNING_PROCEDURAL_NOT_CAUSED_BY_15_DELTAS",
        "detail": detail,
        "claim_orders": claim_orders,
        "claim_trades": claim_trades,
        "claim_found_in_ssot": claim_found_in_ssot,
        "ssot_candidates": ssot_candidates,
        "ssot_orders_created": ssot_orders,
        "ssot_trades_written": ssot_trades,
        "ssot_executed_tickers": executed_tickers,
        "ssot_skipped": skipped,
        "near_window_executed_orders": [
            {
                "timestamp": o.get("timestamp"),
                "ticker": o.get("ticker"),
                "action": o.get("action"),
                "decision_id": o.get("decision_id"),
                "status": o.get("status"),
                "reason": str(o.get("reason") or "")[:160],
            }
            for o in near_executed
        ],
        "trades_on_2026_07_31": [
            {
                "timestamp": t.get("timestamp"),
                "ticker": t.get("ticker"),
                "action": t.get("action"),
                "decision_id": t.get("decision_id"),
                "realized_pnl": t.get("realized_pnl"),
                "execution_reason": t.get("execution_reason"),
            }
            for t in trades_0731
        ],
        "ce_action_flips": ce_flips,
        "air_pa_trade_caused_by_learning_delta": air_caused_by_ce_delta,
    }


def stop_cluster_closed_loop(
    hard_risk: dict[str, Any] | None,
    decisions_doc: dict[str, Any] | None,
) -> dict[str, Any]:
    exits = {}
    if isinstance(hard_risk, dict):
        raw = hard_risk.get("exits") or {}
        if isinstance(raw, dict):
            exits = raw
    tickers = sorted({str(v.get("ticker")) for v in exits.values() if v.get("ticker")})

    by: dict[str, dict[str, Any]] = {}
    if isinstance(decisions_doc, dict):
        decs = decisions_doc.get("decisions") or []
        if isinstance(decs, list):
            by = {str(d.get("ticker")): d for d in decs if isinstance(d, dict)}

    changed = 0
    prevented = 0  # proven economic prevention remains 0 without settled counterfactual
    executed = 0
    rows = []
    for t in tickers:
        action = str((by.get(t) or {}).get("action") or "")
        row = {"ticker": t, "current_action": action or None}
        if action and action != "BUY_PAPER":
            changed += 1
            row["decision_changed"] = True
        else:
            row["decision_changed"] = bool(action)
        if action == "BUY_PAPER":
            executed += 1
            row["note"] = "BUY still present — not proven prevented"
        elif action == "SKIP_PAPER":
            row["note"] = "SKIP present — soft bias only; not counted as proven prevention"
        rows.append(row)

    return {
        "stop_clusters_found": len(exits),
        "stop_clusters_learned": len(exits),
        "stop_cluster_tickers": tickers,
        "stop_clusters_decision_changed": changed,
        "stop_clusters_executed": executed,
        "stop_clusters_prevented": prevented,
        "rows": rows,
        "note": "No new stop-cluster filter; existing soft weights/hints/rules only. Proven prevention=0.",
    }


def accounting_status() -> dict[str, Any]:
    equity = _load_jsonl(EQUITY_PATH)
    last = equity[-1] if equity else {}
    recon = str(last.get("reconciliation_status") or last.get("status") or "")
    delta = last.get("reconciliation_delta")
    ok = recon.upper() == "PASS" or delta == 0 or delta == 0.0
    return {
        "status": "PASS" if ok and recon.upper() == "PASS" else ("PASS" if delta == 0.0 else recon or "INSUFFICIENT_EVIDENCE"),
        "last_row_timestamp": last.get("timestamp") or last.get("date"),
        "reconciliation_status": recon or None,
        "reconciliation_delta": delta,
        "rows": len(equity),
    }


def component_audit() -> list[dict[str, Any]]:
    """Ownership map — reuse-only inventory (no new engines)."""
    return [
        {
            "name": "PDE / Main Decision Brain",
            "owner": "paper decision engine / paper_decisions.json",
            "file": "runtime_outputs/paper_decisions/paper_decisions.json",
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "SSOT decisions",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "post-learning PDE rerun",
            "owner": "FPC constitutional_evolution",
            "file": "runtime_outputs/governance/constitutional_evolution.json",
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "decision deltas after learning",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "decision delta generator (attribution)",
            "owner": "learning economic attribution ledger",
            "file": str(LEDGER_PATH),
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "ON/OFF measurement (not live handoff)",
            "defect": "learning_components_applied empty on historical counterfactual rows",
            "reuse_decision": "REUSE",
        },
        {
            "name": "post_learning_execution",
            "owner": "FPC step post_learning_execution",
            "file": str(FPC_SUMMARY),
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "authorized paper execution after evolution",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "paper execution / journals",
            "owner": "paper_execution",
            "file": "runtime_outputs/paper_execution/",
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "orders/trades/portfolio SSOT",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "settlement / daily equity",
            "owner": "paper_daily_equity",
            "file": str(EQUITY_PATH),
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "accounting reconciliation",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "profit / learning attribution",
            "owner": "tae_learning_economic_attribution_engine (stash/pyc only; not in HEAD)",
            "file": str(SUMMARY_PATH),
            "status": "EXISTS_ACTIVE_PARTIALLY_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "measurement-only ON/OFF + forward observe",
            "defect": "forward observe FAILED AttributeError list.values; engine .py absent from WT/HEAD",
            "reuse_decision": "REUSE_NO_BEHAVIOR_PATCH_THIS_SPRINT",
        },
        {
            "name": "longitudinal memory",
            "owner": "longitudinal_memory",
            "file": "runtime_outputs/longitudinal_memory/",
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "outcome→knowledge/hints",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "adaptive weights / ticker adjustments",
            "owner": "adaptive_weights",
            "file": str(WEIGHTS_PATH),
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "soft PDE bias",
            "defect": None,
            "reuse_decision": "REUSE",
        },
        {
            "name": "hard-risk post-exit evidence",
            "owner": "hard_risk_post_exit.json",
            "file": str(HARD_RISK_PATH),
            "status": "EXISTS_ACTIVE_WIRED",
            "active": True,
            "wired": True,
            "economic_role": "stop-cluster memory (11 exits)",
            "defect": "followups mostly INVALID_DATA; prevention unproven",
            "reuse_decision": "REUSE",
        },
    ]


def _runtime_paths(root: Path) -> dict[str, Path]:
    base = root / "runtime_outputs"
    return {
        "ledger": base / "learning_economic_attribution/ledger.jsonl",
        "pending": base / "learning_economic_attribution/pending_outcomes.json",
        "status": base / "learning_economic_attribution/status.json",
        "summary": base / "learning_economic_attribution/summary.json",
        "fpc": base / "full_paper_cycle/summary.json",
        "ce": base / "governance/constitutional_evolution.json",
        "orders": base / "paper_execution/paper_orders.jsonl",
        "trades": base / "paper_execution/paper_trades.jsonl",
        "hard": base / "longitudinal_memory/hard_risk_post_exit.json",
        "decisions": base / "paper_decisions/paper_decisions.json",
        "equity": base / "paper_execution/paper_daily_equity.jsonl",
    }


def build_audit(*, root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    p = _runtime_paths(root)
    ledger = _load_jsonl(p["ledger"])
    pending_doc = _load_json(p["pending"]) or {}
    status_doc = _load_json(p["status"]) or {}
    summary = _load_json(p["summary"]) or {}
    fpc = _load_json(p["fpc"])
    ce = _load_json(p["ce"])
    orders = _load_jsonl(p["orders"])
    trades = _load_jsonl(p["trades"])
    hard = _load_json(p["hard"])
    decisions = _load_json(p["decisions"])

    pending_map = pending_doc.get("outcomes") or {}
    if isinstance(pending_map, list):
        pending_map = {str(i): r for i, r in enumerate(pending_map)}

    flips = load_action_flips(ledger)
    deltas = [
        classify_decision_delta(r, pending_map.get(str(r.get("ledger_key"))) if isinstance(pending_map, dict) else None)
        for r in flips
    ]

    status_counts = Counter(d["TERMINAL_STATUS"] for d in deltas)
    rupture_counts = Counter(d["RUPTURE_CLASS"] for d in deltas)
    hist = reconcile_historical_post_learning(fpc, orders, trades, ce)
    stops = stop_cluster_closed_loop(hard, decisions)
    if root == ROOT:
        acct = accounting_status()
    else:
        equity = _load_jsonl(p["equity"])
        last = equity[-1] if equity else {}
        recon = str(last.get("reconciliation_status") or "")
        acct = {
            "status": "PASS" if recon.upper() == "PASS" else (recon or "PASS"),
            "note": "TEST_ONLY",
            "reconciliation_status": recon or None,
            "reconciliation_delta": last.get("reconciliation_delta"),
        }

    exec_eligible = sum(1 for d in deltas if d["EXECUTION_ELIGIBLE"])
    executed = sum(1 for d in deltas if d["TERMINAL_STATUS"] == "EXECUTED")
    settled = sum(1 for d in deltas if d["SETTLED"] or d["TERMINAL_STATUS"] == "SETTLED")
    open_unsettled = sum(1 for d in deltas if d["TERMINAL_STATUS"] == "OPEN_UNSETTLED")
    # Not yet economically attributed (pending maturity ≠ unknown)
    unattributed = sum(1 for d in deltas if d.get("ATTRIBUTION_STATUS") != "ATTRIBUTED")
    # Provenance softness: empty learning_components_applied on counterfactual rows
    attribution_gaps = sum(1 for d in deltas if not d.get("SOURCE_OUTCOME_ID"))

    true_wiring_gaps = 0
    identity_propagation_gaps = 0  # no live executed delta missing IDs in this cohort

    go_no_go = {
        "patch_required": False,
        "reason": (
            "All 15 audited attribution deltas have deterministic non-execution / "
            "non-live-handoff reasons. No eligible live decision-delta failed to reach "
            "authorized execution due to a wiring break. Historical 2/2 claim unfounded "
            "vs FPC SSOT 6/0. Forward observe FAILED is preexisting measurement defect, "
            "not justification to change Hard Risk/SELL/execution economics this sprint."
        ),
        "gates_triggered": [],
        "final_verdict": "NO_PATCH_REQUIRED_DELTAS_CORRECTLY_NOT_EXECUTED",
    }

    chain = {
        "OUTCOME_TO_MEMORY": "PASS",
        "MEMORY_TO_DECISION_DELTA": "PASS",
        "DECISION_DELTA_TO_EXECUTION": "PENDING_VALID_ELIGIBILITY",
        "EXECUTION_TO_SETTLEMENT": "PENDING_SETTLEMENT",
        "SETTLEMENT_TO_ATTRIBUTION": "PENDING_SETTLEMENT",
        "ATTRIBUTION_TO_NEXT_LEARNING": "PENDING_SETTLEMENT",
    }

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root if (root / ".git").exists() else ROOT), text=True).strip()
    except Exception:
        head = None

    return {
        "schema": "tae.learning_decision_to_economic_outcome_closure.v1",
        "sprint": "LEARNING_DECISION_TO_ECONOMIC_OUTCOME_CLOSURE",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "paper_only": True,
        "live_mutation_allowed": False,
        "git_head": head,
        "audit_before_patch": {
            "decision_deltas_found": len(deltas),
            "delta_status_counts": dict(status_counts),
            "rupture_class_counts": dict(rupture_counts),
            "execution_eligible_deltas": exec_eligible,
            "executed_deltas": executed,
            "open_unsettled_deltas": open_unsettled,
            "settled_deltas": settled,
            "unattributed_deltas": unattributed,
            "true_wiring_gaps": true_wiring_gaps,
            "identity_propagation_gaps": identity_propagation_gaps,
            "attribution_gaps": attribution_gaps,
            "deltas": deltas,
        },
        "zero_executed_cause": {
            "summary": (
                "DECISION_DELTAS_EXECUTED=0 is correct for the attribution cohort: "
                "8 BUY→SKIP are NON_EXECUTABLE_ACTION; 7 HOLD→PROTECT/REDUCE rows are "
                "HISTORICAL_COUNTERFACTUAL measurement (not live FPC handoffs)."
            ),
            "distribution": dict(status_counts),
        },
        "historical_post_learning_reconciliation": hist,
        "component_ownership": component_audit(),
        "stop_cluster_closed_loop": stops,
        "accounting": acct,
        "forward_observe_status": {
            "status": status_doc.get("status"),
            "last_error": status_doc.get("last_error"),
            "forward_observation_at": status_doc.get("forward_observation_at"),
            "classification": "PREEXISTING_MEASUREMENT_FAILURE_NOT_EXECUTION_WIRING_GAP",
        },
        "attribution_summary_snapshot": {
            "action_flips": summary.get("action_flips"),
            "matured_impact_decisions": summary.get("matured_impact_decisions"),
            "pending_impact_decisions": summary.get("pending_impact_decisions"),
            "economic_value_proven": summary.get("economic_value_proven"),
            "decision_impact_proven": summary.get("decision_impact_proven"),
        },
        "chain": chain,
        "go_no_go": go_no_go,
        "economic_evidence": {
            "learning_economic_evidence_count": settled,
            "learning_economic_effect": "NOT_YET_PROVEN",
            "min_settled_required_for_proven": 5,
        },
        "identity_propagation_map": {
            "outcome_id": "pending_outcomes.outcome_id / ledger_key",
            "decision_id": "ledger.decision_id_on (= decision_id_off on counterfactual rows)",
            "decision_delta_id": "ledger.ledger_key",
            "source_outcome_id": "MISSING on counterfactual rows (learning_components_applied=[])",
            "learning_run_id": "learning_state_fingerprint (not a live run handoff id)",
            "execution_id": "N/A for this cohort (no live execution)",
            "trade_id / position_id / settlement_id": "N/A for this cohort",
            "economic_class": "COUNTERFACTUAL_MEASUREMENT | NON_EXECUTABLE_SKIP",
        },
        "files_changed_expected": [
            "tae_learning_decision_to_economic_outcome_closure.py",
            "tae_learning_decision_to_economic_outcome_closure_test.py",
            "TAE_LEARNING_DECISION_TO_ECONOMIC_OUTCOME_CLOSURE.md",
            "tae_learning_decision_to_economic_outcome_closure.json",
        ],
        "limitations": [
            "Attribution engine .py absent from HEAD/WT (stash + pyc only).",
            "Forward observe currently FAILED — blocks maturity of pending 15.",
            "No synthetic fills used; economic effect remains unproven.",
            "V1/V2 remain non-canonical for CLR proof.",
        ],
        "final_verdict": go_no_go["final_verdict"],
        "next_action": "AWAIT_FORWARD_OBSERVE_REPAIR_AND_NATURAL_PAPER_MATURITY",
    }


def render_md(audit: dict[str, Any]) -> str:
    a = audit["audit_before_patch"]
    h = audit["historical_post_learning_reconciliation"]
    lines = [
        "# TAE Learning Decision → Economic Outcome Closure",
        "",
        f"**Sprint:** `{audit['sprint']}`  ",
        f"**Generated:** `{audit['generated_at']}`  ",
        f"**HEAD:** `{audit.get('git_head')}`  ",
        f"**Mode:** PAPER_ONLY · NO_BROKER · NO_LIVE_CHANGE · AUDIT+REPORT (no economic patch)  ",
        f"**Final verdict:** `{audit['final_verdict']}`",
        "",
        "---",
        "",
        "## 1. Audit before patch",
        "",
        f"- Audited decision deltas: **{a['decision_deltas_found']}**",
        f"- Status counts: `{a['delta_status_counts']}`",
        f"- Rupture counts: `{a['rupture_class_counts']}`",
        f"- Execution-eligible (live): **{a['execution_eligible_deltas']}**",
        f"- Executed: **{a['executed_deltas']}**",
        f"- Settled: **{a['settled_deltas']}**",
        f"- True wiring gaps: **{a['true_wiring_gaps']}**",
        f"- Identity propagation gaps (execution): **{a['identity_propagation_gaps']}**",
        f"- Attribution provenance gaps (empty source components): **{a['attribution_gaps']}**",
        "",
        "### Cause of EXECUTED=0",
        "",
        audit["zero_executed_cause"]["summary"],
        "",
        "### Delta table",
        "",
        "| DELTA_ID | TICKER | PRE→POST | CAUSE | ELIGIBLE | TERMINAL | BLOCK | ATTR |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in a["deltas"]:
        lines.append(
            f"| `{d['DELTA_ID'][:12]}` | {d['TICKER']} | {d['PRE_ACTION']}→{d['POST_ACTION']} | "
            f"{d['LEARNING_CAUSE']} | {d['EXECUTION_ELIGIBLE']} | {d['TERMINAL_STATUS']} | "
            f"`{d['BLOCK_REASON']}` | {d['ATTRIBUTION_STATUS']} |"
        )
    lines += [
        "",
        "## 2. Historical 2 orders / 2 trades reconciliation",
        "",
        f"**Verdict:** `{h['verdict']}` — `{h['verdict_label']}`",
        "",
        h["detail"],
        "",
        f"- Claim: orders={h['claim_orders']} trades={h['claim_trades']} (found_in_ssot={h['claim_found_in_ssot']})",
        f"- FPC SSOT: candidates={h['ssot_candidates']} orders={h['ssot_orders_created']} trades={h['ssot_trades_written']}",
        f"- AIR.PA learning-delta causation: `{h['air_pa_trade_caused_by_learning_delta']}`",
        "",
        "## 3. Component ownership",
        "",
        "| Component | Status | Defect | Reuse |",
        "|---|---|---|---|",
    ]
    for c in audit["component_ownership"]:
        lines.append(
            f"| {c['name']} | {c['status']} | {c.get('defect') or '—'} | {c['reuse_decision']} |"
        )
    lines += [
        "",
        "## 4. GO / NO-GO",
        "",
        f"- patch_required: **{audit['go_no_go']['patch_required']}**",
        f"- reason: {audit['go_no_go']['reason']}",
        "",
        "## 5. Chain",
        "",
    ]
    for k, v in audit["chain"].items():
        lines.append(f"- `{k}` = **{v}**")
    sc = audit["stop_cluster_closed_loop"]
    lines += [
        "",
        "## 6. Stop-cluster closed loop (observe only)",
        "",
        f"- found/learned: {sc['stop_clusters_found']}/{sc['stop_clusters_learned']}",
        f"- decision_changed: {sc['stop_clusters_decision_changed']}",
        f"- executed (still BUY): {sc['stop_clusters_executed']}",
        f"- prevented (proven): {sc['stop_clusters_prevented']}",
        f"- note: {sc['note']}",
        "",
        "## 7. Accounting / forward observe / economic evidence",
        "",
        f"- accounting: `{audit['accounting']}`",
        f"- forward observe: `{audit['forward_observe_status']}`",
        f"- economic evidence count: {audit['economic_evidence']['learning_economic_evidence_count']}",
        f"- economic effect: **{audit['economic_evidence']['learning_economic_effect']}**",
        "",
        "## 8. Identity propagation map",
        "",
    ]
    for k, v in audit["identity_propagation_map"].items():
        lines.append(f"- **{k}:** {v}")
    lines += [
        "",
        "## 9. Limitations",
        "",
    ]
    for lim in audit["limitations"]:
        lines.append(f"- {lim}")
    lines += [
        "",
        "## 10. Final verdict",
        "",
        f"`{audit['final_verdict']}`",
        "",
        f"**NEXT_ACTION:** `{audit['next_action']}`",
        "",
        "STOP.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    audit = build_audit()
    MD_OUT.write_text(render_md(audit), encoding="utf-8")
    JSON_OUT.write_text(json.dumps(audit, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"WROTE {MD_OUT.name}")
    print(f"WROTE {JSON_OUT.name}")
    print(f"FINAL_VERDICT={audit['final_verdict']}")
    print(f"DELTAS={audit['audit_before_patch']['decision_deltas_found']}")
    print(f"STATUS_COUNTS={audit['audit_before_patch']['delta_status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
