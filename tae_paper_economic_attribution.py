#!/usr/bin/env python3
"""
Unified PAPER economic attribution — measurement / observability only.

PAPER_ONLY | NO_BROKER | NO_LIVE | NO_DECISION_AUTHORITY

Builds cycle-level economic records from existing parallel V1/V2 journals,
tranche events, cycle state, and the canonical paper transaction cost model.
Does not mutate positions, cash, PnL, decisions, or LIVE files.
"""

from __future__ import annotations

import json
import math
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "tae.paper.economic_attribution.v1"
STORE_SCHEMA = "tae.paper.economic_attribution.store.v1"
COST_MODEL_VERSION = "paper_tx_cost.v1"

CF = "REQUIRES_COUNTERFACTUAL"
UNAVAILABLE = "UNAVAILABLE"
RISK_NOT_PERSISTED = "RISK_DATA_NOT_PERSISTED_AT_ENTRY"
UNKNOWN_LINKAGE = "UNKNOWN_LINKAGE"

STATUS_OPEN = "OPEN"
STATUS_CLOSED = "CLOSED"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_UNKNOWN = "UNKNOWN_LINKAGE"

METRIC_CLASS = {
    "gross_realized_pnl": "DIRECT_ACCOUNTING",
    "total_transaction_costs": "DIRECT_ACCOUNTING",
    "net_realized_pnl": "DIRECT_ACCOUNTING",
    "capital_committed": "DIRECT_ACCOUNTING",
    "capital_released": "DIRECT_ACCOUNTING",
    "holding_duration": "DIRECT_ACCOUNTING",
    "turnover": "DIRECT_ACCOUNTING",
    "exit_reason": "DIRECT_EVENT_ATTRIBUTION",
    "trailing_as_exit_reason": "DIRECT_EVENT_ATTRIBUTION",
    "hard_risk_as_exit_reason": "DIRECT_EVENT_ATTRIBUTION",
    "add_tranche_capital": "DIRECT_EVENT_ATTRIBUTION",
    "reentry_capital": "DIRECT_EVENT_ATTRIBUTION",
    "trailing_incremental_pnl": "COUNTERFACTUAL_REQUIRED",
    "add_tranche_incremental_pnl": "COUNTERFACTUAL_REQUIRED",
    "reentry_incremental_pnl": "COUNTERFACTUAL_REQUIRED",
    "hard_risk_avoided_loss": "COUNTERFACTUAL_REQUIRED",
    "opportunity_cost": "UNAVAILABLE",
    "entry_risk_snapshot": "UNAVAILABLE",
}

MIN_CLOSED_CYCLES_FOR_WINNER = 30
MIN_OBSERVATION_DAYS_FOR_WINNER = 20
MAX_ATTRIBUTION_RESIDUAL_ABS = 1e-3


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _s(v: Any) -> str:
    return str(v or "").strip()


