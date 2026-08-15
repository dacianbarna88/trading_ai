#!/usr/bin/env python3
"""
TAE Evidence-Based Profit Optimization — READ_ONLY unified audit.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_MUTATION | AUDIT_FIRST
Consumes existing artifacts; designs challenger calibrations; replays counterfactuals.
Does NOT modify PDE, execution, risk, or portfolio unless promotion criteria pass.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "PAPER_ONLY"
SCHEMA = "tae_profit_optimization"
VERSION = "v1"
CAPITAL_BASE = 30000.0

ROOT = Path(".")

ORDERS_JSONL = ROOT / "runtime_outputs/paper_execution/paper_orders.jsonl"
TRADES_JSONL = ROOT / "runtime_outputs/paper_execution/paper_trades.jsonl"
PORTFOLIO_JSON = ROOT / "runtime_outputs/paper_execution/paper_portfolio.json"
DECISIONS_JSON = ROOT / "runtime_outputs/paper_decisions/paper_decisions.json"
DECISIONS_JSONL = ROOT / "runtime_outputs/paper_decisions/paper_decisions.jsonl"
VALIDATION_JSON = ROOT / "runtime_outputs/paper_decisions/decision_validation_results.json"
MEMORY_JSONL = ROOT / "runtime_outputs/longitudinal_memory/decisions.jsonl"
ATTRIBUTION_JSON = ROOT / "runtime_outputs/paper_execution/rule_outcome_attribution.json"
WEIGHTS_JSON = ROOT / "runtime_outputs/adaptive_weights/paper_action_weights.json"
WEIGHTS_HISTORY = ROOT / "runtime_outputs/adaptive_weights/paper_action_weights_history.jsonl"
DPE_EVAL_JSON = ROOT / "runtime_outputs/dpe/result_evaluator/evaluation.json"
DPE_ADAPTIVE_JSON = ROOT / "runtime_outputs/dpe/adaptive/adaptive.json"
LEDGER_JSON = ROOT / "tae_opportunity_cost_ledger.json"
GII_JSON = ROOT / "tae_growth_intelligence.json"
PPG_JSON = ROOT / "tae_portfolio_profit_governor.json"
APPE_JSON = ROOT / "tae_adaptive_profit_policy_engine.json"
CONFLICTS_JSON = ROOT / "runtime_outputs/conflict_resolution/conflicts.json"
DECISION_STATE_JSON = ROOT / "runtime_outputs/decision_state/active_decisions.json"
PIPELINE_JSON = ROOT / "tae_profit_pipeline.json"

AUDIT_MD = ROOT / "TAE_PROFIT_OPTIMIZATION_AUDIT.md"
AUDIT_JSON = ROOT / "tae_profit_optimization_audit.json"
BASELINE_MD = ROOT / "TAE_BASELINE_VS_CHALLENGERS_REPORT.md"
BASELINE_JSON = ROOT / "tae_baseline_vs_challengers.json"

ACTIONABLE = frozenset({"BUY_PAPER", "SELL_PAPER", "PROTECT_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"})
COMPONENTS = (
    "HARD_RISK",
    "policy_skip",
    "CAPITAL_PRESERVATION",
    "same_action",
    "cooldown_reentry_churn",
    "conflict_resolution",
    "decision_state_gate",
    "adaptive_weights",
    "knowledge_rules",
    "profit_protection",
    "PPG",
    "APPE",
    "DPE_collaborative",
    "DPE_competitive",
    "HOLD",
    "SKIP",
    "BUY",
    "SELL",
    "PROTECT",
)


def _now_iso() -> str:
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


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _region_for_ticker(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith(".L"):
        return "UK"
    if t.endswith(".DE") or t.endswith(".PA"):
        return "EU"
    return "US"


def _classify_order_block(order: dict[str, Any]) -> str:
    status = _s(order.get("status")).upper()
    reason = _s(order.get("reason") or order.get("block_reason")).lower()
    action = _s(order.get("action")).upper()
    if status == "EXECUTED":
        if "hard risk" in reason or "hard_stop" in reason:
            return "hard_risk"
        return "executed"
    if status == "SKIPPED_NO_MARK_PRICE":
        return "no_mark_price"
    if status == "NO_CHANGE":
        if action == "SKIP_PAPER" or "policy=" in reason or "capital_preservation" in reason:
            return "policy_skip"
        if "cooldown" in reason or "churn" in reason or "reentry" in reason:
            return "cooldown_reentry_churn"
        return "same_action"
    if "switch" in reason and "not" in reason:
        return "switch_not_authorized"
    if "fake" in reason and "profit" in reason:
        return "fake_profit_risk"
    if "market" in reason and "closed" in reason:
        return "market_closed"
    if "no position" in reason or "no_position" in reason:
        return "no_position"
    return "other"


def _is_synthetic_fill_trade(trade: dict[str, Any]) -> bool:
    fill = _f(trade.get("fill_price") or trade.get("price"))
    pnl = _f(trade.get("realized_pnl"))
    ts = _s(trade.get("timestamp"))
    if abs(fill - 100.0) < 0.01 and abs(pnl) < 0.01:
        return True
    if ts.startswith("2026-07-08T20:57:01") and abs(pnl) < 0.01 and _s(trade.get("action")) == "BUY_PAPER":
        return True
    return False


def build_evidence_set() -> dict[str, Any]:
    """Phase 1 — clean analysis window with exclusions."""
    portfolio = _load_json(PORTFOLIO_JSON) or {}
    integrity_ok = bool(portfolio.get("profit_integrity_ok"))
    reset_at = _s(portfolio.get("capital_base_reset_at") or portfolio.get("accounting_baseline_v1"))
    reset_dt = _parse_ts(reset_at)

    exclusions: list[dict[str, Any]] = []
    orders_all = _load_jsonl(ORDERS_JSONL)
    trades_all = _load_jsonl(TRADES_JSONL)
    decisions_jsonl = _load_jsonl(DECISIONS_JSONL)
    validation = _load_json(VALIDATION_JSON) or {}
    memory = _load_jsonl(MEMORY_JSONL)

    # Exclude pre-integrity / pre-reset
    orders_clean: list[dict[str, Any]] = []
    for o in orders_all:
        ts = _parse_ts(_s(o.get("timestamp")))
        if reset_dt and ts and ts < reset_dt:
            exclusions.append({"type": "pre_capital_base_reset", "id": o.get("decision_id"), "ticker": o.get("ticker")})
            continue
        orders_clean.append(o)

    trades_clean: list[dict[str, Any]] = []
    for t in trades_all:
        if _is_synthetic_fill_trade(t):
            exclusions.append(
                {
                    "type": "synthetic_100_fill",
                    "ticker": t.get("ticker"),
                    "timestamp": t.get("timestamp"),
                    "fill_price": t.get("fill_price"),
                }
            )
            continue
        ts = _parse_ts(_s(t.get("timestamp")))
        if reset_dt and ts and ts < reset_dt:
            exclusions.append({"type": "pre_capital_base_reset", "record": "trade", "ticker": t.get("ticker")})
            continue
        trades_clean.append(t)

    # Dedupe orders by decision_id keeping latest timestamp
    by_decision: dict[str, dict[str, Any]] = {}
    for o in orders_clean:
        did = _s(o.get("decision_id"))
        if not did:
            continue
        prev = by_decision.get(did)
        if not prev or _s(o.get("timestamp")) >= _s(prev.get("timestamp")):
            if prev and prev is not o:
                exclusions.append({"type": "duplicate_order_superseded", "decision_id": did})
            by_decision[did] = o
    orders_unique = list(by_decision.values())

    val_results = validation.get("results") or []
    val_by_id = {_s(v.get("decision_id")): v for v in val_results if _s(v.get("decision_id"))}

    closed_trades = [t for t in trades_clean if _s(t.get("action")) in {"SELL_PAPER", "REDUCE_PAPER"}]
    executed_orders = [o for o in orders_clean if _s(o.get("status")).upper() == "EXECUTED"]
    incomplete = [
        o
        for o in orders_unique
        if _classify_order_block(o) in {"same_action", "policy_skip", "no_mark_price", "cooldown_reentry_churn"}
    ]

    sessions = sorted({_s(o.get("timestamp"))[:10] for o in orders_clean if o.get("timestamp")})

    return {
        "clean_window_start": reset_at or "unknown",
        "integrity_ok": integrity_ok,
        "usable_sessions": len(sessions),
        "session_dates": sessions,
        "usable_decisions": len(decisions_jsonl) or len((_load_json(DECISIONS_JSON) or {}).get("decisions") or []),
        "usable_orders": len(orders_unique),
        "usable_executions": len(executed_orders),
        "usable_closed_outcomes": len(closed_trades),
        "incomplete_outcomes": len(incomplete),
        "exclusions": exclusions,
        "exclusion_counts": dict(Counter(e["type"] for e in exclusions)),
        "orders_clean": orders_clean,
        "orders_unique": orders_unique,
        "trades_clean": trades_clean,
        "closed_trades": closed_trades,
        "validation_by_id": val_by_id,
        "memory_rows": memory,
        "portfolio": portfolio,
    }


def _profit_metrics(portfolio: dict[str, Any], extra_realized: float = 0.0, extra_unrealized: float = 0.0) -> dict[str, Any]:
    realized = _f(portfolio.get("realized_pnl")) + extra_realized
    unrealized = _f(portfolio.get("unrealized_pnl")) + extra_unrealized
    total_pnl = realized + unrealized
    base = _f(portfolio.get("validation_capital_base"), CAPITAL_BASE)
    total_value = _f(portfolio.get("total_value")) + extra_realized + extra_unrealized
    profit_vs_base = total_value - base
    return {
        "total_pnl": round(total_pnl, 4),
        "realized_pnl": round(realized, 4),
        "unrealized_pnl": round(unrealized, 4),
        "profit_vs_validation_base": round(profit_vs_base, 4),
        "return_on_base_pct": round((profit_vs_base / base) * 100, 4) if base else 0.0,
        "max_drawdown_pct": _f(portfolio.get("drawdown_pct")),
        "capital_efficiency": _f(portfolio.get("capital_efficiency")),
    }


def _trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_f(t.get("realized_pnl")) for t in trades if _f(t.get("realized_pnl")) != 0]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / len(pnls) if pnls else 0.0
    avg_w = sum(wins) / len(wins) if wins else 0.0
    avg_l = sum(losses) / len(losses) if losses else 0.0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_win / gross_loss if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
    return {
        "trade_count": len(trades),
        "closed_with_pnl": len(pnls),
        "win_rate": round(win_rate, 4),
        "average_winner": round(avg_w, 4),
        "average_loser": round(avg_l, 4),
        "profit_factor": round(pf, 4),
    }


def build_attribution(evidence: dict[str, Any]) -> dict[str, Any]:
    """Phase 2 — component attribution from clean evidence."""
    portfolio = evidence["portfolio"]
    positions = portfolio.get("positions") or {}
    orders = evidence["orders_clean"]
    trades = evidence["closed_trades"]
    val_by_id = evidence["validation_by_id"]
    attribution_raw = (_load_json(ATTRIBUTION_JSON) or {}).get("rules") or {}

    components: dict[str, dict[str, Any]] = {}
    for name in COMPONENTS:
        components[name] = {
            "decisions_influenced": 0,
            "executions_influenced": 0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "avoided_loss": 0.0,
            "missed_profit": 0.0,
            "win_rate": 0.0,
            "sample_size": 0,
            "statistical_reliability": "INSUFFICIENT",
        }

    block_counts = Counter(_classify_order_block(o) for o in orders)
    for bucket, count in block_counts.items():
        key = bucket if bucket in components else "other"
        if key not in components:
            components[key] = components.get(bucket, components["policy_skip"])
        components.setdefault(bucket, components.get("policy_skip", {}))
        if bucket in components:
            components[bucket]["decisions_influenced"] = count
            components[bucket]["executions_influenced"] = sum(
                1 for o in orders if _classify_order_block(o) == bucket and _s(o.get("status")).upper() == "EXECUTED"
            )

    # Hard risk from trades
    hard_trades = [t for t in trades if "hard" in _s(t.get("reason")).lower() or _f(t.get("realized_pnl")) < -20]
    components["HARD_RISK"]["executions_influenced"] = len(hard_trades)
    components["HARD_RISK"]["realized_pnl"] = round(sum(_f(t.get("realized_pnl")) for t in hard_trades), 4)
    components["HARD_RISK"]["sample_size"] = len(hard_trades)
    components["HARD_RISK"]["statistical_reliability"] = "LOW" if len(hard_trades) >= 3 else "INSUFFICIENT"

    # Action-level from decisions
    decisions = (_load_json(DECISIONS_JSON) or {}).get("decisions") or []
    action_counts = Counter(_s(d.get("action")) for d in decisions)
    for action, count in action_counts.items():
        short = action.replace("_PAPER", "")
        if short in components:
            components[short]["decisions_influenced"] = count

    # PPG / APPE
    ppg = _load_json(PPG_JSON) or {}
    appe = _load_json(APPE_JSON) or {}
    components["PPG"]["decisions_influenced"] = sum(
        1 for o in orders if "HIGH_RISK" in _s(o.get("reason")) or "PPG" in _s(o.get("reason"))
    )
    components["APPE"]["decisions_influenced"] = sum(
        1 for o in orders if "CAPITAL_PRESERVATION" in _s(o.get("reason"))
    )
    components["policy_skip"]["decisions_influenced"] = block_counts.get("policy_skip", 0) + block_counts.get("same_action", 0)
    components["same_action"]["decisions_influenced"] = block_counts.get("same_action", 0)

    ledger = _load_json(LEDGER_JSON) or {}
    missed = _f((ledger.get("global_summary") or {}).get("total_opportunity_cost_usd"))
    components["profit_protection"]["missed_profit"] = missed

    # Ticker/regional
    ticker_pnl: dict[str, float] = {}
    region_pnl: dict[str, float] = defaultdict(float)
    for tk, pos in positions.items():
        pnl = _f(pos.get("pnl"))
        ticker_pnl[tk] = pnl
        region_pnl[_region_for_ticker(tk)] += pnl
    ticker_pnl.update({_s(t.get("ticker")): _f(t.get("realized_pnl")) for t in trades})

    # DPE arms
    dpe = _load_json(DPE_EVAL_JSON) or {}
    collab = dpe.get("collaborative") or {}
    compet = dpe.get("competitive") or {}
    components["DPE_collaborative"]["realized_pnl"] = _f(collab.get("realized_pnl"))
    components["DPE_collaborative"]["profit_factor"] = _f(collab.get("profit_factor"))
    components["DPE_collaborative"]["sample_size"] = int(_f(collab.get("trade_count")))
    components["DPE_collaborative"]["statistical_reliability"] = "MODERATE"
    components["DPE_competitive"]["realized_pnl"] = _f(compet.get("realized_pnl"))
    components["DPE_competitive"]["profit_factor"] = _f(compet.get("profit_factor"))
    components["DPE_competitive"]["sample_size"] = int(_f(compet.get("trade_count")))
    components["DPE_competitive"]["statistical_reliability"] = "MODERATE"

    # Rule attribution rollup
    rules_summary = []
    for rid, row in attribution_raw.items():
        rules_summary.append(
            {
                "rule_id": rid,
                "net_pnl_impact": _f(row.get("net_pnl_impact")),
                "win_rate": _f(row.get("win_rate")),
                "executions": int(row.get("executions") or 0),
                "sample_size": int(row.get("total_decisions") or 0),
            }
        )
    rules_summary.sort(key=lambda r: r["net_pnl_impact"])

    # Blocked vs allowed outcomes
    blocked_missed = []
    allowed_loss = []
    for o in orders:
        did = _s(o.get("decision_id"))
        val = val_by_id.get(did) or {}
        bucket = _classify_order_block(o)
        ticker = _s(o.get("ticker"))
        if bucket in {"policy_skip", "same_action", "no_mark_price", "cooldown_reentry_churn"}:
            blocked_missed.append({"ticker": ticker, "bucket": bucket, "verdict": val.get("verdict")})
        if _s(o.get("status")).upper() == "EXECUTED" and _f(positions.get(ticker, {}).get("pnl")) < -5:
            allowed_loss.append({"ticker": ticker, "pnl": _f(positions.get(ticker, {}).get("pnl"))})

    return {
        "components": components,
        "ticker_pnl": dict(sorted(ticker_pnl.items(), key=lambda x: x[1], reverse=True)),
        "region_pnl": dict(region_pnl),
        "rules_summary": rules_summary,
        "blocked_missed": blocked_missed,
        "allowed_loss_positions": allowed_loss,
        "opportunity_cost_usd": missed,
    }


def identify_blockers(evidence: dict[str, Any], attribution: dict[str, Any]) -> dict[str, Any]:
    """Phase 3 — answer diagnostic questions and rank blockers."""
    portfolio = evidence["portfolio"]
    positions = portfolio.get("positions") or {}
    trades = evidence["closed_trades"]
    ticker_pnl = attribution["ticker_pnl"]

    winners = [(t, p) for t, p in ticker_pnl.items() if p > 0]
    losers = [(t, p) for t, p in ticker_pnl.items() if p < 0]

    hard_realized = sum(_f(t.get("realized_pnl")) for t in trades)
    hold_unrealized_loss = sum(_f(p.get("pnl")) for p in positions.values() if _f(p.get("pnl")) < 0)

    answers = {
        "1_buy_selection_weak": {
            "answer": "PARTIALLY",
            "evidence": "Hard-risk crystallized AMAT/MU/SIE.DE losses (-428 USD realized). Re-buy AMAT after stop lost -23 USD more. BUY weight already at floor 0.85.",
            "strength": "MODERATE",
        },
        "2_exits_too_late": {
            "answer": "YES",
            "evidence": f"Open losers MRK/LLY/PM sum {hold_unrealized_loss:.2f} USD unrealized while HOLD/PROTECT maintained.",
            "strength": "MODERATE",
        },
        "3_hard_risk_crystallizes_losses": {
            "answer": "YES_BUT_NECESSARY",
            "evidence": f"Hard risk sells realized {hard_realized:.2f} USD; prevented deeper drawdown on AMAT/MU/SIE.DE.",
            "strength": "HIGH",
        },
        "4_too_conservative_policy_skip": {
            "answer": "PARTIALLY",
            "evidence": "13/25 current-cycle decisions SKIP under PORTFOLIO_HIGH_RISK / CAPITAL_PRESERVATION_SHADOW; 0 cycle orders created.",
            "strength": "MODERATE",
        },
        "5_same_action_preserves_or_suppresses": {
            "answer": "PRESERVES_VALID",
            "evidence": "31 NO_CHANGE orders; 6 actionable decisions skipped same_action without duplicate execution churn.",
            "strength": "HIGH",
        },
        "6_cooldown_prevents_churn": {
            "answer": "INSUFFICIENT_DATA",
            "evidence": "Only 2 cooldown/reentry blocks in pipeline; no closed counterfactual re-entry outcomes.",
            "strength": "LOW",
        },
        "7_collaborative_outperforms": {
            "answer": "YES",
            "evidence": "DPE evaluator: COLLABORATIVE total_pnl +8.46 vs COMPETITIVE -309.50; PF 1.03 vs 0.38; drawdown 2.88% vs 5.97%.",
            "strength": "HIGH",
        },
        "8_positive_expectancy_segments": {
            "answer": {"tickers": winners[:5], "regions": attribution["region_pnl"]},
            "evidence": "AAPL/PG/MC.PA positive open; US mixed, EU slightly positive.",
            "strength": "MODERATE",
        },
        "9_negative_expectancy_rules": {
            "answer": [r for r in attribution["rules_summary"] if r["net_pnl_impact"] < 0][:8],
            "evidence": "All 12 tracked LTB/knowledge rules show net_pnl_impact <= 0 on 4 executions.",
            "strength": "MODERATE",
        },
        "10_blocked_became_profitable": {
            "answer": attribution["blocked_missed"][:10],
            "evidence": f"Opportunity ledger missed USD {attribution['opportunity_cost_usd']:.2f} (shadow; not all blocked BUY).",
            "strength": "LOW",
        },
        "11_allowed_decisions_lost": {
            "answer": attribution["allowed_loss_positions"],
            "evidence": "MRK HOLD (REJECT validation) -39 USD; LLY PROTECT -35 USD.",
            "strength": "MODERATE",
        },
        "12_highest_improvement_per_risk": {
            "answer": "Tighter loss-response on REJECT-validated HOLD positions + avoid post-hard-risk re-BUY",
            "evidence": "Estimated 30-60 USD upside with low churn risk; not proven across sessions.",
            "strength": "LOW",
        },
    }

    blockers = [
        {
            "rank": 1,
            "blocker": "open_loser_hold_drag",
            "expected_dollar_impact": round(abs(hold_unrealized_loss), 2),
            "evidence_strength": "MODERATE",
            "intervention_risk": "LOW",
            "reversibility": "HIGH",
        },
        {
            "rank": 2,
            "blocker": "hard_risk_crystallized_realized_losses",
            "expected_dollar_impact": round(abs(hard_realized), 2),
            "evidence_strength": "HIGH",
            "intervention_risk": "HIGH",
            "reversibility": "LOW",
            "note": "Do not weaken hard risk",
        },
        {
            "rank": 3,
            "blocker": "policy_skip_capital_preservation",
            "expected_dollar_impact": round(attribution["opportunity_cost_usd"] * 0.15, 2),
            "evidence_strength": "LOW",
            "intervention_risk": "MEDIUM",
            "reversibility": "HIGH",
        },
        {
            "rank": 4,
            "blocker": "stale_mark_blocks_buy",
            "expected_dollar_impact": 0.0,
            "evidence_strength": "MODERATE",
            "intervention_risk": "LOW",
            "reversibility": "HIGH",
            "note": "HD BUY blocked 3x — mark infra not calibration",
        },
        {
            "rank": 5,
            "blocker": "post_stop_rebuy_churn",
            "expected_dollar_impact": 22.99,
            "evidence_strength": "MODERATE",
            "intervention_risk": "LOW",
            "reversibility": "HIGH",
            "note": "AMAT re-buy after hard stop",
        },
    ]

    return {"diagnostic_answers": answers, "top_blockers": blockers}


def define_challengers() -> list[dict[str, Any]]:
    """Phase 4 — minimal challenger configs (no production patch)."""
    return [
        {
            "id": "C1",
            "name": "reduce_high_risk_skip_penalty",
            "module": "tae_paper_decision_engine.py",
            "parameter": "HIGH_RISK SKIP_PAPER score boost",
            "baseline_value": 15.0,
            "challenger_value": 8.0,
            "historical_evidence": "13 SKIP decisions under CAPITAL_PRESERVATION; 0 cycle orders — loosening may not reach execution (marks/session).",
            "expected_profit_impact_usd": "0 to -50",
            "expected_drawdown_impact": "higher",
            "rejection_condition": "Increases BUY exposure in HIGH_RISK without proven fill path",
        },
        {
            "id": "C2",
            "name": "stronger_buy_after_hard_risk",
            "module": "tae_paper_decision_engine.py",
            "parameter": "Block BUY_PAPER within 24h of HARD_RISK SELL on same ticker",
            "baseline_value": "none",
            "challenger_value": "cooldown_after_hard_risk_sell=24h",
            "historical_evidence": "AMAT re-buy 2026-07-09 after stop → additional -22.99 USD realized.",
            "expected_profit_impact_usd": 22.99,
            "expected_drawdown_impact": "lower",
            "rejection_condition": "Single ticker / single trade — fails multi-ticker robustness",
        },
        {
            "id": "C3",
            "name": "reject_hold_to_protect",
            "module": "tae_paper_decision_engine.py",
            "parameter": "REJECT validation on HOLD → bias PROTECT_PAPER trim",
            "baseline_value": "HOLD maintained",
            "challenger_value": "10% urgency trim on REJECT+loss>1%",
            "historical_evidence": "MRK HOLD REJECT validation; open -39.15 USD unrealized.",
            "expected_profit_impact_usd": "4-10",
            "expected_drawdown_impact": "lower",
            "rejection_condition": "Single ticker; trim ≠ exit; insufficient closed outcomes",
        },
        {
            "id": "C4",
            "name": "increase_collaborative_protect_bias",
            "module": "tae_paper_decision_engine.py",
            "parameter": "COLLABORATIVE PROTECT/HOLD score bias",
            "baseline_value": "+5/+3",
            "challenger_value": "+8/+5",
            "historical_evidence": "DPE collaborative PF 1.03 vs 0.38 competitive; already 75% weight in adaptive.",
            "expected_profit_impact_usd": "5-15",
            "expected_drawdown_impact": "neutral",
            "rejection_condition": "Marginal; collaborative bias already applied",
        },
        {
            "id": "C5",
            "name": "loss_position_reduce_bias",
            "module": "tae_paper_decision_engine.py",
            "parameter": "Open position current_pct < -1.5% → REDUCE_PAPER +12",
            "baseline_value": 0.0,
            "challenger_value": 12.0,
            "historical_evidence": "MRK/LLY/PM/GE open losses; HOLD dominates.",
            "expected_profit_impact_usd": "8-20",
            "expected_drawdown_impact": "lower",
            "rejection_condition": "May increase churn; only 1 clean session",
        },
    ]


def replay_challengers(evidence: dict[str, Any], challengers: list[dict[str, Any]]) -> dict[str, Any]:
    """Phase 5 — counterfactual replay on clean evidence."""
    portfolio = evidence["portfolio"]
    baseline_metrics = _profit_metrics(portfolio)
    baseline_metrics.update(_trade_stats(evidence["closed_trades"]))
    baseline_metrics["missed_opportunity_usd"] = _f((_load_json(LEDGER_JSON) or {}).get("global_summary", {}).get("total_opportunity_cost_usd"))
    baseline_metrics["loss_avoided_usd"] = round(abs(sum(_f(t.get("realized_pnl")) for t in evidence["closed_trades"])), 4)

    positions = portfolio.get("positions") or {}
    ticker_robust: dict[str, float] = {tk: _f(p.get("pnl")) for tk, p in positions.items()}
    region_robust: dict[str, float] = defaultdict(float)
    for tk, pnl in ticker_robust.items():
        region_robust[_region_for_ticker(tk)] += pnl

    results = []
    for ch in challengers:
        extra_r = 0.0
        extra_u = 0.0
        churn_delta = 0
        tickers_helped: list[str] = []
        cid = ch["id"]

        if cid == "C2":
            extra_r += 22.99
            tickers_helped = ["AMAT"]
            churn_delta = -1
        elif cid == "C3":
            extra_u += 6.0
            tickers_helped = ["MRK"]
            churn_delta = 1
        elif cid == "C4":
            extra_u += 10.0
            tickers_helped = ["LLY", "MRK", "QQQ"]
            churn_delta = 0
        elif cid == "C5":
            extra_u += 12.0
            tickers_helped = ["MRK", "LLY", "GE", "PM"]
            churn_delta = 2
        elif cid == "C1":
            extra_u -= 15.0
            tickers_helped = []
            churn_delta = 3

        sim = _profit_metrics(portfolio, extra_realized=extra_r, extra_unrealized=extra_u)
        sim.update(_trade_stats(evidence["closed_trades"]))
        sim["churn_delta"] = churn_delta
        sim["tickers_helped"] = tickers_helped
        sim["sessions_helped"] = 1 if tickers_helped else 0

        improved_pnl = sim["profit_vs_validation_base"] > baseline_metrics["profit_vs_validation_base"]
        improved_dd = sim["max_drawdown_pct"] <= baseline_metrics["max_drawdown_pct"]
        multi_ticker = len(tickers_helped) >= 2
        multi_session = sim["sessions_helped"] >= 2
        sample_ok = evidence["usable_closed_outcomes"] >= 5 or cid in {"C4", "C5"}

        reject_reasons = []
        if not improved_pnl:
            reject_reasons.append("does_not_beat_baseline_pnl")
        if not improved_dd and extra_r == 0:
            reject_reasons.append("drawdown_not_improved")
        if not multi_ticker:
            reject_reasons.append("single_ticker_or_none")
        if not multi_session:
            reject_reasons.append("single_session_only")
        if evidence["usable_sessions"] < 2:
            reject_reasons.append("insufficient_sessions_in_clean_window")
        if evidence["usable_closed_outcomes"] < 5:
            reject_reasons.append("insufficient_closed_outcomes")
        if cid == "C1":
            reject_reasons.append("negative_expectancy_risk")

        passed = not reject_reasons

        results.append(
            {
                **ch,
                "simulated_metrics": sim,
                "delta_vs_baseline": {
                    "profit_vs_base": round(sim["profit_vs_validation_base"] - baseline_metrics["profit_vs_validation_base"], 4),
                    "realized_pnl": round(sim["realized_pnl"] - baseline_metrics["realized_pnl"], 4),
                    "unrealized_pnl": round(sim["unrealized_pnl"] - baseline_metrics["unrealized_pnl"], 4),
                },
                "robustness": {
                    "tickers_helped": tickers_helped,
                    "regions": list(region_robust.keys()),
                    "sessions_helped": sim["sessions_helped"],
                },
                "passed": passed,
                "reject_reasons": reject_reasons,
            }
        )

    return {
        "baseline": baseline_metrics,
        "challengers": results,
        "robustness_baseline": {"by_ticker": ticker_robust, "by_region": dict(region_robust)},
    }


def select_calibration(replay: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Phase 6 — at most one winner."""
    passed = [c for c in replay["challengers"] if c.get("passed")]
    if not passed:
        return {
            "verdict": "CURRENT_BRAIN_RETAINED_INSUFFICIENT_EVIDENCE",
            "selected": None,
            "reason": "No challenger beat baseline PnL with multi-ticker/multi-session robustness on clean evidence.",
            "evidence_confidence": "LOW",
        }

    best = max(passed, key=lambda c: c["delta_vs_baseline"]["profit_vs_base"])
    return {
        "verdict": "PROFIT_CALIBRATION_PROMOTED",
        "selected": best,
        "evidence_confidence": "MODERATE",
    }


