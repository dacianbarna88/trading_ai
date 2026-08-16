#!/usr/bin/env python3
"""
TAE Paper Decision Engine — PAPER_ONLY / READ_ONLY / NO_BROKER.

Converts existing intelligence + learning-to-profit outputs into explicit PAPER decisions.
Does NOT execute trades, modify live paths, or promote to live.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from tae_artifact_paths import generated_report
from typing import Any

from tae_decision_event_bus import open_positions_from_portfolio, read_csv_rows, signals_by_ticker

SCHEMA = "tae_paper_decision_engine"
VERSION = "v1"
MODE = "PAPER_ONLY"

LTP_DIR = Path("runtime_outputs/learning_to_profit")
HYPOTHESES_JSON = LTP_DIR / "hypotheses.json"
QUEUE_JSONL = LTP_DIR / "paper_experiment_queue.jsonl"
EXPERIMENTS_JSON = LTP_DIR / "experiment_results.json"

GII_JSON = Path("tae_growth_intelligence.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
SHADOW_VALIDATION_JSON = Path("tae_profit_protection_validation.json")
PROFIT_TARGET_JSON = Path("tae_profit_target_adapter.json")
DPE_EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
DPE_ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
CONFIDENCE_JSON = Path("tae_confidence_evolution.json")
REPLAY_JSON = generated_report("tae_decision_replay.json")
ADAPTATION_HINTS_JSON = Path("runtime_outputs/longitudinal_memory/adaptation_hints.json")
LONGITUDINAL_KNOWLEDGE_JSON = Path("runtime_outputs/longitudinal_memory/knowledge.json")
ADAPTIVE_WEIGHTS_JSON = Path("runtime_outputs/adaptive_weights/paper_action_weights.json")
KNOWLEDGE_JSON = generated_report("tae_knowledge_base.json")
PATTERN_DISCOVERY_TXT = Path("pattern_discovery_summary.txt")
PORTFOLIO_CSV = Path("portfolio.csv")
SIGNALS_CSV = Path("live_signals.csv")

OUTPUT_DIR = Path("runtime_outputs/paper_decisions")
DECISIONS_JSON = OUTPUT_DIR / "paper_decisions.json"
DECISIONS_JSONL = OUTPUT_DIR / "paper_decisions.jsonl"
REPORT_MD = Path("TAE_PAPER_DECISION_ENGINE_REPORT.md")
DISCIPLINE_REPORT_MD = Path("TAE_DECISION_DISCIPLINE_REPORT.md")
PAPER_PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
ORDERS_JSONL = Path("runtime_outputs/paper_execution/paper_orders.jsonl")
RULE_LIFECYCLE_JSON = Path("runtime_outputs/paper_execution/rule_lifecycle.json")
HARD_RISK_JSON = Path("runtime_outputs/governance/hard_risk.json")
CONFLICTS_JSON = Path("runtime_outputs/conflict_resolution/conflicts.json")
ACTIVE_DECISIONS_JSON = Path("runtime_outputs/decision_state/active_decisions.json")

PAPER_ACTIONS = frozenset(
    {
        "BUY_PAPER",
        "SELL_PAPER",
        "REDUCE_PAPER",
        "PROTECT_PAPER",
        "ROTATE_PAPER",
        "HOLD_PAPER",
        "SKIP_PAPER",
    }
)

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
    "research_core/",
)

HEALTHY_LIFECYCLE = frozenset({"SURVIVED", "EARLY_WINNER", "MATURE_WINNER", "PEAK_WINNER"})
WEAK_LIFECYCLE = frozenset({"PROFIT_DECAY", "COLLAPSED", "WEAKENING"})
PRE_ENTRY_CRITICAL_COLLAPSE = 0.95
PRE_ENTRY_SOFT_COLLAPSE = 0.55
PRE_ENTRY_NEAR_STOP_PCT = -2.5

HISTORICAL_INTELLIGENCE_CSV = Path("historical_intelligence.csv")
MULTI_HORIZON_BACKTEST_CSV = Path("multi_horizon_backtest.csv")
STRATEGIC_INTELLIGENCE_TXT = Path("strategic_intelligence_summary.txt")
HORIZON_VOTE_TXT = Path("horizon_vote_summary.txt")
INTRADAY_FADE_JSON = generated_report("tae_intraday_fade_intelligence.json")
CROSS_VALIDATION_JSON = Path("tae_cross_validation_report.json")
HISTORICAL_RESULTS_JSON = Path("tae_historical_results_analysis.json")
HORIZON_LABELS = ("7D", "1M", "1Y", "2Y", "5Y", "10Y", "20Y")

# Learning ablation components (economic ON/OFF harness). Default = all enabled (canonical).
ABLATION_LEARNING_COMPONENTS = frozenset(
    {
        "horizon",
        "knowledge_base",
        "named_confidence",
        "longitudinal",
        "dpe_evaluator",
        "learning_evidence",
        "adaptive_weights",
        "rule_lifecycle",
        "experiment_capital",
        "hypothesis_rules",
        "adaptation_hints",
    }
)


def ablation_learning_enabled(ctx: dict[str, Any]) -> bool:
    """Canonical path defaults True. Ablation LEARNING_OFF sets False."""
    return bool(ctx.get("ablation_learning_enabled", True))


def ablation_component_enabled(ctx: dict[str, Any], component: str) -> bool:
    """When learning is on, optional subset enables selective source attribution."""
    if not ablation_learning_enabled(ctx):
        return False
    selected = ctx.get("ablation_learning_components")
    if selected is None:
        return True
    return component in set(selected)

PAPER_SAFE_KB_RECOMMENDATIONS = frozenset(
    {
        "CONTINUE_OBSERVATION",
        "PRIORITIZE_TRACKING",
        "TEST_TRAILING_SHADOW",
        "TEST_PARTIAL_SELL_SHADOW",
        "TEST_15M_COOLDOWN_SHADOW",
        "SCORE_DECAY_SHADOW",
        "INSUFFICIENT_DATA",
        "DO_NOT_PROMOTE_TO_ADVISORY_YET",
        "DO_NOT_PROMOTE_TO_LIVE",
    }
)
FORBIDDEN_KB_RECOMMENDATIONS = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT", "PROMOTE_TO_LIVE"})
MAX_KNOWLEDGE_SCORE_DELTA = 8.0
MAX_PROFIT_TARGET_SCORE_DELTA = 22.0

PROFIT_TARGET_URGENCY_DELTAS: dict[str, dict[str, float]] = {
    "CRITICAL": {"REDUCE_PAPER": 18.0, "PROTECT_PAPER": 14.0, "HOLD_PAPER": -12.0, "SELL_PAPER": 6.0},
    "HIGH": {"PROTECT_PAPER": 14.0, "REDUCE_PAPER": 10.0, "HOLD_PAPER": -8.0},
    "MEDIUM": {"PROTECT_PAPER": 6.0, "HOLD_PAPER": 4.0, "REDUCE_PAPER": 4.0},
    "LOW": {"HOLD_PAPER": 6.0},
}

PROFIT_TARGET_STRATEGY_DELTAS: dict[str, dict[str, float]] = {
    "REDUCE_EXPOSURE_SHADOW": {"REDUCE_PAPER": 12.0, "PROTECT_PAPER": 6.0},
    "PROTECT_PROFIT_SHADOW": {"PROTECT_PAPER": 12.0, "REDUCE_PAPER": 6.0},
    "TIGHTEN_TRAIL_SHADOW": {"PROTECT_PAPER": 10.0, "REDUCE_PAPER": 4.0},
    "KEEP_GROWING_SHADOW": {"HOLD_PAPER": 8.0},
    "HOLD_AND_MONITOR_SHADOW": {"HOLD_PAPER": 5.0, "PROTECT_PAPER": 3.0},
}

# Live-promotion locks are PAPER-safe as evidence / live_promotion_allowed=false only.
# They must NOT suppress BUY_PAPER scores — that conflates "no live promotion" with "no PAPER buy".
LIVE_PROMOTION_LOCK_RULES = frozenset(
    {
        "DO_NOT_PROMOTE",
        "DO_NOT_PROMOTE_TO_LIVE",
        "DO_NOT_PROMOTE_TO_ADVISORY_YET",
    }
)

NAMED_RULE_SCORE_DELTAS: dict[str, dict[str, float]] = {
    "SCORE_DECAY_SHADOW": {"BUY_PAPER": -8.0, "SKIP_PAPER": 5.0},
    "STOP_REENTRY_CHURN": {"BUY_PAPER": -6.0, "SKIP_PAPER": 4.0},
    "MISSED_PROFIT_PROTECTION": {"PROTECT_PAPER": 8.0, "SELL_PAPER": 4.0, "REDUCE_PAPER": 3.0},
    "TRAILING_1_PROTECTION_HYPOTHESIS": {"PROTECT_PAPER": 6.0},
}

LIFECYCLE_INFLUENCE = {
    "NEW": 0.9,
    "TESTING": 0.85,
    "ACTIVE": 1.0,
    "TRUSTED": 1.06,
    "WATCHLIST": 0.45,
    "DEPRECATED": 0.12,
    "DISABLED": 0.0,
}

POSITION_REQUIRED_ACTIONS = frozenset({"PROTECT_PAPER", "SELL_PAPER", "REDUCE_PAPER", "HOLD_PAPER"})


def load_paper_positions(portfolio_doc: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    positions: dict[str, dict[str, Any]] = {}
    for ticker, pos in ((portfolio_doc or {}).get("positions") or {}).items():
        if _f(pos.get("shares")) > 0:
            positions[_s(ticker).upper()] = pos
    return positions


def paper_position_held(ticker: str, ctx: dict[str, Any]) -> bool:
    pos = (ctx.get("paper_positions") or {}).get(ticker.upper())
    return bool(pos and _f(pos.get("shares")) > 0)


def position_has_exposure(ticker: str, ctx: dict[str, Any]) -> bool:
    ticker = ticker.upper()
    if paper_position_held(ticker, ctx):
        return True
    live = (ctx.get("live_positions") or {}).get(ticker) or {}
    return _f(live.get("shares")) > 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def index_recent_hard_stops(orders: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Latest hard-risk SELL per ticker from existing paper order artifacts."""
    out: dict[str, dict[str, Any]] = {}
    for order in orders:
        ticker = _s(order.get("ticker")).upper()
        action = _s(order.get("action")).upper()
        if not ticker or action != "SELL_PAPER":
            continue
        reason_blob = " ".join(
            _s(order.get(key))
            for key in ("reason", "execution_reason", "order_reason", "evidence", "notes")
        ).upper()
        hard = bool(order.get("hard_risk_override")) or "HARD RISK" in reason_blob or "HARD_RISK" in reason_blob
        if not hard:
            continue
        ts = _s(order.get("timestamp"))
        prev = out.get(ticker)
        if not prev or ts >= _s(prev.get("timestamp")):
            out[ticker] = {
                "timestamp": ts,
                "reason": reason_blob[:240],
                "hard_rule": _s(order.get("hard_rule")),
                "order_id": _s(order.get("order_id") or order.get("decision_id")),
            }
    return out


def has_valid_mark_price(ticker: str, ctx: dict[str, Any]) -> bool:
    ticker = ticker.upper()
    paper = (ctx.get("paper_positions") or {}).get(ticker) or {}
    if _f(paper.get("current_price")) > 0 or _f(paper.get("avg_price")) > 0:
        return True
    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    if _f(gii.get("current_price")) > 0:
        return True
    if gii.get("current_pct") is not None and _s(gii.get("lifecycle_stage")):
        return True
    shadow = (ctx.get("shadow_by") or {}).get(ticker) or {}
    if _f(shadow.get("current_price")) > 0 or shadow.get("current_pct") is not None:
        return True
    signal = (ctx.get("signals") or {}).get(ticker) or {}
    if _f(signal.get("price")) > 0 or _f(signal.get("last_price")) > 0:
        return True
    return False


def evaluate_pre_entry_hard_risk_compatibility(
    ticker: str,
    ctx: dict[str, Any],
    *,
    held: bool | None = None,
) -> dict[str, Any]:
    """Reuse existing Hard Risk / GII / PPG / decision-state evidence — evidence only, no execution."""
    ticker = ticker.upper()
    if held is None:
        held = paper_position_held(ticker, ctx)
    exposure = position_has_exposure(ticker, ctx)

    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    ppg_row = (ctx.get("ppg_by") or {}).get(ticker) or {}
    hard_row = (ctx.get("hard_risk_by") or {}).get(ticker) or {}
    policy_state = _s(ctx.get("policy_state"))
    suggested = _s(ctx.get("suggested_policy")).upper()
    ppg_verdict = _s((ctx.get("ppg") or {}).get("portfolio_verdict"))

    lifecycle = _s(gii.get("lifecycle_stage"))
    collapse = _f(gii.get("collapse_probability"))
    strategy = _s(gii.get("recommended_shadow_strategy"))
    posture = _s(ppg_row.get("governor_posture"))
    pnl_pct = _f(hard_row.get("pnl_pct"))
    hr_status = _s(hard_row.get("status"))
    high_risk = (
        policy_state == "HIGH_RISK"
        or "HIGH_RISK" in ppg_verdict.upper()
        or "PRESERVATION" in suggested
    )

    recent = (ctx.get("recent_hard_stops_by_ticker") or {}).get(ticker) or {}
    recent_hard_stop = bool(recent.get("timestamp"))
    state = (ctx.get("active_decisions_by_ticker") or {}).get(ticker) or {}
    cooldown = state.get("cooldown_status") or {}

    reasons: list[str] = []
    hard_block = False
    reentry_allowed = True
    risk_level = "LOW"

    if exposure and hr_status in {"STOP_LOSS_BREACHED", "CRITICAL_LOSS"}:
        hard_block = True
        risk_level = "CRITICAL"
        reasons.append(f"active_hard_risk_breach:{hr_status}")

    if recent_hard_stop and cooldown.get("active"):
        hard_block = True
        reentry_allowed = False
        risk_level = "CRITICAL"
        reasons.append("hard_stop_reentry_cooldown_active")

    if recent_hard_stop and not cooldown.get("active"):
        if collapse >= PRE_ENTRY_CRITICAL_COLLAPSE and lifecycle in WEAK_LIFECYCLE:
            hard_block = True
            reentry_allowed = False
            risk_level = "CRITICAL"
            reasons.append("persistent_critical_risk_after_hard_stop")

    if collapse >= PRE_ENTRY_CRITICAL_COLLAPSE and lifecycle in WEAK_LIFECYCLE and high_risk:
        hard_block = True
        risk_level = "CRITICAL"
        reasons.append("critical_collapse_profit_decay_high_risk")

    if strategy in {"TIGHTEN_TRAIL_SHADOW", "PROTECT_PROFIT_SHADOW"} and collapse >= PRE_ENTRY_CRITICAL_COLLAPSE:
        hard_block = True
        risk_level = "CRITICAL"
        reasons.append("tighten_trail_critical_collapse")

    if exposure and lifecycle in WEAK_LIFECYCLE and collapse >= PRE_ENTRY_CRITICAL_COLLAPSE:
        hard_block = True
        risk_level = "CRITICAL"
        reasons.append("existing_exposure_structural_decay")

    if exposure and pnl_pct <= PRE_ENTRY_NEAR_STOP_PCT:
        hard_block = True
        risk_level = "CRITICAL"
        reasons.append(f"insufficient_hard_risk_cushion:{pnl_pct:.2f}%")

    if not has_valid_mark_price(ticker, ctx):
        hard_block = True
        risk_level = "CRITICAL"
        reasons.append("missing_valid_mark")

    soft_delta = 0.0
    if not hard_block:
        if high_risk and collapse >= PRE_ENTRY_SOFT_COLLAPSE:
            risk_level = "HIGH"
            soft_delta = -18.0
            reasons.append("high_risk_elevated_collapse_soft_penalty")
        elif high_risk and lifecycle in WEAK_LIFECYCLE:
            risk_level = "MODERATE"
            soft_delta = -12.0
            reasons.append("high_risk_weak_lifecycle_soft_penalty")
        elif strategy in {"TIGHTEN_TRAIL_SHADOW", "PROTECT_PROFIT_SHADOW"} and collapse >= PRE_ENTRY_SOFT_COLLAPSE:
            risk_level = "MODERATE"
            soft_delta = -10.0
            reasons.append("protection_strategy_elevated_collapse_soft_penalty")

    return {
        "compatible": not hard_block,
        "hard_block": hard_block,
        "risk_level": risk_level,
        "reasons": reasons,
        "source_fields": {
            "hard_risk_status": hr_status or "OK",
            "pnl_pct": round(pnl_pct, 4),
            "collapse_probability": round(collapse, 4),
            "lifecycle_stage": lifecycle,
            "recommended_shadow_strategy": strategy,
            "governor_posture": posture,
            "policy_state": policy_state,
            "suggested_policy": _s(ctx.get("suggested_policy")),
            "portfolio_verdict": ppg_verdict,
            "high_risk_context": high_risk,
            "position_exposure": exposure,
            "paper_held": held,
            "cooldown_active": bool(cooldown.get("active")),
            "last_hard_stop_at": recent.get("timestamp"),
        },
        "recent_hard_stop": recent_hard_stop,
        "reentry_allowed": reentry_allowed and not hard_block,
        "soft_score_delta": soft_delta,
    }