def _f(v: Any, d: float = 0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float(d)
    if math.isnan(x) or math.isinf(x):
        return float(d)
    return x


def _parse_ts(ts: Any) -> datetime | None:
    s = _s(ts)
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _duration_seconds(a: Any, b: Any) -> float | None:
    ta, tb = _parse_ts(a), _parse_ts(b)
    if not ta or not tb:
        return None
    return max(0.0, (tb - ta).total_seconds())


def attribution_dir(root: Path | None = None) -> Path:
    from tae_parallel_paper_config import ROOT

    base = Path(root) if root is not None else Path(ROOT)
    out = base / "attribution"
    out.mkdir(parents=True, exist_ok=True)
    return out


def store_path(root: Path | None = None) -> Path:
    return attribution_dir(root) / "economic_cycles.json"


def summary_path(root: Path | None = None) -> Path:
    return attribution_dir(root) / "economic_summary.json"


def empty_store() -> dict[str, Any]:
    return {
        "schema": STORE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "updated_at": _now(),
        "authority": "OBSERVABILITY_ONLY",
        "live_effect": False,
        "decision_authority": False,
        "cycles": {},
        "seen_execution_ids": [],
        "rebuild_stats": {},
    }


def load_store(path: Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else store_path()
    if not p.is_file():
        return empty_store()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_store()
    if not isinstance(raw, dict):
        return empty_store()
    store = empty_store()
    store.update({k: raw.get(k, store.get(k)) for k in store})
    cycles = raw.get("cycles") if isinstance(raw.get("cycles"), dict) else {}
    store["cycles"] = {str(k): dict(v) for k, v in cycles.items() if isinstance(v, dict)}
    seen = raw.get("seen_execution_ids") if isinstance(raw.get("seen_execution_ids"), list) else []
    store["seen_execution_ids"] = [str(x) for x in seen if x]
    return store


def save_store(store: dict[str, Any], path: Path | None = None) -> Path:
    p = Path(path) if path is not None else store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    out = dict(store)
    out["updated_at"] = _now()
    out["schema"] = STORE_SCHEMA
    out["schema_version"] = SCHEMA_VERSION
    tmp = p.with_suffix(p.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return p


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def normalize_decision_id(decision_id: str) -> str:
    s = _s(decision_id)
    for suf in (
        "-OPEN", "-REOPEN", "-BUY", "-EX", "-REENTRY",
        "-manage", "-entry", "-all", "-MANAGE", "-ENTRY", "-ALL",
    ):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def _trade_cost(row: dict[str, Any]) -> float:
    if row.get("total_transaction_cost") is not None:
        return max(0.0, _f(row.get("total_transaction_cost")))
    return max(0.0, _f(row.get("costs")))


def _dedupe_trades(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_eid: dict[str, dict[str, Any]] = {}
    no_eid: list[dict[str, Any]] = []
    for row in rows:
        eid = _s(row.get("execution_id"))
        if not eid:
            no_eid.append(row)
            continue
        prev = by_eid.get(eid)
        if prev is None:
            by_eid[eid] = row
            continue
        score = (1 if row.get("total_transaction_cost") is not None else 0) + (1 if row.get("cycle_id") else 0)
        prev_score = (1 if prev.get("total_transaction_cost") is not None else 0) + (1 if prev.get("cycle_id") else 0)
        if score >= prev_score:
            merged = dict(prev)
            merged.update({k: v for k, v in row.items() if v is not None})
            by_eid[eid] = merged
    out = list(by_eid.values()) + no_eid
    out.sort(key=lambda r: _s(r.get("ts")))
    return out


def _is_buy_action(action: str) -> bool:
    return _s(action).upper() in {"BUY", "OPEN", "ADD", "ADD_TRANCHE", "REBUY", "REENTRY"}


def _is_sell_action(action: str) -> bool:
    return _s(action).upper() in {"SELL", "CLOSE", "CLOSE_CYCLE"}


def _entry_type(action: str, *, in_reentry: bool = False) -> str:
    a = _s(action).upper()
    if in_reentry or a in {"REBUY", "REENTRY"}:
        return "REENTRY" if a == "REENTRY" else "REBUY"
    if a in {"ADD", "ADD_TRANCHE"}:
        return "ADD_TRANCHE"
    return "INITIAL"


def _exit_flags(reason: str) -> dict[str, Any]:
    r = _s(reason).upper()
    trailing = any(x in r for x in ("TRAIL", "PROFIT_TRAILING", "CLOSE_TRAILING"))
    hard = any(x in r for x in ("HARD_RISK", "HARD-RISK", "STOP_LOSS", "V1_STOP"))
    return {
        "exit_reason": reason or None,
        "trailing_exit": bool(trailing),
        "hard_risk_exit": bool(hard),
        "trailing_contribution": CF,
        "hard_risk_contribution": CF,
        "exit_contribution": CF,
    }


def _component_block(*, gross: float, costs: float, net: float) -> dict[str, Any]:
    entry_baseline = round(gross, 6)
    tx_drag = round(costs, 6)
    residual = round(net - (entry_baseline - tx_drag), 6)
    return {
        "entry_baseline_component": entry_baseline,
        "exit_component": CF,
        "trailing_component": CF,
        "add_tranche_component": CF,
        "reentry_component": CF,
        "hard_risk_component": CF,
        "transaction_cost_drag": tx_drag,
        "cash_drag": UNAVAILABLE,
        "opportunity_cost": UNAVAILABLE,
        "unexplained_residual": residual,
        "metric_classes": dict(METRIC_CLASS),
    }


def _risk_block() -> dict[str, Any]:
    return {
        "status": RISK_NOT_PERSISTED,
        "risk_snapshot_status": RISK_NOT_PERSISTED,
        "risk_attribution_status": RISK_NOT_PERSISTED,
        "sizing_formula_id": None,
        "recommended_quantity": None,
        "executed_quantity": None,
        "sizing_quantity_delta": None,
        "sizing_quantity_delta_pct": None,
        "initial_risk_amount": None,
        "initial_risk_pct_of_equity": None,
        "realized_r_multiple": None,
        "gross_r_multiple": None,
        "net_r_multiple": None,
        "risk_adjusted_return": None,
        "risk_data_completeness_pct": 0.0,
        "maximum_adverse_excursion": RISK_NOT_PERSISTED,
        "maximum_favorable_excursion": RISK_NOT_PERSISTED,
        "drawdown_per_cycle": RISK_NOT_PERSISTED,
        "peak_capital_at_risk": RISK_NOT_PERSISTED,
        "stop_distance_at_entry": RISK_NOT_PERSISTED,
        "realized_pnl_per_initial_risk": RISK_NOT_PERSISTED,
        "entry_risk_snapshots": [],
        "shadow_sizing_observability_status": "SHADOW_DATA_NOT_PERSISTED_AT_ENTRY",
        "shadow_sizing_evaluations": [],
        "shadow_formula_count": 0,
        "note": "No persistent entry risk snapshot on parallel PAPER fills.",
    }


def _apply_entry_risk_attribution(
    cycle: dict[str, Any],
    *,
    snapshots: list[dict[str, Any]] | None = None,
    raw_cycle: dict[str, Any] | None = None,
    fills: list[dict[str, Any]] | None = None,
    tranches: list[dict[str, Any]] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> None:
    """Populate risk/sizing observability from frozen entry snapshots (never invent)."""
    import tae_paper_entry_risk_snapshot as ers

    snaps = list(snapshots or [])
    if not snaps:
        snaps = ers.collect_snapshots_from_cycle_sources(
            cycle=raw_cycle or cycle,
            fills=fills or cycle.get("fills"),
            tranches=tranches,
            trades=trades,
        )
    if not snaps:
        cycle["risk"] = _risk_block()
        cycle["risk_attribution_status"] = RISK_NOT_PERSISTED
        cycle["risk_snapshot_status"] = RISK_NOT_PERSISTED
        cycle["shadow_sizing_observability_status"] = "SHADOW_DATA_NOT_PERSISTED_AT_ENTRY"
        cycle["shadow_sizing_evaluations"] = []
        cycle["shadow_formula_count"] = 0
        cycle["shadow_complete_evaluations"] = 0
        cycle["shadow_partial_evaluations"] = 0
        cycle["shadow_not_applicable_evaluations"] = 0
        cycle["shadow_quantity_deltas"] = []
        cycle["shadow_notional_deltas"] = []
        cycle["shadow_risk_deltas"] = []
        return

    total_risk, agg_status = ers.aggregate_initial_risk(snaps)
    first = snaps[0]
    rec = first.get("recommended_quantity")
    exe = first.get("executed_quantity")
    # Prefer sum of executed across snaps for multi-tranche quantity reporting
    exec_sum = 0.0
    exec_n = 0
    rec_sum = 0.0
    rec_n = 0
    formulas: list[str] = []
    risk_pcts: list[float] = []
    for s in snaps:
        if s.get("sizing_formula_id"):
            formulas.append(_s(s.get("sizing_formula_id")))
        eq = s.get("executed_quantity")
        if eq is not None:
            exec_sum += _f(eq)
            exec_n += 1
        rq = s.get("recommended_quantity")
        if rq is not None:
            rec_sum += _f(rq)
            rec_n += 1
        rp = s.get("initial_risk_pct_of_equity")
        if rp is not None:
            risk_pcts.append(_f(rp))

    executed_quantity = round(exec_sum, 6) if exec_n else exe
    recommended_quantity = round(rec_sum, 6) if rec_n else rec
    delta = None
    delta_pct = None
    if recommended_quantity is not None and executed_quantity is not None:
        delta = round(_f(executed_quantity) - _f(recommended_quantity), 8)
        if _f(recommended_quantity) != 0.0:
            delta_pct = round(100.0 * delta / _f(recommended_quantity), 8)

    snap_statuses = [_s(s.get("snapshot_status")) for s in snaps]
    if all(st == ers.STATUS_COMPLETE for st in snap_statuses):
        snap_status = ers.STATUS_COMPLETE
    elif any(st in {ers.STATUS_COMPLETE, ers.STATUS_PARTIAL, ers.STATUS_MINIMUM_ONLY} for st in snap_statuses):
        snap_status = ers.STATUS_PARTIAL
    else:
        snap_status = ers.STATUS_UNAVAILABLE

    present = 0
    checked = (
        "initial_risk_amount",
        "stop_distance_pct",
        "sizing_formula_id",
        "executed_quantity",
        "recommended_quantity",
        "entry_price",
        "execution_id",
        "cash_available",
    )
    for key in checked:
        if any(s.get(key) is not None and s.get(key) != "" for s in snaps):
            present += 1
    completeness = round(100.0 * present / len(checked), 2)

    gross = cycle.get("gross_realized_pnl")
    net = cycle.get("net_realized_pnl")
    gross_r = ers.r_multiple(_f(gross) if gross is not None else None, total_risk)
    net_r = ers.r_multiple(_f(net) if net is not None else None, total_risk)

    if cycle.get("status") != STATUS_CLOSED:
        risk_attr = agg_status if total_risk else (
            "INVALID_INITIAL_RISK" if snaps else RISK_NOT_PERSISTED
        )
        if cycle.get("status") == STATUS_OPEN and total_risk:
            risk_attr = "PARTIAL" if agg_status == "PARTIAL" else "COMPLETE"
        realized_r = None
        risk_adj = None
    else:
        if total_risk is None or total_risk <= 0:
            risk_attr = "INVALID_INITIAL_RISK" if snaps else RISK_NOT_PERSISTED
            realized_r = None
            risk_adj = None
        else:
            risk_attr = agg_status
            realized_r = net_r
            risk_adj = net_r

    stop_dist = first.get("stop_distance_pct")
    peak = total_risk
    initial_risk_pct = round(sum(risk_pcts) / len(risk_pcts), 8) if risk_pcts else first.get("initial_risk_pct_of_equity")

    cycle["risk"] = {
        "status": risk_attr,
        "risk_snapshot_status": snap_status,
        "risk_attribution_status": risk_attr,
        "sizing_formula_id": formulas[0] if formulas else None,
        "sizing_formula_ids": formulas,
        "recommended_quantity": recommended_quantity,
        "executed_quantity": executed_quantity,
        "sizing_quantity_delta": delta,
        "sizing_quantity_delta_pct": delta_pct,
        "initial_risk_amount": total_risk,
        "initial_risk_pct_of_equity": initial_risk_pct,
        "realized_r_multiple": realized_r,
        "gross_r_multiple": gross_r if cycle.get("status") == STATUS_CLOSED else None,
        "net_r_multiple": net_r if cycle.get("status") == STATUS_CLOSED else None,
        "risk_adjusted_return": risk_adj,
        "risk_data_completeness_pct": completeness,
        "maximum_adverse_excursion": UNAVAILABLE,
        "maximum_favorable_excursion": UNAVAILABLE,
        "drawdown_per_cycle": UNAVAILABLE,
        "peak_capital_at_risk": peak,
        "stop_distance_at_entry": stop_dist,
        "realized_pnl_per_initial_risk": realized_r,
        "entry_risk_snapshots": snaps,
        "deployment_ids": sorted(
            {
                _s((s.get("adaptive_deployment") or {}).get("deployment_id") or s.get("deployment_id"))
                for s in snaps
                if _s((s.get("adaptive_deployment") or {}).get("deployment_id") or s.get("deployment_id"))
            }
        ),
        "experiment_arms": sorted(
            {
                _s((s.get("adaptive_deployment") or {}).get("experiment_arm") or s.get("experiment_arm"))
                for s in snaps
                if _s((s.get("adaptive_deployment") or {}).get("experiment_arm") or s.get("experiment_arm"))
            }
        ),
        "note": (
            "Entry risk frozen from paper fill snapshots."
            if total_risk
            else "Snapshots present but initial_risk not computable."
        ),
    }
    cycle["risk_attribution_status"] = risk_attr
    cycle["risk_snapshot_status"] = snap_status
    cycle["sizing_formula_id"] = formulas[0] if formulas else None
    cycle["recommended_quantity"] = recommended_quantity
    cycle["executed_quantity"] = executed_quantity
    cycle["sizing_quantity_delta"] = delta
    cycle["sizing_quantity_delta_pct"] = delta_pct
    cycle["initial_risk_amount"] = total_risk
    cycle["initial_risk_pct_of_equity"] = initial_risk_pct
    cycle["realized_r_multiple"] = realized_r
    cycle["gross_r_multiple"] = gross_r if cycle.get("status") == STATUS_CLOSED else None
    cycle["net_r_multiple"] = net_r if cycle.get("status") == STATUS_CLOSED else None
    cycle["risk_adjusted_return"] = risk_adj
    cycle["risk_data_completeness_pct"] = completeness
    METRIC_CLASS["entry_risk_snapshot"] = "DIRECT_ACCOUNTING" if snaps else "UNAVAILABLE"

    import tae_paper_shadow_sizing as sso

    shadow_sum = sso.summarize_shadow_for_attribution(snaps)
    cycle["risk"]["shadow_sizing_observability_status"] = shadow_sum["shadow_sizing_observability_status"]
    cycle["risk"]["shadow_sizing_evaluations"] = shadow_sum["shadow_sizing_evaluations"]
    cycle["risk"]["shadow_formula_count"] = shadow_sum["shadow_formula_count"]
    for key in (
        "shadow_sizing_observability_status",
        "shadow_sizing_evaluations",
        "shadow_formula_count",
        "shadow_complete_evaluations",
        "shadow_partial_evaluations",
        "shadow_not_applicable_evaluations",
        "shadow_quantity_deltas",
        "shadow_notional_deltas",
        "shadow_risk_deltas",
        "shadow_sizing_experiment_id",
        "hypothetical_gross_pnl",
        "hypothetical_net_pnl",
    ):
        if key in shadow_sum:
            cycle[key] = shadow_sum[key]
    # Keep CF honesty on cycle
    cycle["hypothetical_gross_pnl"] = "REQUIRES_COUNTERFACTUAL"
    cycle["hypothetical_net_pnl"] = "REQUIRES_COUNTERFACTUAL"


def _completeness(cycle: dict[str, Any]) -> dict[str, Any]:
    required = [
        "strategy_arm", "ticker", "cycle_id", "status",
        "gross_realized_pnl", "total_transaction_costs", "net_realized_pnl",
    ]
    present = sum(1 for k in required if cycle.get(k) is not None and cycle.get(k) != "")
    linkage = _s(cycle.get("linkage_status") or "OK")
    pct = round(100.0 * present / len(required), 2)
    if cycle.get("status") == STATUS_CLOSED and abs(_f(cycle.get("unexplained_residual"))) > MAX_ATTRIBUTION_RESIDUAL_ABS:
        pct = min(pct, 80.0)
    if linkage == UNKNOWN_LINKAGE:
        pct = min(pct, 50.0)
    return {
        "attribution_completeness_pct": pct,
        "required_fields_present": present,
        "required_fields_total": len(required),
        "cost_coverage": cycle.get("cost_coverage"),
        "linkage_status": linkage,
    }


def _enrich_capital_days(cycle: dict[str, Any], net: float, max_cap: float) -> None:
    hold = cycle.get("holding_duration_seconds")
    if hold and hold > 0:
        days = float(hold) / 86400.0
        cycle["pnl_per_day"] = round(net / days, 6)
        cycle["pnl_per_1000_capital_days"] = round(net / (max(max_cap, 1e-9) / 1000.0 * days), 6)
    else:
        cycle["pnl_per_day"] = None
        cycle["pnl_per_1000_capital_days"] = None
    cycle["pnl_per_unit_capital"] = round(net / max(max_cap, 1e-9), 6)


def build_v1_cycles_from_trades(
    trades: list[dict[str, Any]],
    *,
    starting_capital: float | None = None,
) -> list[dict[str, Any]]:
    """FIFO BUY→SELL. cycle_id = V1CYC-{entry_execution_id} (restart-stable)."""
    rows = _dedupe_trades(
        [r for r in trades if _s(r.get("arm") or "V1").upper() in {"V1", ""}]
    )
    open_by_ticker: dict[str, list[dict[str, Any]]] = {}
    cycles: list[dict[str, Any]] = []

    for row in rows:
        action = _s(row.get("action")).upper()
        ticker = _s(row.get("ticker")).upper()
        if not ticker:
            continue
        if _is_buy_action(action):
            eid = _s(row.get("execution_id")) or f"V1EX-UNKNOWN-{ticker}-{_s(row.get('ts'))}"
            notional = _f(row.get("gross_notional"), _f(row.get("shares")) * _f(row.get("price")))
            cost = _trade_cost(row)
            coverage = "FULL" if row.get("total_transaction_cost") is not None else ("ZERO_COST" if cost == 0 else "NONE")
            cycle = {
                "schema_version": SCHEMA_VERSION,
                "strategy_arm": "V1",
                "ticker": ticker,
                "cycle_id": f"V1CYC-{eid}",
                "family_id": f"V1CYC-{eid}",
                "parent_cycle_id": None,
                "reentry_sequence": 0,
                "status": STATUS_OPEN,
                "entry_type": "INITIAL",
                "entry_decision_id": row.get("decision_id"),
                "entry_execution_id": eid,
                "exit_decision_id": None,
                "exit_execution_id": None,
                "entry_ts": row.get("ts"),
                "exit_ts": None,
                "entry_price": _f(row.get("price")),
                "exit_price": None,
                "quantity": _f(row.get("shares")),
                "tranche_count": 1,
                "tranche_ids": [],
                "initial_capital_committed": round(notional, 6),
                "additional_capital_committed": 0.0,
                "maximum_capital_committed": round(notional, 6),
                "average_capital_employed": round(notional, 6),
                "buy_transaction_costs": round(cost, 6),
                "sell_transaction_costs": 0.0,
                "total_transaction_costs": round(cost, 6),
                "gross_realized_pnl": None,
                "net_realized_pnl": None,
                "released_capital": None,
                "turnover": round(notional, 6),
                "cost_coverage": coverage,
                "linkage_status": "OK" if row.get("execution_id") else UNKNOWN_LINKAGE,
                "market_regime_entry": UNAVAILABLE,
                "market_regime_exit": UNAVAILABLE,
                "fills": [dict(row)],
                "authority": "OBSERVABILITY_ONLY",
            }
            _apply_entry_risk_attribution(cycle, fills=[row])
            open_by_ticker.setdefault(ticker, []).append(cycle)
        elif _is_sell_action(action):
            stack = open_by_ticker.get(ticker) or []
            if not stack:
                cycles.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "strategy_arm": "V1",
                        "ticker": ticker,
                        "cycle_id": f"V1UNK-{_s(row.get('execution_id')) or _s(row.get('ts'))}",
                        "status": STATUS_UNKNOWN,
                        "linkage_status": UNKNOWN_LINKAGE,
                        "exit_execution_id": row.get("execution_id"),
                        "exit_ts": row.get("ts"),
                        "gross_realized_pnl": None,
                        "net_realized_pnl": _f(row.get("realized_pnl_net"), row.get("realized_pnl")),
                        "note": "SELL without matched BUY — not guessed",
                        "authority": "OBSERVABILITY_ONLY",
                    }
                )
                continue
            cycle = stack.pop(0)
            _close_v1_cycle(cycle, row)
            cycles.append(cycle)

    for stack in open_by_ticker.values():
        cycles.extend(stack)

    buy_times = sorted(_s(r.get("ts")) for r in rows if _is_buy_action(_s(r.get("action"))))
    for c in cycles:
        if c.get("status") != STATUS_CLOSED:
            continue
        exit_ts = _s(c.get("exit_ts"))
        nxt = next((t for t in buy_times if t > exit_ts), None)
        c["redeployment_timestamp"] = nxt
        c["time_to_redeployment_seconds"] = _duration_seconds(exit_ts, nxt) if nxt else None
        c["cash_idle_after_exit"] = UNAVAILABLE
        if starting_capital and starting_capital > 0:
            c["capital_utilization_pct"] = round(
                100.0 * _f(c.get("maximum_capital_committed")) / starting_capital, 6
            )
    return cycles


def _close_v1_cycle(cycle: dict[str, Any], sell: dict[str, Any]) -> None:
    shares = _f(sell.get("shares"), cycle.get("quantity"))
    exit_px = _f(sell.get("price"))
    gross_proceeds = _f(sell.get("gross_proceeds"), shares * exit_px)
    sell_cost = _trade_cost(sell)
    buy_cost = _f(cycle.get("buy_transaction_costs"))
    total_costs = round(buy_cost + sell_cost, 6)
    if sell.get("realized_pnl_net") is not None:
        net = round(_f(sell.get("realized_pnl_net")), 6)
        gross = round(net + total_costs, 6)
    elif sell.get("realized_pnl") is not None and sell_cost == 0.0 and buy_cost == 0.0:
        net = round(_f(sell.get("realized_pnl")), 6)
        gross = net
    else:
        gross = round(gross_proceeds - _f(cycle.get("initial_capital_committed")), 6)
        net = round(gross - total_costs, 6)

    flags = _exit_flags(_s(sell.get("reason") or sell.get("exit_reason")))
    comps = _component_block(gross=gross, costs=total_costs, net=net)
    max_cap = _f(cycle.get("maximum_capital_committed"))
    cycle.update(
        {
            "status": STATUS_CLOSED,
            "exit_decision_id": sell.get("decision_id"),
            "exit_execution_id": sell.get("execution_id"),
            "exit_ts": sell.get("ts"),
            "exit_price": exit_px,
            "sell_transaction_costs": round(sell_cost, 6),
            "total_transaction_costs": total_costs,
            "gross_realized_pnl": gross,
            "net_realized_pnl": net,
            "gross_return_pct": round(100.0 * gross / max(max_cap, 1e-9), 6),
            "net_return_pct": round(100.0 * net / max(max_cap, 1e-9), 6),
            "released_capital": round(_f(sell.get("net"), gross_proceeds - sell_cost), 6),
            "turnover": round(_f(cycle.get("turnover")) + gross_proceeds, 6),
            "holding_duration_seconds": _duration_seconds(cycle.get("entry_ts"), sell.get("ts")),
            "cost_coverage": (
                "FULL"
                if sell.get("total_transaction_cost") is not None
                and cycle.get("cost_coverage") in {"FULL", "ZERO_COST"}
                else cycle.get("cost_coverage") or "PARTIAL"
            ),
            **flags,
            **comps,
            "risk": _risk_block(),
        }
    )
    _enrich_capital_days(cycle, net, max_cap)
    cycle["fills"] = list(cycle.get("fills") or []) + [dict(sell)]
    _apply_entry_risk_attribution(cycle, fills=cycle.get("fills"))
    cycle.update(_completeness(cycle))


def build_v2_cycles(
    *,
    cycle_store: dict[str, Any],
    tranches: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    reentry_store: dict[str, Any] | None = None,
    starting_capital: float | None = None,
) -> list[dict[str, Any]]:
    cycles_raw = (cycle_store or {}).get("cycles") or {}
    trades = _dedupe_trades(trades)
    trades_by_cycle: dict[str, list[dict[str, Any]]] = {}
    trades_by_eid: dict[str, dict[str, Any]] = {}
    for t in trades:
        eid = _s(t.get("execution_id"))
        if eid:
            trades_by_eid[eid] = t
        cid = _s(t.get("cycle_id"))
        if cid:
            trades_by_cycle.setdefault(cid, []).append(t)

    tranches_by_cycle: dict[str, list[dict[str, Any]]] = {}
    for tr in tranches:
        if _s(tr.get("status")).upper() != "FILLED" and _f(tr.get("quantity")) <= 0:
            continue
        if _s(tr.get("status")).upper() not in {"FILLED", ""}:
            if _s(tr.get("status")).upper() in {"BLOCKED", "REJECTED"}:
                continue
        cid = _s(tr.get("cycle_id"))
        if cid:
            tranches_by_cycle.setdefault(cid, []).append(tr)

    parent_of: dict[str, str] = {}
    family_of: dict[str, str] = {}
    seq_of: dict[str, int] = {}
    if isinstance(reentry_store, dict):
        by = reentry_store.get("by_ticker") if isinstance(reentry_store.get("by_ticker"), dict) else {}
        for _tk, row in by.items():
            if not isinstance(row, dict):
                continue
            last = _s(row.get("last_cycle_id"))
            active = _s(row.get("active_cycle_id"))
            if last and active and last != active:
                parent_of[active] = last
                family_of[last] = family_of.get(last) or f"V2FAM-{last}"
                family_of[active] = family_of[last]
                seq_of[active] = int(_f(row.get("completed_profit_cycles"), 1))

    out: list[dict[str, Any]] = []
    for cid, raw in cycles_raw.items():
        if not isinstance(raw, dict):
            continue
        cid = _s(cid or raw.get("cycle_id"))
        ticker = _s(raw.get("ticker")).upper()
        status_raw = _s(raw.get("status")).upper()
        trs = sorted(tranches_by_cycle.get(cid) or [], key=lambda x: int(x.get("sequence") or 0))
        buy_costs = 0.0
        buy_notional = 0.0
        cost_full = True
        entry_eid = None
        entry_did = None
        entry_ts = raw.get("opened_at")
        entry_type = "INITIAL"
        for i, tr in enumerate(trs):
            eid = _s(tr.get("execution_id"))
            trade = trades_by_eid.get(eid) or {}
            filled = _f(tr.get("filled_value"), _f(tr.get("quantity")) * _f(tr.get("price")))
            buy_notional += filled
            c = _trade_cost(trade) if trade else 0.0
            if trade and trade.get("total_transaction_cost") is None and filled > 0:
                cost_full = False
            elif not trade and filled > 0:
                cost_full = False
            buy_costs += c
            if i == 0:
                entry_eid = eid or None
                entry_did = tr.get("decision_id")
                entry_ts = tr.get("filled_at") or tr.get("requested_at") or entry_ts
                entry_type = _entry_type(_s(trade.get("action")) or "OPEN", in_reentry=cid in parent_of)

        sell_rows = [t for t in trades_by_cycle.get(cid, []) if _is_sell_action(_s(t.get("action")))]
        max_cap = round(max(buy_notional, _f(raw.get("budget_used"))), 6)
        avg_cap = round(buy_notional / max(len(trs), 1), 6) if trs else round(_f(raw.get("budget_used")), 6)
        additional = round(max(0.0, buy_notional - (_f(trs[0].get("filled_value")) if trs else 0.0)), 6)
        is_reentry = cid in parent_of

        cycle: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "strategy_arm": "V2",
            "ticker": ticker,
            "cycle_id": cid,
            "family_id": family_of.get(cid) or f"V2FAM-{cid}",
            "parent_cycle_id": parent_of.get(cid),
            "reentry_sequence": seq_of.get(cid, 1 if is_reentry else 0),
            "status": STATUS_OPEN,
            "entry_type": "REENTRY" if is_reentry else entry_type,
            "entry_decision_id": entry_did,
            "entry_execution_id": entry_eid,
            "exit_decision_id": None,
            "exit_execution_id": None,
            "entry_ts": entry_ts,
            "exit_ts": raw.get("closed_at"),
            "tranche_count": int(raw.get("tranche_count") or len(trs) or 0),
            "tranche_ids": [_s(t.get("tranche_id")) for t in trs if _s(t.get("tranche_id"))],
            "initial_capital_committed": round(_f(trs[0].get("filled_value")) if trs else 0.0, 6),
            "additional_capital_committed": additional,
            "maximum_capital_committed": max_cap,
            "average_capital_employed": avg_cap if avg_cap > 0 else max_cap,
            "buy_transaction_costs": round(buy_costs, 6),
            "sell_transaction_costs": 0.0,
            "total_transaction_costs": round(buy_costs, 6),
            "turnover": round(buy_notional, 6),
            "cost_coverage": "FULL" if cost_full and trs else ("NONE" if not trs else "PARTIAL"),
            "linkage_status": "OK" if trs else UNKNOWN_LINKAGE,
            "add_tranche_capital": additional,
            "add_tranche_contribution": CF,
            "reentry_contribution": CF if is_reentry else None,
            "market_regime_entry": UNAVAILABLE,
            "market_regime_exit": UNAVAILABLE,
            "authority": "OBSERVABILITY_ONLY",
            "risk": _risk_block(),
        }

        if status_raw == "CLOSED" or sell_rows:
            sell = sell_rows[-1] if sell_rows else {}
            sell_cost = _trade_cost(sell) if sell else 0.0
            if sell and sell.get("total_transaction_cost") is None:
                cycle["cost_coverage"] = "PARTIAL"
            gross_proceeds = _f(sell.get("gross_proceeds"), _f(sell.get("shares")) * _f(sell.get("price")))
            total_costs = round(buy_costs + sell_cost, 6)
            cycle_realized = raw.get("realized_pnl")
            if sell.get("realized_pnl_net") is not None:
                net = round(_f(sell.get("realized_pnl_net")), 6)
                gross = round(net + total_costs, 6)
            elif cycle_realized is not None and sell_cost == 0.0 and buy_costs == 0.0:
                net = round(_f(cycle_realized), 6)
                gross = net
            elif cycle_realized is not None:
                net = round(_f(cycle_realized), 6)
                gross = round(net + total_costs, 6)
            elif gross_proceeds > 0 and buy_notional > 0:
                gross = round(gross_proceeds - buy_notional, 6)
                net = round(gross - total_costs, 6)
            else:
                net = round(_f(cycle_realized), 6)
                gross = round(net + total_costs, 6)

            flags = _exit_flags(_s(raw.get("close_reason") or sell.get("reason")))
            comps = _component_block(gross=gross, costs=total_costs, net=net)
            cycle.update(
                {
                    "status": STATUS_CLOSED,
                    "exit_decision_id": sell.get("decision_id"),
                    "exit_execution_id": sell.get("execution_id") or raw.get("close_execution_id"),
                    "exit_ts": sell.get("ts") or raw.get("closed_at"),
                    "exit_price": _f(sell.get("price")),
                    "sell_transaction_costs": round(sell_cost, 6),
                    "total_transaction_costs": total_costs,
                    "gross_realized_pnl": gross,
                    "net_realized_pnl": net,
                    "released_capital": round(_f(sell.get("net"), gross_proceeds - sell_cost), 6),
                    "turnover": round(buy_notional + gross_proceeds, 6),
                    "holding_duration_seconds": _duration_seconds(
                        cycle.get("entry_ts"), sell.get("ts") or raw.get("closed_at")
                    ),
                    "gross_return_pct": round(100.0 * gross / max(max_cap, 1e-9), 6),
                    "net_return_pct": round(100.0 * net / max(max_cap, 1e-9), 6),
                    **flags,
                    **comps,
                }
            )
            _enrich_capital_days(cycle, net, max_cap)
        elif status_raw == "CLOSING":
            cycle["status"] = STATUS_INCOMPLETE
        else:
            cycle["status"] = STATUS_OPEN
            cycle["gross_realized_pnl"] = None
            cycle["net_realized_pnl"] = None

        if starting_capital and starting_capital > 0:
            cycle["capital_utilization_pct"] = round(100.0 * max_cap / starting_capital, 6)
        _apply_entry_risk_attribution(
            cycle,
            raw_cycle=raw,
            tranches=trs,
            trades=trades_by_cycle.get(cid) or list(trades_by_eid.values()),
        )
        cycle.update(_completeness(cycle))
        out.append(cycle)

    buy_ts = sorted(_s(t.get("ts")) for t in trades if _is_buy_action(_s(t.get("action"))))
    for c in out:
        if c.get("status") != STATUS_CLOSED:
            continue
        exit_ts = _s(c.get("exit_ts"))
        nxt = next((t for t in buy_ts if t > exit_ts), None)
        c["redeployment_timestamp"] = nxt
        c["time_to_redeployment_seconds"] = _duration_seconds(exit_ts, nxt) if nxt else None
        c["cash_idle_after_exit"] = UNAVAILABLE
    return out


def upsert_cycles(store: dict[str, Any], cycles: list[dict[str, Any]]) -> dict[str, Any]:
    store = deepcopy(store) if store else empty_store()
    cycles_map = dict(store.get("cycles") or {})
    seen = set(store.get("seen_execution_ids") or [])
    for c in cycles:
        cid = _s(c.get("cycle_id"))
        if not cid:
            continue
        prev = cycles_map.get(cid)
        if prev and prev.get("status") == STATUS_CLOSED and c.get("status") != STATUS_CLOSED:
            continue
        cycles_map[cid] = c
        for key in ("entry_execution_id", "exit_execution_id"):
            eid = _s(c.get(key))
            if eid:
                seen.add(eid)
        for fill in c.get("fills") or []:
            eid = _s(fill.get("execution_id"))
            if eid:
                seen.add(eid)
    store["cycles"] = cycles_map
    store["seen_execution_ids"] = sorted(seen)
    return store


def summarize_cycles(
    cycles: list[dict[str, Any]],
    *,
    arm: str,
    starting_capital: float | None = None,
) -> dict[str, Any]:
    arm_cycles = [c for c in cycles if _s(c.get("strategy_arm")).upper() == arm.upper()]
    closed = [c for c in arm_cycles if c.get("status") == STATUS_CLOSED]
    open_c = [c for c in arm_cycles if c.get("status") == STATUS_OPEN]
    incomplete = [c for c in arm_cycles if c.get("status") in {STATUS_INCOMPLETE, STATUS_UNKNOWN}]

    gross = sum(_f(c.get("gross_realized_pnl")) for c in closed)
    costs = sum(_f(c.get("total_transaction_costs")) for c in closed)
    net = sum(_f(c.get("net_realized_pnl")) for c in closed)
    turnover = sum(_f(c.get("turnover")) for c in closed)
    wins = [c for c in closed if _f(c.get("net_realized_pnl")) > 0]
    losses = [c for c in closed if _f(c.get("net_realized_pnl")) < 0]
    win_pnl = sum(_f(c.get("net_realized_pnl")) for c in wins)
    loss_pnl = sum(_f(c.get("net_realized_pnl")) for c in losses)
    avg_win = (win_pnl / len(wins)) if wins else 0.0
    avg_loss = (loss_pnl / len(losses)) if losses else 0.0
    if loss_pnl < 0:
        profit_factor: float | None = win_pnl / abs(loss_pnl)
        pf_inf = False
    else:
        profit_factor = None if win_pnl > 0 else 0.0
        pf_inf = win_pnl > 0
    expectancy = (net / len(closed)) if closed else 0.0
    hold_vals = [_f(c.get("holding_duration_seconds")) for c in closed if c.get("holding_duration_seconds") is not None]
    avg_hold = (sum(hold_vals) / len(hold_vals)) if hold_vals else None
    ttr = [_f(c.get("time_to_redeployment_seconds")) for c in closed if c.get("time_to_redeployment_seconds") is not None]
    avg_ttr = (sum(ttr) / len(ttr)) if ttr else None
    residual = sum(_f(c.get("unexplained_residual")) for c in closed)
    completeness = []
    for c in closed:
        if c.get("attribution_completeness_pct") is not None:
            completeness.append(_f(c.get("attribution_completeness_pct")))
        else:
            completeness.append(_f(_completeness(c).get("attribution_completeness_pct")))
    avg_complete = (sum(completeness) / len(completeness)) if completeness else 0.0
    max_caps = [_f(c.get("maximum_capital_committed")) for c in arm_cycles]
    avg_util = None
    if starting_capital and starting_capital > 0 and max_caps:
        avg_util = round(100.0 * (sum(max_caps) / len(max_caps)) / starting_capital, 6)
    capital_days = 0.0
    for c in closed:
        hold = _f(c.get("holding_duration_seconds"))
        cap = _f(c.get("average_capital_employed") or c.get("maximum_capital_committed"))
        if hold > 0 and cap > 0:
            capital_days += (hold / 86400.0) * (cap / 1000.0)
    pnl_per_cap_day = round(net / capital_days, 6) if capital_days > 0 else None
    fills = sum(int(c.get("tranche_count") or 1) + 1 for c in closed)
    net_per_fill = round(net / fills, 6) if fills else None

    risk_statuses = [_s(c.get("risk_attribution_status") or ((c.get("risk") or {}).get("risk_attribution_status"))) for c in arm_cycles]
    if not risk_statuses:
        risk_summary = RISK_NOT_PERSISTED
    elif all(s == "COMPLETE" for s in risk_statuses if s):
        risk_summary = "COMPLETE"
    elif any(s in {"COMPLETE", "PARTIAL"} for s in risk_statuses):
        risk_summary = "PARTIAL"
    elif any(s == "INVALID_INITIAL_RISK" for s in risk_statuses):
        risk_summary = "INVALID_INITIAL_RISK"
    else:
        risk_summary = RISK_NOT_PERSISTED

    return {
        "strategy_arm": arm.upper(),
        "closed_cycles": len(closed),
        "open_cycles": len(open_c),
        "incomplete_or_unknown_cycles": len(incomplete),
        "gross_realized_pnl": round(gross, 6),
        "transaction_costs": round(costs, 6),
        "net_realized_pnl": round(net, 6),
        "win_rate": round(len(wins) / len(closed), 6) if closed else 0.0,
        "average_win": round(avg_win, 6),
        "average_loss": round(avg_loss, 6),
        "profit_factor": round(profit_factor, 6) if profit_factor is not None else None,
        "profit_factor_infinite": pf_inf,
        "expectancy_per_closed_cycle": round(expectancy, 6),
        "turnover": round(turnover, 6),
        "average_holding_seconds": round(avg_hold, 3) if avg_hold is not None else None,
        "capital_utilization_pct": avg_util,
        "average_time_to_redeployment_seconds": round(avg_ttr, 3) if avg_ttr is not None else None,
        "net_pnl_per_fill": net_per_fill,
        "net_pnl_per_1000_capital_days": pnl_per_cap_day,
        "unexplained_residual": round(residual, 6),
        "attribution_completeness_pct": round(avg_complete, 2),
        "counterfactual_fields_status": CF,
        "risk_attribution_status": risk_summary,
        "opportunity_cost_status": UNAVAILABLE,
        "sample_sufficient_for_winner": len(closed) >= MIN_CLOSED_CYCLES_FOR_WINNER,
        "min_closed_cycles_for_winner": MIN_CLOSED_CYCLES_FOR_WINNER,
        "min_observation_days_for_winner": MIN_OBSERVATION_DAYS_FOR_WINNER,
    }


def compare_arms(v1: dict[str, Any], v2: dict[str, Any]) -> dict[str, Any]:
    def delta(key: str) -> float | None:
        if v1.get(key) is None or v2.get(key) is None:
            return None
        return round(_f(v1.get(key)) - _f(v2.get(key)), 6)

    sufficient = bool(v1.get("sample_sufficient_for_winner") and v2.get("sample_sufficient_for_winner"))
    winner = None
    if sufficient:
        if _f(v1.get("net_realized_pnl")) > _f(v2.get("net_realized_pnl")):
            winner = "V1"
        elif _f(v2.get("net_realized_pnl")) > _f(v1.get("net_realized_pnl")):
            winner = "V2"
        else:
            winner = "TIE"
    return {
        "net_pnl_v1_minus_v2": delta("net_realized_pnl"),
        "profit_factor_v1_minus_v2": delta("profit_factor"),
        "expectancy_v1_minus_v2": delta("expectancy_per_closed_cycle"),
        "costs_v1_minus_v2": delta("transaction_costs"),
        "turnover_v1_minus_v2": delta("turnover"),
        "capital_utilization_v1_minus_v2": delta("capital_utilization_pct"),
        "pnl_per_capital_day_v1_minus_v2": delta("net_pnl_per_1000_capital_days"),
        "winner_declared": winner,
        "winner_status": "DECLARED" if sufficient else "INSUFFICIENT_SAMPLE",
    }


def build_summary_from_store(
    store: dict[str, Any],
    *,
    v1_starting: float = 30000.0,
    v2_starting: float = 30000.0,
    sizing_counterfactual: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cycles = list((store.get("cycles") or {}).values())
    v1 = summarize_cycles(cycles, arm="V1", starting_capital=v1_starting)
    v2 = summarize_cycles(cycles, arm="V2", starting_capital=v2_starting)
    out = {
        "schema": "tae.paper.economic_attribution.summary.v1",
        "schema_version": SCHEMA_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "generated_at": _now(),
        "authority": "OBSERVABILITY_ONLY",
        "v1": v1,
        "v2": v2,
        "comparison": compare_arms(v1, v2),
        "rebuild_stats": store.get("rebuild_stats") or {},
    }
    if sizing_counterfactual:
        # Keep CF economics separate from executed arm summaries
        out["sizing_counterfactual"] = {
            "authority": "OBSERVABILITY_ONLY",
            "counterfactual_level": sizing_counterfactual.get("counterfactual_level"),
            "counterfactual_scope": sizing_counterfactual.get("counterfactual_scope"),
            "exit_model": sizing_counterfactual.get("exit_model"),
            "fill_model": sizing_counterfactual.get("fill_model"),
            "honesty_gates": sizing_counterfactual.get("honesty_gates"),
            "phase7_rescale_status": sizing_counterfactual.get("phase7_rescale_status"),
            "reconciliation_pass": sizing_counterfactual.get("reconciliation_pass"),
            "per_formula": sizing_counterfactual.get("per_formula") or {},
            "note": sizing_counterfactual.get("note"),
            "separated_from_executed": True,
        }
    else:
        out["sizing_counterfactual"] = {
            "status": "NOT_RUN",
            "counterfactual_fields_status": CF,
        }
    return out


def rebuild_from_journals(
    *,
    paths: dict[str, Path] | None = None,
    store_out: Path | None = None,
    v1_starting: float = 30000.0,
    v2_starting: float = 30000.0,
) -> dict[str, Any]:
    """READ-ONLY rebuild from parallel journals. Does not mutate source journals."""
    from tae_parallel_paper_config import paths as default_paths

    p = paths or default_paths()
    v1_trades = read_jsonl(p["v1_trades"])
    v2_trades = read_jsonl(p["v2_trades"])
    tranches = read_jsonl(p["v2_tranches"])
    cycle_store: dict[str, Any] = {}
    if p["v2_cycles"].is_file():
        try:
            cycle_store = json.loads(p["v2_cycles"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cycle_store = {}
    reentry_store: dict[str, Any] = {}
    rp = p.get("v2_reentry")
    if rp and Path(rp).is_file():
        try:
            reentry_store = json.loads(Path(rp).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reentry_store = {}

    v1_cycles = build_v1_cycles_from_trades(v1_trades, starting_capital=v1_starting)
    v2_cycles = build_v2_cycles(
        cycle_store=cycle_store if isinstance(cycle_store, dict) else {},
        tranches=tranches,
        trades=v2_trades,
        reentry_store=reentry_store,
        starting_capital=v2_starting,
    )
    all_cycles = v1_cycles + v2_cycles
    store = upsert_cycles(empty_store(), all_cycles)
    stats = {
        "v1_trades_read": len(v1_trades),
        "v2_trades_read": len(v2_trades),
        "v2_tranches_read": len(tranches),
        "v1_cycles": len(v1_cycles),
        "v2_cycles": len(v2_cycles),
        "closed": sum(1 for c in all_cycles if c.get("status") == STATUS_CLOSED),
        "open": sum(1 for c in all_cycles if c.get("status") == STATUS_OPEN),
        "incomplete_or_unknown": sum(
            1 for c in all_cycles if c.get("status") in {STATUS_INCOMPLETE, STATUS_UNKNOWN}
        ),
        "deterministic": True,
        "source_journals_mutated": False,
    }
    store["rebuild_stats"] = stats
    out = save_store(store, store_out)

    cf_summary = None
    try:
        import tae_paper_sizing_counterfactual_replay as scf

        cf_dir = None
        if isinstance(p.get("root"), Path):
            cf_dir = p["root"] / "counterfactual"
        cf = scf.run_sizing_counterfactual_replay(
            v1_trades=v1_trades,
            v2_trades=v2_trades,
            v1_starting=v1_starting,
            v2_starting=v2_starting,
            output_dir=cf_dir,
        )
        cf_summary = cf.get("summary")
        stats["sizing_counterfactual_reconciliation_pass"] = bool(cf.get("reconciliation_pass"))
        stats["sizing_counterfactual_ledgers"] = int((cf_summary or {}).get("ledger_count") or 0)
    except Exception as exc:
        stats["sizing_counterfactual_error"] = str(exc)

    summary = build_summary_from_store(
        store,
        v1_starting=v1_starting,
        v2_starting=v2_starting,
        sizing_counterfactual=cf_summary,
    )
    summary["rebuild_stats"] = stats
    sp = Path(store_out).parent / "economic_summary.json" if store_out else summary_path()
    tmp = sp.with_suffix(sp.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, sp)
    return {"store_path": str(out), "summary_path": str(sp), "stats": stats, "summary": summary}


def refresh_parallel_attribution(
    paths: dict[str, Path] | None = None,
    *,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Post-accounting hook: rebuild attribution from journals (idempotent)."""
    from tae_parallel_paper_config import load_parallel_paper_config

    cfg = cfg or load_parallel_paper_config()
    return rebuild_from_journals(
        paths=paths,
        v1_starting=float(cfg.get("V1_STARTING_CAPITAL") or 30000.0),
        v2_starting=float(cfg.get("V2_STARTING_CAPITAL") or 30000.0),
    )


__all__ = [
    "SCHEMA_VERSION",
    "CF",
    "UNAVAILABLE",
    "RISK_NOT_PERSISTED",
    "build_v1_cycles_from_trades",
    "build_v2_cycles",
    "upsert_cycles",
    "rebuild_from_journals",
    "refresh_parallel_attribution",
    "summarize_cycles",
    "compare_arms",
    "load_store",
    "save_store",
    "store_path",
    "normalize_decision_id",
]