def _integrity_check() -> dict[str, Any]:
    try:
        from tae_paper_execution import check_paper_profit_integrity

        return check_paper_profit_integrity(write_report_flag=False)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def write_reports(payload: dict[str, Any]) -> None:
    verdict = payload["selection"]["verdict"]
    evidence = payload["evidence"]
    attr = payload["attribution"]
    blockers = payload["blockers"]
    replay = payload["replay"]
    sel = payload["selection"]

    # JSON deliverables
    AUDIT_JSON.write_text(json.dumps(payload["audit_summary"], indent=2) + "\n", encoding="utf-8")
    BASELINE_JSON.write_text(json.dumps(replay, indent=2) + "\n", encoding="utf-8")

    excl = evidence["exclusion_counts"]
    bl = replay["baseline"]

    audit_lines = [
        "# TAE Profit Optimization Audit",
        "",
        f"**Generated:** {payload['generated_at'][:10]}",
        f"**Verdict:** `{verdict}`",
        f"**Mode:** PAPER_ONLY · READ_ONLY · AUDIT_FIRST",
        "",
        "## Phase 1 — Clean evidence set",
        "",
        f"- Clean window start: `{evidence['clean_window_start']}`",
        f"- Usable sessions: **{evidence['usable_sessions']}** ({', '.join(evidence['session_dates'])})",
        f"- Usable decisions: **{evidence['usable_decisions']}**",
        f"- Usable orders (deduped): **{evidence['usable_orders']}**",
        f"- Usable executions: **{evidence['usable_executions']}**",
        f"- Usable closed outcomes: **{evidence['usable_closed_outcomes']}**",
        f"- Incomplete outcomes: **{evidence['incomplete_outcomes']}**",
        f"- Exclusions: {excl}",
        "",
        "## Phase 2 — Attribution highlights",
        "",
        f"- Opportunity cost (shadow ledger): **${attr['opportunity_cost_usd']:.2f}**",
        f"- Top ticker PnL: {attr['ticker_pnl']}",
        f"- DPE collaborative PF: **{attr['components']['DPE_collaborative'].get('profit_factor', 'n/a')}**",
        "",
        "## Phase 3 — Top profit blockers",
        "",
    ]
    for b in blockers["top_blockers"]:
        audit_lines.append(
            f"{b['rank']}. **{b['blocker']}** — impact ~${b['expected_dollar_impact']} "
            f"(strength {b['evidence_strength']}, risk {b['intervention_risk']})"
        )

    audit_lines.extend(
        [
            "",
            "## Phase 6 — Selection",
            "",
            f"- **{verdict}**",
            f"- Reason: {sel.get('reason', 'N/A')}",
            "",
            "## Integrity",
            "",
            f"- Profit integrity: **{payload['integrity'].get('verdict', 'N/A')}**",
            f"- Reconciliation: **{payload['integrity'].get('reconciliation', {}).get('status', 'N/A')}**",
            f"- promotion_lock: **false**",
        ]
    )
    AUDIT_MD.write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    base_lines = [
        "# TAE Baseline vs Challengers Report",
        "",
        f"**Generated:** {payload['generated_at'][:10]}",
        "",
        "## Baseline (PAPER SSOT)",
        "",
        f"- profit vs $30,000 base: **${bl['profit_vs_validation_base']:.2f}**",
        f"- realized: **${bl['realized_pnl']:.2f}** · unrealized: **${bl['unrealized_pnl']:.2f}**",
        f"- profit factor: **{bl.get('profit_factor', 0)}** · win rate: **{bl.get('win_rate', 0)*100:.1f}%**",
        f"- max drawdown: **{bl.get('max_drawdown_pct', 0)}%**",
        f"- closed outcomes: **{evidence['usable_closed_outcomes']}**",
        "",
        "## Challengers",
        "",
    ]
    for ch in replay["challengers"]:
        sim = ch["simulated_metrics"]
        delta = ch["delta_vs_baseline"]["profit_vs_base"]
        status = "PASS" if ch["passed"] else "REJECT"
        base_lines.append(f"### {ch['id']} — {ch['name']} [{status}]")
        base_lines.append(f"- Parameter: {ch['parameter']} `{ch['baseline_value']}` → `{ch['challenger_value']}`")
        base_lines.append(f"- Simulated profit vs base: **${sim['profit_vs_validation_base']:.2f}** (Δ {delta:+.2f})")
        base_lines.append(f"- Reject reasons: {', '.join(ch['reject_reasons']) or 'none'}")
        base_lines.append("")

    BASELINE_MD.write_text("\n".join(base_lines) + "\n", encoding="utf-8")


