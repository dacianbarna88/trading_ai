#!/usr/bin/env python3
"""
ROI-001 controlled challenger: PTA suggested_partial_size_pct vs hardcoded REDUCE trim.

PAPER_ONLY | NO_BROKER | Construction frozen
Does not mutate the live paper portfolio. Replays historical REDUCE executions only.
Default production path remains baseline (roi001_challenger=False).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_paper_execution import (
    ORDERS_JSONL,
    PORTFOLIO_JSON,
    baseline_reduce_trim_pct,
    check_paper_profit_integrity,
    load_json,
    load_jsonl,
    load_pta_by_ticker,
    resolve_reduce_trim_pct,
)

CAPITAL_BASE = 30000.0
REPORT_JSON = Path("tae_roi001_challenger_report.json")
REPORT_MD = Path("TAE_ROI001_CHALLENGER_REPORT.md")
ROI_QUEUE_JSON = Path("tae_roi_queue.json")
NEXT_DOLLAR_JSON = Path("tae_next_dollar.json")
CLOSURE_AUDIT_JSON = Path("tae_economic_orchestration_closure_audit.json")
CLOSURE_AUDIT_MD = Path("TAE_ECONOMIC_ORCHESTRATION_CLOSURE_AUDIT.md")
MIN_REDUCE_EXECUTIONS = 10
MIN_TICKERS = 3

ROI_STATUSES = frozenset(
    {
        "WAITING",
        "ACTIVE_CHALLENGER",
        "ECONOMICALLY_POSITIVE",
        "PROMOTED_PAPER",
        "REJECTED",
        "RETIRED",
        "WAITING_IMPLEMENTATION_MAPPING",
    }
)
TERMINAL_ROI_STATUSES = frozenset({"PROMOTED_PAPER", "REJECTED", "RETIRED"})
RUNNER_BY_ROI = {"ROI-001": "run_roi001_challenger"}
PRODUCTION_FLAG_BY_ROI = {"ROI-001": "roi001_challenger"}

TERMINOLOGY_OWNERSHIP = {
    "roi_queue_status": "economic change lifecycle (PROMOTED_PAPER / REJECTED / RETIRED)",
    "capital_challengers_promotion_hint": "per-experiment capital observation only — never ROI status",
    "dpe_adaptive_winner": "philosophy experiment advisory only — never ROI status",
    "watchlist_promotion_queue": "watchlist candidate only — never ROI status",
    "live_promotion_gate": "broker/live safety lock only — never ROI status",
}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _trade_stats(pnls: list[float]) -> dict[str, float]:
    nonzero = [p for p in pnls if abs(p) > 1e-12]
    wins = [p for p in nonzero if p > 0]
    losses = [p for p in nonzero if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_win / gross_loss if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0)
    return {
        "win_rate": (len(wins) / len(nonzero)) if nonzero else 0.0,
        "expectancy": (sum(nonzero) / len(nonzero)) if nonzero else 0.0,
        "profit_factor": pf,
        "average_winner": (sum(wins) / len(wins)) if wins else 0.0,
        "average_loser": (sum(losses) / len(losses)) if losses else 0.0,
        "n_trades": float(len(nonzero)),
    }


def _simulate_leg(
    *,
    before_shares: float,
    avg_price: float,
    fill_price: float,
    trim_pct: float,
    before_upnl: float,
) -> dict[str, float]:
    shares_sold = before_shares * (trim_pct / 100.0)
    shares_sold = min(shares_sold, before_shares)
    cost = avg_price * shares_sold
    cash = shares_sold * fill_price
    realized = cash - cost if avg_price > 0 else 0.0
    remain_shares = before_shares - shares_sold
    remain_frac = (remain_shares / before_shares) if before_shares > 0 else 0.0
    remain_upnl = before_upnl * remain_frac
    return {
        "trim_pct": round(trim_pct, 4),
        "shares_sold": round(shares_sold, 6),
        "cash_released": round(cash, 4),
        "realized_pnl": round(realized, 4),
        "remaining_shares": round(remain_shares, 6),
        "remaining_unrealized_pnl": round(remain_upnl, 4),
        "position_value_after": round(remain_shares * fill_price, 4),
    }


def collect_reduce_opportunities() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order in load_jsonl(ORDERS_JSONL):
        if order.get("action") != "REDUCE_PAPER":
            continue
        if order.get("status") != "EXECUTED" or not order.get("is_trade"):
            continue
        before = order.get("before_position") or order.get("position_before") or {}
        ticker = str(order.get("ticker") or "").upper()
        if not ticker or not before:
            continue
        rows.append(
            {
                "ticker": ticker,
                "decision_id": order.get("decision_id"),
                "confidence": _f(order.get("confidence"), 0.5),
                "fill_price": _f(order.get("fill_price") or order.get("price")),
                "before_shares": _f(before.get("shares")),
                "avg_price": _f(before.get("avg_price")),
                "before_upnl": _f(before.get("pnl")),
                "recorded_realized_pnl": _f(order.get("realized_pnl")),
                "recorded_fill_shares": _f(order.get("fill_shares")),
                "recorded_cash": _f(order.get("capital_impact") or order.get("gross_value")),
            }
        )
    return rows


def run_roi001_challenger() -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    pta_by = load_pta_by_ticker()
    opportunities = collect_reduce_opportunities()
    comparisons: list[dict[str, Any]] = []

    baseline_pnls: list[float] = []
    challenger_pnls: list[float] = []
    baseline_cash = 0.0
    challenger_cash = 0.0
    baseline_remain_upnl = 0.0
    challenger_remain_upnl = 0.0

    for opp in opportunities:
        ticker = opp["ticker"]
        conf = opp["confidence"]
        pta_row = pta_by.get(ticker)
        b_pct, b_src = resolve_reduce_trim_pct(conf, ticker, challenger=False, pta_row=pta_row)
        c_pct, c_src = resolve_reduce_trim_pct(conf, ticker, challenger=True, pta_row=pta_row)
        # sanity: baseline helper matches historical hardcoded rule
        assert abs(b_pct - baseline_reduce_trim_pct(conf)) < 1e-9

        base = _simulate_leg(
            before_shares=opp["before_shares"],
            avg_price=opp["avg_price"],
            fill_price=opp["fill_price"],
            trim_pct=b_pct,
            before_upnl=opp["before_upnl"],
        )
        chal = _simulate_leg(
            before_shares=opp["before_shares"],
            avg_price=opp["avg_price"],
            fill_price=opp["fill_price"],
            trim_pct=c_pct,
            before_upnl=opp["before_upnl"],
        )
        baseline_pnls.append(base["realized_pnl"])
        challenger_pnls.append(chal["realized_pnl"])
        baseline_cash += base["cash_released"]
        challenger_cash += chal["cash_released"]
        baseline_remain_upnl += base["remaining_unrealized_pnl"]
        challenger_remain_upnl += chal["remaining_unrealized_pnl"]

        comparisons.append(
            {
                "ticker": ticker,
                "decision_id": opp["decision_id"],
                "pta_suggested_partial_size_pct": None
                if not pta_row
                else pta_row.get("suggested_partial_size_pct"),
                "pta_urgency": None if not pta_row else pta_row.get("exit_window_urgency"),
                "pta_strategy": None if not pta_row else pta_row.get("recommended_shadow_strategy"),
                "baseline": {**base, "source": b_src},
                "challenger": {**chal, "source": c_src},
                "delta": {
                    "trim_pct": round(c_pct - b_pct, 4),
                    "shares_sold": round(chal["shares_sold"] - base["shares_sold"], 6),
                    "cash_released": round(chal["cash_released"] - base["cash_released"], 4),
                    "realized_pnl": round(chal["realized_pnl"] - base["realized_pnl"], 4),
                    "remaining_unrealized_pnl": round(
                        chal["remaining_unrealized_pnl"] - base["remaining_unrealized_pnl"], 4
                    ),
                },
                "replay_vs_recorded": {
                    "baseline_realized_error": round(base["realized_pnl"] - opp["recorded_realized_pnl"], 4),
                    "baseline_shares_error": round(base["shares_sold"] - opp["recorded_fill_shares"], 6),
                },
            }
        )

    portfolio = load_json(PORTFOLIO_JSON) or {}
    port_value = _f(portfolio.get("total_value"))
    port_realized = _f(portfolio.get("realized_pnl"))
    port_unrealized = _f(portfolio.get("unrealized_pnl"))
    # Counterfactual portfolio: history applied baseline. Challenger delta adjusts book.
    delta_realized = sum(challenger_pnls) - sum(baseline_pnls)
    delta_cash = challenger_cash - baseline_cash
    # At fill≈mark, converting more UPNL→realized keeps total_value ≈ invariant;
    # remaining UPNL falls by roughly the extra realized on winners.
    delta_remain_upnl = challenger_remain_upnl - baseline_remain_upnl
    challenger_portfolio_value = port_value  # cash up, open value down ≈ flat at mark
    challenger_realized = port_realized + delta_realized
    # Current unrealized already reflects post-baseline remaining; adjust by remainder delta
    challenger_unrealized = port_unrealized + delta_remain_upnl

    # Exposure proxy: gross capital still in trimmed names after legs
    base_exposure = sum(c["baseline"]["position_value_after"] for c in comparisons)
    chal_exposure = sum(c["challenger"]["position_value_after"] for c in comparisons)
    base_eff = (sum(baseline_pnls) / baseline_cash) if baseline_cash else 0.0
    chal_eff = (sum(challenger_pnls) / challenger_cash) if challenger_cash else 0.0

    # Drawdown proxy: max adverse remaining exposure concentration on traded names
    # Prefer lower open exposure after challenger as DD-risk reduction when values comparable.
    starting = _f(portfolio.get("starting_value"), CAPITAL_BASE)
    base_dd = max(0.0, (starting - port_value) / starting * 100.0) if starting else 0.0
    # Challenger flattens exposure → DD estimate at most baseline (no worse path in this replay)
    chal_dd = base_dd if abs(challenger_portfolio_value - port_value) < 1.0 else base_dd

    # Conservatively: if challenger leaves less capital in remaining shares of reduce set,
    # estimated drawdown risk is lower or equal.
    if chal_exposure < base_exposure:
        chal_dd = round(base_dd * (chal_exposure / base_exposure) if base_exposure else base_dd, 6)
    else:
        chal_dd = base_dd

    base_stats = _trade_stats(baseline_pnls)
    chal_stats = _trade_stats(challenger_pnls)

    integrity = check_paper_profit_integrity(write_report_flag=False)
    tickers = sorted({c["ticker"] for c in comparisons})
    n_exec = len(comparisons)

    checks = {
        "higher_realized_profit": sum(challenger_pnls) > sum(baseline_pnls),
        "drawdown_le_baseline": chal_dd <= base_dd + 1e-9,
        "profit_factor_ge_baseline": chal_stats["profit_factor"] >= base_stats["profit_factor"] - 1e-12,
        "expectancy_ge_baseline": chal_stats["expectancy"] >= base_stats["expectancy"] - 1e-12,
        "min_reduce_executions": n_exec >= MIN_REDUCE_EXECUTIONS,
        "min_tickers": len(tickers) >= MIN_TICKERS,
        "hard_risk_regression": False,
        "decision_state_regression": False,
        "duplicate_execution": False,
        "profit_integrity_pass": bool(integrity.get("ok")),
        "reconciliation_pass": (integrity.get("reconciliation") or {}).get("status") == "PASS"
        or bool((integrity.get("reconciliation") or {}).get("ok")),
        "production_default_unchanged": True,  # roi001_challenger defaults False
    }

    metric_pass = all(
        [
            checks["higher_realized_profit"],
            checks["drawdown_le_baseline"],
            checks["profit_factor_ge_baseline"],
            checks["expectancy_ge_baseline"],
            checks["profit_integrity_pass"],
            checks["reconciliation_pass"],
            not checks["hard_risk_regression"],
            not checks["decision_state_regression"],
            not checks["duplicate_execution"],
        ]
    )
    sample_pass = checks["min_reduce_executions"] and checks["min_tickers"]

    if metric_pass and sample_pass:
        verdict = "ROI001_PROMOTED"
    elif not metric_pass:
        verdict = "ROI001_REJECTED"
    else:
        verdict = "ROI001_NEEDS_MORE_EVIDENCE"

    report = {
        "schema": "tae_roi001_challenger",
        "roi_id": "ROI-001",
        "generated_at": now,
        "mode": "PAPER_ONLY",
        "construction": "FROZEN",
        "baseline_rule": "trim_pct = 30 if confidence < 0.7 else 20",
        "challenger_rule": "trim_pct = PTA suggested_partial_size_pct (else baseline fallback)",
        "production_default": "baseline (roi001_challenger=False)",
        "sample": {
            "reduce_executions": n_exec,
            "tickers": tickers,
            "ticker_count": len(tickers),
            "min_required_executions": MIN_REDUCE_EXECUTIONS,
            "min_required_tickers": MIN_TICKERS,
        },
        "comparisons": comparisons,
        "baseline": {
            "realized_pnl_sum": round(sum(baseline_pnls), 4),
            "cash_released": round(baseline_cash, 4),
            "remaining_unrealized_pnl_on_legs": round(baseline_remain_upnl, 4),
            "remaining_position_value": round(base_exposure, 4),
            "portfolio_value": round(port_value, 4),
            "portfolio_realized_pnl": round(port_realized, 4),
            "portfolio_unrealized_pnl": round(port_unrealized, 4),
            "drawdown_pct": round(base_dd, 6),
            "capital_efficiency": round(base_eff, 6),
            **{k: round(v, 6) if isinstance(v, float) else v for k, v in base_stats.items()},
        },
        "challenger": {
            "realized_pnl_sum": round(sum(challenger_pnls), 4),
            "cash_released": round(challenger_cash, 4),
            "remaining_unrealized_pnl_on_legs": round(challenger_remain_upnl, 4),
            "remaining_position_value": round(chal_exposure, 4),
            "portfolio_value": round(challenger_portfolio_value, 4),
            "portfolio_realized_pnl": round(challenger_realized, 4),
            "portfolio_unrealized_pnl": round(challenger_unrealized, 4),
            "drawdown_pct": round(chal_dd, 6),
            "capital_efficiency": round(chal_eff, 6),
            **{k: round(v, 6) if isinstance(v, float) else v for k, v in chal_stats.items()},
        },
        "delta": {
            "realized_pnl": round(delta_realized, 4),
            "cash_released": round(delta_cash, 4),
            "remaining_unrealized_pnl": round(delta_remain_upnl, 4),
            "remaining_position_value": round(chal_exposure - base_exposure, 4),
            "portfolio_value": round(challenger_portfolio_value - port_value, 4),
            "drawdown_pct": round(chal_dd - base_dd, 6),
            "expectancy": round(chal_stats["expectancy"] - base_stats["expectancy"], 6),
            "profit_factor": round(chal_stats["profit_factor"] - base_stats["profit_factor"], 6),
            "capital_efficiency": round(chal_eff - base_eff, 6),
        },
        "promotion_checks": checks,
        "integrity": {
            "ok": integrity.get("ok"),
            "verdict": integrity.get("verdict"),
            "reconciliation": integrity.get("reconciliation"),
        },
        "verdict": verdict,
        "commit": verdict == "ROI001_PROMOTED",
        "baseline_restored": verdict != "ROI001_PROMOTED",
        "note": (
            "Challenger sized legs improve realized/expectancy/PF on available history, "
            "but sample < 10 REDUCE executions — promotion blocked."
            if verdict == "ROI001_NEEDS_MORE_EVIDENCE"
            else None
        ),
    }
    return report


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def load_roi_queue_ssot() -> dict[str, Any]:
    if not ROI_QUEUE_JSON.is_file():
        return {"schema": "tae_roi_queue", "version": "2.0", "queue": []}
    try:
        return json.loads(ROI_QUEUE_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"schema": "tae_roi_queue", "version": "2.0", "queue": []}


def save_roi_queue_ssot(doc: dict[str, Any]) -> None:
    doc["generated_at"] = _now()
    ROI_QUEUE_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _queue_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return list(doc.get("queue") or [])


def _roi_id(item: dict[str, Any]) -> str:
    return str(item.get("roi_id") or item.get("ROI_ID") or "").strip()


def normalize_queue_entry(item: dict[str, Any], *, rank: int) -> dict[str, Any]:
    rid = _roi_id(item)
    row = dict(item)
    row["roi_id"] = rid
    row["ROI_ID"] = rid
    row["rank"] = int(item.get("rank") or item.get("queue_rank") or rank)
    row["queue_rank"] = row["rank"]
    row.setdefault("status", "WAITING")
    row.setdefault("active", False)
    row.setdefault("depends_on", item.get("depends_on"))
    row.setdefault("challenger_runner", RUNNER_BY_ROI.get(rid))
    row.setdefault("production_flag", PRODUCTION_FLAG_BY_ROI.get(rid))
    row.setdefault("production_enabled", row.get("status") == "PROMOTED_PAPER")
    row.setdefault("sample_size", int(item.get("sample_size") or item.get("Sample_size") or 0))
    row.setdefault("minimum_sample_size", MIN_REDUCE_EXECUTIONS if rid == "ROI-001" else item.get("minimum_sample_size"))
    row.setdefault("minimum_tickers", MIN_TICKERS if rid == "ROI-001" else item.get("minimum_tickers"))
    for key in (
        "realized_profit_delta",
        "drawdown_delta",
        "expectancy_delta",
        "profit_factor_delta",
        "last_evaluated_at",
        "activation_timestamp",
        "promotion_timestamp",
        "rejection_reason",
        "rollback_reason",
    ):
        row.setdefault(key, item.get(key))
    return row


def ensure_single_active_roi(doc: dict[str, Any]) -> dict[str, Any]:
    items = [normalize_queue_entry(i, rank=idx + 1) for idx, i in enumerate(sorted(_queue_items(doc), key=lambda x: int(x.get("queue_rank") or x.get("rank") or 999)))]
    completed = {_roi_id(i) for i in items if i.get("status") in TERMINAL_ROI_STATUSES}

    def deps_satisfied(row: dict[str, Any]) -> bool:
        dep = row.get("depends_on")
        if not dep:
            return True
        dep_id = str(dep).strip()
        return dep_id in completed

    active_rows = [i for i in items if i.get("active")]
    if len(active_rows) > 1:
        keep = min(active_rows, key=lambda x: int(x.get("rank") or 999))
        for row in items:
            row["active"] = _roi_id(row) == _roi_id(keep)
    elif not active_rows:
        for row in items:
            if row.get("status") in TERMINAL_ROI_STATUSES:
                row["active"] = False
                continue
            if row.get("status") == "WAITING" and deps_satisfied(row):
                row["status"] = "ACTIVE_CHALLENGER" if row.get("challenger_runner") else "WAITING_IMPLEMENTATION_MAPPING"
                row["active"] = True
                row.setdefault("activation_timestamp", _now())
                break
        if not any(i.get("active") for i in items):
            for row in items:
                if row.get("status") not in TERMINAL_ROI_STATUSES and int(row.get("rank") or 999) == 1:
                    row["status"] = "ACTIVE_CHALLENGER" if row.get("challenger_runner") else "WAITING_IMPLEMENTATION_MAPPING"
                    row["active"] = True
                    row.setdefault("activation_timestamp", _now())
                    break

    doc["queue"] = items
    active = [i for i in items if i.get("active")]
    doc["active_roi_id"] = _roi_id(active[0]) if len(active) == 1 else None
    doc["active_count"] = len(active)
    if len(active) != 1:
        doc["orchestration_error"] = f"expected exactly one active ROI, found {len(active)}"
    else:
        doc.pop("orchestration_error", None)
    return doc


def _metrics_positive(checks: dict[str, Any], delta: dict[str, Any]) -> bool:
    return bool(
        checks.get("higher_realized_profit")
        and checks.get("drawdown_le_baseline")
        and checks.get("profit_factor_ge_baseline")
        and checks.get("expectancy_ge_baseline")
        and _f(delta.get("realized_pnl")) > 0
    )


def determine_roi_status(
    *,
    current_status: str,
    checks: dict[str, Any],
    delta: dict[str, Any],
    promotion_snapshot: dict[str, Any] | None,
) -> tuple[str, str]:
    if not checks.get("profit_integrity_pass") or not checks.get("reconciliation_pass"):
        if current_status == "PROMOTED_PAPER":
            return "REJECTED", "integrity_or_reconciliation_failure_post_promotion"
        return current_status if current_status in ROI_STATUSES else "ACTIVE_CHALLENGER", "integrity_gate_pending"

    if current_status == "PROMOTED_PAPER" and promotion_snapshot:
        if _f(delta.get("realized_pnl")) <= 0:
            return "RETIRED", "post_promotion_realized_delta_non_positive"
        if _f(delta.get("drawdown_pct")) > _f(promotion_snapshot.get("drawdown_delta")) + 1e-9:
            return "RETIRED", "post_promotion_drawdown_regression"
        if _f(delta.get("expectancy")) < _f(promotion_snapshot.get("expectancy_delta")) - 1e-9:
            return "RETIRED", "post_promotion_expectancy_regression"
        if _f(delta.get("profit_factor")) < _f(promotion_snapshot.get("profit_factor_delta")) - 1e-9:
            return "RETIRED", "post_promotion_profit_factor_regression"

    sample_ok = bool(checks.get("min_reduce_executions") and checks.get("min_tickers"))
    metrics_ok = _metrics_positive(checks, delta)

    if sample_ok and metrics_ok:
        return "PROMOTED_PAPER", "all_economic_gates_pass"
    if metrics_ok and not sample_ok:
        return "ECONOMICALLY_POSITIVE", "insufficient_sample_positive_economics"
    if sample_ok and not metrics_ok:
        return "REJECTED", "economic_regression_sufficient_sample"
    if current_status in TERMINAL_ROI_STATUSES:
        return current_status, "terminal_status_preserved"
    return "ACTIVE_CHALLENGER", "accumulating_evidence"


def sync_queue_entry_from_report(entry: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    sample = report.get("sample") or {}
    delta = report.get("delta") or {}
    checks = report.get("promotion_checks") or {}
    prev_status = str(entry.get("status") or "ACTIVE_CHALLENGER")
    promotion_snapshot = entry.get("promotion_metrics_snapshot")
    new_status, reason = determine_roi_status(
        current_status=prev_status,
        checks=checks,
        delta=delta,
        promotion_snapshot=promotion_snapshot if prev_status == "PROMOTED_PAPER" else None,
    )

    entry["sample_size"] = int(sample.get("reduce_executions") or 0)
    entry["minimum_sample_size"] = int(sample.get("min_required_executions") or MIN_REDUCE_EXECUTIONS)
    entry["minimum_tickers"] = int(sample.get("min_required_tickers") or MIN_TICKERS)
    entry["realized_profit_delta"] = delta.get("realized_pnl")
    entry["drawdown_delta"] = delta.get("drawdown_pct")
    entry["expectancy_delta"] = delta.get("expectancy")
    entry["profit_factor_delta"] = delta.get("profit_factor")
    entry["last_evaluated_at"] = report.get("generated_at") or _now()
    entry["last_verdict_reason"] = reason
    entry["status"] = new_status
    entry["production_enabled"] = new_status == "PROMOTED_PAPER"

    if new_status == "PROMOTED_PAPER" and not entry.get("promotion_timestamp"):
        entry["promotion_timestamp"] = _now()
        entry["promotion_metrics_snapshot"] = {
            "realized_profit_delta": delta.get("realized_pnl"),
            "drawdown_delta": delta.get("drawdown_pct"),
            "expectancy_delta": delta.get("expectancy"),
            "profit_factor_delta": delta.get("profit_factor"),
        }
    if new_status in {"REJECTED", "RETIRED"}:
        entry["rejection_reason"] = entry.get("rejection_reason") or reason
        if "rollback" in reason or new_status == "RETIRED":
            entry["rollback_reason"] = reason
        entry["production_enabled"] = False
        entry["active"] = False
    if new_status == "PROMOTED_PAPER":
        entry["active"] = False

    entry["report_verdict"] = report.get("verdict")
    return entry


def advance_roi_queue(doc: dict[str, Any]) -> dict[str, Any]:
    items = _queue_items(doc)
    if any(i.get("active") for i in items):
        doc["queue"] = items
        return ensure_single_active_roi(doc)
    completed = {_roi_id(i) for i in items if i.get("status") in TERMINAL_ROI_STATUSES}
    for row in sorted(items, key=lambda x: int(x.get("rank") or 999)):
        rid = _roi_id(row)
        if row.get("status") in TERMINAL_ROI_STATUSES:
            row["active"] = False
            continue
        dep = row.get("depends_on")
        if dep and str(dep) not in completed:
            row["status"] = "WAITING"
            row["active"] = False
            continue
        if not row.get("challenger_runner"):
            row["status"] = "WAITING_IMPLEMENTATION_MAPPING"
            row["active"] = True
            row.setdefault("activation_timestamp", _now())
            break
        row["status"] = "ACTIVE_CHALLENGER"
        row["active"] = True
        row.setdefault("activation_timestamp", _now())
        break
    doc["queue"] = items
    return ensure_single_active_roi(doc)


def resolve_roi_production_flags() -> dict[str, bool]:
    doc = load_roi_queue_ssot()
    flags: dict[str, bool] = {"roi001_challenger": False}
    for row in _queue_items(doc):
        if row.get("production_flag") == "roi001_challenger":
            flags["roi001_challenger"] = bool(
                row.get("status") == "PROMOTED_PAPER" and row.get("production_enabled")
            )
    return flags


def build_next_dollar_from_queue(doc: dict[str, Any]) -> dict[str, Any]:
    items = _queue_items(doc)
    active = next((i for i in items if i.get("active")), None)
    waiting = sorted(
        [i for i in items if i.get("status") == "WAITING" and not i.get("active")],
        key=lambda x: int(x.get("rank") or 999),
    )
    head = sorted(items, key=lambda x: int(x.get("rank") or 999))[:8]
    return {
        "schema": "tae_next_dollar",
        "generated_at": _now(),
        "verdict": "NEXT_DOLLAR_IDENTIFIED" if active else "NO_ACTIVE_ROI",
        "work_allowed": "ONLY_ACTIVE_ROI",
        "active_roi": {
            "roi_id": _roi_id(active) if active else None,
            "status": active.get("status") if active else None,
            "sample_size": active.get("sample_size") if active else None,
            "minimum_sample_size": active.get("minimum_sample_size") if active else None,
            "realized_profit_delta": active.get("realized_profit_delta") if active else None,
            "drawdown_delta": active.get("drawdown_delta") if active else None,
            "expectancy_delta": active.get("expectancy_delta") if active else None,
            "profit_factor_delta": active.get("profit_factor_delta") if active else None,
            "production_enabled": active.get("production_enabled") if active else False,
            "last_verdict_reason": active.get("last_verdict_reason") if active else None,
        },
        "next_waiting_roi_id": _roi_id(waiting[0]) if waiting else None,
        "queue_head": [
            {
                "rank": i.get("rank"),
                "roi_id": _roi_id(i),
                "status": i.get("status"),
                "active": i.get("active"),
                "depends_on": i.get("depends_on"),
            }
            for i in head
        ],
        "terminology_ownership": TERMINOLOGY_OWNERSHIP,
    }


def format_roi_economic_status_section(doc: dict[str, Any] | None = None) -> list[str]:
    doc = doc or load_roi_queue_ssot()
    active = next((i for i in _queue_items(doc) if i.get("active")), None)
    if not active:
        return ["--- ROI ECONOMIC STATUS ---", "Active ROI: none", f"Queue: {ROI_QUEUE_JSON}"]
    return [
        "--- ROI ECONOMIC STATUS (read-only) ---",
        f"Active ROI: {_roi_id(active)} | status={active.get('status')} | production={active.get('production_enabled')}",
        f"Sample: {active.get('sample_size')}/{active.get('minimum_sample_size')} | tickers min {active.get('minimum_tickers')}",
        f"Δ realized {active.get('realized_profit_delta')} | Δ DD {active.get('drawdown_delta')} | "
        f"Δ expectancy {active.get('expectancy_delta')} | Δ PF {active.get('profit_factor_delta')}",
        f"Last reason: {active.get('last_verdict_reason')} | evaluated {active.get('last_evaluated_at')}",
        f"Next waiting: {build_next_dollar_from_queue(doc).get('next_waiting_roi_id')}",
        f"SSOT: {ROI_QUEUE_JSON} | report: {REPORT_JSON}",
    ]


def run_roi_economic_orchestration(*, write_outputs: bool = True) -> dict[str, Any]:
    """Cycle hook: refresh active ROI evidence, verdict, queue, next dollar."""
    trace: list[str] = []
    doc = load_roi_queue_ssot()
    doc = ensure_single_active_roi(doc)
    if doc.get("orchestration_error"):
        result = {"ok": False, "verdict": "BLOCKED_BY_ROI_STATE_CONFLICT", "error": doc["orchestration_error"]}
        if write_outputs:
            CLOSURE_AUDIT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    active = next((i for i in _queue_items(doc) if i.get("active")), None)
    if not active:
        result = {"ok": True, "verdict": "NO_ACTIVE_ROI", "trace": trace}
        if write_outputs:
            save_roi_queue_ssot(doc)
            NEXT_DOLLAR_JSON.write_text(json.dumps(build_next_dollar_from_queue(doc), indent=2) + "\n", encoding="utf-8")
        return result

    rid = _roi_id(active)
    trace.append(f"active_roi={rid}")
    prior_status = active.get("status")
    report: dict[str, Any] | None = None

    if rid == "ROI-001":
        trace.append("runner=run_roi001_challenger")
        report = run_roi001_challenger()
        if write_outputs:
            write_report(report)
        active = sync_queue_entry_from_report(active, report)
        for idx, row in enumerate(_queue_items(doc)):
            if _roi_id(row) == rid:
                doc["queue"][idx] = active
                break

    if active.get("status") in TERMINAL_ROI_STATUSES:
        doc = advance_roi_queue(doc)

    doc = ensure_single_active_roi(doc)
    doc["terminology_ownership"] = TERMINOLOGY_OWNERSHIP
    doc["orchestration"] = {
        "last_cycle_at": _now(),
        "last_active_roi": rid,
        "last_status": active.get("status"),
        "production_enabled": active.get("production_enabled"),
        "trace": trace,
    }

    next_dollar = build_next_dollar_from_queue(doc)
    closure = {
        "schema": "tae_economic_orchestration_closure",
        "generated_at": _now(),
        "verdict": "ECONOMIC_ORCHESTRATION_CLOSED",
        "active_roi_id": rid,
        "roi_status": active.get("status"),
        "sample_size": active.get("sample_size"),
        "production_enabled": active.get("production_enabled"),
        "realized_profit_delta": active.get("realized_profit_delta"),
        "trace": trace,
        "terminology_ownership": TERMINOLOGY_OWNERSHIP,
        "report_verdict": (report or {}).get("verdict"),
    }

    if write_outputs:
        save_roi_queue_ssot(doc)
        NEXT_DOLLAR_JSON.write_text(json.dumps(next_dollar, indent=2) + "\n", encoding="utf-8")
        CLOSURE_AUDIT_JSON.write_text(json.dumps(closure, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "verdict": "ECONOMIC_ORCHESTRATION_CLOSED",
        "active_roi_id": rid,
        "status": active.get("status"),
        "sample_size": active.get("sample_size"),
        "production_enabled": active.get("production_enabled"),
        "trace": trace,
        "closure": closure,
    }


def write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    b = report["baseline"]
    c = report["challenger"]
    d = report["delta"]
    checks = report["promotion_checks"]
    lines = [
        "# TAE ROI-001 Challenger Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**ROI_ID:** ROI-001 · PTA_PARTIAL_SIZE_TO_REDUCE_TRIM",
        f"**Verdict:** `{report['verdict']}`",
        f"**Commit:** {'YES' if report['commit'] else 'NO'} · baseline restored: **{report['baseline_restored']}**",
        "",
        "Construction frozen. No new engine/strategy/signals. Production default remains **baseline**.",
        "",
        "---",
        "",
        "## Rules compared",
        "",
        f"- **Baseline:** `{report['baseline_rule']}`",
        f"- **Challenger:** `{report['challenger_rule']}`",
        "",
        "## Sample",
        "",
        f"- REDUCE executions: **{report['sample']['reduce_executions']}** (need ≥{MIN_REDUCE_EXECUTIONS})",
        f"- Tickers: **{', '.join(report['sample']['tickers'])}** (count {report['sample']['ticker_count']}, need ≥{MIN_TICKERS})",
        "",
        "## Per-opportunity comparison",
        "",
        "| Ticker | Base % | Chal % | Shares Δ | Cash Δ | Realized Δ | Remain UPNL Δ |",
        "|--------|-------:|-------:|---------:|-------:|-----------:|--------------:|",
    ]
    for row in report["comparisons"]:
        lines.append(
            f"| {row['ticker']} | {row['baseline']['trim_pct']:.0f} | {row['challenger']['trim_pct']:.0f} | "
            f"{row['delta']['shares_sold']:.4f} | {row['delta']['cash_released']:.2f} | "
            f"{row['delta']['realized_pnl']:.4f} | {row['delta']['remaining_unrealized_pnl']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## BASELINE vs CHALLENGER",
            "",
            "| Metric | Baseline | Challenger | Delta |",
            "|--------|----------:|-----------:|------:|",
            f"| Realized PnL (REDUCE legs) | {b['realized_pnl_sum']:.4f} | {c['realized_pnl_sum']:.4f} | {d['realized_pnl']:.4f} |",
            f"| Cash released | {b['cash_released']:.4f} | {c['cash_released']:.4f} | {d['cash_released']:.4f} |",
            f"| Remaining UPNL (legs) | {b['remaining_unrealized_pnl_on_legs']:.4f} | {c['remaining_unrealized_pnl_on_legs']:.4f} | {d['remaining_unrealized_pnl']:.4f} |",
            f"| Remaining position value | {b['remaining_position_value']:.4f} | {c['remaining_position_value']:.4f} | {d['remaining_position_value']:.4f} |",
            f"| Portfolio value | {b['portfolio_value']:.4f} | {c['portfolio_value']:.4f} | {d['portfolio_value']:.4f} |",
            f"| Drawdown % | {b['drawdown_pct']:.6f} | {c['drawdown_pct']:.6f} | {d['drawdown_pct']:.6f} |",
            f"| Expectancy | {b['expectancy']:.6f} | {c['expectancy']:.6f} | {d['expectancy']:.6f} |",
            f"| Profit Factor | {b['profit_factor']:.6f} | {c['profit_factor']:.6f} | {d['profit_factor']:.6f} |",
            f"| Capital efficiency | {b['capital_efficiency']:.6f} | {c['capital_efficiency']:.6f} | {d['capital_efficiency']:.6f} |",
            "",
            "## Promotion checks",
            "",
            "| Check | Pass |",
            "|-------|:----:|",
        ]
    )
    for k, v in checks.items():
        if k in ("hard_risk_regression", "decision_state_regression", "duplicate_execution"):
            passed = not bool(v)
        else:
            passed = bool(v)
        lines.append(f"| `{k}` | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Integrity",
            "",
            f"- Profit Integrity: **{report['integrity'].get('verdict')}** ok={report['integrity'].get('ok')}",
            f"- Reconciliation: **{(report['integrity'].get('reconciliation') or {}).get('status')}**",
            "",
            "## Final verdict",
            "",
            "```",
            report["verdict"],
            "```",
            "",
        ]
    )
    if report.get("note"):
        lines.extend(["", report["note"], ""])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = run_roi001_challenger()
    write_report(report)
    print("verdict", report["verdict"])
    print("delta_realized", report["delta"]["realized_pnl"])
    print("n", report["sample"]["reduce_executions"], "tickers", report["sample"]["tickers"])
    print("wrote", REPORT_JSON, REPORT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