def apply_pre_entry_hard_risk_sync(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    pre_entry: dict[str, Any],
    *,
    held: bool,
) -> dict[str, Any]:
    """Adjust BUY scoring from pre-entry compatibility — does not execute trades."""
    buy_before = _f(scores.get("BUY_PAPER"))
    if pre_entry.get("hard_block"):
        scores["BUY_PAPER"] = 0.0
        scores["SKIP_PAPER"] += max(45.0, buy_before + 30.0)
        if held:
            scores["HOLD_PAPER"] += 20.0
            scores["PROTECT_PAPER"] += 15.0
        evidence.append(
            "pre-entry hard risk sync: BUY blocked — "
            + "; ".join((pre_entry.get("reasons") or [])[:4])
        )
        return {
            "risk_score_delta": round(-buy_before, 2),
            "decision_coherence_status": "BLOCKED_HARD_RISK_CONFLICT",
            "buy_blocked": True,
        }

    soft_delta = _f(pre_entry.get("soft_score_delta"))
    if soft_delta < 0 and buy_before > 0:
        applied = max(soft_delta, -buy_before)
        scores["BUY_PAPER"] = max(0.0, buy_before + applied)
        scores["SKIP_PAPER"] += min(15.0, abs(applied) * 0.6)
        evidence.append(
            f"pre-entry hard risk sync: BUY soft penalty {applied:.1f} "
            f"(risk_level={pre_entry.get('risk_level')})"
        )
        return {
            "risk_score_delta": round(applied, 2),
            "decision_coherence_status": "SOFT_RISK_CONFLICT_RESOLVED",
            "buy_blocked": False,
        }

    return {
        "risk_score_delta": 0.0,
        "decision_coherence_status": "COHERENT",
        "buy_blocked": False,
    }


def collect_rules_applied(consumption: dict[str, Any], named_rules: list[str]) -> list[str]:
    applied: list[str] = list(named_rules or [])
    ke = consumption.get("knowledge_evidence") or {}
    applied.extend(ke.get("rules_applied") or [])
    lk = consumption.get("longitudinal_knowledge_evidence") or {}
    for rule in lk.get("rules_applied") or lk.get("rule_ids") or []:
        applied.append(_s(rule))
    return sorted(set(r for r in applied if r))


