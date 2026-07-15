#!/usr/bin/env python3
"""
TAE Profit Pipeline — READ_ONLY consolidation from existing artifacts.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_MUTATION
Joins existing producers; does not change decisions, execution, or portfolio.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "PAPER_ONLY"
SCHEMA = "tae_profit_pipeline"
VERSION = "v1"

ROOT = Path(".")

SIGNALS_CSV = ROOT / "live_signals.csv"
GII_JSON = ROOT / "tae_growth_intelligence.json"
LEDGER_JSON = ROOT / "tae_opportunity_cost_ledger.json"
DECISIONS_JSON = ROOT / "runtime_outputs/paper_decisions/paper_decisions.json"
DECISION_STATE_JSON = ROOT / "runtime_outputs/decision_state/active_decisions.json"
CONFLICTS_JSON = ROOT / "runtime_outputs/conflict_resolution/conflicts.json"
ORDERS_JSONL = ROOT / "runtime_outputs/paper_execution/paper_orders.jsonl"
TRADES_JSONL = ROOT / "runtime_outputs/paper_execution/paper_trades.jsonl"
PORTFOLIO_JSON = ROOT / "runtime_outputs/paper_execution/paper_portfolio.json"
VALIDATION_JSON = ROOT / "runtime_outputs/paper_decisions/decision_validation_results.json"
MEMORY_JSONL = ROOT / "runtime_outputs/longitudinal_memory/decisions.jsonl"
ATTRIBUTION_JSON = ROOT / "runtime_outputs/paper_execution/rule_outcome_attribution.json"
ATTRIBUTION_JSON_ALT = ROOT / "runtime_outputs/rule_outcome_attribution.json"
INTEGRITY_JSON = ROOT / "tae_paper_profit_integrity_guard_report.json"

REPORT_MD = ROOT / "TAE_PROFIT_PIPELINE_REPORT.md"
REPORT_JSON = ROOT / "tae_profit_pipeline.json"

ACTIONABLE_ACTIONS = frozenset(
    {"BUY_PAPER", "SELL_PAPER", "PROTECT_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"}
)
BLOCK_BUCKETS = (
    "same_action",
    "switch_not_authorized",
    "no_mark_price",
    "fake_profit_risk",
    "market_closed",
    "no_position",
    "hard_risk",
    "cooldown_reentry_churn",
    "policy_skip",
    "no_change",
    "executed",
    "other",
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
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text[:19] if "T" not in text else text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
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


def _read_signals() -> dict[str, dict[str, Any]]:
    by_ticker: dict[str, dict[str, Any]] = {}
    if not SIGNALS_CSV.is_file():
        return by_ticker
    try:
        with SIGNALS_CSV.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = _s(row.get("Ticker")).upper()
                if not ticker:
                    continue
                by_ticker[ticker] = {
                    "ticker": ticker,
                    "time": _s(row.get("Time")),
                    "price": _f(row.get("Price")),
                    "score": _f(row.get("Score")),
                    "signal": _s(row.get("Signal")),
                    "rsi": _f(row.get("RSI")),
                    "join_confidence": "TICKER",
                }
    except OSError:
        pass
    return by_ticker


def _index_gii_opportunities(gii: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in (gii or {}).get("tickers") or []:
        ticker = _s(row.get("ticker")).upper()
        if ticker:
            out[ticker] = row
    portfolio = (gii or {}).get("portfolio") or {}
    if not out and portfolio:
        out["_PORTFOLIO"] = portfolio
    return out


def _index_ledger(ledger: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = (
        (ledger or {}).get("ledger")
        or (ledger or {}).get("entries")
        or (ledger or {}).get("tickers")
        or []
    )
    for row in rows:
        ticker = _s(row.get("ticker")).upper()
        if ticker:
            out[ticker] = row
    return out


def _index_validation(validation: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in (validation or {}).get("results") or []:
        did = _s(row.get("decision_id") or row.get("source_decision_id"))
        if did:
            out[did] = row
    return out


def _index_memory(memory_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in memory_rows:
        did = _s(row.get("decision_id"))
        if did:
            out[did] = row
    return out


def _latest_orders_by_decision(
    orders: list[dict[str, Any]],
    *,
    cycle_ts: datetime | None,
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for order in orders:
        did = _s(order.get("decision_id"))
        if not did:
            continue
        ts = _parse_ts(order.get("timestamp"))
        if cycle_ts and ts and ts < cycle_ts:
            continue
        prev = by_id.get(did)
        if not prev:
            by_id[did] = order
            continue
        prev_ts = _parse_ts(prev.get("timestamp"))
        if ts and prev_ts and ts >= prev_ts:
            by_id[did] = order
    return by_id


def _trades_by_decision(
    trades: list[dict[str, Any]],
    *,
    cycle_ts: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for trade in trades:
        did = _s(trade.get("decision_id"))
        if not did:
            continue
        ts = _parse_ts(trade.get("timestamp"))
        if cycle_ts and ts and ts < cycle_ts:
            continue
        prev = by_id.get(did)
        prev_ts = _parse_ts((prev or {}).get("timestamp"))
        if not prev or (ts and prev_ts and ts >= prev_ts):
            by_id[did] = trade
    return by_id


def _conflict_by_ticker(conflicts: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in (conflicts or {}).get("tickers") or []:
        ticker = _s(row.get("ticker")).upper()
        if ticker:
            out[ticker] = row
    return out


def _classify_block(
    *,
    decision: dict[str, Any],
    order: dict[str, Any] | None,
    inferred_skip: str | None,
) -> str:
    if order:
        status = _s(order.get("status")).upper()
        reason = _s(order.get("reason")).lower()
        if status == "EXECUTED":
            if "hard risk" in reason:
                return "hard_risk"
            return "executed"
        if status == "SKIPPED_SWITCH_NOT_AUTHORIZED":
            return "switch_not_authorized"
        if status == "SKIPPED_NO_MARK_PRICE":
            return "no_mark_price"
        if status == "SKIPPED_NO_POSITION":
            return "no_position"
        if status == "BLOCKED_FAKE_PROFIT_RISK":
            return "fake_profit_risk"
        if status == "NO_CHANGE":
            return "no_change"
        if "market closed" in reason or "session" in reason:
            return "market_closed"
        if "cooldown" in reason or "churn" in reason or "reentry" in reason:
            return "cooldown_reentry_churn"
        if "hard risk" in reason or "hard stop" in reason:
            return "hard_risk"
        return "other"
    if inferred_skip == "skipped_same_action":
        return "same_action"
    action = _s(decision.get("action")).upper()
    if action == "SKIP_PAPER":
        return "policy_skip"
    if not decision.get("decision_switch_authorized") and decision.get("previous_action"):
        return "switch_not_authorized"
    churn = _s(decision.get("churn_risk")).upper()
    cooldown = decision.get("cooldown_status") or {}
    if churn in {"HIGH", "MEDIUM"} or cooldown.get("active"):
        return "cooldown_reentry_churn"
    if (decision.get("hard_risk_discipline") or {}).get("override"):
        return "hard_risk"
    return "other"


def _opportunity_row(
    ticker: str,
    gii_by: dict[str, dict[str, Any]],
    ledger_by: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gii = gii_by.get(ticker) or {}
    led = ledger_by.get(ticker) or {}
    missed = _f(gii.get("missed_usd") or led.get("missed_usd"))
    category = _s(led.get("opportunity_cost_category") or gii.get("opportunity_category"))
    has_opp = missed > 0 or bool(category) or bool(gii)
    return {
        "has_opportunity": has_opp,
        "missed_usd": missed,
        "category": category or None,
        "growth_score": _f(gii.get("growth_score")),
        "join_confidence": "TICKER" if gii or led else "LOW_CONFIDENCE_JOIN",
    }


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def build_profit_pipeline(*, write_outputs: bool = True) -> dict[str, Any]:
    signals = _read_signals()
    gii = _load_json(GII_JSON)
    ledger = _load_json(LEDGER_JSON)
    decisions_doc = _load_json(DECISIONS_JSON) or {}
    decision_state = _load_json(DECISION_STATE_JSON)
    conflicts = _load_json(CONFLICTS_JSON)
    orders_all = _load_jsonl(ORDERS_JSONL)
    trades_all = _load_jsonl(TRADES_JSONL)
    portfolio = _load_json(PORTFOLIO_JSON) or {}
    validation = _load_json(VALIDATION_JSON)
    memory = _index_memory(_load_jsonl(MEMORY_JSONL))
    integrity = _load_json(INTEGRITY_JSON)
    if portfolio:
        try:
            from tae_paper_execution import check_paper_profit_integrity

            accounting = _load_json(ROOT / "tae_accounting_snapshot.json")
            integrity = check_paper_profit_integrity(
                portfolio=portfolio,
                accounting=accounting,
                write_report_flag=False,
                update_validation_json=False,
            )
        except Exception:
            pass
    attribution = _load_json(ATTRIBUTION_JSON) or _load_json(ATTRIBUTION_JSON_ALT) or {}

    cycle_ts = _parse_ts(decisions_doc.get("generated_at"))
    decisions = list(decisions_doc.get("decisions") or [])
    gii_by = _index_gii_opportunities(gii)
    ledger_by = _index_ledger(ledger)
    val_by = _index_validation(validation)
    conflict_by = _conflict_by_ticker(conflicts)
    orders_by = _latest_orders_by_decision(orders_all, cycle_ts=cycle_ts)
    trades_by = _trades_by_decision(trades_all, cycle_ts=cycle_ts)
    state_tickers = (decision_state or {}).get("tickers") or {}

    opportunity_tickers = set(gii_by) | set(ledger_by) | set(signals) | {d.get("ticker") for d in decisions}
    opportunity_tickers.discard("_PORTFOLIO")
    opportunity_tickers = {t for t in opportunity_tickers if t}

    action_summary = Counter(_s(d.get("action")).upper() for d in decisions)
    actionable_decisions = [d for d in decisions if _s(d.get("action")).upper() in ACTIONABLE_ACTIONS]

    timelines: list[dict[str, Any]] = []
    block_rollup: Counter[str] = Counter()
    join_stats = {"decision_id": 0, "ticker_cycle": 0, "ticker_only": 0, "low_confidence": 0}
    missing_stages: Counter[str] = Counter()

    for decision in decisions:
        did = _s(decision.get("decision_id"))
        ticker = _s(decision.get("ticker")).upper()
        action = _s(decision.get("action")).upper()
        order = orders_by.get(did)
        trade = trades_by.get(did)
        val = val_by.get(did)
        mem = memory.get(did)
        signal = signals.get(ticker)
        opp = _opportunity_row(ticker, gii_by, ledger_by)
        state = state_tickers.get(ticker) or {}
        conflict = conflict_by.get(ticker) or {}

        inferred_skip = None
        join_method = "decision_id"
        join_confidence = "HIGH"
        if not order:
            if action in ACTIONABLE_ACTIONS:
                inferred_skip = "skipped_same_action"
                join_confidence = "INFERRED_NO_ORDER"
                join_stats["low_confidence"] += 1
            missing_stages["order"] += 1
        else:
            join_stats["decision_id"] += 1

        if not signal:
            missing_stages["signal"] += 1
            if opp.get("has_opportunity"):
                join_stats["ticker_only"] += 1
        else:
            if not did:
                join_stats["ticker_cycle"] += 1

        if not val:
            missing_stages["validation"] += 1

        block_bucket = _classify_block(decision=decision, order=order, inferred_skip=inferred_skip)
        block_rollup[block_bucket] += 1

        pos = (portfolio.get("positions") or {}).get(ticker) or {}
        realized = _f((trade or {}).get("realized_pnl") or (order or {}).get("realized_pnl"))
        unrealized = _f(pos.get("pnl"))
        current_pnl = realized if realized != 0 else unrealized

        gate_result = {
            "decision_switch_authorized": decision.get("decision_switch_authorized"),
            "switch_reason": decision.get("switch_reason"),
            "churn_risk": decision.get("churn_risk"),
            "cooldown_active": (decision.get("cooldown_status") or {}).get("active"),
            "hard_risk_override": bool((decision.get("hard_risk_discipline") or {}).get("override")),
            "conflict_winner": conflict.get("winner_action"),
            "state_last_action": state.get("last_action"),
        }

        timelines.append(
            {
                "decision_id": did,
                "ticker": ticker,
                "join_method": join_method,
                "join_confidence": join_confidence,
                "opportunity": opp,
                "signal": signal,
                "pde_decision": {
                    "action": action,
                    "confidence": _f(decision.get("confidence")),
                    "expected_profit_delta": _f(decision.get("expected_profit_delta")),
                    "evidence": _s(decision.get("evidence"))[:240],
                    "created_at": decision.get("created_at") or decisions_doc.get("generated_at"),
                },
                "gate_result": gate_result,
                "order": {
                    "timestamp": (order or {}).get("timestamp"),
                    "status": (order or {}).get("status") or inferred_skip or "MISSING",
                    "executed": bool((order or {}).get("executed")),
                    "block_bucket": block_bucket,
                    "fill_price": _f((order or {}).get("fill_price") or (order or {}).get("price")),
                    "mark_source": pos.get("mark_source"),
                    "mark_status": pos.get("mark_status"),
                    "reason": _s((order or {}).get("reason"))[:200] if order else inferred_skip,
                },
                "trade": {
                    "exists": trade is not None,
                    "realized_pnl": realized,
                    "fill_shares": _f((trade or {}).get("fill_shares")),
                },
                "pnl": {
                    "realized_pnl": realized,
                    "unrealized_pnl": unrealized,
                    "current_pnl": current_pnl,
                },
                "validation": {
                    "verdict": (val or {}).get("verdict"),
                    "profit_delta": _f((val or {}).get("profit_delta")),
                },
                "rule_attribution": list((order or {}).get("rule_sources") or [])[:8],
                "memory_verdict": (mem or {}).get("validation_verdict"),
            }
        )

    orders_created_cycle = sum(1 for t in timelines if t["order"]["status"] not in {"MISSING", "skipped_same_action"})
    orders_executed = sum(1 for t in timelines if t["order"].get("executed"))
    orders_blocked_skipped = sum(
        1
        for t in timelines
        if t["order"]["block_bucket"]
        not in {"executed", "no_change", "policy_skip"}
        and not t["order"].get("executed")
    )
    trades_written = sum(1 for t in timelines if t["trade"]["exists"])

    realized_pnl = _f(portfolio.get("realized_pnl"))
    unrealized_pnl = _f(portfolio.get("unrealized_pnl"))
    total_value = _f(portfolio.get("total_value"))
    capital_base = _f(portfolio.get("validation_capital_base") or 30000.0)
    profit_vs_base = round(total_value - capital_base, 2)

    opp_with_signal = sum(1 for t in timelines if t["opportunity"]["has_opportunity"] and t.get("signal"))
    opp_count = len(opportunity_tickers) or len(timelines)
    signal_count = len(signals)
    actionable_count = len(actionable_decisions)

    conv_opp_signal = round(opp_with_signal / opp_count, 4) if opp_count else 0.0
    conv_signal_actionable = round(
        sum(1 for t in timelines if t.get("signal") and t["pde_decision"]["action"] in ACTIONABLE_ACTIONS)
        / max(signal_count, 1),
        4,
    )
    conv_actionable_order = round(orders_created_cycle / max(actionable_count, 1), 4)
    conv_order_execution = round(orders_executed / max(orders_created_cycle, 1), 4)
    profitable_exec = sum(1 for t in timelines if t["order"].get("executed") and t["pnl"]["current_pnl"] > 0)
    conv_execution_profitable = round(profitable_exec / max(orders_executed, 1), 4)

    attribution_rules = (attribution.get("rules") or {}) if isinstance(attribution.get("rules"), dict) else {}
    rule_rows = sorted(
        attribution_rules.values(),
        key=lambda r: _f(r.get("net_pnl_impact")),
        reverse=True,
    )
    top_profit = [r for r in rule_rows if _f(r.get("net_pnl_impact")) > 0][:5]
    top_loss = sorted(
        [r for r in rule_rows if _f(r.get("net_pnl_impact")) < 0],
        key=lambda r: _f(r.get("net_pnl_impact")),
    )[:5]

    profitable_decisions = [t for t in timelines if t["pnl"]["current_pnl"] > 0]
    losing_decisions = [t for t in timelines if t["pnl"]["current_pnl"] < 0]
    blocked_avoided_loss = [
        t
        for t in timelines
        if t["order"]["block_bucket"] in {"switch_not_authorized", "no_mark_price", "fake_profit_risk", "same_action"}
        and _f(t["pde_decision"]["expected_profit_delta"]) < 0
    ]
    blocked_missed_profit = [
        t
        for t in timelines
        if t["order"]["block_bucket"] in {"switch_not_authorized", "no_mark_price", "same_action", "policy_skip"}
        and _f(t["pde_decision"]["expected_profit_delta"]) > 0
    ]
    unresolved = [
        t
        for t in timelines
        if _s(t["validation"].get("verdict")) in {"NEEDS_MORE_DATA", ""}
        or t["validation"].get("verdict") is None
    ]

    stale_marks = sum(
        1
        for t in timelines
        if _s((t.get("order") or {}).get("mark_status")).upper() not in {"", "DATA_OK"}
        and t["order"].get("mark_status")
    )

    integrity_ok = bool((integrity or {}).get("ok"))
    reconciliation = (integrity or {}).get("reconciliation") or {}
    reconciliation_ok = bool(reconciliation.get("ok"))
    if integrity and not reconciliation_ok:
        reconciliation_ok = any(
            c.get("pass") for c in (integrity.get("checks") or []) if c.get("name") == "portfolio_reconciliation"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_portfolio_mutation": True,
        "generated_at": _now_iso(),
        "cycle_generated_at": decisions_doc.get("generated_at"),
        "summary": {
            "opportunities_detected": len(opportunity_tickers),
            "signals_generated": signal_count,
            "final_decisions": len(decisions),
            "final_buy": int(action_summary.get("BUY_PAPER", 0)),
            "final_sell": int(action_summary.get("SELL_PAPER", 0)),
            "final_hold": int(action_summary.get("HOLD_PAPER", 0)),
            "final_skip": int(action_summary.get("SKIP_PAPER", 0)),
            "final_protect": int(action_summary.get("PROTECT_PAPER", 0)),
            "actionable_decisions": actionable_count,
            "orders_created": orders_created_cycle,
            "orders_executed": orders_executed,
            "orders_blocked_skipped": orders_blocked_skipped,
            "trades_written": trades_written,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_value": total_value,
            "validation_capital_base": capital_base,
            "profit_vs_validation_capital_base": profit_vs_base,
        },
        "conversion_metrics": {
            "opportunity_to_signal": {
                "numerator": opp_with_signal,
                "denominator": opp_count,
                "rate": conv_opp_signal,
            },
            "signal_to_actionable_decision": {
                "numerator": sum(
                    1 for t in timelines if t.get("signal") and t["pde_decision"]["action"] in ACTIONABLE_ACTIONS
                ),
                "denominator": signal_count,
                "rate": conv_signal_actionable,
            },
            "actionable_decision_to_order": {
                "numerator": orders_created_cycle,
                "denominator": actionable_count,
                "rate": conv_actionable_order,
            },
            "order_to_execution": {
                "numerator": orders_executed,
                "denominator": orders_created_cycle,
                "rate": conv_order_execution,
            },
            "execution_to_profitable_outcome": {
                "numerator": profitable_exec,
                "denominator": orders_executed,
                "rate": conv_execution_profitable,
            },
        },
        "block_reason_rollup": dict(block_rollup),
        "timelines": timelines,
        "profit_attribution": {
            "top_profit_contributors": top_profit,
            "top_loss_contributors": top_loss,
            "profitable_decisions": [
                {"decision_id": t["decision_id"], "ticker": t["ticker"], "pnl": t["pnl"]["current_pnl"]}
                for t in sorted(profitable_decisions, key=lambda x: -x["pnl"]["current_pnl"])[:8]
            ],
            "losing_decisions": [
                {"decision_id": t["decision_id"], "ticker": t["ticker"], "pnl": t["pnl"]["current_pnl"]}
                for t in sorted(losing_decisions, key=lambda x: x["pnl"]["current_pnl"])[:8]
            ],
            "blocked_avoided_loss_count": len(blocked_avoided_loss),
            "blocked_missed_profit_count": len(blocked_missed_profit),
            "unresolved_outcomes_count": len(unresolved),
        },
        "data_quality": {
            "join_coverage": {
                "decision_id": join_stats["decision_id"],
                "ticker_cycle": join_stats["ticker_cycle"],
                "ticker_only": join_stats["ticker_only"],
                "low_confidence_joins": join_stats["low_confidence"],
                "total_decisions": len(decisions),
                "decision_id_coverage_pct": round(100.0 * join_stats["decision_id"] / max(len(decisions), 1), 1),
            },
            "missing_stages": dict(missing_stages),
            "stale_or_fallback_marks": stale_marks,
            "profit_integrity_status": (integrity or {}).get("verdict") or (integrity or {}).get("status"),
            "profit_integrity_ok": integrity_ok,
            "reconciliation_status": "PASS" if reconciliation_ok else "FAIL",
            "reconciliation_ok": reconciliation_ok,
            "promotion_lock": False,
            "duplicate_timeline_rows": 0,
        },
        "sources": {
            "live_signals.csv": SIGNALS_CSV.is_file(),
            "tae_growth_intelligence.json": GII_JSON.is_file(),
            "tae_opportunity_cost_ledger.json": LEDGER_JSON.is_file(),
            "paper_decisions.json": DECISIONS_JSON.is_file(),
            "active_decisions.json": DECISION_STATE_JSON.is_file(),
            "conflicts.json": CONFLICTS_JSON.is_file(),
            "paper_orders.jsonl": ORDERS_JSONL.is_file(),
            "paper_trades.jsonl": TRADES_JSONL.is_file(),
            "paper_portfolio.json": PORTFOLIO_JSON.is_file(),
            "decision_validation_results.json": VALIDATION_JSON.is_file(),
            "longitudinal_memory/decisions.jsonl": MEMORY_JSONL.is_file(),
            "rule_outcome_attribution.json": ATTRIBUTION_JSON.is_file() or ATTRIBUTION_JSON_ALT.is_file(),
        },
    }

    if write_outputs:
        write_profit_pipeline_report(payload)
    return payload


def write_profit_pipeline_report(payload: dict[str, Any]) -> None:
    summary = payload.get("summary") or {}
    conv = payload.get("conversion_metrics") or {}
    blocks = payload.get("block_reason_rollup") or {}
    dq = payload.get("data_quality") or {}
    attr = payload.get("profit_attribution") or {}

    lines = [
        "# TAE Profit Pipeline Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Mode:** {MODE} — READ_ONLY — NO_BROKER — NO_PORTFOLIO_MUTATION",
        f"**Decision cycle:** {payload.get('cycle_generated_at')}",
        "",
        "## Pipeline summary",
        "",
        f"- Opportunities detected: **{summary.get('opportunities_detected')}**",
        f"- Signals generated: **{summary.get('signals_generated')}**",
        f"- Final decisions: **{summary.get('final_decisions')}** "
        f"(BUY {summary.get('final_buy')} / SELL {summary.get('final_sell')} / "
        f"HOLD {summary.get('final_hold')} / SKIP {summary.get('final_skip')} / "
        f"PROTECT {summary.get('final_protect')})",
        f"- Actionable decisions: **{summary.get('actionable_decisions')}**",
        f"- Orders created: **{summary.get('orders_created')}**",
        f"- Orders executed: **{summary.get('orders_executed')}**",
        f"- Orders blocked/skipped: **{summary.get('orders_blocked_skipped')}**",
        f"- Trades written: **{summary.get('trades_written')}**",
        f"- Realized PnL: **{_fmt_money(summary.get('realized_pnl'))}**",
        f"- Unrealized PnL: **{_fmt_money(summary.get('unrealized_pnl'))}**",
        f"- PAPER account value: **{_fmt_money(summary.get('total_value'))}**",
        f"- Profit vs validation capital base ({_fmt_money(summary.get('validation_capital_base'))}): "
        f"**{_fmt_money(summary.get('profit_vs_validation_capital_base'))}**",
        "",
        "## Conversion metrics",
        "",
    ]
    for key, row in conv.items():
        lines.append(
            f"- {key}: **{row.get('numerator')}/{row.get('denominator')}** "
            f"({100 * _f(row.get('rate')):.1f}%)"
        )
    lines.extend(["", "## Block reason rollup", ""])
    for bucket in BLOCK_BUCKETS:
        if blocks.get(bucket):
            lines.append(f"- {bucket}: **{blocks[bucket]}**")
    for bucket, count in sorted(blocks.items()):
        if bucket not in BLOCK_BUCKETS:
            lines.append(f"- {bucket}: **{count}**")

    lines.extend(["", "## Profit attribution", ""])
    lines.append(f"- Profitable decisions: **{len(attr.get('profitable_decisions') or [])}**")
    lines.append(f"- Losing decisions: **{len(attr.get('losing_decisions') or [])}**")
    lines.append(f"- Blocked avoided loss (heuristic): **{attr.get('blocked_avoided_loss_count')}**")
    lines.append(f"- Blocked missed profit (heuristic): **{attr.get('blocked_missed_profit_count')}**")
    lines.append(f"- Unresolved outcomes: **{attr.get('unresolved_outcomes_count')}**")

    lines.extend(["", "## Data quality", ""])
    jc = dq.get("join_coverage") or {}
    lines.append(
        f"- decision_id join coverage: **{jc.get('decision_id')}/{jc.get('total_decisions')}** "
        f"({jc.get('decision_id_coverage_pct')}%)"
    )
    lines.append(f"- low-confidence joins: **{jc.get('low_confidence_joins')}**")
    lines.append(f"- profit integrity: **{dq.get('profit_integrity_status')}** (ok={dq.get('profit_integrity_ok')})")
    lines.append(f"- reconciliation: **{dq.get('reconciliation_status')}**")
    lines.append(f"- stale/fallback marks: **{dq.get('stale_or_fallback_marks')}**")

    lines.extend(["", "## Per-ticker timeline (current cycle)", ""])
    for row in (payload.get("timelines") or [])[:15]:
        lines.append(
            f"- **{row.get('ticker')}** [{row.get('decision_id')}] "
            f"signal={((row.get('signal') or {}).get('signal')) or '—'} → "
            f"{row['pde_decision']['action']} → "
            f"{row['order']['status']} ({row['order']['block_bucket']}) → "
            f"PnL {_fmt_money(row['pnl']['current_pnl'])} / "
            f"val={row['validation'].get('verdict') or '—'}"
        )
    if len(payload.get("timelines") or []) > 15:
        lines.append(f"- … +{len(payload['timelines']) - 15} more in `tae_profit_pipeline.json`")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def format_pipeline_section(payload: dict[str, Any]) -> list[str]:
    summary = payload.get("summary") or {}
    conv = payload.get("conversion_metrics") or {}
    dq = payload.get("data_quality") or {}
    jc = dq.get("join_coverage") or {}
    lines = [
        "--- PROFIT PIPELINE (read-only consolidation) ---",
        f"Opportunities: {summary.get('opportunities_detected')} | Signals: {summary.get('signals_generated')} | "
        f"Decisions: {summary.get('final_decisions')} | Orders: {summary.get('orders_created')} | "
        f"Executed: {summary.get('orders_executed')} | Trades: {summary.get('trades_written')}",
        f"PnL realized {_fmt_money(summary.get('realized_pnl'))} | unrealized {_fmt_money(summary.get('unrealized_pnl'))} | "
        f"vs base {_fmt_money(summary.get('profit_vs_validation_capital_base'))}",
        f"Conversion order→execution: {conv.get('order_to_execution', {}).get('numerator')}/"
        f"{conv.get('order_to_execution', {}).get('denominator')} "
        f"({100 * _f(conv.get('order_to_execution', {}).get('rate')):.1f}%)",
        f"Join coverage decision_id: {jc.get('decision_id')}/{jc.get('total_decisions')} "
        f"({jc.get('decision_id_coverage_pct')}%) | integrity={dq.get('profit_integrity_status')} | "
        f"reconciliation={dq.get('reconciliation_status')}",
        f"Full report: {REPORT_MD} | {REPORT_JSON}",
    ]
    try:
        from tae_roi001_challenger import format_roi_economic_status_section

        lines.extend(format_roi_economic_status_section())
    except Exception:
        pass
    return lines


def main() -> int:
    payload = build_profit_pipeline(write_outputs=True)
    print("\n".join(format_pipeline_section(payload)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