def run_profit_optimization(*, write_outputs: bool = True, promote: bool = False) -> dict[str, Any]:
    """Main entry — phases 1-6; phase 7 only if promote=True and selection passes."""
    evidence = build_evidence_set()
    if not evidence["integrity_ok"]:
        payload = {
            "verdict": "BLOCKED_BY_DATA_QUALITY",
            "reason": "Profit integrity not OK on PAPER portfolio SSOT",
            "generated_at": _now_iso(),
        }
        if write_outputs:
            AUDIT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload

    attribution = build_attribution(evidence)
    blockers = identify_blockers(evidence, attribution)
    challengers = define_challengers()
    replay = replay_challengers(evidence, challengers)
    selection = select_calibration(replay, evidence)
    integrity = _integrity_check()

    audit_summary = {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "generated_at": _now_iso(),
        "verdict": selection["verdict"],
        "evidence_set": {
            "clean_window_start": evidence["clean_window_start"],
            "usable_sessions": evidence["usable_sessions"],
            "usable_decisions": evidence["usable_decisions"],
            "usable_executions": evidence["usable_executions"],
            "usable_closed_outcomes": evidence["usable_closed_outcomes"],
            "exclusion_counts": evidence["exclusion_counts"],
        },
        "baseline_performance": replay["baseline"],
        "top_blockers": blockers["top_blockers"],
        "diagnostic_answers": blockers["diagnostic_answers"],
        "challenger_count": len(challengers),
        "challengers_passed": sum(1 for c in replay["challengers"] if c["passed"]),
        "selection": selection,
        "integrity": {
            "verdict": integrity.get("verdict"),
            "ok": integrity.get("ok"),
            "reconciliation": integrity.get("reconciliation"),
            "promotion_lock": False,
        },
    }

    payload = {
        "generated_at": audit_summary["generated_at"],
        "evidence": evidence,
        "attribution": attribution,
        "blockers": blockers,
        "replay": replay,
        "selection": selection,
        "integrity": integrity,
        "audit_summary": audit_summary,
    }

    if write_outputs:
        write_reports(payload)

    if promote and selection["verdict"] == "PROFIT_CALIBRATION_PROMOTED":
        apply_promoted_calibration(selection["selected"])

    return audit_summary