def apply_rule_lifecycle_bias(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    rules_applied: list[str],
) -> dict[str, Any]:
    lifecycle_doc = ctx.get("rule_lifecycle") or {}
    lifecycle_rules = lifecycle_doc.get("rules") or {}
    adjustments: list[str] = []
    rule_states: dict[str, str] = {}

    for rule_id in rules_applied:
        info = lifecycle_rules.get(rule_id) or lifecycle_rules.get(rule_id.upper()) or {}
        state = _s(info.get("state"), "TESTING")
        rule_states[rule_id] = state
        mult = _f(info.get("influence_multiplier"), LIFECYCLE_INFLUENCE.get(state, 1.0))
        deltas = NAMED_RULE_SCORE_DELTAS.get(rule_id) or NAMED_RULE_SCORE_DELTAS.get(rule_id.upper())
        if not deltas:
            continue
        if state == "DISABLED":
            for action, delta in deltas.items():
                if delta > 0 and action in scores:
                    scores[action] = max(0.0, scores[action] - delta)
            adjustments.append(f"DISABLED {rule_id}: blocked positive score influence")
        elif state == "TRUSTED" and mult > 1.0:
            for action, delta in deltas.items():
                if delta > 0 and action in scores:
                    boost = min(4.0, delta * (mult - 1.0))
                    scores[action] += boost
            adjustments.append(f"TRUSTED {rule_id}: modest boost x{mult}")
        elif mult < 1.0:
            for action, delta in deltas.items():
                if delta > 0 and action in scores:
                    scores[action] = max(0.0, scores[action] - delta * (1.0 - mult))
            adjustments.append(f"{state} {rule_id}: reduced influence x{mult}")

    if adjustments:
        evidence.append(f"rule lifecycle: {'; '.join(adjustments[:4])}")
    return {
        "rules_applied": rules_applied,
        "rule_states": rule_states,
        "adjustments": adjustments,
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def enforce_hard_risk_discipline(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """HARD layer: -3% stop / -5% critical override before all soft policy logic."""
    ticker = ticker.upper()
    if not paper_position_held(ticker, ctx):
        return {"override": False, "evaluated": False}

    row = (ctx.get("hard_risk_by") or {}).get(ticker) or {}
    status = _s(row.get("status"))
    if status not in {"STOP_LOSS_BREACHED", "CRITICAL_LOSS"}:
        return {
            "override": False,
            "evaluated": True,
            "status": status or "OK",
            "pnl_pct": _f(row.get("pnl_pct")),
        }

    hard_rule = _s(row.get("hard_rule"))
    pnl_pct = _f(row.get("pnl_pct"))
    required = _s(row.get("required_action"))
    for action in scores:
        scores[action] = 0.0
    scores["SELL_PAPER"] = 100.0
    evidence.append(
        f"HARD RISK override ({hard_rule}): {pnl_pct:.2f}% loss → SELL_PAPER "
        f"(required={required}, before soft logic)"
    )
    return {
        "override": True,
        "evaluated": True,
        "status": status,
        "hard_rule": hard_rule,
        "pnl_pct": pnl_pct,
        "required_action": required,
    }


def enforce_position_discipline(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    ticker = ticker.upper()
    has_paper = paper_position_held(ticker, ctx)
    blocked: list[str] = []
    if has_paper:
        return {"blocked": blocked, "has_paper_position": True}

    for action in POSITION_REQUIRED_ACTIONS:
        if scores.get(action, 0.0) > 0:
            blocked.append(action)
            scores[action] = 0.0
    if scores.get("ROTATE_PAPER", 0.0) > 0:
        blocked.append("ROTATE_PAPER")
        scores["ROTATE_PAPER"] = 0.0
    if blocked:
        evidence.append(f"position discipline: blocked {','.join(blocked)} — no PAPER position")
    return {"blocked": blocked, "has_paper_position": False}


def enforce_loss_discipline(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    rule_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    ticker = ticker.upper()
    if not paper_position_held(ticker, ctx):
        return {"evaluated": False}

    pos = (ctx.get("paper_positions") or {}).get(ticker) or {}
    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    current_pct = _f(pos.get("unrealized_pct") or pos.get("current_pct") or gii.get("current_pct"))
    lifecycle = _s(gii.get("lifecycle_stage"))
    hz = build_horizon_context(ticker, ctx)
    long_positive = trend_polarity(hz.get("long_term_trend")) > 0
    strong_hold = lifecycle in HEALTHY_LIFECYCLE and long_positive

    weak_rules = any(
        state in {"WATCHLIST", "DEPRECATED", "DISABLED"} for state in (rule_states or {}).values()
    )
    detail: dict[str, Any] = {
        "evaluated": True,
        "current_pct": round(current_pct, 4),
        "strong_hold_reason": strong_hold,
        "weak_rule_evidence": weak_rules,
    }

    if current_pct <= -7.0:
        scores["SELL_PAPER"] += 45.0
        protect_before = scores.get("PROTECT_PAPER", 0.0)
        if not strong_hold:
            scores["PROTECT_PAPER"] = min(protect_before, max(0.0, protect_before * 0.25))
            detail["protect_suppressed"] = True
            evidence.append(
                f"loss discipline: {current_pct:.1f}% loss — SELL required unless strong hold "
                f"(lifecycle={lifecycle}, long_positive={long_positive})"
            )
        else:
            evidence.append(
                f"loss discipline: {current_pct:.1f}% loss — SELL boosted but strong hold retained "
                f"(lifecycle={lifecycle})"
            )
        detail["severity"] = "critical"
    elif current_pct <= -5.0 and weak_rules:
        sell_boost = 40.0 if current_pct <= -6.0 else 30.0
        protect_cut = 35.0 if current_pct <= -6.0 else 20.0
        scores["SELL_PAPER"] += sell_boost
        scores["PROTECT_PAPER"] = max(0.0, scores.get("PROTECT_PAPER", 0.0) - protect_cut)
        if not strong_hold:
            scores["PROTECT_PAPER"] = min(scores.get("PROTECT_PAPER", 0.0), scores.get("SELL_PAPER", 0.0))
            scores["HOLD_PAPER"] = min(scores.get("HOLD_PAPER", 0.0), scores.get("SELL_PAPER", 0.0))
        evidence.append(
            f"loss discipline: {current_pct:.1f}% + weak rules — SELL outranks PROTECT"
        )
        detail["severity"] = "elevated"

    detail["sell_score"] = round(scores.get("SELL_PAPER", 0.0), 2)
    detail["protect_score"] = round(scores.get("PROTECT_PAPER", 0.0), 2)
    detail["preferred"] = "SELL_PAPER" if detail["sell_score"] > detail["protect_score"] else "PROTECT_PAPER"
    return detail


def write_decision_discipline_report(decisions: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
    blocked_no_position = [
        d for d in decisions if (d.get("position_discipline") or {}).get("blocked")
    ]
    loss_evals = [
        d
        for d in decisions
        if (d.get("loss_discipline") or {}).get("evaluated")
        and _f((d.get("loss_discipline") or {}).get("current_pct")) <= -5.0
    ]
    lifecycle = ctx.get("rule_lifecycle") or {}
    by_state = lifecycle.get("by_state") or {}

    lines = [
        "# TAE Decision Discipline Report",
        "",
        f"**Generated:** {_now()}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
        "",
        "## Position discipline",
        "",
        f"- Decisions blocked (no PAPER position): **{len(blocked_no_position)}**",
        f"- PAPER positions held: **{len(ctx.get('paper_positions') or {})}**",
        f"- Canonical positions (read-only): **{len(ctx.get('live_positions') or {})}**",
        "",
    ]
    if blocked_no_position:
        lines.append("| ticker | blocked actions | chosen action |")
        lines.append("| --- | --- | --- |")
        for d in blocked_no_position[:20]:
            pd = d.get("position_discipline") or {}
            lines.append(
                f"| {d.get('ticker')} | {','.join(pd.get('blocked') or [])} | {d.get('action')} |"
            )
        lines.append("")

    lines.extend(["## Loss discipline (positions ≤ -5%)", ""])
    if loss_evals:
        lines.append("| ticker | current_pct | sell | protect | preferred | reason |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for d in sorted(loss_evals, key=lambda x: _f((x.get("loss_discipline") or {}).get("current_pct"))):
            ld = d.get("loss_discipline") or {}
            lines.append(
                f"| {d.get('ticker')} | {ld.get('current_pct', 0):.1f}% | {ld.get('sell_score')} | "
                f"{ld.get('protect_score')} | {ld.get('preferred')} | {d.get('action')} chosen |"
            )
    else:
        lines.append("- No losing positions below -5% threshold.")
    lines.append("")

    lines.extend(["## Rule lifecycle summary", ""])
    for state in ("DISABLED", "DEPRECATED", "WATCHLIST", "TRUSTED", "ACTIVE"):
        ids = by_state.get(state) or []
        if ids:
            lines.append(f"- **{state}**: `{ids[:8]}`")

    DISCIPLINE_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if path.resolve() != REPORT_MD.resolve() and output_root not in path.resolve().parents:
        raise RuntimeError(f"Unsafe output path outside paper_decisions/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def index_gii(gii: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _s(t.get("ticker")).upper(): t for t in (gii or {}).get("tickers") or [] if t.get("ticker")
    }


def index_shadow(shadow: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _s(p.get("ticker")).upper(): p for p in (shadow or {}).get("positions") or [] if p.get("ticker")
    }


def ppg_posture_by_ticker(ppg: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in ("top_5_risky_tickers", "top_5_keep_winners"):
        for row in (ppg or {}).get(key) or []:
            if isinstance(row, dict):
                ticker = _s(row.get("ticker")).upper()
                if ticker:
                    out[ticker] = row
    return out


def experiments_by_ticker(experiments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for exp in experiments:
        tickers = exp.get("affected_tickers") or []
        if not tickers:
            out.setdefault("_PORTFOLIO", []).append(exp)
            continue
        for raw in tickers:
            ticker = _s(raw).upper()
            out.setdefault(ticker, []).append(exp)
    return out


def file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600, 1)


def market_proxy_ticker(ticker: str) -> str:
    ticker = ticker.upper()
    if ticker.endswith(".L"):
        return "EWU"
    if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
        return "VGK"
    if ticker in {"SPY", "QQQ", "DIA", "IWM", "VGK", "EWU", "FEZ"}:
        return ticker
    return "SPY"


def classify_trend(value: float | None, *, pos: float = 1.0, neg: float = -1.0) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= pos:
        return "POSITIVE"
    if value <= neg:
        return "NEGATIVE"
    return "NEUTRAL"


def trend_polarity(trend: str) -> int:
    return {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": -1, "UNKNOWN": 0}.get(trend, 0)


def load_historical_horizon_returns(path: Path = HISTORICAL_INTELLIGENCE_CSV) -> dict[str, dict[str, float]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = _s(row.get("Ticker")).upper()
            horizon = _s(row.get("Horizon"))
            if not ticker or horizon not in {"2Y", "5Y", "10Y", "20Y"}:
                continue
            try:
                out.setdefault(ticker, {})[horizon] = float(row.get("Return_%") or 0)
            except (TypeError, ValueError):
                continue
    return out


def parse_strategic_market_returns(path: Path = STRATEGIC_INTELLIGENCE_TXT) -> dict[str, dict[str, float]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, float]] = {}
    pattern = re.compile(
        r"\|\s*([A-Z0-9._]+)\s*\|\s*1M\s*([-\d.]+)%?\s*\|\s*3M\s*([-\d.]+)%?\s*\|\s*6M\s*([-\d.]+)%?\s*\|\s*12M\s*([-\d.]+)%"
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        proxy = match.group(1).upper()
        out[proxy] = {
            "1M": float(match.group(2)),
            "1Y": float(match.group(5)),
        }
    return out


def load_intraday_by_ticker(path: Path = INTRADAY_FADE_JSON) -> dict[str, dict[str, Any]]:
    doc = load_json(path) or {}
    return {
        _s(p.get("ticker")).upper(): p
        for p in (doc.get("positions") or [])
        if p.get("ticker")
    }


def load_horizon_ssot() -> dict[str, Any]:
    cross = load_json(CROSS_VALIDATION_JSON) or {}
    hist_results = load_json(HISTORICAL_RESULTS_JSON) or {}
    horizon_vote = HORIZON_VOTE_TXT.read_text(encoding="utf-8", errors="replace") if HORIZON_VOTE_TXT.is_file() else ""
    return {
        "historical_returns": load_historical_horizon_returns(),
        "strategic_returns": parse_strategic_market_returns(),
        "multi_horizon_backtest_present": MULTI_HORIZON_BACKTEST_CSV.is_file(),
        "intraday_by_ticker": load_intraday_by_ticker(),
        "cross_horizon_consistency": cross.get("cross_horizon_consistency_summary"),
        "horizon_vote_text": horizon_vote,
        "historical_results_horizons": list((hist_results.get("top_10_per_horizon") or {}).keys()),
        "freshness_hours": {
            "historical_intelligence.csv": file_age_hours(HISTORICAL_INTELLIGENCE_CSV),
            "strategic_intelligence_summary.txt": file_age_hours(STRATEGIC_INTELLIGENCE_TXT),
            "horizon_vote_summary.txt": file_age_hours(HORIZON_VOTE_TXT),
            "tae_intraday_fade_intelligence.json": file_age_hours(INTRADAY_FADE_JSON),
            "tae_cross_validation_report.json": file_age_hours(CROSS_VALIDATION_JSON),
        },
    }


def build_horizon_context(ticker: str, ctx: dict[str, Any]) -> dict[str, Any]:
    ticker = ticker.upper()
    ssot = ctx.get("horizon_ssot") or {}
    stale_paths = set(ctx.get("stale_source_paths") or [])
    hist_stale = "historical_intelligence.csv" in stale_paths
    strat_stale = "strategic_intelligence_summary.txt" in stale_paths
    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    intraday = (ssot.get("intraday_by_ticker") or {}).get(ticker) or {}
    hist = (ssot.get("historical_returns") or {}).get(ticker) or {}
    proxy = market_proxy_ticker(ticker)
    strategic = (ssot.get("strategic_returns") or {}).get(proxy) or {}

    short_pct = _f(intraday.get("current_pct") or gii.get("current_pct"))
    short_drawdown = abs(_f(intraday.get("drawdown_from_high_pct") or gii.get("drawdown")))

    ret_2y = hist.get("2Y") if not hist_stale else None
    ret_5y = hist.get("5Y") if not hist_stale else None
    ret_10y = hist.get("10Y") if not hist_stale else None
    ret_20y = hist.get("20Y") if not hist_stale else None

    ret_1m = strategic.get("1M") if not strat_stale else None
    ret_1y = strategic.get("1Y") if not strat_stale else None

    if ret_1y is None and ret_2y is not None:
        ret_1y = ret_2y / 2.0

    horizon_context: dict[str, dict[str, Any]] = {
        "7D": {
            "return_pct": round(short_pct, 2),
            "trend": classify_trend(short_pct, pos=0.5, neg=-0.5),
            "source": "tae_intraday_fade_intelligence.json|tae_growth_intelligence.json",
        },
        "1M": {
            "return_pct": ret_1m,
            "trend": "UNKNOWN" if strat_stale else classify_trend(ret_1m),
            "source": f"strategic_intelligence_summary.txt via {proxy}",
            "stale": strat_stale,
        },
        "1Y": {
            "return_pct": round(ret_1y, 2) if ret_1y is not None else None,
            "trend": "UNKNOWN" if strat_stale else classify_trend(ret_1y),
            "source": f"strategic_intelligence_summary.txt|historical_intelligence.csv via {proxy}",
            "stale": strat_stale or hist_stale,
        },
        "2Y": {
            "return_pct": ret_2y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_2y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
        "5Y": {
            "return_pct": ret_5y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_5y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
        "10Y": {
            "return_pct": ret_10y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_10y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
        "20Y": {
            "return_pct": ret_20y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_20y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
    }

    short_term_trend_7d = horizon_context["7D"]["trend"]
    monthly_trend = horizon_context["1M"]["trend"]
    yearly_trend = horizon_context["1Y"]["trend"]
    long_values = [ret_5y, ret_10y, ret_20y]
    long_avg = sum(v for v in long_values if v is not None) / max(1, len([v for v in long_values if v is not None]))
    long_term_trend = classify_trend(long_avg if long_values else None)

    polarities = [trend_polarity(horizon_context[h]["trend"]) for h in HORIZON_LABELS]
    alignment_score = round(50.0 + sum(polarities) * (50.0 / len(HORIZON_LABELS)), 1)
    alignment_score = max(0.0, min(100.0, alignment_score))

    short_pol = trend_polarity(short_term_trend_7d)
    medium_pol = trend_polarity(monthly_trend)
    long_pol = trend_polarity(long_term_trend)
    conflict = (short_pol < 0 and long_pol > 0) or (short_pol > 0 and long_pol < 0)

    parts: list[str] = []
    for label in HORIZON_LABELS:
        row = horizon_context[label]
        ret = row.get("return_pct")
        ret_txt = f"{ret:.1f}%" if isinstance(ret, (int, float)) else "n/a"
        parts.append(f"{label}={row['trend']}({ret_txt})")
    if conflict:
        parts.append("short-vs-long CONFLICT")
    else:
        parts.append("horizons aligned")
    if hist_stale:
        parts.append("STALE historical_intelligence.csv — 2Y-20Y not used")
    if strat_stale:
        parts.append("STALE strategic_intelligence_summary.txt — 1M/1Y not used")
    horizon_reason = "; ".join(parts)

    return {
        "horizon_context": horizon_context,
        "short_term_trend_7d": short_term_trend_7d,
        "monthly_trend": monthly_trend,
        "yearly_trend": yearly_trend,
        "long_term_trend": long_term_trend,
        "horizon_alignment_score": alignment_score,
        "horizon_conflict_flag": conflict,
        "horizon_reason": horizon_reason,
        "short_drawdown_pct": round(short_drawdown, 2),
        "market_proxy": proxy,
        "cross_horizon_consistency": ssot.get("cross_horizon_consistency"),
        "historical_stale": hist_stale,
        "strategic_stale": strat_stale,
    }


def apply_stale_source_penalty(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> float:
    penalty = _f((ctx.get("historical_runtime") or {}).get("confidence_penalty"))
    stale = (ctx.get("historical_runtime") or {}).get("stale_sources") or []
    if not stale and not penalty:
        return 0.0
    if stale:
        evidence.append(f"STALE sources: {', '.join(stale)} — confidence reduced")
    if penalty > 0:
        for action in scores:
            if action != "SKIP_PAPER":
                scores[action] *= max(0.5, 1.0 - penalty)
        scores["SKIP_PAPER"] += penalty * 40.0
    return penalty


def parse_final_recommendation(confidence_doc: dict[str, Any] | None) -> dict[str, Any]:
    raw = (confidence_doc or {}).get("final_recommendation")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.startswith("{"):
        try:
            parsed = json.loads(raw.replace("'", '"'))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def is_paper_safe_kb_entry(entry: dict[str, Any]) -> bool:
    if entry.get("shadow_only") is False and not entry.get("recommendation"):
        return False
    rec = _s(entry.get("recommendation")).upper()
    if rec in FORBIDDEN_KB_RECOMMENDATIONS:
        return False
    if rec and rec not in PAPER_SAFE_KB_RECOMMENDATIONS and "SHADOW" not in rec and "DO_NOT_PROMOTE" not in rec:
        return False
    if "PROMOTE_TO_LIVE" in rec and "DO_NOT" not in rec:
        return False
    return True


def apply_score_deltas(
    scores: dict[str, float],
    deltas: dict[str, float],
    *,
    cap: float = MAX_KNOWLEDGE_SCORE_DELTA,
) -> float:
    applied = 0.0
    for action, delta in deltas.items():
        if action not in scores or not delta:
            continue
        bounded = max(-cap, min(cap, delta))
        scores[action] += bounded
        applied += abs(bounded)
    return applied


def apply_named_rule(
    scores: dict[str, float],
    rule_key: str,
    *,
    cap: float = MAX_KNOWLEDGE_SCORE_DELTA,
) -> list[str]:
    key = _s(rule_key).upper()
    if key in LIVE_PROMOTION_LOCK_RULES:
        # Evidence-only: do not alter PAPER action scores.
        return [key]
    deltas = NAMED_RULE_SCORE_DELTAS.get(key) or NAMED_RULE_SCORE_DELTAS.get(rule_key)
    if not deltas:
        return []
    apply_score_deltas(scores, deltas, cap=cap)
    return [key]


def apply_knowledge_base_bias(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    ticker: str,
) -> dict[str, Any]:
    kb = ctx.get("knowledge_base") or {}
    entries = kb.get("entries") or []
    rules_applied: list[str] = []
    matched_ids: list[str] = []
    ticker_u = ticker.upper()

    for entry in entries:
        if not is_paper_safe_kb_entry(entry):
            continue
        subject = _s(entry.get("subject")).upper()
        pattern = _s(entry.get("pattern_type")).upper()
        if (
            subject
            and subject not in {ticker_u, "_PORTFOLIO", "PORTFOLIO", ""}
            and subject not in NAMED_RULE_SCORE_DELTAS
            and subject != pattern
        ):
            continue
        rec = _s(entry.get("recommendation")).upper()
        key = pattern or rec
        if key in NAMED_RULE_SCORE_DELTAS:
            rules_applied.extend(apply_named_rule(scores, key))
            matched_ids.append(_s(entry.get("id")))
        elif rec == "SCORE_DECAY_SHADOW" or pattern == "SCORE_DECAY_SHADOW":
            rules_applied.extend(apply_named_rule(scores, "SCORE_DECAY_SHADOW"))
            matched_ids.append(_s(entry.get("id")))
        elif "TRAILING" in rec or "TRAILING" in pattern:
            rules_applied.extend(apply_named_rule(scores, "TRAILING_1_PROTECTION_HYPOTHESIS"))
            matched_ids.append(_s(entry.get("id")))

    if rules_applied:
        evidence.append(f"knowledge base rules: {', '.join(sorted(set(rules_applied)))}")
    return {
        "source": str(KNOWLEDGE_JSON),
        "rules_applied": sorted(set(rules_applied)),
        "entry_ids": matched_ids[:10],
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def apply_named_confidence_rules(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> list[str]:
    confidence_doc = ctx.get("confidence_evolution") or {}
    replay_doc = ctx.get("decision_replay") or {}
    rules_applied: list[str] = []

    for entry in confidence_doc.get("confidence_evolution_entries") or []:
        hyp = _s(entry.get("hypothesis")).upper()
        rec = _s(entry.get("recommendation")).upper()
        if hyp in NAMED_RULE_SCORE_DELTAS:
            rules_applied.extend(apply_named_rule(scores, hyp))
        elif rec == "SCORE_DECAY_SHADOW":
            rules_applied.extend(apply_named_rule(scores, "SCORE_DECAY_SHADOW"))

    final_rec = parse_final_recommendation(confidence_doc)
    # Stage 3C: accept both DO_NOT_PROMOTE (legacy upper) and do_not_promote (producer key)
    do_not_promote_items = list(final_rec.get("DO_NOT_PROMOTE") or []) + list(
        final_rec.get("do_not_promote") or []
    )
    for item in do_not_promote_items:
        item_s = _s(item).upper()
        if "DO_NOT_PROMOTE" in item_s:
            rules_applied.extend(apply_named_rule(scores, "DO_NOT_PROMOTE"))
            evidence.append(
                "live promotion lock noted (DO_NOT_PROMOTE) — PAPER scores unchanged; "
                "live_promotion_allowed=false"
            )
            break

    for rec in replay_doc.get("recommendations") or []:
        rec_u = _s(rec).upper()
        if rec_u in LIVE_PROMOTION_LOCK_RULES or rec_u == "DO_NOT_PROMOTE_TO_LIVE":
            rules_applied.extend(apply_named_rule(scores, "DO_NOT_PROMOTE_TO_LIVE"))
            evidence.append(
                "live promotion lock noted (DO_NOT_PROMOTE_TO_LIVE) — PAPER scores unchanged; "
                "live_promotion_allowed=false"
            )
            break

    if rules_applied:
        evidence.append(f"named confidence rules: {', '.join(sorted(set(rules_applied)))}")
    return sorted(set(rules_applied))


def apply_longitudinal_knowledge_bias(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    doc = ctx.get("longitudinal_knowledge") or {}
    rules_applied: list[str] = []
    for rule in doc.get("rules") or []:
        rid = _s(rule.get("rule_id")).upper()
        conf = _f(rule.get("confidence"), 0.5)
        delta = max(-4.0, min(4.0, (conf - 0.5) * 8.0))
        action = None
        for candidate in PAPER_ACTIONS:
            if candidate.replace("_PAPER", "") in rid or rid.endswith(candidate):
                action = candidate
                break
        if not action or abs(delta) < 0.01:
            continue
        scores[action] += delta
        rules_applied.append(rid)
    if rules_applied:
        evidence.append(f"longitudinal knowledge: {len(rules_applied)} rules")
    return {
        "source": str(LONGITUDINAL_KNOWLEDGE_JSON),
        "rules_applied": rules_applied,
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def apply_dpe_evaluator_bias(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    held: bool,
) -> dict[str, Any] | None:
    dpe = ctx.get("dpe_eval") or {}
    overall = dpe.get("overall") or {}
    winner = _s(overall.get("winner") or dpe.get("winner")).upper()
    if not winner:
        return None

    ppg_verdict = _s((ctx.get("ppg") or {}).get("portfolio_verdict"))
    high_risk = _s(ctx.get("policy_state")) == "HIGH_RISK" or "HIGH_RISK" in ppg_verdict
    deltas: dict[str, float] = {}

    if winner == "COLLABORATIVE":
        if high_risk:
            deltas = {
                "PROTECT_PAPER": 5.0,
                "HOLD_PAPER": 3.0,
                "SELL_PAPER": 2.0,
                "BUY_PAPER": -4.0,
            }
        else:
            deltas = {"PROTECT_PAPER": 3.0, "HOLD_PAPER": 2.0, "BUY_PAPER": -2.0}
    elif winner == "COMPETITIVE":
        deltas = {"BUY_PAPER": 3.0, "HOLD_PAPER": 2.0, "ROTATE_PAPER": 2.0}
        if high_risk and not held:
            deltas["BUY_PAPER"] = 1.0

    apply_score_deltas(scores, deltas, cap=6.0)
    evidence.append(f"DPE evaluator winner={winner} high_risk={high_risk}")
    return {
        "winner": winner,
        "high_risk_context": high_risk,
        "deltas_applied": deltas,
        "confidence_pct": overall.get("confidence_pct"),
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def apply_learning_evidence_bias(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> None:
    confidence_doc = ctx.get("confidence_evolution") or {}
    final_rec = parse_final_recommendation(confidence_doc)
    final_text = _s(confidence_doc.get("final_recommendation")).upper()
    if final_rec.get("DO_NOT_PROMOTE") or final_rec.get("do_not_promote") or "DO_NOT_PROMOTE" in final_text:
        apply_named_rule(scores, "DO_NOT_PROMOTE")
        evidence.append(
            "confidence evolution aggregate: DO_NOT_PROMOTE caution "
            "(PAPER scores unchanged; live_promotion_allowed=false)"
        )
    elif "INSUFFICIENT" in final_text:
        evidence.append("confidence evolution aggregate: insufficient promotion evidence (informational)")

    if ctx.get("pattern_discovery_present"):
        scores["ROTATE_PAPER"] += 3.0
        evidence.append("pattern discovery summary available")


def apply_adaptive_paper_weights(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    ticker: str,
) -> dict[str, Any] | None:
    from tae_adaptive_paper_weights import effective_weight_for

    weights_doc = ctx.get("paper_action_weights")
    if not weights_doc:
        return None
    applied: dict[str, Any] = {}
    for action in scores:
        detail = effective_weight_for(action, ticker.upper(), weights_doc)
        mult = _f(detail.get("effective_multiplier"), 1.0)
        if mult != 1.0:
            scores[action] *= mult
            applied[action] = detail
    if applied:
        best_action = max(scores, key=lambda a: scores[a])
        best = applied.get(best_action) or effective_weight_for(best_action, ticker.upper(), weights_doc)
        evidence.append(
            f"adaptive weight {best_action}={best.get('effective_multiplier')} "
            f"(base={best.get('base_weight')}, ticker_adj={best.get('ticker_adjustment'):+.4f})"
        )
        return best
    return None


def apply_horizon_action_bias(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    held: bool,
) -> dict[str, Any]:
    hz = build_horizon_context(ticker, ctx)
    short = trend_polarity(hz["short_term_trend_7d"])
    medium = trend_polarity(hz["monthly_trend"])
    long_t = trend_polarity(hz["long_term_trend"])
    alignment = _f(hz["horizon_alignment_score"])
    conflict = bool(hz["horizon_conflict_flag"])
    drawdown = _f(hz.get("short_drawdown_pct"))

    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper(), [])
    override = ticker in (ctx.get("top_growth") or []) or any(
        e.get("verdict") == "PROMISING" for e in exps
    )

    if not override and (short < 0 or medium < 0):
        scores["BUY_PAPER"] -= 28.0
        scores["SKIP_PAPER"] += 18.0
        evidence.append(f"horizon BUY gate: short/medium not aligned — {hz['horizon_reason'][:120]}")
    elif short > 0 and medium > 0:
        scores["BUY_PAPER"] += 10.0
        evidence.append("horizon supports BUY (short+medium positive)")

    if short < 0 and long_t > 0:
        scores["SELL_PAPER"] += 14.0
        scores["REDUCE_PAPER"] += 12.0
        evidence.append("horizon: short weakness vs positive long-term trend")

    if held and short <= 0 and long_t > 0 and not conflict:
        scores["HOLD_PAPER"] += 16.0
        evidence.append("horizon: long-term positive — treat short weakness as pullback")

    if drawdown >= 2.5 and long_t > 0:
        scores["PROTECT_PAPER"] += 18.0
        evidence.append(f"horizon: short volatility elevated (drawdown {drawdown:.1f}%) with intact long trend")

    if held and alignment >= 65.0:
        scores["HOLD_PAPER"] += 6.0
    elif alignment <= 35.0:
        scores["ROTATE_PAPER"] += 10.0
        scores["SELL_PAPER"] += 6.0

    if ticker in (ctx.get("top_growth") or []):
        held_alignments = [
            _f(build_horizon_context(t, ctx).get("horizon_alignment_score"))
            for t in (ctx.get("live_positions") or {})
            if t != ticker
        ]
        if held_alignments and alignment > min(held_alignments) + 8.0:
            scores["ROTATE_PAPER"] += 14.0
            evidence.append("horizon: candidate alignment beats weakest held position")

    if conflict:
        scores["PROTECT_PAPER"] += 8.0
        scores["SKIP_PAPER"] += 5.0

    return hz


def build_context() -> dict[str, Any]:
    gii = load_json(GII_JSON)
    ppg = load_json(PPG_JSON)
    appe = load_json(APPE_JSON)
    shadow = load_json(SHADOW_JSON)
    shadow_val = load_json(SHADOW_VALIDATION_JSON)
    dpe_eval = load_json(DPE_EVAL_JSON)
    dpe_adaptive = load_json(DPE_ADAPTIVE_JSON)
    accounting = load_json(ACCOUNTING_JSON)
    try:
        from research_core.accounting.accounting_snapshot import build_accounting_snapshot

        accounting = build_accounting_snapshot(".")
    except Exception:
        pass
    hypotheses = load_json(HYPOTHESES_JSON)
    experiments_doc = load_json(EXPERIMENTS_JSON)
    confidence_evolution = load_json(CONFIDENCE_JSON)
    decision_replay = load_json(REPLAY_JSON)
    adaptation_hints = load_json(ADAPTATION_HINTS_JSON)
    paper_action_weights = load_json(ADAPTIVE_WEIGHTS_JSON)
    knowledge_base = load_json(KNOWLEDGE_JSON)
    longitudinal_knowledge = load_json(LONGITUDINAL_KNOWLEDGE_JSON)
    profit_targets = load_json(PROFIT_TARGET_JSON)

    portfolio_rows = read_csv_rows(PORTFOLIO_CSV) if PORTFOLIO_CSV.is_file() else []
    signal_rows = read_csv_rows(SIGNALS_CSV) if SIGNALS_CSV.is_file() else []
    live_positions = open_positions_from_portfolio(portfolio_rows)
    signals = signals_by_ticker(signal_rows)

    gii_by = index_gii(gii)
    shadow_by = index_shadow(shadow)
    ppg_by = ppg_posture_by_ticker(ppg)
    experiments = (experiments_doc or {}).get("experiments") or []
    exp_by_ticker = experiments_by_ticker(experiments)

    top_growth = [
        _s(t.get("ticker")).upper()
        for t in sorted((gii or {}).get("tickers") or [], key=lambda x: _f(x.get("growth_score")), reverse=True)[:5]
    ]

    latest_appe = (appe or {}).get("latest_observation") or {}
    portfolio_gii = (gii or {}).get("portfolio") or {}
    horizon_ssot = load_horizon_ssot()
    from tae_historical_runtime_refresh import load_runtime_state, stale_source_paths

    hist_runtime = load_runtime_state()
    paper_portfolio = load_json(PAPER_PORTFOLIO_JSON) or {}
    if not isinstance(paper_portfolio, dict):
        paper_portfolio = {}
    from tae_paper_profit_trailing import (
        load_pce_by_ticker,
        sync_portfolio_profit_trailing,
        wire_paper_profit_protection,
    )

    wire_paper_profit_protection(
        paper_portfolio,
        pce_by=load_pce_by_ticker(),
        gii_by=gii_by,
    )
    trailing_events = sync_portfolio_profit_trailing(paper_portfolio)
    trailing_by = {
        str(ev.get("ticker") or "").upper(): ev
        for ev in trailing_events
        if str(ev.get("ticker") or "").strip()
    }
    paper_positions = load_paper_positions(paper_portfolio)
    # PAPER decisions must use PAPER cash. Live accounting cash_available can be ~0 while
    # paper_portfolio still has deployable cash — using live cash falsely triggers SKIP+15/BUY−10.
    if isinstance(paper_portfolio, dict) and "cash" in paper_portfolio:
        acct_cash_hint = _f(paper_portfolio.get("cash"))
    else:
        acct_cash_hint = _f((accounting or {}).get("cash_available")) or _f(
            (accounting or {}).get("account_value_corrected")
        ) * 0.1
    rule_lifecycle = load_json(RULE_LIFECYCLE_JSON)
    hard_risk_doc = load_json(HARD_RISK_JSON)
    conflict_doc = load_json(CONFLICTS_JSON)
    active_doc = load_json(ACTIVE_DECISIONS_JSON)
    active_by: dict[str, dict[str, Any]] = dict((active_doc or {}).get("tickers") or {})
    conflict_by: dict[str, dict[str, Any]] = {}
    for row in (conflict_doc or {}).get("tickers") or []:
        if isinstance(row, dict):
            t = _s(row.get("ticker")).upper()
            if t:
                conflict_by[t] = row
    hard_risk_by: dict[str, dict[str, Any]] = {}
    for row in (hard_risk_doc or {}).get("positions") or []:
        if isinstance(row, dict):
            t = _s(row.get("ticker")).upper()
            if t:
                hard_risk_by[t] = row
    for row in (hard_risk_doc or {}).get("breaches") or []:
        if isinstance(row, dict):
            t = _s(row.get("ticker")).upper()
            if t:
                hard_risk_by[t] = row

    recent_hard_stops_by_ticker = index_recent_hard_stops(load_jsonl(ORDERS_JSONL))

    ctx_out = {
        "gii": gii,
        "gii_by": gii_by,
        "portfolio_gii": portfolio_gii,
        "ppg": ppg,
        "ppg_by": ppg_by,
        "appe": appe,
        "policy_state": _s(latest_appe.get("policy_state")),
        "suggested_policy": _s(latest_appe.get("suggested_shadow_policy")),
        "shadow_by": shadow_by,
        "shadow_validation": shadow_val,
        "dpe_eval": dpe_eval,
        "dpe_adaptive": dpe_adaptive,
        "preferred_philosophy": _s((dpe_adaptive or {}).get("preferred_philosophy")),
        "accounting": accounting,
        "cash_hint": acct_cash_hint,
        "hypotheses": hypotheses,
        "experiments": experiments,
        "exp_by_ticker": exp_by_ticker,
        "confidence_evolution": confidence_evolution,
        "decision_replay": decision_replay,
        "adaptation_hints": adaptation_hints,
        "paper_action_weights": paper_action_weights,
        "knowledge_base": knowledge_base,
        "longitudinal_knowledge": longitudinal_knowledge,
        "profit_targets": profit_targets,
        "profit_target_by": index_profit_targets(profit_targets),
        "pattern_discovery_present": PATTERN_DISCOVERY_TXT.is_file(),
        "live_positions": live_positions,
        "paper_positions": paper_positions,
        "paper_portfolio": paper_portfolio,
        "profit_trailing_events": trailing_events,
        "profit_trailing_by_ticker": trailing_by,
        "paper_portfolio_trailing_dirty": any(bool(ev.get("changed")) for ev in trailing_events),
        "rule_lifecycle": rule_lifecycle,
        "hard_risk": hard_risk_doc,
        "hard_risk_by": hard_risk_by,
        "recent_hard_stops_by_ticker": recent_hard_stops_by_ticker,
        "conflict_resolution": conflict_doc,
        "conflict_resolution_by_ticker": conflict_by,
        "active_decisions": active_doc,
        "active_decisions_by_ticker": active_by,
        "signals": signals,
        "top_growth": top_growth,
        "horizon_ssot": horizon_ssot,
        "historical_runtime": hist_runtime,
        "stale_source_paths": sorted(stale_source_paths()),
        "sources_loaded": {
            "hypotheses": HYPOTHESES_JSON.is_file(),
            "experiments": EXPERIMENTS_JSON.is_file(),
            "gii": GII_JSON.is_file(),
            "ppg": PPG_JSON.is_file(),
            "appe": APPE_JSON.is_file(),
            "shadow": SHADOW_JSON.is_file(),
            "shadow_validation": SHADOW_VALIDATION_JSON.is_file(),
            "dpe_eval": DPE_EVAL_JSON.is_file(),
            "dpe_adaptive": DPE_ADAPTIVE_JSON.is_file(),
            "portfolio": PORTFOLIO_CSV.is_file(),
            "signals": SIGNALS_CSV.is_file(),
            "accounting": ACCOUNTING_JSON.is_file(),
            "historical_intelligence": HISTORICAL_INTELLIGENCE_CSV.is_file(),
            "strategic_intelligence": STRATEGIC_INTELLIGENCE_TXT.is_file(),
            "horizon_vote": HORIZON_VOTE_TXT.is_file(),
            "intraday_fade": INTRADAY_FADE_JSON.is_file(),
            "cross_validation": CROSS_VALIDATION_JSON.is_file(),
            "confidence_evolution": CONFIDENCE_JSON.is_file(),
            "longitudinal_adaptation_hints": ADAPTATION_HINTS_JSON.is_file(),
            "adaptive_paper_weights": ADAPTIVE_WEIGHTS_JSON.is_file(),
            "knowledge_base": KNOWLEDGE_JSON.is_file(),
            "longitudinal_knowledge": LONGITUDINAL_KNOWLEDGE_JSON.is_file(),
            "decision_replay": REPLAY_JSON.is_file(),
            "pattern_discovery": PATTERN_DISCOVERY_TXT.is_file(),
            "paper_portfolio": PAPER_PORTFOLIO_JSON.is_file(),
            "rule_lifecycle": RULE_LIFECYCLE_JSON.is_file(),
            "hard_risk": HARD_RISK_JSON.is_file(),
            "paper_orders": ORDERS_JSONL.is_file(),
            "conflict_resolution": CONFLICTS_JSON.is_file(),
            "active_decisions": ACTIVE_DECISIONS_JSON.is_file(),
            "profit_target_adapter": PROFIT_TARGET_JSON.is_file(),
        },
    }
    # Instrumentation only — prospective learning attribution (Sprint 2); no strategy change
    try:
        import hashlib as _hl

        _parts = []
        for _label, _doc in (
            ("w", paper_action_weights),
            ("k", longitudinal_knowledge),
            ("l", rule_lifecycle),
        ):
            if isinstance(_doc, dict) and _doc:
                _blob = json.dumps(
                    {
                        "generated_at": _doc.get("generated_at"),
                        "version": _doc.get("version"),
                        "schema": _doc.get("schema"),
                    },
                    sort_keys=True,
                    default=str,
                )
                _parts.append(f"{_label}:{_hl.sha256(_blob.encode()).hexdigest()[:16]}")
            else:
                _parts.append(f"{_label}:missing")
        ctx_out["learning_state_fingerprint"] = _hl.sha256("|".join(_parts).encode()).hexdigest()
    except Exception:
        ctx_out["learning_state_fingerprint"] = None
    return ctx_out


def ticker_universe(ctx: dict[str, Any]) -> list[str]:
    held = set(ctx.get("paper_positions") or {}) or set(ctx.get("live_positions") or {})
    signal_tickers = set(ctx.get("signals") or {})
    gii_tickers = set(ctx.get("gii_by") or {})
    top = set(ctx.get("top_growth") or [])
    universe = held | signal_tickers | (gii_tickers & top)
    return sorted(universe)


# paper_experiment_action → existing PDE action only (None = no safe executable mapping)
EXPERIMENT_ACTION_MAP: dict[str, str | None] = {
    "PAPER_TRAILING_PROTECT_TRIM": "REDUCE_PAPER",  # bounded trim via existing REDUCE path
    "PAPER_LIFECYCLE_TRIM": "REDUCE_PAPER",
    "PAPER_PORTFOLIO_PROTECT": "PROTECT_PAPER",
    "PAPER_REALLOCATION": "ROTATE_PAPER",  # held source required; no invented BUY
    "PAPER_ROTATION_REDUCE": "ROTATE_PAPER",
    "PAPER_LIFECYCLE_HOLD": "HOLD_PAPER",
    "PAPER_DPE_PHILOSOPHY_WEIGHT": None,  # portfolio policy / philosophy only
    "PAPER_MAINTENANCE_REFRESH": None,
    "PAPER_PATTERN_DISCOVERY": None,
    "PAPER_DECISION_REPLAY": None,
    "PAPER_CONFIDENCE_SHADOW": None,
}

CHALLENGER_MAX_ALLOCATION_USD = 400.0
CHALLENGER_MAX_TRIM_FRACTION = 0.10
CHALLENGER_ACTION_SCORE_DELTA = 32.0
MIN_REPRODUCIBLE_PROFIT_DELTA = 1.0
CAPITAL_CHALLENGERS_JSON = LTP_DIR / "capital_challengers.json"


def map_paper_experiment_action(paper_experiment_action: str) -> str | None:
    """Map LTB experiment action strings onto existing PDE actions only."""
    return EXPERIMENT_ACTION_MAP.get(_s(paper_experiment_action).upper())


def experiment_boost(ticker: str, ctx: dict[str, Any]) -> tuple[float, list[str]]:
    """Legacy aggregate boost kept for callers/tests; prefer apply_experiment_capital_evidence."""
    detail = apply_experiment_capital_evidence(
        ticker, {a: 0.0 for a in PAPER_ACTIONS}, [], ctx, apply_scores=False
    )
    return _f(detail.get("legacy_net_boost")), list(detail.get("notes") or [])


def classify_experiment_capital_eligibility(
    exp: dict[str, Any],
    *,
    ticker: str,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Classify one experiment for capital-allocation eligibility (no raw PROMISING auto-buy)."""
    ticker_u = ticker.upper()
    hid = _s(exp.get("hypothesis_id"))
    verdict = _s(exp.get("verdict")).upper()
    paper_action = _s(exp.get("paper_experiment_action")).upper()
    hyp_type = _s(exp.get("hypothesis_type")).upper()
    deltas = exp.get("deltas") or {}
    profit_delta = _f(deltas.get("expected_profit_delta_usd"))
    risk_delta = _f(deltas.get("risk_delta"))
    cap_eff_delta = _f(deltas.get("capital_efficiency_delta"))
    confidence = _f(exp.get("confidence"))
    scoring = _s(exp.get("scoring_method"), "unknown")
    mapped = map_paper_experiment_action(paper_action)

    if ticker_u in {"_PORTFOLIO", "PORTFOLIO", ""} or hyp_type == "DPE_PHILOSOPHY" or paper_action == "PAPER_DPE_PHILOSOPHY_WEIGHT":
        return {
            "experiment_id": hid,
            "experiment_verdict": verdict,
            "hypothesis_type": hyp_type,
            "paper_experiment_action": paper_action,
            "experiment_action_mapping": None,
            "capital_candidate_status": "PORTFOLIO_POLICY_CANDIDATE",
            "allocation_authorized": False,
            "allocation_block_reason": "philosophy/policy only — no direct trade mapping",
            "proposed_allocation_usd": 0.0,
            "expected_profit_delta": profit_delta,
            "expected_risk_delta": risk_delta,
            "capital_efficiency_delta": cap_eff_delta,
            "evidence_quality": "SIMULATED",
            "sample_size": int(
                _f((((ctx.get("rule_lifecycle") or {}).get("rules") or {}).get(hid) or {}).get("total_decisions"))
            ),
            "confidence": confidence,
            "scoring_method": scoring,
            "held": False,
            "hard_block": False,
            "pre_entry_risk_level": None,
            "rollback_condition": "n/a — policy bias only",
            "challenger_lifecycle": "PORTFOLIO_POLICY_CANDIDATE",
        }

    held = paper_position_held(ticker_u, ctx)
    pre_entry = evaluate_pre_entry_hard_risk_compatibility(ticker_u, ctx, held=held)
    lifecycle = ((ctx.get("rule_lifecycle") or {}).get("rules") or {}).get(hid) or {}
    sample_size = int(_f(lifecycle.get("total_decisions")))
    pos = (ctx.get("paper_positions") or {}).get(ticker_u) or {}
    shares = _f(pos.get("shares"))
    mark = _f(pos.get("current_price") or pos.get("avg_price"))
    cash = _f(((ctx.get("paper_portfolio") or {}).get("cash")) or ((ctx.get("accounting") or {}).get("cash_available")))
    signal = (ctx.get("signals") or {}).get(ticker_u) or {}
    signal_name = _s(signal.get("signal")).upper()
    signal_score = _f(signal.get("score"))

    block_reasons: list[str] = []
    status = "NOT_EXECUTABLE"
    allocation_authorized = False
    proposed_allocation_usd = 0.0
    rollback_condition = "realized_pnl < 0 OR drawdown increase without profit capture after next cycle"

    if verdict != "PROMISING":
        status = "INSUFFICIENT_EVIDENCE"
        block_reasons.append(f"verdict={verdict or 'NONE'}")
    elif paper_action in {"PAPER_DPE_PHILOSOPHY_WEIGHT"} or hyp_type == "DPE_PHILOSOPHY" or mapped is None and paper_action.startswith("PAPER_DPE"):
        status = "PORTFOLIO_POLICY_CANDIDATE"
        block_reasons.append("philosophy/policy only — no direct trade mapping")
    elif mapped is None:
        status = "NOT_EXECUTABLE"
        block_reasons.append(f"no safe PDE mapping for {paper_action or 'EMPTY'}")
    elif profit_delta < MIN_REPRODUCIBLE_PROFIT_DELTA:
        status = "INSUFFICIENT_EVIDENCE"
        block_reasons.append(f"profit_delta={profit_delta} below minimum")
    elif scoring and "simulation" in scoring and confidence < 0.45:
        status = "INSUFFICIENT_EVIDENCE"
        block_reasons.append("low-confidence simulation evidence")
    elif mapped in {"BUY_PAPER"} and pre_entry.get("hard_block"):
        status = "NOT_EXECUTABLE"
        block_reasons.append("hard_risk_incompatible_buy")
        block_reasons.extend([_s(r) for r in (pre_entry.get("reasons") or [])[:3]])
    elif mapped in {"BUY_PAPER", "ROTATE_PAPER"} and not held and mapped == "ROTATE_PAPER":
        # REALLOCATION without held source cannot rotate; BUY not invented from PROMISING alone
        if pre_entry.get("hard_block"):
            status = "NOT_EXECUTABLE"
            block_reasons.append("hard_risk_blocks_new_allocation")
            block_reasons.extend([_s(r) for r in (pre_entry.get("reasons") or [])[:3]])
        elif signal_score < 90.0 or "BUY" not in signal_name:
            status = "NOT_EXECUTABLE"
            block_reasons.append("reallocation lacks held source and strong BUY signal")
        elif cash < 100.0:
            status = "NOT_EXECUTABLE"
            block_reasons.append("insufficient cash for challenger allocation")
        else:
            # Still no invented BUY mapping from PAPER_REALLOCATION when not held
            status = "NOT_EXECUTABLE"
            block_reasons.append("PAPER_REALLOCATION requires held source for ROTATE; no invented BUY")
    elif mapped in {"REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER", "SELL_PAPER"} and not held:
        status = "NOT_EXECUTABLE"
        block_reasons.append("no open paper position for protection/trim/rotate")
    elif mapped == "HOLD_PAPER":
        status = "PROTECTION_ONLY_CANDIDATE"
        block_reasons.append("HOLD mapping is non-capital-moving")
    elif mapped == "PROTECT_PAPER" and shares > 0 and mark <= 0:
        status = "INSUFFICIENT_EVIDENCE"
        block_reasons.append("invalid mark price")
    elif mapped in {"REDUCE_PAPER", "PROTECT_PAPER"} and shares > 0:
        # Prefer REDUCE for capital-moving challenger; PROTECT alone may be bookkeeping
        if mapped == "PROTECT_PAPER":
            status = "PROTECTION_ONLY_CANDIDATE"
            block_reasons.append("PROTECT mapping may be protect-mode only unless risk trim triggers")
        else:
            status = "ACTIONABLE_CAPITAL_CANDIDATE"
            allocation_authorized = True
            proposed_allocation_usd = round(
                min(CHALLENGER_MAX_ALLOCATION_USD, max(0.0, shares * mark * CHALLENGER_MAX_TRIM_FRACTION)),
                2,
            )
            if proposed_allocation_usd < 1.0:
                status = "INSUFFICIENT_EVIDENCE"
                allocation_authorized = False
                block_reasons.append("trim notional below $1")
            else:
                block_reasons = []
    elif mapped == "ROTATE_PAPER" and held:
        if pre_entry.get("hard_block") and _s(pre_entry.get("risk_level")).upper() == "CRITICAL":
            # held rotate/sell still allowed under hard risk SELL discipline; mark as actionable sell-side
            status = "ACTIONABLE_CAPITAL_CANDIDATE"
            allocation_authorized = True
            proposed_allocation_usd = round(
                min(CHALLENGER_MAX_ALLOCATION_USD, max(0.0, shares * mark * CHALLENGER_MAX_TRIM_FRACTION)),
                2,
            )
            mapped = "REDUCE_PAPER"  # safer existing path than full rotate under CRITICAL
            block_reasons.append("CRITICAL held exposure → bounded REDUCE challenger instead of full ROTATE")
        else:
            status = "ACTIONABLE_CAPITAL_CANDIDATE"
            allocation_authorized = True
            proposed_allocation_usd = round(min(CHALLENGER_MAX_ALLOCATION_USD, max(0.0, shares * mark * 0.2)), 2)
    else:
        status = "NOT_EXECUTABLE"
        block_reasons.append("eligibility gates not satisfied")

    evidence_quality = "SIMULATED"
    if sample_size >= 5 and _f(lifecycle.get("net_pnl_impact")) != 0.0:
        evidence_quality = "REALIZED_SUPPORTED"
    elif sample_size >= 1:
        evidence_quality = "PARTIAL_REALIZED"

    return {
        "experiment_id": hid,
        "experiment_verdict": verdict,
        "hypothesis_type": hyp_type,
        "paper_experiment_action": paper_action,
        "experiment_action_mapping": mapped,
        "capital_candidate_status": status,
        "allocation_authorized": allocation_authorized,
        "allocation_block_reason": "; ".join(block_reasons) if block_reasons else None,
        "proposed_allocation_usd": proposed_allocation_usd,
        "expected_profit_delta": profit_delta,
        "expected_risk_delta": risk_delta,
        "capital_efficiency_delta": cap_eff_delta,
        "evidence_quality": evidence_quality,
        "sample_size": sample_size,
        "confidence": confidence,
        "scoring_method": scoring,
        "held": held,
        "hard_block": bool(pre_entry.get("hard_block")),
        "pre_entry_risk_level": pre_entry.get("risk_level"),
        "rollback_condition": rollback_condition,
        "challenger_lifecycle": "PROMISING→CAPITAL_CHALLENGER" if allocation_authorized else status,
    }


def apply_experiment_capital_evidence(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    apply_scores: bool = True,
) -> dict[str, Any]:
    """Apply ticker/action-specific experiment evidence. No uniform PROMISING boost."""
    ticker_u = ticker.upper()
    ticker_exps = list((ctx.get("exp_by_ticker") or {}).get(ticker_u) or [])
    portfolio_exps = list((ctx.get("exp_by_ticker") or {}).get("_PORTFOLIO") or [])
    notes: list[str] = []
    evaluations: list[dict[str, Any]] = []
    score_deltas: dict[str, float] = {a: 0.0 for a in PAPER_ACTIONS}
    authorized: list[dict[str, Any]] = []
    legacy_net = 0.0

    # Ticker-local experiments drive capital challenger scoring
    for exp in ticker_exps:
        row = classify_experiment_capital_eligibility(exp, ticker=ticker_u, ctx=ctx)
        evaluations.append(row)
        verdict = row["experiment_verdict"]
        mapped = row.get("experiment_action_mapping")
        notes.append(f"experiment {row['experiment_id']} {verdict} → {row['capital_candidate_status']}")
        if mapped:
            notes.append(f"map {row['paper_experiment_action']}→{mapped}")

        if row["capital_candidate_status"] == "ACTIONABLE_CAPITAL_CANDIDATE" and mapped:
            delta = CHALLENGER_ACTION_SCORE_DELTA
            if row["expected_profit_delta"] >= 10.0:
                delta += 8.0
            if row["evidence_quality"] == "REALIZED_SUPPORTED":
                delta += 6.0
            score_deltas[mapped] = score_deltas.get(mapped, 0.0) + delta
            # Mild relative lift vs competing hold when trim authorized
            if mapped == "REDUCE_PAPER":
                score_deltas["HOLD_PAPER"] = score_deltas.get("HOLD_PAPER", 0.0) - 10.0
                score_deltas["PROTECT_PAPER"] = score_deltas.get("PROTECT_PAPER", 0.0) + 6.0
            authorized.append(row)
            legacy_net += 12.0
        elif row["capital_candidate_status"] == "PROTECTION_ONLY_CANDIDATE" and mapped:
            score_deltas[mapped] = score_deltas.get(mapped, 0.0) + 14.0
            legacy_net += 5.0
        elif verdict == "REJECT":
            if mapped:
                score_deltas[mapped] = score_deltas.get(mapped, 0.0) - 20.0
            legacy_net -= 20.0
        elif verdict == "CONTINUE_TESTING" and mapped:
            score_deltas[mapped] = score_deltas.get(mapped, 0.0) + 6.0
            legacy_net += 5.0

    # Portfolio-policy experiments: philosophy bias only (never invent trades)
    for exp in portfolio_exps:
        verdict = _s(exp.get("verdict")).upper()
        paper_action = _s(exp.get("paper_experiment_action")).upper()
        hid = _s(exp.get("hypothesis_id"))
        if paper_action == "PAPER_DPE_PHILOSOPHY_WEIGHT" or _s(exp.get("hypothesis_type")).upper() == "DPE_PHILOSOPHY":
            row = {
                "experiment_id": hid,
                "experiment_verdict": verdict,
                "paper_experiment_action": paper_action,
                "experiment_action_mapping": None,
                "capital_candidate_status": "PORTFOLIO_POLICY_CANDIDATE",
                "allocation_authorized": False,
                "allocation_block_reason": "DPE philosophy — collaborative/competitive weight bias only",
                "proposed_allocation_usd": 0.0,
                "expected_profit_delta": _f((exp.get("deltas") or {}).get("expected_profit_delta_usd")),
                "expected_risk_delta": _f((exp.get("deltas") or {}).get("risk_delta")),
                "evidence_quality": "SIMULATED",
                "sample_size": 0,
            }
            evaluations.append(row)
            notes.append(f"experiment {hid} PORTFOLIO_POLICY_CANDIDATE")
            if verdict == "PROMISING":
                preferred = _s(ctx.get("preferred_philosophy")).upper()
                if preferred == "COLLABORATIVE":
                    score_deltas["PROTECT_PAPER"] += 5.0
                    score_deltas["HOLD_PAPER"] += 3.0
                elif preferred == "COMPETITIVE":
                    score_deltas["ROTATE_PAPER"] += 4.0
                legacy_net += 4.0
        # Do NOT apply uniform NEEDS_MORE_DATA penalties from portfolio maintenance hyps

    primary: dict[str, Any] = {}
    if authorized:
        primary = authorized[0]
    else:
        ticker_evals = [
            e
            for e in evaluations
            if e.get("capital_candidate_status") not in {"PORTFOLIO_POLICY_CANDIDATE"}
        ]
        primary = ticker_evals[0] if ticker_evals else {}

    experiment_score_delta = {
        a: round(v, 2) for a, v in score_deltas.items() if abs(v) >= 0.01
    }

    if apply_scores:
        for action, delta in score_deltas.items():
            if abs(delta) >= 0.01 and action in scores:
                scores[action] += delta
        if experiment_score_delta:
            evidence.append(
                "experiment capital evidence: "
                + ", ".join(f"{a}{d:+.1f}" for a, d in sorted(experiment_score_delta.items()))
            )
        evidence.extend(notes[:6])

    return {
        "experiment_id": primary.get("experiment_id"),
        "experiment_verdict": primary.get("experiment_verdict"),
        "capital_candidate_status": primary.get("capital_candidate_status") or "NOT_EXECUTABLE",
        "experiment_action_mapping": primary.get("experiment_action_mapping"),
        "experiment_score_delta": experiment_score_delta,
        "proposed_allocation_usd": primary.get("proposed_allocation_usd") or 0.0,
        "expected_profit_delta": primary.get("expected_profit_delta") or 0.0,
        "expected_risk_delta": primary.get("expected_risk_delta") or 0.0,
        "evidence_quality": primary.get("evidence_quality") or "NONE",
        "allocation_authorized": bool(primary.get("allocation_authorized")),
        "allocation_block_reason": primary.get("allocation_block_reason"),
        "evaluations": evaluations,
        "authorized_challengers": authorized,
        "notes": notes,
        "legacy_net_boost": legacy_net,
        "rollback_condition": primary.get("rollback_condition"),
    }


def estimate_deltas(ticker: str, action: str, ctx: dict[str, Any]) -> dict[str, float]:
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    shadow = (ctx.get("shadow_by") or {}).get(ticker.upper()) or {}
    missed = _f(gii.get("missed_usd") or shadow.get("missed_opportunity_usd"))
    cap_eff = _f(gii.get("capital_efficiency"))
    collapse = _f(gii.get("collapse_probability"))

    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper()) or []
    if exps and exps[0].get("deltas"):
        d = exps[0]["deltas"]
        return {
            "expected_profit_delta": _f(d.get("expected_profit_delta_usd")),
            "expected_risk_delta": _f(d.get("risk_delta")),
            "capital_efficiency_delta": _f(d.get("capital_efficiency_delta")),
        }

    if action == "BUY_PAPER":
        return {"expected_profit_delta": 15.0, "expected_risk_delta": 0.05, "capital_efficiency_delta": 5.0}
    if action == "SELL_PAPER":
        return {
            "expected_profit_delta": missed * 0.1,
            "expected_risk_delta": -collapse * 0.2,
            "capital_efficiency_delta": max(0.0, 50.0 - cap_eff) * 0.1,
        }
    if action == "REDUCE_PAPER":
        return {
            "expected_profit_delta": missed * 0.2,
            "expected_risk_delta": -0.12,
            "capital_efficiency_delta": 2.0,
        }
    if action == "PROTECT_PAPER":
        return {
            "expected_profit_delta": missed * 0.25,
            "expected_risk_delta": -0.15,
            "capital_efficiency_delta": -1.0,
        }
    if action == "ROTATE_PAPER":
        return {
            "expected_profit_delta": missed * 0.18,
            "expected_risk_delta": -0.06,
            "capital_efficiency_delta": max(0.0, 45.0 - cap_eff) * 0.08,
        }
    if action == "HOLD_PAPER":
        return {
            "expected_profit_delta": missed * 0.08,
            "expected_risk_delta": 0.03,
            "capital_efficiency_delta": 0.0,
        }
    return {"expected_profit_delta": 0.0, "expected_risk_delta": 0.0, "capital_efficiency_delta": 0.0}


def hypotheses_for_ticker(ticker: str, hypotheses_doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    ticker = ticker.upper()
    matched: list[dict[str, Any]] = []
    for hyp in (hypotheses_doc or {}).get("hypotheses") or []:
        tickers = [_s(t).upper() for t in (hyp.get("affected_tickers") or [])]
        if not tickers or ticker in tickers:
            matched.append(hyp)
    return matched


def index_profit_targets(doc: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    by: dict[str, dict[str, Any]] = {}
    for row in (doc or {}).get("tickers") or []:
        if isinstance(row, dict):
            ticker = _s(row.get("ticker")).upper()
            if ticker:
                by[ticker] = row
    return by


def apply_profit_target_adapter_bias(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    held: bool,
) -> dict[str, Any]:
    """Apply existing Profit Target Adapter outputs to held-position exit scoring only."""
    if not held:
        return {"applied": False, "reason": "not_held"}

    row = (ctx.get("profit_target_by") or {}).get(ticker.upper())
    if not row:
        return {"applied": False, "reason": "no_profit_target_row"}

    confidence = _f(row.get("target_confidence"), 0.5)
    if confidence < 0.35:
        return {"applied": False, "reason": "low_target_confidence", "target_confidence": confidence}

    scale = max(0.5, min(1.0, confidence))
    urgency = _s(row.get("exit_window_urgency"), "MEDIUM").upper()
    strategy = _s(row.get("recommended_shadow_strategy"))
    partial_size = _f(row.get("suggested_partial_size_pct"))
    partial_tp = row.get("dynamic_partial_tp_pct")
    recovery_only = bool(row.get("recovery_exit_management_only"))

    deltas_applied: dict[str, float] = {}

    def _apply(action: str, raw: float) -> None:
        if action not in scores or raw == 0.0:
            return
        bounded = max(-MAX_PROFIT_TARGET_SCORE_DELTA, min(MAX_PROFIT_TARGET_SCORE_DELTA, raw * scale))
        scores[action] += bounded
        deltas_applied[action] = round(deltas_applied.get(action, 0.0) + bounded, 2)

    if recovery_only:
        for action, raw in {
            "REDUCE_PAPER": 20.0,
            "PROTECT_PAPER": 15.0,
            "HOLD_PAPER": -15.0,
        }.items():
            _apply(action, raw)
    else:
        for action, raw in (PROFIT_TARGET_URGENCY_DELTAS.get(urgency) or {}).items():
            _apply(action, raw)
        for action, raw in (PROFIT_TARGET_STRATEGY_DELTAS.get(strategy) or {}).items():
            _apply(action, raw)
        if partial_size >= 33.0:
            _apply("REDUCE_PAPER", 8.0)
        if partial_size >= 50.0:
            _apply("REDUCE_PAPER", 12.0)

        paper_pos = (ctx.get("paper_positions") or {}).get(ticker.upper()) or {}
        current_pct = _f(paper_pos.get("current_pct") or paper_pos.get("unrealized_pct"))
        if partial_tp is not None and current_pct >= _f(partial_tp):
            _apply("PROTECT_PAPER", 12.0)
            _apply("REDUCE_PAPER", 8.0)
            evidence.append(
                f"profit target: partial TP threshold {partial_tp}% reached at {current_pct:.1f}%"
            )

    if deltas_applied:
        evidence.append(
            f"profit target adapter: urgency={urgency} strategy={strategy} "
            f"partial_size={partial_size:.0f}% conf={confidence:.2f}"
        )

    return {
        "applied": bool(deltas_applied),
        "ticker": ticker.upper(),
        "exit_window_urgency": urgency,
        "recommended_shadow_strategy": strategy,
        "suggested_partial_size_pct": partial_size,
        "dynamic_partial_tp_pct": partial_tp,
        "target_confidence": confidence,
        "recovery_exit_management_only": recovery_only,
        "score_deltas": deltas_applied,
        "source": str(PROFIT_TARGET_JSON),
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def protection_validation_bias(
    ticker: str,
    validation: dict[str, Any] | None,
) -> tuple[float, float, float, bool]:
    """Return (protect_boost, reduce_boost, sell_penalty, gates_passed)."""
    if not validation:
        return 0.0, 0.0, 0.0, False
    gates = validation.get("gates") or {}
    gates_passed = bool(gates.get("gates_passed"))
    protect_boost = 15.0 if gates_passed else -5.0
    reduce_boost = 8.0 if gates_passed else 0.0
    sell_penalty = 0.0

    best = validation.get("best_strategy") or {}
    best_id = _s(best.get("strategy_id")).lower()
    if "trailing" in best_id:
        protect_boost += 12.0
    if "partial" in best_id or "sell" in best_id:
        reduce_boost += 10.0
    if _f(best.get("delta_vs_hold_total")) <= 0:
        sell_penalty += 6.0

    for row in validation.get("ticker_breakdown") or []:
        if _s(row.get("ticker")).upper() == ticker.upper():
            delta = _f(row.get("delta_vs_hold"))
            if delta == 0.0 and row.get("best_strategy_value") is not None and row.get("hold_value") is not None:
                delta = _f(row.get("best_strategy_value")) - _f(row.get("hold_value"))
            if delta > 0:
                protect_boost += 8.0
            elif delta < 0:
                sell_penalty += 5.0
    return protect_boost, reduce_boost, sell_penalty, gates_passed


def apply_hypothesis_rules(
    ticker: str,
    action: str,
    confidence: float,
    ctx: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], str]:
    """
    Apply hypothesis rules without allowing unrelated research experiments
    to veto a canonical PAPER decision.

    Canonical BUY_PAPER is owned by PDE scoring plus the existing market,
    data, Hard Risk, capital and execution gates. Portfolio-policy,
    maintenance and unmapped experiments remain observational.
    """
    hyps = hypotheses_for_ticker(ticker, ctx.get("hypotheses"))
    applied: list[dict[str, Any]] = []
    for hyp in hyps:
        applied.append(
            {
                "hypothesis_id": hyp.get("hypothesis_id"),
                "validation_rule": hyp.get("validation_rule"),
                "rejection_rule": hyp.get("rejection_rule"),
                "hypothesis_type": hyp.get("hypothesis_type"),
            }
        )

    ticker_exps = list(
        (ctx.get("exp_by_ticker") or {}).get(ticker.upper(), []) or []
    )

    # A rejected experiment may veto only the executable action to which
    # that specific experiment maps. Unmapped research/policy experiments
    # must never turn a canonical BUY into SKIP.
    rejected_for_action = []
    promising_for_action = []

    for exp in ticker_exps:
        mapped = map_paper_experiment_action(
            _s(exp.get("paper_experiment_action")).upper()
        )
        verdict = _s(exp.get("verdict")).upper()

        if mapped == action and verdict == "REJECT":
            rejected_for_action.append(exp)

        if mapped == action and verdict == "PROMISING":
            promising_for_action.append(exp)

    if rejected_for_action:
        ids = ",".join(
            _s(exp.get("hypothesis_id")) for exp in rejected_for_action
        )
        return (
            "SKIP_PAPER",
            applied,
            f"hypothesis rejection_rule: action-specific experiment REJECT ({ids})",
        )

    # ROTATE and PROTECT may still depend on their mapped experimental
    # evidence. Canonical BUY_PAPER does not require a PROMISING experiment:
    # it has already passed PDE scoring and the common safety gates.
    if (
        action == "ROTATE_PAPER"
        and not promising_for_action
        and confidence < 0.5
    ):
        return (
            "SKIP_PAPER",
            applied,
            "hypothesis rejection_rule: no PROMISING validation for ROTATE_PAPER",
        )

    if (
        action == "PROTECT_PAPER"
        and hyps
        and not promising_for_action
        and confidence < 0.42
    ):
        return (
            "SKIP_PAPER",
            applied,
            "hypothesis rejection_rule: protect action lacks mapped validation evidence",
        )

    return action, applied, ""


def compute_risk_score(ticker: str, ctx: dict[str, Any]) -> float:
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    ppg_row = (ctx.get("ppg_by") or {}).get(ticker.upper()) or {}
    posture = _s(ppg_row.get("governor_posture"))
    score = _f(gii.get("collapse_probability")) * 50.0
    score += _f(gii.get("opportunity_score")) * 0.3
    if posture in {"PROTECT_SHADOW", "TRAIL_SHADOW"}:
        score += 20.0
    elif posture == "WATCH_SHADOW":
        score += 10.0
    if _s(gii.get("lifecycle_stage")) in WEAK_LIFECYCLE:
        score += 25.0
    return round(min(100.0, max(0.0, score)), 2)


def score_actions_for_ticker(
    ticker: str, ctx: dict[str, Any]
) -> tuple[str, dict[str, float], list[str], list, bool, dict, dict, dict, dict, dict]:
    ticker = ticker.upper()
    held = paper_position_held(ticker, ctx)
    paper_pos = (ctx.get("paper_positions") or {}).get(ticker) or {}
    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    shadow = (ctx.get("shadow_by") or {}).get(ticker) or {}
    ppg_row = (ctx.get("ppg_by") or {}).get(ticker) or {}
    signal = (ctx.get("signals") or {}).get(ticker) or {}

    strategy = _s(gii.get("recommended_shadow_strategy"))
    lifecycle = _s(gii.get("lifecycle_stage"))
    cap_eff = _f(gii.get("capital_efficiency"))
    growth_score = _f(gii.get("growth_score"))
    missed = _f(gii.get("missed_usd") or shadow.get("missed_opportunity_usd"))
    current_pct = _f(paper_pos.get("unrealized_pct") or paper_pos.get("current_pct"))
    if current_pct == 0.0:
        current_pct = _f(gii.get("current_pct") or shadow.get("current_pct"))
    opp_cat = _s(gii.get("opportunity_category"))
    posture = _s(ppg_row.get("governor_posture"))
    protect_signal = _s(shadow.get("protection_signal"))
    signal_name = _s(signal.get("signal")).upper()
    signal_score = _f(signal.get("score"))

    policy_state = _s(ctx.get("policy_state"))
    suggested_policy = _s(ctx.get("suggested_policy")).upper()
    preferred = _s(ctx.get("preferred_philosophy"))

    scores: dict[str, float] = {a: 0.0 for a in PAPER_ACTIONS}
    evidence: list[str] = []

    hard_risk_discipline = enforce_hard_risk_discipline(ticker, scores, evidence, ctx)
    if hard_risk_discipline.get("override"):
        hz = build_horizon_context(ticker, ctx)
        position_discipline = enforce_position_discipline(ticker, scores, evidence, ctx)
        loss_discipline = {"evaluated": True, "superseded_by": "hard_risk_discipline"}
        consumption = {
            "hard_risk_discipline": hard_risk_discipline,
            "profit_trailing": {"evaluated": True, "superseded_by": "hard_risk_discipline"},
            "rule_lifecycle_evidence": None,
        }
        return (
            "SELL_PAPER",
            scores,
            evidence,
            [],
            False,
            hz,
            consumption,
            position_discipline,
            loss_discipline,
            hard_risk_discipline,
        )

    from tae_paper_profit_trailing import (
        REASON_EXIT,
        REASON_SOFT_SUPPRESSED,
        suppress_soft_exit_if_trailing_active,
        trailing_active_on_position,
    )

    trailing_ev = dict((ctx.get("profit_trailing_by_ticker") or {}).get(ticker) or {})
    if not trailing_ev and held:
        # Fixture/unit path: evaluate transition against in-memory position.
        from tae_paper_profit_trailing import apply_profit_trailing_transition, is_valid_trailing_mark

        mark = paper_pos.get("current_price") or paper_pos.get("mark_price")
        if is_valid_trailing_mark(mark, pos=paper_pos):
            trailing_ev = apply_profit_trailing_transition(
                paper_pos,
                ticker=ticker,
                mark=float(mark),
                average_cost=_f(paper_pos.get("avg_price")),
            )
            (ctx.setdefault("profit_trailing_by_ticker", {}))[ticker] = trailing_ev
            ctx["paper_portfolio_trailing_dirty"] = True

    if trailing_ev.get("exit_ready"):
        for action_name in scores:
            scores[action_name] = 0.0
        scores["SELL_PAPER"] = 100.0
        evidence.append(
            f"{REASON_EXIT}: mark={trailing_ev.get('mark')} peak={trailing_ev.get('peak_price')} "
            f"drawdown={trailing_ev.get('drawdown_from_peak')} "
            f"cycle={trailing_ev.get('position_cycle_id') or paper_pos.get('position_cycle_id')}"
        )
        hz = build_horizon_context(ticker, ctx)
        position_discipline = enforce_position_discipline(ticker, scores, evidence, ctx)
        loss_discipline = {"evaluated": True, "superseded_by": "profit_trailing_exit"}
        consumption = {
            "hard_risk_discipline": hard_risk_discipline,
            "profit_trailing": trailing_ev,
            "rule_lifecycle_evidence": None,
        }
        return (
            "SELL_PAPER",
            scores,
            evidence,
            [],
            False,
            hz,
            consumption,
            position_discipline,
            loss_discipline,
            hard_risk_discipline,
        )

    trailing_owns = bool(trailing_ev.get("trailing_active") or trailing_active_on_position(paper_pos))
    if trailing_ev.get("reason_code"):
        evidence.append(f"profit trailing: {trailing_ev.get('reason_code')}")

    if not gii and not shadow and not signal:
        scores["SKIP_PAPER"] = 80.0
        evidence.append("insufficient intelligence for ticker")
        hz = build_horizon_context(ticker, ctx)
        named_rules: list[str] = []
        knowledge_evidence: dict[str, Any] | None = None
        longitudinal_knowledge_evidence: dict[str, Any] | None = None
        dpe_evaluator_evidence: dict[str, Any] | None = None
        if ablation_component_enabled(ctx, "named_confidence"):
            named_rules = apply_named_confidence_rules(scores, evidence, ctx)
        if ablation_component_enabled(ctx, "knowledge_base"):
            knowledge_evidence = apply_knowledge_base_bias(scores, evidence, ctx, ticker)
        if ablation_component_enabled(ctx, "longitudinal"):
            longitudinal_knowledge_evidence = apply_longitudinal_knowledge_bias(scores, evidence, ctx)
        if ablation_component_enabled(ctx, "dpe_evaluator"):
            dpe_evaluator_evidence = apply_dpe_evaluator_bias(scores, evidence, ctx, held=held)
        consumption = {
            "knowledge_evidence": knowledge_evidence,
            "longitudinal_knowledge_evidence": longitudinal_knowledge_evidence,
            "dpe_evaluator_evidence": dpe_evaluator_evidence,
            "adaptive_weight_evidence": None,
            "named_confidence_rules": named_rules,
            "ablation_learning_enabled": ablation_learning_enabled(ctx),
        }
        rules_applied = collect_rules_applied(consumption, named_rules)
        if ablation_component_enabled(ctx, "rule_lifecycle"):
            lifecycle_evidence = apply_rule_lifecycle_bias(scores, evidence, ctx, rules_applied)
        else:
            lifecycle_evidence = {
                "rules_applied": rules_applied,
                "rule_states": {},
                "adjustments": [],
                "mode": MODE,
                "live_promotion_allowed": False,
                "ablation_skipped": True,
            }
        position_discipline = enforce_position_discipline(ticker, scores, evidence, ctx)
        loss_discipline = enforce_loss_discipline(
            ticker, scores, evidence, ctx, rule_states=lifecycle_evidence.get("rule_states")
        )
        consumption["rule_lifecycle_evidence"] = lifecycle_evidence
        consumption["hard_risk_discipline"] = hard_risk_discipline
        consumption["profit_trailing"] = trailing_ev
        best = max(scores, key=lambda a: scores[a])
        if scores[best] < 18.0:
            best = "SKIP_PAPER"
        best, soft_reason = suppress_soft_exit_if_trailing_active(
            best, trailing_active=trailing_owns, exit_ready=False
        )
        if soft_reason:
            evidence.append(f"{soft_reason}: soft action suppressed while profit trailing active")
            scores["HOLD_PAPER"] = max(scores.get("HOLD_PAPER", 0.0), 100.0)
        return (
            best,
            scores,
            evidence,
            [],
            False,
            hz,
            consumption,
            position_discipline,
            loss_discipline,
            hard_risk_discipline,
        )

    if held:
        if posture in {"PROTECT_SHADOW"} and current_pct > 2.0 and missed >= 15.0:
            scores["REDUCE_PAPER"] += 45.0
            evidence.append(f"PPG posture={posture} missed=${missed:.2f}")
        if strategy == "REDUCE_EXPOSURE_SHADOW" or (cap_eff < 25.0 and posture not in {"PROTECT_SHADOW"}):
            scores["SELL_PAPER"] += 35.0 + max(0.0, 30.0 - cap_eff) * 0.5
            evidence.append(f"low capital_efficiency={cap_eff:.1f}")
        if lifecycle in WEAK_LIFECYCLE or _f(gii.get("collapse_probability")) > 0.55:
            scores["SELL_PAPER"] += 30.0
            evidence.append(f"weak lifecycle={lifecycle}")
            if current_pct <= -5.0:
                scores["SELL_PAPER"] += 15.0
                scores["PROTECT_PAPER"] = max(0.0, scores.get("PROTECT_PAPER", 0.0) - 15.0)
                evidence.append(f"weak lifecycle + {current_pct:.1f}% loss favors SELL over PROTECT")
        if opp_cat in {"CAPITAL_LOCKED", "CASH_CONSTRAINT"} and cap_eff < 45.0:
            scores["ROTATE_PAPER"] += 38.0
            evidence.append(f"opportunity_category={opp_cat}")
        if posture in {"TRAIL_SHADOW"} or "TRAILING" in protect_signal.upper():
            scores["PROTECT_PAPER"] += 40.0
            evidence.append(f"protection posture/signal={posture}/{protect_signal}")
        if strategy in {"TIGHTEN_TRAIL_SHADOW", "PROTECT_PROFIT_SHADOW"}:
            scores["PROTECT_PAPER"] += 25.0
            evidence.append(f"GII strategy={strategy}")
        if strategy == "KEEP_GROWING_SHADOW" and lifecycle in HEALTHY_LIFECYCLE:
            scores["HOLD_PAPER"] += 42.0 + growth_score * 0.1
            evidence.append(f"healthy winner lifecycle={lifecycle}")
        if strategy == "HOLD_AND_MONITOR_SHADOW":
            scores["HOLD_PAPER"] += 28.0
            evidence.append(f"monitor strategy={strategy}")
        if missed >= 30.0 and cap_eff < 40.0 and ticker not in (ctx.get("top_growth") or []):
            scores["ROTATE_PAPER"] += 20.0
        if not any(scores[a] > 20 for a in ("SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER", "HOLD_PAPER")):
            scores["HOLD_PAPER"] += 20.0
            evidence.append("default hold for open position with partial evidence")
    else:
        if signal_score >= 90.0 and "STRONG BUY" in signal_name:
            scores["BUY_PAPER"] += 40.0
            evidence.append(f"signal={signal_name} score={signal_score}")
        elif signal_score >= 75.0 and "BUY" in signal_name:
            scores["BUY_PAPER"] += 25.0
            evidence.append(f"signal={signal_name}")
        if ticker in (ctx.get("top_growth") or []):
            scores["BUY_PAPER"] += 20.0 + growth_score * 0.15
            evidence.append(f"top_growth_candidate growth_score={growth_score:.1f}")
        if policy_state == "HIGH_RISK" or "PRESERVATION" in suggested_policy:
            scores["SKIP_PAPER"] += 15.0
            scores["BUY_PAPER"] -= 8.0
            evidence.append(f"policy={policy_state}/{ctx.get('suggested_policy')}")
        if _f(ctx.get("cash_hint")) < 1000.0:
            scores["SKIP_PAPER"] += 15.0
            scores["BUY_PAPER"] -= 10.0
            evidence.append("limited capital hint from accounting snapshot")
        if not signal and ticker not in (ctx.get("top_growth") or []):
            scores["SKIP_PAPER"] += 35.0
            evidence.append("no signal and not top growth candidate")

    if preferred == "COLLABORATIVE":
        scores["PROTECT_PAPER"] += 5.0
        scores["HOLD_PAPER"] += 3.0
    elif preferred == "COMPETITIVE":
        scores["ROTATE_PAPER"] += 4.0
        scores["SELL_PAPER"] += 3.0

    if ablation_component_enabled(ctx, "horizon"):
        hz = apply_horizon_action_bias(ticker, scores, evidence, ctx, held=held)
    else:
        hz = build_horizon_context(ticker, ctx)
        if not ablation_learning_enabled(ctx):
            evidence.append("ablation LEARNING_OFF: horizon action bias skipped")
    apply_stale_source_penalty(scores, evidence, ctx)
    knowledge_evidence: dict[str, Any] = {
        "source": str(KNOWLEDGE_JSON),
        "rules_applied": [],
        "entry_ids": [],
        "mode": MODE,
        "live_promotion_allowed": False,
    }
    named_rules: list[str] = []
    if ablation_component_enabled(ctx, "knowledge_base"):
        knowledge_evidence = apply_knowledge_base_bias(scores, evidence, ctx, ticker)
    if ablation_component_enabled(ctx, "named_confidence"):
        named_rules = apply_named_confidence_rules(scores, evidence, ctx)
    knowledge_evidence["named_confidence_rules"] = named_rules
    longitudinal_knowledge_evidence: dict[str, Any] | None = None
    dpe_evaluator_evidence: dict[str, Any] | None = None
    if ablation_component_enabled(ctx, "longitudinal"):
        longitudinal_knowledge_evidence = apply_longitudinal_knowledge_bias(scores, evidence, ctx)
    if ablation_component_enabled(ctx, "dpe_evaluator"):
        dpe_evaluator_evidence = apply_dpe_evaluator_bias(scores, evidence, ctx, held=held)
    if ablation_component_enabled(ctx, "learning_evidence"):
        apply_learning_evidence_bias(scores, evidence, ctx)
    adaptive_weight_detail = None
    if ablation_component_enabled(ctx, "adaptive_weights"):
        adaptive_weight_detail = apply_adaptive_paper_weights(scores, evidence, ctx, ticker)
    prot_boost, reduce_boost, sell_penalty, gates_passed = protection_validation_bias(
        ticker, ctx.get("shadow_validation"),
    )
    scores["PROTECT_PAPER"] += prot_boost
    scores["REDUCE_PAPER"] += reduce_boost
    scores["SELL_PAPER"] -= sell_penalty
    profit_target_evidence = apply_profit_target_adapter_bias(
        ticker, scores, evidence, ctx, held=held
    )
    if not gates_passed:
        evidence.append("protection validation gates not passed")
    else:
        evidence.append("protection validation gates passed")

    apply_exp_scores = ablation_component_enabled(ctx, "experiment_capital")
    experiment_capital_evidence = apply_experiment_capital_evidence(
        ticker, scores, evidence, ctx, apply_scores=apply_exp_scores
    )

    # Authorized challenger: elevate mapped EXISTING action over soft HOLD/PROTECT/SKIP.
    # Never elevates BUY_PAPER and never bypasses Hard Risk SELL overrides.
    if apply_exp_scores and experiment_capital_evidence.get("allocation_authorized") and held:
        mapped = _s(experiment_capital_evidence.get("experiment_action_mapping"))
        if mapped in {"REDUCE_PAPER", "ROTATE_PAPER", "SELL_PAPER", "PROTECT_PAPER"}:
            soft_lead = max(
                scores.get("HOLD_PAPER", 0.0),
                scores.get("PROTECT_PAPER", 0.0) if mapped != "PROTECT_PAPER" else 0.0,
                scores.get("SKIP_PAPER", 0.0),
                scores.get(mapped, 0.0),
            )
            if scores.get(mapped, 0.0) <= soft_lead:
                bump = (soft_lead - scores.get(mapped, 0.0)) + 8.0
                scores[mapped] = scores.get(mapped, 0.0) + bump
                deltas = dict(experiment_capital_evidence.get("experiment_score_delta") or {})
                deltas[mapped] = round(_f(deltas.get(mapped)) + bump, 2)
                experiment_capital_evidence["experiment_score_delta"] = deltas
                evidence.append(
                    f"capital challenger authorized: elevate {mapped} +{bump:.1f} over soft peers"
                )

    consumption_evidence = {
        "knowledge_evidence": knowledge_evidence,
        "longitudinal_knowledge_evidence": longitudinal_knowledge_evidence,
        "dpe_evaluator_evidence": dpe_evaluator_evidence,
        "adaptive_weight_evidence": adaptive_weight_detail,
        "profit_target_evidence": profit_target_evidence,
        "experiment_capital_evidence": experiment_capital_evidence,
        "ablation_learning_enabled": ablation_learning_enabled(ctx),
    }

    rules_applied = collect_rules_applied(consumption_evidence, named_rules)
    if ablation_component_enabled(ctx, "rule_lifecycle"):
        lifecycle_evidence = apply_rule_lifecycle_bias(scores, evidence, ctx, rules_applied)
    else:
        lifecycle_evidence = {
            "rules_applied": rules_applied,
            "rule_states": {},
            "adjustments": [],
            "mode": MODE,
            "live_promotion_allowed": False,
            "ablation_skipped": True,
        }
    consumption_evidence["rule_lifecycle_evidence"] = lifecycle_evidence
    position_discipline = enforce_position_discipline(ticker, scores, evidence, ctx)
    loss_discipline = enforce_loss_discipline(
        ticker, scores, evidence, ctx, rule_states=lifecycle_evidence.get("rule_states")
    )
    consumption_evidence["hard_risk_discipline"] = hard_risk_discipline
    consumption_evidence["profit_trailing"] = trailing_ev

    pre_entry = evaluate_pre_entry_hard_risk_compatibility(ticker, ctx, held=held)
    risk_sync = apply_pre_entry_hard_risk_sync(ticker, scores, evidence, pre_entry, held=held)
    consumption_evidence["pre_entry_hard_risk"] = pre_entry
    consumption_evidence["risk_sync"] = risk_sync

    from tae_conflict_resolution import apply_conflict_resolution_bias
    from tae_decision_state import apply_decision_state_gate

    conflict_resolution_evidence = apply_conflict_resolution_bias(ticker, scores, evidence, ctx)
    consumption_evidence["conflict_resolution_evidence"] = conflict_resolution_evidence

    prelim_best = max(scores, key=lambda a: scores[a])
    scenario_ev_table = conflict_resolution_evidence.get("scenario_ev_table") or (
        (ctx.get("conflict_resolution_by_ticker") or {}).get(ticker.upper(), {}).get("scenario_ev_table")
    )
    state_detail = apply_decision_state_gate(
        ticker,
        prelim_best,
        scores,
        evidence,
        ctx,
        hard_risk_discipline=hard_risk_discipline,
        loss_discipline=loss_discipline,
        scenario_ev_table=scenario_ev_table,
    )
    consumption_evidence["decision_state_evidence"] = state_detail

    best = prelim_best
    if not state_detail.get("decision_switch_authorized") and not hard_risk_discipline.get("override"):
        gate = state_detail.get("decision_state_evidence") or {}
        best = _s(gate.get("final_action"), best)

    # Capital challenger may authorize a soft switch onto the mapped EXISTING action.
    if (
        apply_exp_scores
        and experiment_capital_evidence.get("allocation_authorized")
        and not hard_risk_discipline.get("override")
        and held
    ):
        mapped = _s(experiment_capital_evidence.get("experiment_action_mapping"))
        if mapped in {"REDUCE_PAPER", "ROTATE_PAPER", "SELL_PAPER"} and scores.get(mapped, 0.0) >= 18.0:
            best = mapped
            state_detail["decision_switch_authorized"] = True
            state_detail["switch_reason"] = (
                f"capital_challenger:{experiment_capital_evidence.get('experiment_id')}"
            )
            gate = dict(state_detail.get("decision_state_evidence") or {})
            gate["final_action"] = mapped
            gate["switch_reason"] = state_detail["switch_reason"]
            state_detail["decision_state_evidence"] = gate
            consumption_evidence["decision_state_evidence"] = state_detail
            evidence.append(
                f"capital challenger switch authorized → {mapped} "
                f"(experiment {experiment_capital_evidence.get('experiment_id')})"
            )

    if best == "BUY_PAPER" and pre_entry.get("hard_block"):
        best = "SKIP_PAPER" if not held else "HOLD_PAPER"
        scores[best] = max(scores.get(best, 0.0), scores.get("BUY_PAPER", 0.0) + 30.0)
        scores["BUY_PAPER"] = 0.0
        evidence.append("pre-entry hard risk: final BUY veto — incompatible with Hard Risk evidence")
        risk_sync["decision_coherence_status"] = "BLOCKED_HARD_RISK_CONFLICT"
        consumption_evidence["risk_sync"] = risk_sync

    if scores[best] < 18.0:
        best = "SKIP_PAPER"
        evidence.append("no action met minimum confidence threshold")

    best, soft_reason = suppress_soft_exit_if_trailing_active(
        best, trailing_active=trailing_owns, exit_ready=False
    )
    if soft_reason:
        evidence.append(f"{soft_reason}: soft action suppressed while profit trailing active")
        scores["HOLD_PAPER"] = max(scores.get("HOLD_PAPER", 0.0), scores.get(best, 0.0), 100.0)
        # Keep HOLD as final action after soft suppress.
        if best != "HOLD_PAPER":
            best = "HOLD_PAPER"

    confidence = round(min(0.95, max(0.25, scores[best] / 100.0)), 3)
    if ablation_component_enabled(ctx, "hypothesis_rules"):
        # Trailing ownership: hypothesis rules must not reintroduce soft exits.
        if trailing_owns:
            applied_hyps = []
            evidence.append("profit trailing active: hypothesis rules skipped for exit ownership")
        else:
            best, applied_hyps, rule_note = apply_hypothesis_rules(ticker, best, confidence, ctx)
            if rule_note:
                evidence.append(rule_note)
            best, soft_reason2 = suppress_soft_exit_if_trailing_active(
                best, trailing_active=trailing_owns, exit_ready=False
            )
            if soft_reason2:
                evidence.append(soft_reason2)
                best = "HOLD_PAPER"
    else:
        applied_hyps = []
        if not ablation_learning_enabled(ctx):
            evidence.append("ablation LEARNING_OFF: hypothesis rules skipped")

    return (
        best,
        scores,
        evidence,
        applied_hyps,
        gates_passed,
        hz,
        consumption_evidence,
        position_discipline,
        loss_discipline,
        hard_risk_discipline,
    )


def build_decision(ticker: str, ctx: dict[str, Any], *, seq: int) -> dict[str, Any]:
    (
        action,
        scores,
        evidence_notes,
        applied_hypotheses,
        gates_passed,
        horizon,
        consumption_evidence,
        position_discipline,
        loss_discipline,
        hard_risk_discipline,
    ) = score_actions_for_ticker(ticker, ctx)
    adaptive_weight_detail = consumption_evidence.get("adaptive_weight_evidence")
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    deltas = estimate_deltas(ticker.upper(), action, ctx)
    risk_score = compute_risk_score(ticker.upper(), ctx)
    confidence = round(min(0.95, max(0.25, scores.get(action, 18.0) / 100.0)), 3)
    stale_penalty = _f((ctx.get("historical_runtime") or {}).get("confidence_penalty"))
    if stale_penalty > 0:
        confidence = round(max(0.25, confidence * (1.0 - stale_penalty)), 3)

    hints = ctx.get("adaptation_hints") or {}
    action_bias = 0.0
    if ablation_component_enabled(ctx, "adaptation_hints"):
        action_bias = _f((hints.get("action_confidence_bias") or {}).get(action))
    if action_bias:
        confidence = round(min(0.95, max(0.25, confidence + action_bias * 0.05)), 3)
        evidence_notes.append(f"longitudinal memory action bias {action_bias:+.3f}")

    sources: list[str] = []
    if gii:
        sources.append("tae_growth_intelligence.json")
    if ticker.upper() in (ctx.get("shadow_by") or {}):
        sources.append("tae_profit_protection_shadow.json")
    if ticker.upper() in (ctx.get("ppg_by") or {}):
        sources.append("tae_portfolio_profit_governor.json")
    if ctx.get("appe"):
        sources.append("tae_adaptive_profit_policy_engine.json")
    if (ctx.get("exp_by_ticker") or {}).get(ticker.upper()):
        sources.append("runtime_outputs/learning_to_profit/experiment_results.json")
    if applied_hypotheses:
        sources.append("runtime_outputs/learning_to_profit/hypotheses.json")
    if ctx.get("shadow_validation"):
        sources.append("tae_profit_protection_validation.json")
    if ctx.get("horizon_ssot", {}).get("historical_returns"):
        sources.append("historical_intelligence.csv")
    if STRATEGIC_INTELLIGENCE_TXT.is_file():
        sources.append("strategic_intelligence_summary.txt")
    if ctx.get("confidence_evolution"):
        sources.append("tae_confidence_evolution.json")
    if ctx.get("adaptation_hints"):
        sources.append("runtime_outputs/longitudinal_memory/adaptation_hints.json")
    if ctx.get("profit_targets"):
        sources.append("tae_profit_target_adapter.json")
    if ctx.get("paper_action_weights"):
        sources.append("runtime_outputs/adaptive_weights/paper_action_weights.json")
    if ctx.get("knowledge_base"):
        sources.append("tae_knowledge_base.json")
    if ctx.get("longitudinal_knowledge"):
        sources.append("runtime_outputs/longitudinal_memory/knowledge.json")
    if ctx.get("dpe_eval"):
        sources.append("runtime_outputs/dpe/result_evaluator/evaluation.json")
    if ctx.get("decision_replay"):
        sources.append("tae_decision_replay.json")
    if ctx.get("pattern_discovery_present"):
        sources.append("pattern_discovery_summary.txt")
    if ticker.upper() in (ctx.get("signals") or {}):
        sources.append("live_signals.csv")
    if ctx.get("rule_lifecycle"):
        sources.append("runtime_outputs/paper_execution/rule_lifecycle.json")
    if ctx.get("hard_risk"):
        sources.append("runtime_outputs/governance/hard_risk.json")
    if ctx.get("conflict_resolution"):
        sources.append("runtime_outputs/conflict_resolution/conflicts.json")
    if ctx.get("active_decisions"):
        sources.append("runtime_outputs/decision_state/active_decisions.json")
    if ticker.upper() in (ctx.get("paper_positions") or {}):
        sources.append("runtime_outputs/paper_execution/paper_portfolio.json")

    conflict_resolution_evidence = consumption_evidence.get("conflict_resolution_evidence") or {}
    decision_state_detail = consumption_evidence.get("decision_state_evidence") or {}
    pre_entry = consumption_evidence.get("pre_entry_hard_risk") or {}
    risk_sync = consumption_evidence.get("risk_sync") or {}
    gate = decision_state_detail.get("decision_state_evidence") or decision_state_detail

    mechanical_tp = consumption_evidence.get("profit_trailing") or {}
    profit_trailing = mechanical_tp
    coherence_status = _s(risk_sync.get("decision_coherence_status"), "COHERENT")
    if hard_risk_discipline.get("override"):
        coherence_status = "HARD_RISK_OVERRIDE"
    elif profit_trailing.get("exit_ready"):
        coherence_status = "PROFIT_TRAILING_EXIT"
    elif profit_trailing.get("trailing_active"):
        coherence_status = "PROFIT_TRAILING_ACTIVE"
    elif action == "BUY_PAPER" and pre_entry.get("hard_block"):
        coherence_status = "BLOCKED_HARD_RISK_CONFLICT"

    ts = _now()
    # BUY_PAPER gets a cycle-stamped id so a deferred opening-noise decision cannot
    # permanently block reevaluation. Fresh cycle ⇒ fresh decision_id (no auto-fill).
    # Non-BUY actions keep sticky ids for same-action idempotency (REDUCE/PROTECT).
    decision_id = mint_decision_id(ticker, seq=seq, action=action, ctx=ctx)
    hyp_validation = applied_hypotheses[0].get("validation_rule") if applied_hypotheses else (
        "PAPER decision validated against GII/PPG/shadow evidence over validation_window."
    )
    hyp_rejection = applied_hypotheses[0].get("rejection_rule") if applied_hypotheses else (
        "Reject PAPER decision if 30-day shadow metrics regress: profit_capture_rate down, "
        "missed_usd up, or risk_score rises without offsetting profit gain."
    )

    decision = {
        "decision_id": decision_id,
        "timestamp": ts,
        "ticker": ticker.upper(),
        "action": action,
        "source_systems": sorted(set(sources)),
        "evidence": "; ".join(evidence_notes)[:500],
        "confidence": confidence,
        "risk_score": risk_score,
        "expected_profit_delta": round(deltas["expected_profit_delta"], 2),
        "expected_risk_delta": round(deltas["expected_risk_delta"], 4),
        "capital_efficiency_delta": round(deltas["capital_efficiency_delta"], 2),
        "validation_window": 30,
        "validation_rule": hyp_validation,
        "rejection_rule": hyp_rejection,
        "promotion_rule": (
            "PAPER validation must show PROMISING experiment verdict + non-negative profit delta "
            "before any advisory review; live promotion remains blocked (live_promotion_allowed=false)."
        ),
        "live_promotion_allowed": False,
        "mode": MODE,
        "action_scores": {k: round(v, 2) for k, v in scores.items() if v > 0},
        "hypothesis_rules_applied": applied_hypotheses,
        "protection_validation_gates_passed": gates_passed,
        "horizon_context": horizon.get("horizon_context"),
        "short_term_trend_7d": horizon.get("short_term_trend_7d"),
        "monthly_trend": horizon.get("monthly_trend"),
        "yearly_trend": horizon.get("yearly_trend"),
        "long_term_trend": horizon.get("long_term_trend"),
        "horizon_alignment_score": horizon.get("horizon_alignment_score"),
        "horizon_conflict_flag": horizon.get("horizon_conflict_flag"),
        "horizon_reason": horizon.get("horizon_reason"),
        "historical_sources_stale": bool((ctx.get("historical_runtime") or {}).get("stale_sources")),
        "confidence_penalty_stale": stale_penalty,
        "knowledge_evidence": consumption_evidence.get("knowledge_evidence"),
        "longitudinal_knowledge_evidence": consumption_evidence.get("longitudinal_knowledge_evidence"),
        "dpe_evaluator_evidence": consumption_evidence.get("dpe_evaluator_evidence"),
        "adaptive_weight_evidence": adaptive_weight_detail,
        "learning_state_fingerprint": (
            ctx.get("learning_state_fingerprint")
        ),
        "profit_target_evidence": consumption_evidence.get("profit_target_evidence"),
        "rule_lifecycle_evidence": consumption_evidence.get("rule_lifecycle_evidence"),
        "position_discipline": position_discipline,
        "loss_discipline": loss_discipline,
        "hard_risk_discipline": hard_risk_discipline,
        "profit_trailing": profit_trailing,
        "reason_code": (
            str(hard_risk_discipline.get("hard_rule") or "HARD_RISK")
            if hard_risk_discipline.get("override")
            else (
                "PDE_SOFT_EXIT_SUPPRESSED_BY_ACTIVE_PROFIT_TRAILING"
                if action == "HOLD_PAPER"
                and any(
                    "PDE_SOFT_EXIT_SUPPRESSED_BY_ACTIVE_PROFIT_TRAILING" in str(x)
                    for x in evidence_notes
                )
                else (
                    str(profit_trailing.get("reason_code") or "")
                    if profit_trailing.get("exit_ready") or profit_trailing.get("trailing_active")
                    else None
                )
            )
        ),
        "position_cycle_id": (
            profit_trailing.get("position_cycle_id")
            or ((ctx.get("paper_positions") or {}).get(ticker.upper()) or {}).get("position_cycle_id")
        ),
        "full_position_intent": bool(profit_trailing.get("exit_ready") or hard_risk_discipline.get("override")),
        "conflict_resolution_evidence": conflict_resolution_evidence,
        "scenario_ev_table": conflict_resolution_evidence.get("scenario_ev_table") or [],
        "winning_scenario": conflict_resolution_evidence.get("winning_scenario"),
        "ev_reason": conflict_resolution_evidence.get("ev_reason"),
        "final_authority": conflict_resolution_evidence.get("final_authority"),
        "decision_state_evidence": decision_state_detail,
        "previous_action": gate.get("previous_action"),
        "previous_action_at": gate.get("previous_action_at"),
        "decision_switch_authorized": bool(decision_state_detail.get("decision_switch_authorized")),
        "switch_reason": gate.get("switch_reason") or decision_state_detail.get("switch_reason"),
        "cooldown_status": gate.get("cooldown_status"),
        "churn_risk": gate.get("churn_risk"),
        "ev_margin_actual": gate.get("ev_margin_actual"),
        "ev_margin_required": gate.get("ev_margin_required"),
        "hard_rule_override": bool(hard_risk_discipline.get("override")),
        "paper_position_held": paper_position_held(ticker.upper(), ctx),
        "pre_entry_hard_risk_compatible": bool(pre_entry.get("compatible")),
        "pre_entry_hard_risk_level": pre_entry.get("risk_level"),
        "pre_entry_hard_risk_reasons": pre_entry.get("reasons") or [],
        "recent_hard_stop": bool(pre_entry.get("recent_hard_stop")),
        "reentry_authorized": bool(pre_entry.get("reentry_allowed")),
        "risk_score_delta": _f(risk_sync.get("risk_score_delta")),
        "decision_coherence_status": coherence_status,
        "experiment_capital_evidence": consumption_evidence.get("experiment_capital_evidence"),
        "experiment_id": (consumption_evidence.get("experiment_capital_evidence") or {}).get("experiment_id"),
        "experiment_verdict": (consumption_evidence.get("experiment_capital_evidence") or {}).get("experiment_verdict"),
        "capital_candidate_status": (consumption_evidence.get("experiment_capital_evidence") or {}).get(
            "capital_candidate_status"
        ),
        "experiment_action_mapping": (consumption_evidence.get("experiment_capital_evidence") or {}).get(
            "experiment_action_mapping"
        ),
        "experiment_score_delta": (consumption_evidence.get("experiment_capital_evidence") or {}).get(
            "experiment_score_delta"
        ),
        "proposed_allocation_usd": (consumption_evidence.get("experiment_capital_evidence") or {}).get(
            "proposed_allocation_usd"
        ),
        "allocation_authorized": bool(
            (consumption_evidence.get("experiment_capital_evidence") or {}).get("allocation_authorized")
        ),
        "allocation_block_reason": (consumption_evidence.get("experiment_capital_evidence") or {}).get(
            "allocation_block_reason"
        ),
        "evidence_quality": (consumption_evidence.get("experiment_capital_evidence") or {}).get("evidence_quality"),
        "created_at": ts,
    }
    try:
        import tae_adaptive_deployment as adep

        dep = adep.deployment_metadata(selection_reason="pde_decision_stamp")
        decision["adaptive_deployment"] = dep
        decision["deployment_id"] = dep.get("deployment_id")
        decision["deployment_version"] = dep.get("deployment_version")
        decision["deployment_state"] = dep.get("deployment_state")
        decision["formula_id"] = dep.get("formula_id")
        decision["formula_version"] = dep.get("formula_version")
        decision["git_head"] = dep.get("git_head")
        decision["selection_reason"] = dep.get("selection_reason")
        # Preserve capital-challenger experiment_id when present; else use deployment experiment.
        if not decision.get("experiment_id"):
            decision["experiment_id"] = dep.get("experiment_id")
        decision["deployment_experiment_arm"] = dep.get("experiment_arm")
    except Exception:
        pass
    try:
        if action != "HOLD_PAPER":
            from tae_paper_shadow_sizing import PAPER_MIN_ORDER_USD
            from tae_paper_transaction_costs import compute_transaction_cost

            side = "BUY" if action == "BUY_PAPER" else "SELL"
            cost_detail = compute_transaction_cost(PAPER_MIN_ORDER_USD, side=side)
            est_cost = _f(cost_detail.get("total_transaction_cost"))
            profit_delta = _f(decision.get("expected_profit_delta"))
            decision["edge_vs_cost_estimate"] = {
                "note": (
                    "Informational only — does not affect action/score. Proxy notional "
                    "(PAPER_MIN_ORDER_USD) is a conservative minimum; the real fill size "
                    "is unknown until execution, so this is not an exact cost."
                ),
                "proxy_notional_usd": PAPER_MIN_ORDER_USD,
                "estimated_cost_usd": round(est_cost, 6),
                "expected_profit_delta_usd": profit_delta,
                "edge_covers_estimated_cost": profit_delta >= est_cost,
                "margin_usd": round(profit_delta - est_cost, 6),
            }
    except Exception:
        pass
    return decision


def pde_cycle_stamp(ctx: dict[str, Any] | None = None) -> str:
    """Shared stamp for one PDE run — minute UTC. Overridable via ctx['cycle_stamp']."""
    raw = _s((ctx or {}).get("cycle_stamp"))
    if raw:
        return raw
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M")


def mint_decision_id(ticker: str, *, seq: int, action: str, ctx: dict[str, Any]) -> str:
    """Mint decision_id. BUY_PAPER is cycle-stamped; other actions stay sticky per ticker+seq."""
    ticker_u = ticker.upper()
    seq_s = f"{int(seq):04d}"
    if _s(action).upper() == "BUY_PAPER":
        return f"PDEC-{ticker_u}-{pde_cycle_stamp(ctx)}-{seq_s}"
    return f"PDEC-{ticker_u}-{seq_s}"


def build_decisions(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    # One stamp per PDE cycle so all BUY_PAPER ids in this run share identity.
    if not _s(ctx.get("cycle_stamp")):
        ctx["cycle_stamp"] = pde_cycle_stamp(ctx)
    universe = ticker_universe(ctx)
    decisions = [build_decision(ticker, ctx, seq=i + 1) for i, ticker in enumerate(universe)]
    action_order = {
        "BUY_PAPER": 0,
        "SELL_PAPER": 1,
        "REDUCE_PAPER": 2,
        "PROTECT_PAPER": 3,
        "ROTATE_PAPER": 4,
        "HOLD_PAPER": 5,
        "SKIP_PAPER": 6,
    }
    decisions.sort(key=lambda d: (action_order.get(d["action"], 9), -d["confidence"], d["ticker"]))
    return decisions


def build_report_payload(decisions: list[dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    for d in decisions:
        action_counts[d["action"]] = action_counts.get(d["action"], 0) + 1

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_live_execution": True,
        "no_execution": True,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "decision_count": len(decisions),
        "action_summary": action_counts,
        "sources_loaded": ctx.get("sources_loaded") or {},
        "policy_context": {
            "policy_state": ctx.get("policy_state"),
            "suggested_policy": ctx.get("suggested_policy"),
            "preferred_philosophy": ctx.get("preferred_philosophy"),
        },
        "decisions": decisions,
        "safety": {
            "mode": MODE,
            "PAPER_ONLY": True,
            "NO_BROKER": True,
            "NO_LIVE_CHANGE": True,
            "NO_EXECUTION": True,
            "live_promotion_allowed": False,
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    assert_safe_output_path(DECISIONS_JSON)
    assert_safe_output_path(DECISIONS_JSONL)
    assert_safe_output_path(REPORT_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    DECISIONS_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with DECISIONS_JSONL.open("w", encoding="utf-8") as handle:
        for row in report.get("decisions") or []:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = report.get("action_summary") or {}
    lines = [
        "# TAE Paper Decision Engine Report",
        "",
        f"**Generated:** {report['generated_at']}",
        "**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION",
        "**Live promotion allowed:** false",
        "",
        "> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**",
        "",
        "## Executive summary",
        "",
        f"- Decisions generated: **{report.get('decision_count', 0)}**",
    ]
    for action in sorted(summary.keys()):
        lines.append(f"- **{action}**: {summary[action]}")
    lines.extend(
        [
            "",
            "## Decision table",
            "",
            "| ticker | action | confidence | risk | profit Δ | cap eff Δ | switch | evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in (report.get("decisions") or [])[:25]:
        ev = _s(row.get("evidence"))[:60].replace("|", "/")
        sw = "yes" if row.get("decision_switch_authorized") else "no"
        lines.append(
            f"| {row.get('ticker')} | {row.get('action')} | {row.get('confidence')} | "
            f"{row.get('risk_score')} | {row.get('expected_profit_delta')} | "
            f"{row.get('capital_efficiency_delta')} | switch={sw} | {ev} |"
        )

    switch_accepted = sum(1 for d in (report.get("decisions") or []) if d.get("decision_switch_authorized"))
    switch_blocked = sum(
        1
        for d in (report.get("decisions") or [])
        if d.get("previous_action") and d.get("previous_action") != d.get("action") and not d.get("decision_switch_authorized")
    )
    lines.extend(
        [
            "",
            "## Decision state / switch summary",
            "",
            f"- Switch authorized: **{switch_accepted}**",
            f"- Switch blocked (PDE gate): **{switch_blocked}**",
            f"- Active decisions loaded: **{(report.get('sources_loaded') or {}).get('active_decisions')}**",
            "",
            "## Closed intelligence loop",
            "",
            "- Consumes: learning-to-profit hypotheses + experiment results",
            "- Consumes: GII, PPG, APPE, profit protection, DPE adaptive/evaluation",
            "- Consumes: portfolio.csv + live_signals.csv (read-only)",
            "- Produces explicit PAPER BUY/SELL/HOLD/REDUCE/PROTECT/ROTATE/SKIP decisions",
            "- Applies hypothesis validation/rejection rules and protection validation scoring",
            "- Applies multi-horizon context (7D/1M/1Y/2Y/5Y/10Y/20Y) from existing SSOT artifacts",
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| NO_LIVE_CHANGE | ✅ |",
            "| NO_EXECUTION | ✅ |",
            "| live_promotion_allowed | **false** |",
            "| portfolio.csv modified | **false** |",
            "| live_bot.py modified | **false** |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return DECISIONS_JSON, DECISIONS_JSONL, REPORT_MD


def update_capital_challenger_registry(
    *,
    decisions: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Observe Validation→Capital Allocation outcomes using existing decisions/orders."""
    LTP_DIR.mkdir(parents=True, exist_ok=True)
    if decisions is None:
        decisions = list((load_json(DECISIONS_JSON) or {}).get("decisions") or [])
    if orders is None:
        orders = load_jsonl(ORDERS_JSONL)[-40:]

    prev = load_json(CAPITAL_CHALLENGERS_JSON) or {}
    by_id: dict[str, dict[str, Any]] = {
        _s(r.get("experiment_id")): dict(r)
        for r in (prev.get("challengers") or [])
        if _s(r.get("experiment_id"))
    }

    orders_by_ticker = {}
    for o in orders:
        t = _s(o.get("ticker")).upper()
        if t:
            orders_by_ticker[t] = o

    progressed = 0
    capital_moved = 0.0
    for d in decisions:
        exp_id = _s(d.get("experiment_id"))
        status = _s(d.get("capital_candidate_status"))
        if not exp_id:
            continue
        row = by_id.get(exp_id) or {
            "experiment_id": exp_id,
            "lifecycle": "PROMISING",
            "created_at": _now(),
        }
        row.update(
            {
                "ticker": _s(d.get("ticker")).upper(),
                "experiment_verdict": d.get("experiment_verdict"),
                "capital_candidate_status": status,
                "experiment_action_mapping": d.get("experiment_action_mapping"),
                "proposed_allocation_usd": d.get("proposed_allocation_usd"),
                "expected_profit_delta": d.get("expected_profit_delta"),
                "expected_risk_delta": d.get("expected_risk_delta"),
                "allocation_authorized": bool(d.get("allocation_authorized")),
                "allocation_block_reason": d.get("allocation_block_reason"),
                "evidence_quality": d.get("evidence_quality"),
                "final_action": d.get("action"),
                "updated_at": _now(),
            }
        )
        if d.get("allocation_authorized"):
            row["lifecycle"] = "CAPITAL_CHALLENGER"
            progressed += 1
        order = orders_by_ticker.get(_s(d.get("ticker")).upper()) or {}
        if order and order.get("executed") and bool(order.get("is_trade")):
            row["lifecycle"] = "EXECUTED_PAPER"
            row["observed_fill_shares"] = order.get("fill_shares")
            row["observed_capital_impact"] = order.get("capital_impact")
            row["observed_realized_pnl"] = order.get("realized_pnl")
            capital_moved += abs(_f(order.get("capital_impact") or order.get("gross_value")))
            # Promotion/retirement deferred to attribution/realized evidence
            realized = _f(order.get("realized_pnl"))
            if realized > 0:
                row["lifecycle"] = "OBSERVED"
                row["promotion_hint"] = "PROMOTED_CANDIDATE"
            elif realized < 0:
                row["lifecycle"] = "OBSERVED"
                row["promotion_hint"] = "REVERT_OR_RETIRE"
            else:
                row["lifecycle"] = "EXECUTED_PAPER"
                row["promotion_hint"] = "OBSERVE"
        elif status in {"NOT_EXECUTABLE", "INSUFFICIENT_EVIDENCE", "PORTFOLIO_POLICY_CANDIDATE", "PROTECTION_ONLY_CANDIDATE"}:
            row["lifecycle"] = status
        by_id[exp_id] = row

    challengers = sorted(by_id.values(), key=lambda r: _s(r.get("experiment_id")))
    doc = {
        "schema": "tae.capital_challengers.v1",
        "mode": MODE,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "challenger_count": len(challengers),
        "authorized_count": sum(1 for r in challengers if r.get("allocation_authorized")),
        "executed_trade_count": sum(1 for r in challengers if r.get("lifecycle") in {"EXECUTED_PAPER", "OBSERVED"}),
        "capital_moved_abs_usd": round(capital_moved, 2),
        "challengers": challengers,
        "arrow": "Validation→Capital Allocation",
        "notes": [
            "PROMISING alone never authorizes capital",
            "Hard Risk remains non-bypassable",
            "PDE remains single final authority",
        ],
    }
    CAPITAL_CHALLENGERS_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def replay_promising_capital_allocation(
    experiment_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Retrospective eligibility replay of PROMISING experiments (read-only classification)."""
    ctx = build_context()
    experiments = (load_json(EXPERIMENTS_JSON) or {}).get("experiments") or []
    target = set(experiment_ids or [])
    rows: list[dict[str, Any]] = []
    for exp in experiments:
        hid = _s(exp.get("hypothesis_id"))
        if target and hid not in target:
            continue
        if _s(exp.get("verdict")).upper() != "PROMISING" and (not target or hid not in target):
            continue
        tickers = [_s(t).upper() for t in (exp.get("affected_tickers") or []) if _s(t)]
        if not tickers:
            # portfolio-scope
            row = classify_experiment_capital_eligibility(exp, ticker="_PORTFOLIO", ctx=ctx)
            row["ticker"] = "_PORTFOLIO"
            row["claimed_profit_delta"] = _f((exp.get("deltas") or {}).get("expected_profit_delta_usd"))
            row["would_move_capital"] = False
            rows.append(row)
            continue
        for t in tickers:
            row = classify_experiment_capital_eligibility(exp, ticker=t, ctx=ctx)
            row["ticker"] = t
            row["claimed_profit_delta"] = row.get("expected_profit_delta")
            row["would_move_capital"] = bool(row.get("allocation_authorized"))
            rows.append(row)

    return {
        "schema": "tae.capital_allocation_replay.v1",
        "mode": MODE,
        "generated_at": _now(),
        "rows": rows,
        "eligible_count": sum(1 for r in rows if r.get("capital_candidate_status") == "ACTIONABLE_CAPITAL_CANDIDATE"),
        "ineligible_count": sum(1 for r in rows if r.get("capital_candidate_status") != "ACTIONABLE_CAPITAL_CANDIDATE"),
    }


def build_strategy_v2_structural_decision(**kwargs: Any) -> dict[str, Any]:
    """
    Structural Strategy V2 decision stub for tests / future wiring.
    NOT called by build_decisions / scoring. Default flag remains false.
    """
    from tae_strategy_v2_foundation import build_v2_decision_payload

    return build_v2_decision_payload(**kwargs)


def maybe_attach_v2_buy_policy(
    decision: dict[str, Any],
    ctx: dict[str, Any],
    *,
    enabled_override: bool | None = None,
) -> dict[str, Any]:
    """
    Optional annotation only when STRATEGY_V2_ENABLED (or explicit override).
    Default flag false → decision returned unchanged (V1 semantic identity).
    """
    from tae_strategy_v2_buy_policy import pde_maybe_v2_buy_policy

    v2 = pde_maybe_v2_buy_policy(
        ticker=str(decision.get("ticker") or ""),
        pde_decision=decision,
        ctx=ctx,
        enabled_override=enabled_override,
    )
    if v2 is None:
        return decision
    out = dict(decision)
    out["strategy_v2_buy_policy"] = v2
    return out


def print_summary(report: dict[str, Any]) -> None:
    summary = report.get("action_summary") or {}
    print("===== TAE PAPER DECISION ENGINE =====")
    print("Mode: PAPER_ONLY — NO_BROKER — NO_EXECUTION — no live change")
    print("Decisions:", report.get("decision_count", 0))
    print("Actions:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
    for row in (report.get("decisions") or [])[:5]:
        print(f"  {row['ticker']} → {row['action']} conf={row['confidence']} risk={row['risk_score']}")


def persist_paper_profit_trailing_state(ctx: dict[str, Any]) -> bool:
    """Ask execution owner to persist trailing fields (no direct portfolio write from PDE)."""
    if not ctx.get("paper_portfolio_trailing_dirty"):
        return False
    import tae_paper_execution as pe

    disk = pe.merge_and_persist_profit_trailing_state(ctx.get("paper_positions") or {})
    if not isinstance(disk, dict):
        return False
    ctx["paper_portfolio"] = disk
    ctx["paper_positions"] = load_paper_positions(disk)
    ctx["paper_portfolio_trailing_dirty"] = False
    return True


def main() -> int:
    from tae_decision_state import run_decision_state_refresh
    from tae_conflict_resolution import run_conflict_resolution

    run_decision_state_refresh(write_outputs_flag=True)
    run_conflict_resolution(write_outputs_flag=True)
    ctx = build_context()
    if not ctx.get("gii_by") and not ctx.get("live_positions"):
        print("paper-decision-engine: insufficient inputs — run growth-intelligence and ensure portfolio.csv", flush=True)
        return 1

    if ctx.get("paper_portfolio_trailing_dirty"):
        persist_paper_profit_trailing_state(ctx)

    decisions = build_decisions(ctx)
    report = build_report_payload(decisions, ctx)
    paths = write_outputs(report)
    write_decision_discipline_report(decisions, ctx)
    print_summary(report)
    print("Wrote:", *paths, DISCIPLINE_REPORT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
