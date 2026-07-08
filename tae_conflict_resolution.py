#!/usr/bin/env python3
"""
TAE Conflict Resolution — thin evidence orchestrator.

PAPER_ONLY | READ_ONLY | NO_BROKER | NO_LIVE_PROMOTION

Reuses existing PDE context loaders and delta estimators.
Produces EV-ranked scenario evidence for PDE consumption — does NOT decide trades.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae.conflict_resolution.v1"
MODE = "PAPER_ONLY"
RISK_PENALTY = 1.15
EV_TIE_THRESHOLD = 2.0
IDLE_CASH_THRESHOLD = 2000.0
MAX_ACCEPTABLE_BUY_DRAWDOWN = 8.0

OUTPUT_DIR = Path("runtime_outputs/conflict_resolution")
CONFLICTS_JSON = OUTPUT_DIR / "conflicts.json"
SCENARIO_REGISTRY_JSON = OUTPUT_DIR / "scenario_registry.json"
REPORT_MD = Path("TAE_CONFLICT_RESOLUTION_REPORT.md")

GOVERNANCE_JSON = Path("runtime_outputs/governance/structural_governance.json")

POSITION_REQUIRED = frozenset({"SELL_PAPER", "PROTECT_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"})

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
    "research_core/",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if path.resolve() != REPORT_MD.resolve() and output_root not in path.resolve().parents:
        raise RuntimeError(f"Unsafe output path outside conflict_resolution/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _governance_reconciliation_ok() -> tuple[bool, str]:
    gov = load_json(GOVERNANCE_JSON)
    if not gov:
        return True, "governance artifact not present — assume OK for standalone run"
    steps = gov.get("steps") or []
    for step in steps:
        if _s(step.get("step_id")) == "accounting_reconciliation":
            ok = bool(step.get("ok"))
            return ok, _s(step.get("reason"), "reconciliation gate")
    return True, "reconciliation step not found in governance snapshot"


def _hard_risk_status(ticker: str, ctx: dict[str, Any], *, held: bool) -> dict[str, Any]:
    row = (ctx.get("hard_risk_by") or {}).get(ticker.upper()) or {}
    status = _s(row.get("status"))
    if not held:
        return {"applies": False, "override": False, "status": "NO_POSITION"}
    if status in {"STOP_LOSS_BREACHED", "CRITICAL_LOSS"}:
        return {
            "applies": True,
            "override": True,
            "status": status,
            "hard_rule": _s(row.get("hard_rule")),
            "required_action": "SELL_PAPER",
            "pnl_pct": _f(row.get("pnl_pct")),
        }
    return {
        "applies": True,
        "override": False,
        "status": status or "OK",
        "pnl_pct": _f(row.get("pnl_pct")),
    }


def _policy_blockers(ticker: str, action: str, ctx: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    policy_state = _s(ctx.get("policy_state"))
    suggested = _s(ctx.get("suggested_policy")).upper()
    cash = _f(ctx.get("cash_hint"))

    if action == "BUY_PAPER":
        if policy_state == "HIGH_RISK":
            blockers.append("APPE_HIGH_RISK_POLICY")
        if "PRESERVATION" in suggested:
            blockers.append("APPE_CAPITAL_PRESERVATION")
        if cash < 1000.0:
            blockers.append("LOW_CASH_HINT")
    return blockers


def _supporting_modules(ticker: str, action: str, ctx: dict[str, Any]) -> list[str]:
    mods: list[str] = []
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    signal = (ctx.get("signals") or {}).get(ticker.upper()) or {}

    if gii:
        mods.append("tae_growth_intelligence.json")
    if ticker.upper() in (ctx.get("shadow_by") or {}):
        mods.append("tae_profit_protection_shadow.json")
    if (ctx.get("exp_by_ticker") or {}).get(ticker.upper()):
        mods.append("runtime_outputs/learning_to_profit/experiment_results.json")
    if action == "BUY_PAPER" and signal:
        mods.append("live_signals.csv")
    if ctx.get("dpe_eval"):
        mods.append("runtime_outputs/dpe/result_evaluator/evaluation.json")
    if ctx.get("paper_action_weights"):
        mods.append("runtime_outputs/adaptive_weights/paper_action_weights.json")
    if ctx.get("adaptation_hints"):
        mods.append("runtime_outputs/longitudinal_memory/adaptation_hints.json")
    if ctx.get("decision_replay"):
        mods.append("tae_decision_replay.json")
    if ctx.get("horizon_ssot", {}).get("historical_returns"):
        mods.append("historical_intelligence.csv")
    return sorted(set(mods))


def _opposing_modules(ticker: str, action: str, ctx: dict[str, Any]) -> list[str]:
    opposing: list[str] = []
    policy_state = _s(ctx.get("policy_state"))
    replay = ctx.get("decision_replay") or {}
    readiness = replay.get("advisory_readiness") or {}

    if action == "BUY_PAPER" and policy_state == "HIGH_RISK":
        opposing.append("tae_adaptive_profit_policy_engine.json")
    if action == "BUY_PAPER" and readiness.get("status") == "NOT_READY":
        opposing.append("tae_decision_replay.json")
    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper()) or []
    if any(_s(e.get("verdict")) == "REJECT" for e in exps):
        opposing.append("runtime_outputs/learning_to_profit/experiment_results.json")
    return sorted(set(opposing))


def probability_success(ticker: str, action: str, ctx: dict[str, Any], *, horizon: dict[str, Any]) -> float:
    factors: list[float] = []

    for exp in (ctx.get("exp_by_ticker") or {}).get(ticker.upper()) or []:
        verdict = _s(exp.get("verdict"))
        if verdict == "PROMISING":
            factors.append(0.78)
        elif verdict == "CONTINUE_TESTING":
            factors.append(0.55)
        elif verdict == "REJECT":
            factors.append(0.22)
        elif verdict == "NEEDS_MORE_DATA":
            factors.append(0.42)

    overall = (ctx.get("dpe_eval") or {}).get("overall") or {}
    dpe_conf = _f(overall.get("confidence_pct")) / 100.0
    if dpe_conf > 0:
        factors.append(min(0.88, dpe_conf))

    adaptive = ctx.get("dpe_adaptive") or {}
    if _s(adaptive.get("preferred_philosophy")):
        factors.append(min(0.82, _f(adaptive.get("confidence"), 0.55)))

    weights_doc = ctx.get("paper_action_weights") or {}
    action_weights = weights_doc.get("weights") or weights_doc.get("action_weights") or {}
    w = _f(action_weights.get(action), 1.0)
    factors.append(min(0.9, max(0.32, 0.48 + (w - 1.0) * 2.5)))

    hints = ctx.get("adaptation_hints") or {}
    bias = _f((hints.get("action_confidence_bias") or {}).get(action))
    factors.append(min(0.9, max(0.3, 0.5 + bias)))

    align = _f(horizon.get("horizon_alignment_score")) / 100.0
    factors.append(min(0.85, max(0.35, 0.38 + align * 0.52)))

    lifecycle_doc = ctx.get("rule_lifecycle") or {}
    rules = lifecycle_doc.get("rules") or {}
    win_rates = [_f(r.get("win_rate")) for r in rules.values() if _f(r.get("win_rate")) > 0]
    if win_rates:
        factors.append(min(0.85, sum(win_rates) / len(win_rates)))

    signal = (ctx.get("signals") or {}).get(ticker.upper()) or {}
    if action == "BUY_PAPER" and signal:
        factors.append(min(0.92, _f(signal.get("score")) / 100.0))

    replay = ctx.get("decision_replay") or {}
    readiness = replay.get("advisory_readiness") or {}
    if readiness.get("status") == "NOT_READY":
        factors.append(0.34)
    elif readiness.get("status") == "WATCH":
        factors.append(0.48)

    if not factors:
        return 0.45
    return round(min(0.92, max(0.25, sum(factors) / len(factors))), 4)


def expected_drawdown(ticker: str, action: str, ctx: dict[str, Any], *, horizon: dict[str, Any], risk_delta: float) -> float:
    risk_score = 0.0
    try:
        from tae_paper_decision_engine import compute_risk_score

        risk_score = compute_risk_score(ticker, ctx)
    except Exception:
        pass
    short_dd = _f(horizon.get("short_drawdown_pct"))
    base = max(abs(risk_delta) * 100.0, risk_score * 0.06, short_dd * 0.15)
    if action in {"BUY_PAPER", "ROTATE_PAPER"}:
        base *= 1.1
    elif action in {"SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER"}:
        base *= 0.85
    return round(base, 4)


def risk_adjusted_ev(expected_profit: float, probability: float, drawdown: float) -> float:
    return round((expected_profit * probability) - (abs(drawdown) * RISK_PENALTY), 4)


def scenario_deltas(ticker: str, action: str, ctx: dict[str, Any]) -> dict[str, float]:
    """Action-specific deltas — experiments apply only to matching hypothesis actions."""
    from tae_paper_decision_engine import estimate_deltas

    if action == "SKIP_PAPER":
        return {"expected_profit_delta": 0.0, "expected_risk_delta": 0.0, "capital_efficiency_delta": 0.0}

    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper()) or []
    exp = exps[0] if exps else None
    exp_action = _s(exp.get("paper_experiment_action") if exp else "").upper()
    use_experiment = bool(
        exp
        and exp.get("deltas")
        and (
            (action == "BUY_PAPER" and "BUY" in exp_action)
            or (action == "HOLD_PAPER" and "HOLD" in exp_action)
            or (action == "PROTECT_PAPER" and "PROTECT" in exp_action)
            or (action == "SELL_PAPER" and "SELL" in exp_action)
            or (action == "ROTATE_PAPER" and "ROTATE" in exp_action)
            or (action == "REDUCE_PAPER" and ("TRIM" in exp_action or "REDUCE" in exp_action))
        )
    )
    if use_experiment:
        return estimate_deltas(ticker, action, ctx)

    exp_by = dict(ctx.get("exp_by_ticker") or {})
    ticker = ticker.upper()
    saved = exp_by.get(ticker)
    if saved:
        exp_by[ticker] = []
        ctx = {**ctx, "exp_by_ticker": exp_by}
    try:
        return estimate_deltas(ticker, action, ctx)
    finally:
        if saved is not None:
            exp_by[ticker] = saved
            ctx["exp_by_ticker"] = exp_by


def build_scenario_row(
    ticker: str,
    action: str,
    ctx: dict[str, Any],
    *,
    held: bool,
    hard_risk: dict[str, Any],
    recon_ok: bool,
) -> dict[str, Any]:
    from tae_paper_decision_engine import build_horizon_context

    horizon = build_horizon_context(ticker, ctx)
    deltas = scenario_deltas(ticker, action, ctx)
    expected_profit = _f(deltas.get("expected_profit_delta"))
    risk_delta = _f(deltas.get("expected_risk_delta"))
    drawdown = expected_drawdown(ticker, action, ctx, horizon=horizon, risk_delta=risk_delta)
    prob = probability_success(ticker, action, ctx, horizon=horizon)
    policy_blockers = _policy_blockers(ticker, action, ctx)

    hard_blocked = False
    hard_reason = ""
    if not recon_ok:
        hard_blocked = True
        hard_reason = "accounting_reconciliation FAIL"
    elif hard_risk.get("override"):
        if action != "SELL_PAPER":
            hard_blocked = True
            hard_reason = _s(hard_risk.get("hard_rule"), "HARD_RISK")
    elif action in POSITION_REQUIRED and not held:
        hard_blocked = True
        hard_reason = "no_position_for_exit_action"
    elif action == "HOLD_PAPER" and not held:
        hard_blocked = True
        hard_reason = "hold_requires_open_position"

    raev = risk_adjusted_ev(expected_profit, prob, drawdown) if not hard_blocked else -9999.0
    if action == "SKIP_PAPER" and not hard_blocked:
        raev = round(-abs(drawdown) * RISK_PENALTY * 0.25, 4)
    elif action == "BUY_PAPER":
        for blocker in policy_blockers:
            if blocker.startswith("APPE_") and not hard_blocked:
                raev -= 1.5

    learning: list[str] = []
    for exp in (ctx.get("exp_by_ticker") or {}).get(ticker.upper()) or []:
        learning.append(f"{exp.get('hypothesis_id')}:{exp.get('verdict')}")

    rule_survival: list[str] = []
    lifecycle_rules = (ctx.get("rule_lifecycle") or {}).get("rules") or {}
    for rule_id, row in list(lifecycle_rules.items())[:6]:
        if isinstance(row, dict):
            rule_survival.append(f"{rule_id}:{row.get('state')} wr={row.get('win_rate')}")

    replay_evidence: list[str] = []
    replay = ctx.get("decision_replay") or {}
    for rec in (replay.get("recommendations") or [])[:4]:
        replay_evidence.append(_s(rec))
    for mode in (replay.get("dominant_failure_modes") or [])[:3]:
        replay_evidence.append(f"failure_mode:{mode}")

    dpe_evidence = {
        "preferred_philosophy": _s((ctx.get("dpe_adaptive") or {}).get("preferred_philosophy")),
        "evaluator_winner": _s(((ctx.get("dpe_eval") or {}).get("overall") or {}).get("winner")),
        "evaluator_confidence_pct": _f(((ctx.get("dpe_eval") or {}).get("overall") or {}).get("confidence_pct")),
    }

    weight_doc = ctx.get("paper_action_weights") or {}
    action_weights = weight_doc.get("weights") or weight_doc.get("action_weights") or {}
    adaptive_weight = _f(action_weights.get(action), 1.0)

    return {
        "action": action,
        "supporting_modules": _supporting_modules(ticker, action, ctx),
        "opposing_modules": _opposing_modules(ticker, action, ctx),
        "hard_rule_status": {
            "blocked": hard_blocked,
            "reason": hard_reason or None,
            "hard_risk_override": bool(hard_risk.get("override")),
            "reconciliation_ok": recon_ok,
        },
        "policy_blockers": policy_blockers,
        "learning_evidence": learning,
        "historical_replay_evidence": replay_evidence,
        "dpe_evidence": dpe_evidence,
        "rule_survival_evidence": rule_survival,
        "adaptive_weight_evidence": {"action": action, "weight": adaptive_weight},
        "horizon_evidence": {
            "alignment_score": horizon.get("horizon_alignment_score"),
            "conflict_flag": horizon.get("horizon_conflict_flag"),
            "reason": _s(horizon.get("horizon_reason"))[:200],
        },
        "expected_profit_delta": round(expected_profit, 2),
        "expected_drawdown": drawdown,
        "probability_success": prob,
        "risk_adjusted_EV": raev,
    }


def resolve_ticker(ticker: str, ctx: dict[str, Any], *, recon_ok: bool) -> dict[str, Any]:
    from tae_decision_state import evaluate_action_switch
    from tae_paper_decision_engine import PAPER_ACTIONS, paper_position_held

    ticker = ticker.upper()
    held = paper_position_held(ticker, ctx)
    hard_risk = _hard_risk_status(ticker, ctx, held=held)

    scenario_table = [
        build_scenario_row(ticker, action, ctx, held=held, hard_risk=hard_risk, recon_ok=recon_ok)
        for action in sorted(PAPER_ACTIONS)
    ]

    eligible = [row for row in scenario_table if not row["hard_rule_status"]["blocked"]]
    if hard_risk.get("override"):
        winning = "SELL_PAPER"
        final_authority = "HARD_RULE"
    elif not eligible:
        winning = "SKIP_PAPER"
        final_authority = "HARD_RULE"
    else:
        eligible_sorted = sorted(eligible, key=lambda r: _f(r["risk_adjusted_EV"]), reverse=True)
        top = eligible_sorted[0]
        second = eligible_sorted[1] if len(eligible_sorted) > 1 else None
        top_ev = _f(top.get("risk_adjusted_EV"))
        second_ev = _f(second.get("risk_adjusted_EV")) if second else -999.0

        if abs(top_ev - second_ev) < EV_TIE_THRESHOLD and top.get("action") not in {"HOLD_PAPER", "SKIP_PAPER"}:
            winning = "HOLD_PAPER" if held else "SKIP_PAPER"
            final_authority = "POLICY_CAUTION"
        elif top_ev <= 0 and (held or top.get("action") != "BUY_PAPER"):
            winning = "HOLD_PAPER" if held else "SKIP_PAPER"
            final_authority = "POLICY_CAUTION"
        else:
            winning = _s(top.get("action"))
            final_authority = "EV_OPTIMIZER"

    buy_row = next((r for r in scenario_table if r["action"] == "BUY_PAPER"), None)
    acct_cash = _f(ctx.get("cash_hint"))
    paper_cash = _f(((ctx.get("paper_portfolio") or {}).get("cash")))
    cash = max(acct_cash, paper_cash)
    idle_cash = cash >= IDLE_CASH_THRESHOLD
    buy_ev_positive = buy_row and _f(buy_row.get("risk_adjusted_EV")) > 0 and not buy_row["hard_rule_status"]["blocked"]
    buy_drawdown_ok = buy_row and _f(buy_row.get("expected_drawdown")) <= MAX_ACCEPTABLE_BUY_DRAWDOWN
    policy_state = _s(ctx.get("policy_state"))
    high_risk_buy_allowed = bool(
        buy_ev_positive and buy_drawdown_ok and idle_cash and policy_state == "HIGH_RISK"
    )

    if high_risk_buy_allowed and winning in {"SKIP_PAPER", "HOLD_PAPER"} and buy_row:
        winning = "BUY_PAPER"
        final_authority = "EV_OPTIMIZER"
        buy_row["policy_blockers"] = [b for b in buy_row.get("policy_blockers") or [] if not b.startswith("APPE_")]
        buy_row["policy_blockers"].append("HIGH_RISK_MITIGATED_BY_POSITIVE_EV")

    losing = [
        r["action"]
        for r in sorted(scenario_table, key=lambda x: _f(x["risk_adjusted_EV"]), reverse=True)
        if r["action"] != winning and _f(r["risk_adjusted_EV"]) > -9000
    ][:5]

    winner_row = next((r for r in scenario_table if r["action"] == winning), scenario_table[0])
    explanation_parts = [
        f"winner={winning} raEV={winner_row.get('risk_adjusted_EV')}",
        f"authority={final_authority}",
        f"prob={winner_row.get('probability_success')}",
    ]
    if buy_row and buy_row.get("policy_blockers"):
        explanation_parts.append(f"BUY blockers={','.join(buy_row['policy_blockers'])}")
    if high_risk_buy_allowed:
        explanation_parts.append(f"idle cash=${cash:.0f} positive BUY EV overrides HIGH_RISK policy penalty")

    signal = (ctx.get("signals") or {}).get(ticker) or {}
    signal_name = _s(signal.get("signal")).upper()
    strong_buy_skip = "STRONG BUY" in signal_name and winning == "SKIP_PAPER"

    active_state = (ctx.get("active_decisions_by_ticker") or {}).get(ticker) or {}
    raev_map = {r["action"]: _f(r.get("risk_adjusted_EV")) for r in scenario_table if _f(r.get("risk_adjusted_EV")) > -9000}
    switch_eval = evaluate_action_switch(
        ticker,
        winning,
        state=active_state,
        hard_rule_override=bool(hard_risk.get("override")),
        scenario_raev=raev_map,
        loss_context={"current_pct": _f(((ctx.get("paper_positions") or {}).get(ticker) or {}).get("unrealized_pct"))},
        held=held,
    )
    switch_cost = round(max(0.0, _f(switch_eval.get("ev_margin_required")) - _f(switch_eval.get("ev_margin_actual"))), 4)

    for row in scenario_table:
        prop = _s(row.get("action"))
        row_switch = evaluate_action_switch(
            ticker,
            prop,
            state=active_state,
            hard_rule_override=bool(hard_risk.get("override")),
            scenario_raev=raev_map,
            held=held,
        )
        row["previous_action"] = active_state.get("last_executed_action")
        row["switch_cost"] = switch_cost if prop != active_state.get("last_executed_action") else 0.0
        row["churn_risk"] = active_state.get("churn_risk")
        row["cooldown_status"] = active_state.get("cooldown_status")
        row["ev_margin_required"] = row_switch.get("ev_margin_required")
        row["ev_margin_actual"] = row_switch.get("ev_margin_actual")
        row["switch_authorized"] = bool(row_switch.get("switch_authorized"))

    if not switch_eval.get("switch_authorized") and not hard_risk.get("override"):
        winning = _s(switch_eval.get("final_action"), winning)
        final_authority = "DECISION_STATE_GATE"

    return {
        "ticker": ticker,
        "paper_position_held": held,
        "candidate_actions": [r["action"] for r in scenario_table],
        "scenario_ev_table": scenario_table,
        "winning_scenario": winning,
        "losing_scenarios": losing,
        "final_authority": final_authority,
        "explanation": "; ".join(explanation_parts),
        "high_risk_buy_allowed": high_risk_buy_allowed,
        "strong_buy_to_skip": strong_buy_skip,
        "idle_cash_usd": round(cash, 2),
        "policy_state": policy_state,
        "switch_authorized": bool(switch_eval.get("switch_authorized")),
        "switch_reason": switch_eval.get("switch_reason"),
        "ev_margin_actual": switch_eval.get("ev_margin_actual"),
        "ev_margin_required": switch_eval.get("ev_margin_required"),
        "previous_action": active_state.get("last_executed_action"),
        "churn_risk": active_state.get("churn_risk"),
        "cooldown_status": active_state.get("cooldown_status"),
    }


def _buy_scenario_row(row: dict[str, Any]) -> dict[str, Any]:
    return next((s for s in row.get("scenario_ev_table") or [] if s.get("action") == "BUY_PAPER"), {})


def build_conflict_resolution(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    from tae_decision_state import load_active_by_ticker
    from tae_paper_decision_engine import build_context, ticker_universe

    ctx = ctx or build_context()
    ctx["active_decisions_by_ticker"] = load_active_by_ticker()
    recon_ok, recon_note = _governance_reconciliation_ok()
    tickers = ticker_universe(ctx)
    rows = [resolve_ticker(ticker, ctx, recon_ok=recon_ok) for ticker in tickers]

    top_conflicts = sorted(
        rows,
        key=lambda r: (
            1 if r.get("strong_buy_to_skip") else 0,
            1 if r.get("high_risk_buy_allowed") else 0,
            len(_buy_scenario_row(r).get("policy_blockers") or []),
        ),
        reverse=True,
    )[:12]

    buy_blocked_despite_cash = [
        {
            "ticker": r["ticker"],
            "idle_cash_usd": r.get("idle_cash_usd"),
            "policy_state": r.get("policy_state"),
            "buy_raEV": _f(_buy_scenario_row(r).get("risk_adjusted_EV")),
            "buy_blockers": _buy_scenario_row(r).get("policy_blockers"),
            "winning_scenario": r.get("winning_scenario"),
            "high_risk_buy_allowed": r.get("high_risk_buy_allowed"),
        }
        for r in rows
        if _f(r.get("idle_cash_usd")) >= IDLE_CASH_THRESHOLD
        and r.get("winning_scenario") != "BUY_PAPER"
        and _f(_buy_scenario_row(r).get("risk_adjusted_EV")) > 0
    ]

    strong_buy_skips = [r for r in rows if r.get("strong_buy_to_skip")]

    switch_accepted = sum(
        1
        for r in rows
        if r.get("previous_action")
        and r.get("winning_scenario") != r.get("previous_action")
        and r.get("switch_authorized")
    )
    switch_blocked = sum(
        1
        for r in rows
        if r.get("previous_action")
        and r.get("winning_scenario") != r.get("previous_action")
        and not r.get("switch_authorized")
    )

    registry = {
        "schema": "tae.scenario_registry.v1",
        "generated_at": _now(),
        "mode": MODE,
        "scenarios": [
            {
                "ticker": r["ticker"],
                "winning_scenario": r["winning_scenario"],
                "risk_adjusted_EV": _f(
                    (next((s for s in r.get("scenario_ev_table") or [] if s["action"] == r["winning_scenario"]), {}) or {}).get(
                        "risk_adjusted_EV"
                    )
                ),
                "final_authority": r["final_authority"],
            }
            for r in rows
        ],
    }

    return {
        "schema": SCHEMA,
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "reconciliation_ok": recon_ok,
        "reconciliation_note": recon_note,
        "policy_context": {
            "policy_state": ctx.get("policy_state"),
            "suggested_policy": ctx.get("suggested_policy"),
            "cash_hint": _f(ctx.get("cash_hint")),
            "preferred_philosophy": ctx.get("preferred_philosophy"),
        },
        "ticker_count": len(rows),
        "tickers": rows,
        "top_conflicts": top_conflicts,
        "buy_blocked_despite_cash": buy_blocked_despite_cash,
        "strong_buy_to_skip": strong_buy_skips,
        "switch_accepted_count": switch_accepted,
        "switch_blocked_count": switch_blocked,
        "scenario_registry": registry,
        "sources_loaded": ctx.get("sources_loaded") or {},
        "safety": {
            "PAPER_ONLY": True,
            "NO_BROKER": True,
            "NO_LIVE_PROMOTION": True,
            "live_promotion_allowed": False,
        },
    }


def write_conflict_report(payload: dict[str, Any]) -> None:
    lines = [
        "# TAE Conflict Resolution Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        "**Mode:** PAPER_ONLY — evidence orchestrator — NO_BROKER — NO_LIVE_PROMOTION",
        f"**Reconciliation:** {'PASS' if payload.get('reconciliation_ok') else 'FAIL'} — {payload.get('reconciliation_note')}",
        "",
        "## Executive summary",
        "",
        f"- Tickers analyzed: **{payload.get('ticker_count', 0)}**",
        f"- Policy state: **{(payload.get('policy_context') or {}).get('policy_state')}**",
        f"- Cash hint: **${ _f((payload.get('policy_context') or {}).get('cash_hint')):,.2f}**",
        f"- BUY blocked despite cash (positive BUY EV): **{len(payload.get('buy_blocked_despite_cash') or [])}**",
        f"- STRONG BUY → SKIP cases: **{len(payload.get('strong_buy_to_skip') or [])}**",
        f"- Switch authorized: **{payload.get('switch_accepted_count', 0)}**",
        f"- Switch blocked (decision state): **{payload.get('switch_blocked_count', 0)}**",
        "",
        "## Switch gating sample",
        "",
        "| ticker | prev | winner | authorized | hard bypass | cooldown | churn | EV act/req |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in (payload.get("tickers") or [])[:12]:
        if not row.get("previous_action"):
            continue
        cd = row.get("cooldown_status") or {}
        lines.append(
            f"| {row.get('ticker')} | {row.get('previous_action')} | {row.get('winning_scenario')} | "
            f"{'yes' if row.get('switch_authorized') else 'no'} | "
            f"{'yes' if row.get('final_authority') == 'HARD_RULE' else 'no'} | "
            f"{'active' if cd.get('active') else 'no'} | {row.get('churn_risk') or '-'} | "
            f"{row.get('ev_margin_actual')} / {row.get('ev_margin_required')} |"
        )
    lines.extend(
        [
        "",
        "## Top conflicts",
        "",
        "| ticker | winner | authority | explanation |",
        "| --- | --- | --- | --- |",
    ]
    )
    for row in payload.get("top_conflicts") or []:
        lines.append(
            f"| {row.get('ticker')} | {row.get('winning_scenario')} | {row.get('final_authority')} | "
            f"{_s(row.get('explanation'))[:80].replace('|', '/')} |"
        )

    lines.extend(["", "## EV table sample (first 8 tickers)", ""])
    for row in (payload.get("tickers") or [])[:8]:
        lines.append(f"### {row.get('ticker')} → {row.get('winning_scenario')} ({row.get('final_authority')})")
        lines.append("")
        lines.append("| action | profit Δ | drawdown | P(success) | raEV | blockers |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for scen in row.get("scenario_ev_table") or []:
            if _f(scen.get("risk_adjusted_EV")) <= -9000:
                continue
            blockers = ",".join(scen.get("policy_blockers") or []) or "-"
            lines.append(
                f"| {scen.get('action')} | {scen.get('expected_profit_delta')} | {scen.get('expected_drawdown')} | "
                f"{scen.get('probability_success')} | {scen.get('risk_adjusted_EV')} | {blockers} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Safety",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| live_promotion_allowed | **false** |",
            "| Overrides hard rules | **false** |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path, Path]:
    assert_safe_output_path(CONFLICTS_JSON)
    assert_safe_output_path(SCENARIO_REGISTRY_JSON)
    assert_safe_output_path(REPORT_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    CONFLICTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    registry = payload.get("scenario_registry") or {}
    SCENARIO_REGISTRY_JSON.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    write_conflict_report(payload)
    return CONFLICTS_JSON, SCENARIO_REGISTRY_JSON, REPORT_MD


def load_conflict_by_ticker(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = load_json(path or CONFLICTS_JSON) or {}
    by: dict[str, dict[str, Any]] = {}
    for row in doc.get("tickers") or []:
        ticker = _s(row.get("ticker")).upper()
        if ticker:
            by[ticker] = row
    return by


def apply_conflict_resolution_bias(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Apply precomputed EV evidence to PDE action scores — never overrides hard rules."""
    row = (ctx.get("conflict_resolution_by_ticker") or {}).get(ticker.upper())
    if not row:
        return {}

    winning = _s(row.get("winning_scenario"))
    winner_scen = next((s for s in row.get("scenario_ev_table") or [] if s.get("action") == winning), {})
    raev = _f(winner_scen.get("risk_adjusted_EV"))
    ev_table = row.get("scenario_ev_table") or []

    if row.get("final_authority") != "HARD_RULE":
        boost = min(32.0, max(0.0, raev * 0.65)) if raev > 0 else max(-12.0, raev * 0.35)
        if winning in scores:
            scores[winning] += boost + 10.0
            evidence.append(f"conflict EV winner {winning} raEV={raev:.2f} boost={boost:.1f}")

    buy_row = next((s for s in ev_table if s.get("action") == "BUY_PAPER"), None)
    if buy_row and row.get("high_risk_buy_allowed") and not buy_row["hard_rule_status"]["blocked"]:
        buy_raev = _f(buy_row.get("risk_adjusted_EV"))
        prev = _s((row.get("previous_action") or (ctx.get("active_decisions_by_ticker") or {}).get(ticker.upper(), {}).get("last_executed_action")))
        if prev and prev != "BUY_PAPER" and not row.get("switch_authorized"):
            evidence.append(f"conflict resolution: BUY boost skipped — switch not authorized ({row.get('switch_reason')})")
        else:
            scores["BUY_PAPER"] += 38.0
            scores["SKIP_PAPER"] = max(0.0, scores.get("SKIP_PAPER", 0.0) - 22.0)
            evidence.append(
                f"conflict resolution: HIGH_RISK BUY allowed raEV={buy_raev:.2f} "
                f"cash=${_f(row.get('idle_cash_usd')):.0f} drawdown={buy_row.get('expected_drawdown')}"
            )
    elif winning == "BUY_PAPER" and row.get("final_authority") == "EV_OPTIMIZER" and row.get("switch_authorized", True):
        scores["BUY_PAPER"] += 18.0
        scores["SKIP_PAPER"] = max(0.0, scores.get("SKIP_PAPER", 0.0) - 10.0)
        evidence.append("conflict resolution: EV_OPTIMIZER selects BUY_PAPER over policy SKIP bias")

    if len(ev_table) >= 2 and row.get("final_authority") == "POLICY_CAUTION":
        scores["HOLD_PAPER"] += 10.0
        scores["SKIP_PAPER"] += 8.0
        evidence.append("conflict resolution: weak/narrow EV — HOLD/SKIP preference")

    return {
        "source": str(CONFLICTS_JSON),
        "winning_scenario": winning,
        "risk_adjusted_EV": raev,
        "final_authority": row.get("final_authority"),
        "ev_reason": row.get("explanation"),
        "high_risk_buy_allowed": bool(row.get("high_risk_buy_allowed")),
        "scenario_ev_table": [
            {
                "action": s.get("action"),
                "expected_profit_delta": s.get("expected_profit_delta"),
                "expected_drawdown": s.get("expected_drawdown"),
                "probability_success": s.get("probability_success"),
                "risk_adjusted_EV": s.get("risk_adjusted_EV"),
                "policy_blockers": s.get("policy_blockers"),
            }
            for s in ev_table
            if _f(s.get("risk_adjusted_EV")) > -9000
        ],
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def run_conflict_resolution(*, write_outputs_flag: bool = True, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    from tae_decision_state import run_decision_state_refresh

    run_decision_state_refresh(write_outputs_flag=write_outputs_flag)
    payload = build_conflict_resolution(ctx)
    if write_outputs_flag:
        paths = write_outputs(payload)
        print("===== TAE CONFLICT RESOLUTION =====")
        print(f"Tickers: {payload.get('ticker_count', 0)}")
        print(f"BUY blocked despite cash: {len(payload.get('buy_blocked_despite_cash') or [])}")
        print(f"STRONG BUY→SKIP: {len(payload.get('strong_buy_to_skip') or [])}")
        print("Wrote:", *paths)
    return payload


def main() -> int:
    run_conflict_resolution(write_outputs_flag=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