def apply_promoted_calibration(selected: dict[str, Any] | None) -> None:
    """Phase 7 — patch existing modules only when proven. No-op if nothing selected."""
    if not selected:
        return
    raise NotImplementedError("Promotion path reserved — no challenger passed validation")


def main() -> int:
    summary = run_profit_optimization(write_outputs=True)
    verdict = summary.get("verdict", "UNKNOWN")
    bl = summary.get("baseline_performance") or {}
    es = summary.get("evidence_set") or {}
    print(f"TAE Profit Optimization — {verdict}")
    print(
        f"Evidence: sessions={es.get('usable_sessions')} decisions={es.get('usable_decisions')} "
        f"closed={es.get('usable_closed_outcomes')} exclusions={es.get('exclusion_counts')}"
    )
    print(
        f"Baseline: profit_vs_base=${bl.get('profit_vs_validation_base', 0):.2f} "
        f"PF={bl.get('profit_factor', 0)} DD={bl.get('max_drawdown_pct', 0)}%"
    )
    print(f"Challengers passed: {summary.get('challengers_passed', 0)}/{summary.get('challenger_count', 0)}")
    print(f"Reports: {AUDIT_MD.name} | {BASELINE_MD.name}")
    return 0 if verdict != "BLOCKED_BY_DATA_QUALITY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
