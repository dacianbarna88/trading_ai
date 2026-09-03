#!/usr/bin/env python3
"""
Parallel PAPER orchestrator — isolated V1 benchmark + V2 arms.

PAPER_ONLY | NO_BROKER | NO_LIVE | fail-isolated
Does not read/write canonical paper_portfolio.json or live_bot.py.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import traceback
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import tae_paper_execution as pe
import tae_strategy_v3_learning_policy as v3pol
import tae_strategy_v2_buy_policy as pol
import tae_strategy_v2_exit_policy as xp
import tae_strategy_v2_foundation as v2
import tae_strategy_v2_reentry_policy as reentry
import tae_strategy_v2_routing as route
import tae_strategy_v1_trailing as v1trail
import tae_strategy_v1_vol_stop as v1volstop
import tae_strategy_v2_kelly_sizing as v2kelly
try:
    from tae_strategy_v2_trailing import V2_PROFIT_TRAILING_REASON
except ImportError:  # fail-soft constant for V2 profit-trailing reason
    V2_PROFIT_TRAILING_REASON = "V2_PROFIT_TRAILING_5_2"
from tae_parallel_paper_config import (
    load_parallel_paper_config,
    paths,
    v2_parallel_mutation_allowed,
)
from tae_strategy_v2_config import load_strategy_v2_config
from tae_strategy_v2_hard_risk_adapter import (
    buy_policy_hard_risk_fields,
    classify_hard_risk_for_v2,
    fill_time_blocks_add,
)

MarkProvider = Callable[[list[str]], dict[str, dict[str, Any]]]

BLOCKED_PAPER_ISOLATION = "BLOCKED_PAPER_ISOLATION"
PHASE_MANAGE = "manage"
PHASE_ENTRY = "entry"
PHASE_ALL = "all"

# V1/V2 entry-eligibility score floor (matches live_bot.MIN_SCORE_TO_BUY,
# duplicated here as three separate literal 80s until 2026-08-25, when it
# was relaxed to 60 — too little candidate turnover was showstopping V1/V2
# in the Phase 5 soak: with a 25-ticker watchlist, only 8 tickers cleared
# 80 on a typical day, and once V1 held all of them there was nothing left
# to evaluate. One named constant now, not three literals to keep in sync.
V1_V2_ENTRY_MIN_SCORE = 60

# V2 had no position-count cap at all: it opened a new position for every
# candidate that cleared entry across the 100-ticker watchlist, diluting a
# real per-trade edge (profit factor 10.49 on closed trades, measured over
# 41 days) across 50 concurrent ~$520 positions — index-level diversification
# instead of a concentrated bet on a proven edge. This caps NEW-ticker opens
# only; adding to an already-held position is never blocked by this.
V2_MAX_POSITIONS = 18


class _PhaseComplete(Exception):
    """Internal control-flow for phase early exit inside _run_v2_arm."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _f(v: Any, d: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return d
        return x
    except (TypeError, ValueError):
        return d


def _s(v: Any) -> str:
    return str(v or "").strip()


def _atomic_write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _entry_price_allowed(snap: dict[str, Any] | None, mark_status: str) -> tuple[bool, str]:
    """BUY/REBUY require a non-closed, non-stale usable mark. Protective SELL may use MARKET_CLOSED."""
    freshness = _s((snap or {}).get("mark_freshness") or mark_status).upper()
    session = _s((snap or {}).get("market_session")).upper()
    if freshness in {"MARKET_CLOSED", "MARKET_CLOSED_VALID_PREVIOUS_CLOSE"} or session == "CLOSED":
        return False, "MARKET_CLOSED"
    if freshness in {"STALE", "MARK_STALE", "INVALID", "MARK_UNAVAILABLE", "UNAVAILABLE"}:
        return False, "MARK_STALE"
    if (snap or {}).get("data_fresh") is False:
        return False, "MARK_STALE"
    return True, "OK"


def _assert_paper_isolation(cfg: dict[str, Any] | None = None) -> None:
    cfg = cfg or load_parallel_paper_config()
    if cfg.get("V2_LIVE_ENABLED") is True:
        raise RuntimeError(BLOCKED_PAPER_ISOLATION)
    if str(cfg.get("V2_ACTIVATION_SCOPE") or "").upper() == "LIVE":
        raise RuntimeError(BLOCKED_PAPER_ISOLATION)


def _log_capital_event(event: str, **fields: Any) -> None:
    """Append structured capital-cycle events to parallel_paper.log (no new dashboard)."""
    p = paths()
    parts = [f"{_now()} {event}"]
    for key in (
        "arm",
        "ticker",
        "quantity",
        "price",
        "gross",
        "costs",
        "net",
        "realized_pnl",
        "cash_before",
        "cash_after",
        "cycle_id",
        "decision_id",
        "execution_id",
        "reason",
    ):
        if key in fields and fields[key] is not None:
            parts.append(f"{key}={fields[key]}")
    line = " ".join(parts) + "\n"
    for name in ("log", "daemon_log"):
        log = p.get(name)
        if not log:
            continue
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass


def _paper_tx_cost_cfg(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicit PAPER-only cost configuration for parallel fill paths."""
    from tae_paper_transaction_costs import load_paper_tx_cost_config

    return load_paper_tx_cost_config(cfg)


def _take_fill_economics(portfolio: dict[str, Any]) -> dict[str, Any]:
    eco = portfolio.get("_last_paper_fill_economics")
    return dict(eco) if isinstance(eco, dict) else {}


def _apply_adaptive_deployment_to_v2_buy(
    bd: dict[str, Any],
    binp: Any,
    *,
    ticker: str,
    portfolio: dict[str, Any],
    v2_cfg: dict[str, Any],
    v2_add_authorized: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    """
    Resize an already-eligible V2 OPEN/ADD tranche via Adaptive Deployment.

    Does not invent eligibility. Never exceeds V2 proposed_tranche_value (control).
    For authorized ADD_TRANCHE outside canary ticker_scope: CONTROL fallback (non-blocking).
    Returns (bd, deployment_meta_or_None, block_reason_or_None).
    """
    try:
        import tae_adaptive_deployment as adep
    except Exception:
        return bd, None, None

    control = _f(bd.get("proposed_tranche_value"))
    if control <= 0:
        return bd, None, None
    cash = _f(getattr(binp, "cash", None), _f(portfolio.get("cash")))
    reserve = _f(v2_cfg.get("V2_MIN_CASH_RESERVE") or v2_cfg.get("min_cash_reserve"), 500.0)
    sizing = adep.resolve_buy_notional(
        control_notional=control,
        inputs={
            "cash_available": cash,
            "cash_reserve": reserve,
            "maximum_position_notional": control,
            "confidence": _f(getattr(binp, "score", None), 0.5) / 100.0
            if _f(getattr(binp, "score", None), 0.0) > 1.0
            else _f(getattr(binp, "score", None), 0.5),
            "current_open_positions": len(
                [x for x in (portfolio.get("positions") or {}).values() if _f((x or {}).get("shares")) > 0]
            ),
            "maximum_positions": int(_f(v2_cfg.get("max_open_positions"), 20)),
        },
        ticker=ticker,
        arm="V2",
        v2_add_authorized=bool(v2_add_authorized),
    )
    meta = dict(sizing.get("deployment") or {})
    # Telemetry on decision payload (reuse adaptive_deployment dict; no parallel schema).
    def _attach_scope_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
        out = dict(payload)
        out["adaptive_arm"] = sizing.get("adaptive_arm") or sizing.get("used_arm")
        out["adaptive_reason"] = sizing.get("adaptive_reason") or sizing.get("selection_note")
        out["ticker_scope_match"] = sizing.get("ticker_scope_match")
        out["challenger_exposure"] = bool(sizing.get("challenger_exposure"))
        out["v2_add_authorized"] = bool(v2_add_authorized)
        out["scope_result"] = sizing.get("scope_result")
        out["decision"] = sizing.get("decision")
        return out

    control_notes = {
        "V2_OUT_OF_ENTRY_SCOPE_USE_CONTROL",
        "NEW_BUY_OUT_OF_ENTRY_SCOPE_USE_CONTROL",
        getattr(adep, "CONTROL_FALLBACK_OUT_OF_SCOPE", "CONTROL_FALLBACK_OUT_OF_SCOPE"),
    }
    if sizing.get("selection_note") in control_notes or (
        not sizing.get("blocked") and _s(sizing.get("used_arm")).upper() == "CONTROL"
        and sizing.get("scope_result") == getattr(adep, "CONTROL_FALLBACK_OUT_OF_SCOPE", "")
    ):
        bd = dict(bd)
        bd["adaptive_deployment"] = _attach_scope_telemetry(meta)
        bd["authorized_notional"] = control
        return bd, bd["adaptive_deployment"], None
    if sizing.get("blocked"):
        return bd, _attach_scope_telemetry(meta), _s(sizing.get("reason_code")) or "BLOCKED_ADAPTIVE_DEPLOYMENT"
    if sizing.get("used_arm") == "CHALLENGER":
        bd = dict(bd)
        exec_n = _f(sizing.get("executed_notional"), control)
        bd["proposed_tranche_value"] = min(control, exec_n)
        meta = _attach_scope_telemetry(meta)
        bd["adaptive_deployment"] = meta
        bd["v2_tranche_cap"] = control
        bd["recommended_notional"] = sizing.get("challenger_notional_raw")
        bd["authorized_notional"] = bd["proposed_tranche_value"]
        meta["v2_tranche_cap"] = control
        meta["v2_tranche_index"] = bd.get("tranche_index") or bd.get("next_tranche_index")
        meta["v2_tranche_trigger"] = bd.get("tranche_gate_code") or bd.get("reason_code")
        meta["recommended_notional"] = sizing.get("challenger_notional_raw")
        meta["authorized_notional"] = bd["proposed_tranche_value"]
        meta["executed_notional"] = bd["proposed_tranche_value"]
        return bd, meta, None
    return bd, _attach_scope_telemetry(meta) if meta else meta, None


def _record_adaptive_exposure_if_challenger(
    meta: dict[str, Any] | None,
    notional: float,
    *,
    arm: str,
    ticker: str,
) -> None:
    if not meta or meta.get("experiment_arm") != "CHALLENGER":
        return
    try:
        import tae_adaptive_deployment as adep

        adep.record_challenger_exposure(notional, arm=arm, ticker=ticker)
    except Exception:
        pass


def _trade_cost_fields(eco: dict[str, Any], *, gross: float, side: str) -> dict[str, Any]:
    """Persistable cost fields; safe defaults for historical compatibility."""
    total = _f(eco.get("total_transaction_cost"))
    if side.upper() == "SELL":
        net_move = _f(eco.get("net_cash_movement"), _f(eco.get("net_proceeds"), gross - total))
        gross_key = "gross_proceeds"
    else:
        net_move = _f(eco.get("net_cash_movement"), -(gross + total))
        gross_key = "gross_notional"
    out = {
        gross_key: round(_f(eco.get(gross_key), gross), 6),
        "commission_cost": round(_f(eco.get("commission_cost")), 6),
        "spread_cost": round(_f(eco.get("spread_cost")), 6),
        "slippage_cost": round(_f(eco.get("slippage_cost")), 6),
        "total_transaction_cost": round(total, 6),
        "net_cash_movement": round(net_move, 6),
        "cost_model_version": eco.get("cost_model_version"),
        "cost_configuration": eco.get("cost_configuration"),
    }
    if eco.get("realized_pnl_gross") is not None:
        out["realized_pnl_gross"] = round(_f(eco.get("realized_pnl_gross")), 6)
    if eco.get("realized_pnl_net") is not None:
        out["realized_pnl_net"] = round(_f(eco.get("realized_pnl_net")), 6)
    return out


def _v1_entry_risk_snapshot(
    *,
    ticker: str,
    execution_id: str,
    decision_id: str,
    entry_ts: str,
    mark: float,
    shares: float,
    notional_requested: float,
    cash_before: float,
    reserve: float,
    portfolio_before: dict[str, Any],
    snap: dict[str, Any] | None,
) -> dict[str, Any]:
    """Freeze V1 PAPER entry risk/sizing context (does not change fill qty)."""
    import tae_paper_entry_risk_snapshot as ers
    import tae_paper_shadow_sizing as sso

    equity = ers.portfolio_mark_equity(portfolio_before)
    open_n = ers.open_position_count(portfolio_before)
    rec_qty = round(notional_requested / mark, 6) if mark > 0 else None
    stop = ers.v1_stop_policy_fields(mark) if mark > 0 else {}
    pos = (portfolio_before.get("positions") or {}).get(ticker) or {}
    held_qty = _f(pos.get("shares"))
    snapshot = ers.build_entry_risk_snapshot(
        ticker=ticker,
        strategy_arm="V1",
        execution_id=execution_id,
        entry_timestamp=entry_ts,
        entry_price=mark,
        executed_quantity=shares,
        executed_notional=round(shares * mark, 6),
        sizing_formula_id=ers.FORMULA_V1_DEPLOYABLE_25PCT,
        sizing_source_path=ers.SOURCE_V1,
        entry_type="INITIAL",
        decision_id=decision_id,
        recommended_quantity=rec_qty,
        authorized_quantity=rec_qty,
        stop_fields=stop,
        cash_available=cash_before,
        account_equity=equity,
        portfolio_value=equity,
        cash_reserve=reserve,
        maximum_position_notional=2500.0,
        maximum_positions=None,
        current_open_positions=open_n,
        signal_score=(float(snap["score"]) if isinstance(snap, dict) and snap.get("score") is not None else None),
        market_regime=None,
        snapshot_source=ers.SOURCE_V1,
    )
    inputs = sso.build_prefill_inputs(
        price=mark,
        cash_available=cash_before,
        account_equity=equity,
        portfolio_value=equity,
        current_position_quantity=held_qty if held_qty > 0 else 0.0,
        current_position_notional=round(held_qty * mark, 6) if held_qty > 0 else 0.0,
        cash_reserve=reserve,
        maximum_position_notional=2500.0,
        maximum_positions=12,
        current_open_positions=open_n,
        signal_score=(float(snap["score"]) if isinstance(snap, dict) and snap.get("score") is not None else None),
        stop_price=snapshot.get("stop_price"),
        stop_distance=snapshot.get("stop_distance"),
        ticker_exposure=round(held_qty * mark, 6) if held_qty > 0 else 0.0,
        evaluated_at=entry_ts,
    )
    evals = sso.evaluate_shadow_sizing(
        identity={
            "strategy_arm": "V1",
            "ticker": ticker,
            "decision_id": decision_id,
            "execution_id": execution_id,
            "entry_type": "INITIAL",
            "evaluated_at": entry_ts,
        },
        inputs=inputs,
        executed_formula_id=ers.FORMULA_V1_DEPLOYABLE_25PCT,
        executed_quantity=shares,
        executed_notional=round(shares * mark, 6),
        portfolio_before=portfolio_before,
        existing=snapshot.get("shadow_sizing_evaluations"),
    )
    return sso.attach_shadow_evaluations(snapshot, evals)


def _v2_entry_risk_snapshot(
    *,
    ticker: str,
    execution_id: str,
    decision_id: str,
    entry_ts: str,
    mark: float,
    shares: float,
    filled_value: float,
    entry_kind: str,
    cash_before: float,
    portfolio_before: dict[str, Any],
    v2_cfg: dict[str, Any],
    bd: dict[str, Any] | None,
    order: dict[str, Any] | None,
    cycle_id: str | None,
    snap: dict[str, Any] | None,
    in_reentry: bool = False,
) -> dict[str, Any]:
    """Freeze V2 PAPER OPEN/ADD/REENTRY risk/sizing context (no qty mutation)."""
    import tae_paper_entry_risk_snapshot as ers
    import tae_paper_shadow_sizing as sso

    equity = ers.portfolio_mark_equity(portfolio_before)
    open_n = ers.open_position_count(portfolio_before)
    kind = _s(entry_kind).upper()
    if in_reentry or kind in {"REENTRY", "REBUY"}:
        formula = ers.FORMULA_V2_REENTRY_BUDGET_TRANCHE
        entry_type = "REENTRY"
    elif kind in {"ADD", "ADD_TRANCHE"}:
        formula = ers.FORMULA_V2_ADD_BUDGET_TRANCHE
        entry_type = "ADD"
    else:
        formula = ers.FORMULA_V2_INITIAL_BUDGET_TRANCHE
        entry_type = "INITIAL"

    prop = None
    if isinstance(bd, dict) and bd.get("proposed_tranche_value") is not None:
        prop = _f(bd.get("proposed_tranche_value"))
    tranche = (order or {}).get("tranche") if isinstance(order, dict) else None
    tranche_id = None
    rec_qty = None
    if isinstance(tranche, dict):
        tranche_id = _s(tranche.get("tranche_id")) or None
        req = tranche.get("requested_value")
        if prop is None and req is not None:
            prop = _f(req)
    fx = 1.0
    if isinstance(tranche, dict) and tranche.get("fx_rate") is not None:
        fx = _f(tranche.get("fx_rate"), 1.0) or 1.0
    if prop is not None and mark > 0 and fx > 0:
        rec_qty = round(prop / (mark * fx), 6)
    auth_qty = rec_qty
    stop = ers.v2_stop_policy_fields(mark, v2_cfg) if mark > 0 else {}
    budget = None
    budget_remaining = None
    if isinstance(bd, dict):
        if bd.get("company_budget") is not None:
            budget = _f(bd.get("company_budget"))
        if bd.get("budget_remaining") is not None:
            budget_remaining = _f(bd.get("budget_remaining"))
    cycle_obj = (order or {}).get("cycle") if isinstance(order, dict) else None
    if isinstance(cycle_obj, dict):
        if budget is None and cycle_obj.get("company_budget") is not None:
            budget = _f(cycle_obj.get("company_budget"))
        if budget_remaining is None and cycle_obj.get("budget_remaining") is not None:
            budget_remaining = _f(cycle_obj.get("budget_remaining"))
    if budget_remaining is None and isinstance(bd, dict) and prop is not None and budget is not None:
        # Pre-fill remaining before this tranche spend
        used = _f(bd.get("budget_used"))
        budget_remaining = max(0.0, float(budget) - used) if budget is not None else None

    pos = (portfolio_before.get("positions") or {}).get(ticker) or {}
    held_qty = _f(pos.get("shares"))
    snapshot = ers.build_entry_risk_snapshot(
        ticker=ticker,
        strategy_arm="V2",
        execution_id=execution_id,
        entry_timestamp=entry_ts,
        entry_price=mark,
        executed_quantity=shares,
        executed_notional=round(filled_value if filled_value else shares * mark, 6),
        sizing_formula_id=formula,
        sizing_source_path=ers.SOURCE_V2_BUY_POLICY,
        entry_type=entry_type,
        cycle_id=cycle_id,
        decision_id=decision_id,
        tranche_id=tranche_id,
        recommended_quantity=rec_qty,
        authorized_quantity=auth_qty,
        stop_fields=stop,
        cash_available=cash_before,
        account_equity=equity,
        portfolio_value=equity,
        position_budget=budget,
        cash_reserve=_f(v2_cfg.get("MIN_CASH_RESERVE_USD"), 500.0),
        maximum_position_notional=_f(v2_cfg.get("max_order_value_usd"), 2500.0),
        maximum_positions=None,
        current_open_positions=open_n,
        signal_score=(float(snap["score"]) if isinstance(snap, dict) and snap.get("score") is not None else None),
        snapshot_source=ers.SOURCE_V2_BUY_POLICY,
    )
    inputs = sso.build_prefill_inputs(
        price=mark,
        cash_available=cash_before,
        account_equity=equity,
        portfolio_value=equity,
        current_position_quantity=held_qty,
        current_position_notional=round(held_qty * mark, 6) if held_qty > 0 else 0.0,
        company_budget=budget,
        tranche_budget=budget_remaining if budget_remaining is not None else prop,
        cash_reserve=_f(v2_cfg.get("MIN_CASH_RESERVE_USD"), 500.0),
        maximum_position_notional=_f(v2_cfg.get("max_order_value_usd"), 2500.0),
        maximum_positions=None,
        current_open_positions=open_n,
        signal_score=(float(snap["score"]) if isinstance(snap, dict) and snap.get("score") is not None else None),
        stop_price=snapshot.get("stop_price"),
        stop_distance=snapshot.get("stop_distance"),
        ticker_exposure=round(held_qty * mark, 6) if held_qty > 0 else 0.0,
        evaluated_at=entry_ts,
    )
    evals = sso.evaluate_shadow_sizing(
        identity={
            "strategy_arm": "V2",
            "ticker": ticker,
            "cycle_id": cycle_id,
            "decision_id": decision_id,
            "execution_id": execution_id,
            "tranche_id": tranche_id,
            "entry_type": entry_type,
            "evaluated_at": entry_ts,
        },
        inputs=inputs,
        executed_formula_id=formula,
        executed_quantity=shares,
        executed_notional=round(filled_value if filled_value else shares * mark, 6),
        portfolio_before=portfolio_before,
        existing=snapshot.get("shadow_sizing_evaluations"),
    )
    return sso.attach_shadow_evaluations(snapshot, evals)


def _persist_v2_cycle_risk_snapshot(p: dict[str, Any], cycle_id: str | None, snap: dict[str, Any]) -> dict[str, Any]:
    import tae_paper_entry_risk_snapshot as ers

    if not cycle_id:
        return snap
    return ers.persist_cycle_entry_risk_snapshot(p.get("v2_cycles"), cycle_id, snap)


def accumulate_tx_cost_metrics(trades_path: Path) -> dict[str, Any]:
    """Observability metrics from trade journals (existing report surface)."""
    buy_costs = 0.0
    sell_costs = 0.0
    gross_realized = 0.0
    net_realized = 0.0
    fill_count = 0
    today = _now()[:10]
    costs_today = 0.0
    for row in _read_jsonl_rows(trades_path):
        action = _s(row.get("action")).upper()
        if action not in {"BUY", "SELL", "CLOSE", "CLOSE_CYCLE", "ADD", "OPEN", "REBUY"}:
            # count only executed capital fills with cost fields or classic trades
            pass
        if action in {"BUY", "SELL", "CLOSE", "CLOSE_CYCLE", "ADD", "OPEN", "REBUY", "ADD_TRANCHE"}:
            fill_count += 1
            cost = _f(row.get("total_transaction_cost") or row.get("costs"))
            ts = _s(row.get("ts") or row.get("timestamp"))
            if ts.startswith(today):
                costs_today += cost
            if action in {"BUY", "ADD", "OPEN", "REBUY", "ADD_TRANCHE"}:
                buy_costs += cost
            else:
                sell_costs += cost
            if row.get("realized_pnl_gross") is not None:
                gross_realized += _f(row.get("realized_pnl_gross"))
            elif row.get("realized_pnl") is not None and cost == 0.0:
                gross_realized += _f(row.get("realized_pnl"))
            if row.get("realized_pnl_net") is not None:
                net_realized += _f(row.get("realized_pnl_net"))
            elif row.get("realized_pnl") is not None:
                net_realized += _f(row.get("realized_pnl"))
    total_costs = buy_costs + sell_costs
    ratio = None
    if abs(gross_realized) > 1e-9:
        ratio = round(total_costs / abs(gross_realized), 6)
    return {
        "total_costs_today": round(costs_today, 6),
        "total_costs_lifetime": round(total_costs, 6),
        "buy_costs": round(buy_costs, 6),
        "sell_costs": round(sell_costs, 6),
        "gross_realized_pnl": round(gross_realized, 6),
        "net_realized_pnl": round(net_realized, 6),
        "cost_to_gross_profit_ratio": ratio,
        "fill_count": fill_count,
        "average_cost_per_fill": round(total_costs / fill_count, 6) if fill_count else 0.0,
    }


def empty_portfolio(cash: float, *, arm: str) -> dict[str, Any]:
    return {
        "schema": "tae.parallel_paper.portfolio.v1",
        "arm": arm,
        "cash": float(cash),
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "positions": {},
        "starting_capital": float(cash),
        "created_at": _now(),
        "updated_at": _now(),
    }


def load_portfolio(path: Path, *, starting: float, arm: str) -> dict[str, Any]:
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "cash" in raw:
                return raw
        except (OSError, json.JSONDecodeError):
            pass
    return empty_portfolio(starting, arm=arm)


def save_portfolio(path: Path, portfolio: dict[str, Any]) -> None:
    portfolio = dict(portfolio)
    portfolio["updated_at"] = _now()
    _atomic_write_json(path, portfolio)


def accounting_pass(portfolio: dict[str, Any]) -> bool:
    """
    Cost-basis identity for isolated arms, or canonical mirror identities:
      cash + market_value ≈ account_value
      starting_value + total_pnl ≈ account_value
    """
    if str(portfolio.get("v1_mode") or portfolio.get("V1_MODE") or "") == "CANONICAL_PAPER_MIRROR":
        cash = _f(portfolio.get("cash"))
        mv = _f(portfolio.get("open_positions_value"))
        if mv <= 0:
            mv = sum(
                _f(p.get("shares")) * _f(p.get("current_price") or p.get("avg_price"))
                for p in (portfolio.get("positions") or {}).values()
            )
        av = _f(portfolio.get("account_value") or portfolio.get("total_value") or (cash + mv))
        start = _f(portfolio.get("starting_value") or portfolio.get("starting_capital"))
        total_pnl = _f(portfolio.get("total_pnl"), _f(portfolio.get("realized_pnl")) + _f(portfolio.get("unrealized_pnl")))
        assets_ok = abs(cash + mv - av) < 1.0
        pnl_ok = abs(start + total_pnl - av) < 1.0 if start else assets_ok
        return bool(assets_ok and pnl_ok)

    start = _f(portfolio.get("starting_capital"))
    cash = _f(portfolio.get("cash"))
    realized = _f(portfolio.get("realized_pnl"))
    cost = sum(
        _f(p.get("shares")) * _f(p.get("avg_price"))
        for p in (portfolio.get("positions") or {}).values()
    )
    return abs(cash + cost - (start + realized)) < 1.0


CANONICAL_PAPER_DEFAULT = Path("runtime_outputs/paper_execution/paper_portfolio.json")


def load_canonical_paper_raw(path: Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else CANONICAL_PAPER_DEFAULT
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "cash" not in raw:
        raise ValueError(f"invalid canonical PAPER portfolio at {p}")
    return raw


def map_canonical_paper_to_v1_mirror(raw: dict[str, Any], *, source_path: str) -> dict[str, Any]:
    """Read-only economic mirror of canonical PAPER — never a fresh 30k book."""
    positions: dict[str, Any] = {}
    for t, pos in (raw.get("positions") or {}).items():
        if not isinstance(pos, dict):
            continue
        positions[str(t).upper()] = {
            "ticker": str(t).upper(),
            "shares": _f(pos.get("shares")),
            "avg_price": _f(pos.get("avg_price")),
            "current_price": _f(pos.get("current_price") or pos.get("avg_price")),
            "current_value": _f(pos.get("current_value")),
            "pnl": _f(pos.get("pnl")),
            "status": _s(pos.get("status") or "OPEN"),
            "drawdown_pct": _f(pos.get("drawdown_pct")),
            "strategy_version": "V1_CANONICAL_MIRROR",
        }
    cash = _f(raw.get("cash"))
    mv = _f(raw.get("open_positions_value"))
    av = _f(raw.get("total_value"), cash + mv)
    realized = _f(raw.get("realized_pnl"))
    unreal = _f(raw.get("unrealized_pnl"))
    total_pnl = _f(raw.get("total_pnl"), realized + unreal)
    starting_value = _f(raw.get("starting_value"), _f(raw.get("validation_capital_base"), 30000.0))
    inception = _s(raw.get("created_at") or raw.get("capital_base_reset_at") or "")
    return {
        "schema": "tae.parallel_paper.portfolio.v1_mirror",
        "arm": "V1",
        "v1_mode": "CANONICAL_PAPER_MIRROR",
        "V1_MODE": "CANONICAL_PAPER_MIRROR",
        "read_only": True,
        "source": "CANONICAL_PAPER",
        "source_path": source_path,
        "inception_date": inception,
        "created_at": inception,
        "updated_at": _s(raw.get("updated_at") or _now()),
        "cash": cash,
        "positions": positions,
        "open_positions_value": mv,
        "account_value": av,
        "total_value": av,
        "realized_pnl": realized,
        "unrealized_pnl": unreal,
        "total_pnl": total_pnl,
        "starting_capital": starting_value,
        "starting_value": starting_value,
        "validation_capital_base": _f(raw.get("validation_capital_base"), 30000.0),
        "peak_value": _f(raw.get("peak_value"), starting_value),
        "drawdown_pct": _f(raw.get("drawdown_pct")),
        "drawdown": -abs(_f(raw.get("drawdown_pct"))) * max(starting_value, 1.0) / 100.0,
        "canonical_hash_hint": None,
    }


def portfolio_mtm(
    portfolio: dict[str, Any],
    marks: dict[str, float],
    *,
    mark_meta: dict[str, dict[str, Any]] | None = None,
) -> tuple[float, float]:
    """
    Mark-to-market open positions.

    Never treats entry/avg price as a fresh market mark. Missing/invalid marks
    keep the last valid price (if any) and set mark_status MARK_UNAVAILABLE/STALE;
    unrealized is computed only from a finite mark > 0 that is not a silent avg fallback.
    """
    cash = _f(portfolio.get("cash"))
    unreal = 0.0
    invested = 0.0
    meta = mark_meta or {}
    for t, pos in (portfolio.get("positions") or {}).items():
        sh = _f(pos.get("shares"))
        avg = _f(pos.get("avg_price"))
        invested += sh * avg
        raw_mark = marks.get(t)
        mmeta = meta.get(t) or {}
        freshness = _s(mmeta.get("mark_freshness") or "").upper()
        valid_incoming = (
            raw_mark is not None
            and _f(raw_mark) > 0
            and math.isfinite(_f(raw_mark))
            and freshness not in {"STALE", "INVALID", "UNAVAILABLE", "MARK_STALE", "MARK_UNAVAILABLE"}
        )
        if valid_incoming:
            px = _f(raw_mark)
            pos["current_price"] = px
            if freshness in {"MARKET_CLOSED", "MARKET_CLOSED_VALID_PREVIOUS_CLOSE"}:
                pos["mark_status"] = "MARKET_CLOSED"
            else:
                pos["mark_status"] = "FRESH"
            pos["mark_timestamp"] = mmeta.get("mark_timestamp") or _now()
            pos["last_valid_mark"] = px
            pos["last_valid_mark_timestamp"] = pos["mark_timestamp"]
            unreal += sh * (px - avg)
        else:
            last = _f(pos.get("last_valid_mark"))
            if last > 0 and math.isfinite(last):
                pos["current_price"] = last
                pos["mark_status"] = "MARK_STALE"
                unreal += sh * (last - avg)
            else:
                # Keep avg on the position for cost basis only — do NOT report as market mark.
                pos["mark_status"] = "MARK_UNAVAILABLE"
                # Do not invent unrealized=0 from avg==current; leave last known uPnL field alone
                # and exclude from cycle MTM when no valid mark exists.
                if _f(pos.get("current_price")) > 0 and abs(_f(pos.get("current_price")) - avg) > 1e-12:
                    unreal += sh * (_f(pos.get("current_price")) - avg)
                else:
                    pos["unrealized_pnl_status"] = "MARK_UNAVAILABLE"
        pos["unrealized_pnl"] = round(sh * (_f(pos.get("current_price") or avg) - avg), 6) if pos.get("mark_status") != "MARK_UNAVAILABLE" else None
    av = cash + invested + unreal
    portfolio["unrealized_pnl"] = round(unreal, 6)
    return round(av, 6), round(invested, 6)


def _mark_is_usable(snap: dict[str, Any] | None) -> tuple[bool, str, float]:
    """Return (ok, status, mark_price). Reject non-finite / non-positive / explicit stale.

    MARKET_CLOSED / MARKET_CLOSED_VALID_PREVIOUS_CLOSE remain usable (not defects).
    """
    if not isinstance(snap, dict):
        return False, "MARK_UNAVAILABLE", 0.0
    px = _f(snap.get("mark_price"))
    freshness = _s(snap.get("mark_freshness") or "FRESH").upper()
    if px <= 0 or not math.isfinite(px):
        return False, "MARK_UNAVAILABLE", 0.0
    if freshness in {"STALE", "INVALID", "UNAVAILABLE", "MARK_STALE", "MARK_UNAVAILABLE"}:
        return False, "MARK_STALE", px
    if snap.get("data_fresh") is False:
        return False, "MARK_STALE", px
    if freshness in {"MARKET_CLOSED", "MARKET_CLOSED_VALID_PREVIOUS_CLOSE"}:
        return True, "MARKET_CLOSED", px
    return True, "FRESH", px


def default_mark_provider(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Best-effort marks from signals.csv / live_signals.csv; no silent entry-price invent.

    Session-aware labeling (MARKET_SESSION_POLICY=session_aware_mark_and_report):
    valid previous-close while the ticker market is closed is MARKET_CLOSED (usable),
    not a silent stale fallback and not a defect.
    """
    out: dict[str, dict[str, Any]] = {}
    rows: dict[str, dict[str, Any]] = {}
    for signals in (Path("signals.csv"), Path("live_signals.csv")):
        if not signals.is_file():
            continue
        try:
            import csv

            with signals.open(encoding="utf-8", errors="replace") as fh:
                for row in csv.DictReader(fh):
                    t = _s(row.get("Ticker") or row.get("ticker")).upper()
                    if not t:
                        continue
                    rows[t] = row
        except OSError:
            pass
    targets = [str(t).upper() for t in (tickers or [])]
    if not targets:
        targets = sorted(rows.keys())[:40]
    ts = _now()
    try:
        from markets.market_hours import is_ticker_market_open
    except Exception:  # pragma: no cover - defensive
        is_ticker_market_open = None  # type: ignore[assignment]
    for t in targets:
        row = rows.get(t) or {}
        px = _f(row.get("Price") or row.get("price") or row.get("Close") or row.get("Current_Price"), 0.0)
        score = row.get("Score") or row.get("score")
        try:
            score_f = float(score) if score is not None and str(score).strip() != "" else None
        except (TypeError, ValueError):
            score_f = None
        signal = _s(row.get("Signal") or row.get("signal") or "WAIT")
        if px <= 0 or not math.isfinite(px):
            out[t] = {
                "mark_price": None,
                "score": score_f,
                "signal": signal,
                "eligible": False,
                "mark_freshness": "MARK_UNAVAILABLE",
                "mark_age_seconds": None,
                "data_fresh": False,
                "mark_timestamp": ts,
                "mark_status": "MARK_UNAVAILABLE",
            }
            continue
        market_open = True
        if is_ticker_market_open is not None:
            try:
                market_open = bool(is_ticker_market_open(t))
            except Exception:
                market_open = True
        # Closed session: previous close remains usable for MTM/report, labeled explicitly.
        freshness = "FRESH" if market_open else "MARKET_CLOSED"
        out[t] = {
            "mark_price": px,
            "score": score_f,
            "signal": signal,
            "eligible": signal in {"STRONG BUY", "BUY"} or (score_f is not None and score_f >= V1_V2_ENTRY_MIN_SCORE),
            "mark_freshness": freshness,
            "mark_age_seconds": 0.0,
            "data_fresh": True,
            "mark_timestamp": ts,
            "mark_status": freshness,
            "market_session": "OPEN" if market_open else "CLOSED",
        }
    return out


def snapshot_id(marks: dict[str, dict[str, Any]], ts: str) -> str:
    blob = json.dumps({"ts": ts, "marks": marks}, sort_keys=True, default=str).encode()
    return "SNAP-" + hashlib.sha256(blob).hexdigest()[:16].upper()


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
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


def reconstruct_isolated_portfolio_from_trades(
    *,
    trades_path: Path,
    starting: float,
    arm: str,
) -> dict[str, Any]:
    """Rebuild isolated arm book from trade journal without inventing new fills."""
    portfolio = empty_portfolio(starting, arm=arm)
    portfolio["v1_mode"] = "ISOLATED_PARALLEL_PAPER" if arm == "V1" else "ISOLATED_PARALLEL_PAPER"
    portfolio["reconstructed_from_trades"] = True
    portfolio["source"] = "ISOLATED_TRADE_JOURNAL"
    for trade in _read_jsonl_rows(trades_path):
        action = _s(trade.get("action")).upper()
        ticker = _s(trade.get("ticker")).upper()
        shares = _f(trade.get("shares") or trade.get("quantity"))
        price = _f(trade.get("price") or trade.get("mark_price"))
        if not ticker or shares <= 0 or price <= 0:
            continue
        # Historical rows without cost fields replay zero-cost (forward compatible).
        cost_cfg = trade.get("cost_configuration") if isinstance(trade.get("cost_configuration"), dict) else None
        apply_costs = bool(cost_cfg is not None or trade.get("total_transaction_cost") is not None)
        if action == "BUY":
            notional = shares * price
            got, after = pe._buy_shares(
                portfolio,
                ticker,
                notional,
                price,
                apply_paper_tx_costs=apply_costs,
                paper_tx_cost_cfg=cost_cfg,
            )
            if got > 0 and after:
                after["strategy_version"] = "V1" if arm == "V1" else after.get("strategy_version") or arm
                after["current_price"] = price
                after["last_valid_mark"] = price
                after["mark_status"] = "MARK_STALE"
                after["mark_timestamp"] = trade.get("ts") or _now()
        elif action in {"SELL", "CLOSE", "CLOSE_CYCLE"}:
            pe._sell_shares(
                portfolio,
                ticker,
                shares,
                price,
                apply_paper_tx_costs=apply_costs,
                paper_tx_cost_cfg=cost_cfg,
            )
    portfolio["updated_at"] = _now()
    return portfolio


def load_v1_portfolio(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load V1 isolated PAPER portfolio (default) or optional canonical mirror."""
    cfg = cfg or load_parallel_paper_config()
    p = paths()
    mode = str(cfg.get("V1_MODE") or "ISOLATED_PARALLEL_PAPER").upper()
    if mode == "CANONICAL_PAPER_MIRROR":
        src = Path(str(cfg.get("CANONICAL_PAPER_PORTFOLIO") or CANONICAL_PAPER_DEFAULT))
        raw = load_canonical_paper_raw(src)
        mirror = map_canonical_paper_to_v1_mirror(raw, source_path=str(src))
        # Audit snapshot only — never the economic mutation ledger
        _atomic_write_json(p["v1_mirror_snapshot"], mirror)
        _atomic_write_json(
            p["v1_mirror_meta"],
            {
                "V1_MODE": "CANONICAL_PAPER_MIRROR",
                "source": "CANONICAL_PAPER",
                "source_path": str(src),
                "inception_date": mirror.get("inception_date"),
                "read_only": True,
                "writes_canonical_paper": False,
                "updated_at": _now(),
            },
        )
        return mirror

    starting = float(cfg["V1_STARTING_CAPITAL"])
    if p["v1_portfolio"].is_file():
        port = load_portfolio(p["v1_portfolio"], starting=starting, arm="V1")
        port["v1_mode"] = "ISOLATED_PARALLEL_PAPER"
        port["V1_MODE"] = "ISOLATED_PARALLEL_PAPER"
        port["read_only"] = False
        port["source"] = port.get("source") or "ISOLATED"
        return port

    # Restore from trade journal when portfolio.json was lost during mirror regression
    if p["v1_trades"].is_file() and p["v1_trades"].stat().st_size > 0:
        restored = reconstruct_isolated_portfolio_from_trades(
            trades_path=p["v1_trades"],
            starting=starting,
            arm="V1",
        )
        save_portfolio(p["v1_portfolio"], restored)
        return restored

    port = empty_portfolio(starting, arm="V1")
    port["v1_mode"] = "ISOLATED_PARALLEL_PAPER"
    port["V1_MODE"] = "ISOLATED_PARALLEL_PAPER"
    port["read_only"] = False
    port["source"] = "ISOLATED"
    return port


def assert_canonical_paper_untouched(*, before_hash: str | None = None) -> str:
    """Return current canonical PAPER digest; raise if mutated vs before_hash."""
    import hashlib

    data = Path(str(CANONICAL_PAPER_DEFAULT)).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if before_hash is not None and digest != before_hash:
        raise RuntimeError("CANONICAL_PAPER_MUTATED")
    return digest


def acquire_lock(lock_path: Path) -> Any:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        raise RuntimeError("DUPLICATE_PARALLEL_PAPER_RUNTIME")
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def release_lock(fh: Any) -> None:
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
    except Exception:
        pass


def bootstrap(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from tae_parallel_paper_config import configured_arms, enabled_arms, arm_dir

    cfg = cfg or load_parallel_paper_config()
    p = paths(cfg)
    v1_mode = str(cfg.get("V1_MODE") or "ISOLATED_PARALLEL_PAPER").upper()
    # V1/V2 book bootstrap unchanged when those arms are enabled (legacy path).
    v1 = load_v1_portfolio(cfg)
    if cfg.get("V1_PARALLEL_ENABLED") and v1_mode != "CANONICAL_PAPER_MIRROR":
        if not p["v1_portfolio"].is_file():
            save_portfolio(p["v1_portfolio"], v1)
    v2p = load_portfolio(p["v2_portfolio"], starting=float(cfg["V2_STARTING_CAPITAL"]), arm="V2")
    if cfg.get("V2_PARALLEL_ENABLED"):
        if not p["v2_portfolio"].is_file():
            save_portfolio(p["v2_portfolio"], v2p)
        if not p["v2_cycles"].is_file():
            v2.save_cycle_store(v2.empty_cycle_store(), p["v2_cycles"])
    equal = abs(float(cfg.get("V1_STARTING_CAPITAL") or 0) - float(cfg["V2_STARTING_CAPITAL"])) < 1e-9
    if v1_mode == "CANONICAL_PAPER_MIRROR":
        equal = False
        comparison_warning = (
            "V1 is CANONICAL_PAPER_MIRROR (historical book); V2 is isolated 30k — "
            "not equal-capital day-one A/B."
        )
    else:
        comparison_warning = (
            None if equal else "UNEQUAL_STARTING_CAPITAL — comparison not apples-to-apples"
        )

    # Preserve live daemon status if already running
    prev: dict[str, Any] = {}
    if p["runtime_status"].is_file():
        try:
            prev = json.loads(p["runtime_status"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = {}
    running = bool(prev.get("running"))
    pid = prev.get("pid")
    if p["pid"].is_file():
        try:
            pid_file = int(p["pid"].read_text(encoding="utf-8").strip())
            os.kill(pid_file, 0)
            running = True
            pid = pid_file
        except (OSError, ValueError):
            pass

    arms_cfg = configured_arms(cfg)
    enabled = enabled_arms(cfg)
    status = {
        "schema": "tae.parallel_paper.runtime_status.v2",
        "running": running,
        "pid": pid,
        "bootstrapped_at": _now(),
        "V1_MODE": v1_mode,
        "V2_MODE": "ISOLATED_PARALLEL_PAPER",
        "equal_starting_capital": equal,
        "comparison_warning": comparison_warning,
        "V2_ACTIVATION_SCOPE": cfg["V2_ACTIVATION_SCOPE"],
        "V2_LIVE_ENABLED": False,
        "V2_CANONICAL_PAPER_ENABLED": False,
        "v1_inception_date": v1.get("inception_date") or v1.get("created_at"),
        "v1_cash": _f(v1.get("cash")),
        "v1_account_value": _f(v1.get("account_value") or v1.get("total_value")),
        "n_arm_topology": True,
        "configured_arm_ids": [a["arm_id"] for a in arms_cfg],
        "enabled_arm_ids": [a["arm_id"] for a in enabled],
        "disabled_stub_arm_ids": [
            a["arm_id"] for a in arms_cfg if not a.get("enabled")
        ],
        "stub_dirs_created": [
            a["arm_id"]
            for a in arms_cfg
            if (not a.get("enabled")) and arm_dir(a["arm_id"]).exists()
        ],
        "paths": {
            k: (str(v) if not isinstance(v, dict) else {kk: str(vv) for kk, vv in v.items()})
            for k, v in p.items()
        },
    }
    if prev.get("started_at"):
        status["started_at"] = prev["started_at"]
    if prev.get("owner"):
        status["owner"] = prev["owner"]
    _atomic_write_json(p["runtime_status"], status)
    return {"ok": True, "status": status, "paths": p, "cfg": cfg, "v1": v1, "v2": v2p}


def start_runtime(cfg: dict[str, Any] | None = None, *, spawn_daemon: bool = True) -> dict[str, Any]:
    """Start persistent parallel PAPER daemon. Preserves portfolios. Does NOT run a cycle."""
    import subprocess
    import sys
    import time

    from tae_parallel_paper_daemon import is_enabled, set_enabled

    cfg = cfg or load_parallel_paper_config()
    if not cfg.get("PARALLEL_PAPER_ENABLED"):
        return {"ok": False, "reason": "PARALLEL_PAPER_DISABLED"}
    boot = bootstrap(cfg)
    p = boot["paths"]
    interval = int(cfg.get("RUNTIME_INTERVAL_SEC") or 300)

    # Already running? Refuse duplicate — do not run another cycle.
    existing_pid = None
    if p["pid"].is_file():
        try:
            existing_pid = int(p["pid"].read_text(encoding="utf-8").strip())
            os.kill(existing_pid, 0)
            return {
                "ok": False,
                "duplicate": True,
                "status": "ALREADY_RUNNING",
                "pid": existing_pid,
                "reason": "DUPLICATE_PARALLEL_PAPER_RUNTIME",
                "paths": {k: str(v) for k, v in p.items()},
                "V2_LIVE_ENABLED": False,
            }
        except (OSError, ValueError):
            existing_pid = None

    set_enabled(True)
    if not spawn_daemon:
        write_status = {
            "schema": "tae.parallel_paper.runtime_status.v1",
            "running": True,
            "pid": os.getpid(),
            "started_at": _now(),
            "V2_LIVE_ENABLED": False,
            "enabled_flag": True,
            "owner": "inline",
        }
        _atomic_write_json(p["runtime_status"], write_status)
        _atomic_write_json(p["status"], write_status)
        return {"ok": True, "status": write_status, "pid": os.getpid(), "paths": {k: str(v) for k, v in p.items()}}

    def _wait_alive(timeout_sec: float = 8.0) -> int | None:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if p["pid"].is_file():
                try:
                    pid = int(p["pid"].read_text(encoding="utf-8").strip())
                    os.kill(pid, 0)
                    # Prefer heartbeat presence, but PID alone is enough to confirm start
                    return pid
                except (OSError, ValueError):
                    pass
            time.sleep(0.15)
        return None

    # Prefer LaunchAgent owner only for the production root (never kick production from temp tests)
    used_launchagent = False
    try:
        from tae_parallel_paper_autostart import status_autostart

        prod_root = (Path(".").resolve() / "runtime_outputs" / "parallel_paper").resolve()
        using_prod_root = p["root"].resolve() == prod_root
        ast = status_autostart() if using_prod_root else {}
        if using_prod_root and (ast.get("plist_installed") or ast.get("launchctl_listed")):
            used_launchagent = True
            label = f"gui/{os.getuid()}/com.tradingai.parallel-paper"
            subprocess.run(["launchctl", "kickstart", "-k", label], capture_output=True)
            pid = _wait_alive(10.0)
            if pid:
                status = {
                    "schema": "tae.parallel_paper.runtime_status.v1",
                    "running": True,
                    "pid": pid,
                    "started_at": _now(),
                    "V2_LIVE_ENABLED": False,
                    "owner": "launchagent",
                    "enabled_flag": is_enabled(),
                    "interval_sec": interval,
                }
                _atomic_write_json(p["runtime_status"], status)
                _atomic_write_json(p["status"], status)
                return {"ok": True, "status": status, "pid": pid, "paths": {k: str(v) for k, v in p.items()}}
    except Exception:
        used_launchagent = False

    # Probe lock — if held, duplicate without pid file
    try:
        lock_fh = acquire_lock(p["lock"])
        release_lock(lock_fh)
    except RuntimeError as exc:
        return {"ok": False, "reason": str(exc), "status": "DUPLICATE", "duplicate": True}

    # Direct spawn (tests / LaunchAgent unavailable / kickstart failed)
    log_out = p["log"]
    log_fh = log_out.open("a", encoding="utf-8")
    env = os.environ.copy()
    # Isolate child daemon to the same ROOT the parent is using (tests / custom roots)
    env["TAE_PARALLEL_PAPER_ROOT"] = str(p["root"].resolve())
    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path("tae_parallel_paper_daemon.py").resolve()),
            "--interval",
            str(interval),
            "--ensure-enabled",
        ],
        cwd=str(Path(".").resolve()),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    try:
        log_fh.close()
    except OSError:
        pass

    pid = _wait_alive(8.0) or proc.pid
    alive = False
    try:
        os.kill(int(pid), 0)
        alive = True
    except (OSError, ValueError):
        alive = False
    if not alive:
        return {
            "ok": False,
            "reason": "FAILED_TO_START_PERSISTENT_RUNTIME",
            "status": "FAILED",
            "launchagent_attempted": used_launchagent,
            "paths": {k: str(v) for k, v in p.items()},
        }

    # Ensure pid file exists even if daemon still bootstrapping
    try:
        p["pid"].write_text(str(pid) + "\n", encoding="utf-8")
    except OSError:
        pass
    status = {
        "schema": "tae.parallel_paper.runtime_status.v1",
        "running": True,
        "pid": pid,
        "started_at": _now(),
        "V2_LIVE_ENABLED": False,
        "spawned": True,
        "owner": "spawn",
        "enabled_flag": is_enabled(),
        "interval_sec": interval,
    }
    _atomic_write_json(p["runtime_status"], status)
    _atomic_write_json(p["status"], status)
    return {"ok": True, "status": status, "pid": pid, "paths": {k: str(v) for k, v in p.items()}}


def stop_runtime(*, remove_enabled_flag: bool = True) -> dict[str, Any]:
    """Stop daemon cleanly. Does not unload LaunchAgent unless remove_enabled_flag clears PathState."""
    import signal
    import time

    from tae_parallel_paper_daemon import set_enabled

    p = paths()
    pid = None
    if p["pid"].is_file():
        try:
            pid = int(p["pid"].read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = None
    if remove_enabled_flag:
        set_enabled(False)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                break
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    status = {
        "schema": "tae.parallel_paper.runtime_status.v1",
        "running": False,
        "pid": None,
        "stopped_at": _now(),
        "V2_LIVE_ENABLED": False,
        "previous_pid": pid,
    }
    _atomic_write_json(p["runtime_status"], status)
    _atomic_write_json(p["status"], status)
    if p["pid"].is_file():
        try:
            p["pid"].unlink()
        except OSError:
            pass
    return {"ok": True, "status": status}


def _parse_iso_age_sec(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        raw = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except ValueError:
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        from core.process_identity import pid_exists

        return bool(pid_exists(int(pid)))
    except Exception:
        try:
            os.kill(int(pid), 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False


def _cmdline_is_parallel_daemon(cmdline: str | None, *, project_dir: Path) -> bool:
    if not cmdline:
        return False
    lowered = cmdline.lower()
    if "cursorsandbox" in lowered or "unittest" in lowered:
        return False
    if "tae_parallel_paper_daemon.py" not in cmdline.replace("\\", "/"):
        return False
    project = str(project_dir.resolve()).replace("\\", "/")
    normalized = cmdline.replace("\\", "/")
    return project in normalized or normalized.rstrip().endswith("tae_parallel_paper_daemon.py")


def find_parallel_paper_daemon_pids(*, project_dir: Path | None = None) -> list[int]:
    """Discover tae_parallel_paper_daemon.py processes owned by this project."""
    project_dir = Path(project_dir or Path.cwd()).resolve()
    lines: list[str] = []
    for cmd in (["pgrep", "-fl", "tae_parallel_paper_daemon.py"], ["ps", "aux"]):
        try:
            import subprocess

            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in (result.stdout or "").splitlines():
            if "tae_parallel_paper_daemon.py" in line:
                lines.append(line.strip())
        if lines and cmd[0] == "pgrep":
            break
    pids: list[int] = []
    for line in lines:
        pid: int | None = None
        cmd_text: str | None = None
        parts = line.split(None, 1)
        if parts and parts[0].isdigit():
            pid = int(parts[0])
            cmd_text = parts[1] if len(parts) > 1 else None
        else:
            tokens = line.split(None, 10)
            if len(tokens) >= 11 and tokens[1].isdigit():
                pid = int(tokens[1])
                cmd_text = tokens[10]
        if pid is None:
            continue
        if cmd_text is None:
            try:
                from core.process_identity import read_cmdline

                cmd_text = read_cmdline(pid)
            except Exception:
                cmd_text = None
        if not _cmdline_is_parallel_daemon(cmd_text, project_dir=project_dir):
            continue
        if _pid_alive(pid):
            pids.append(pid)
    out: list[int] = []
    seen: set[int] = set()
    for pid in pids:
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


def _resolve_parallel_daemon_pid(
    *,
    p: dict[str, Path],
    hb: dict[str, Any],
    rt: dict[str, Any],
    project_dir: Path,
    allow_process_discovery: bool = True,
) -> tuple[int | None, list[int], str]:
    """Return (canonical_pid, duplicates, source)."""
    candidates: list[tuple[int, str]] = []
    for label, raw in (
        ("pid_file", p["pid"].read_text(encoding="utf-8").strip() if p["pid"].is_file() else None),
        ("heartbeat", hb.get("pid")),
        ("runtime_status", rt.get("pid")),
    ):
        try:
            if raw is None or str(raw).strip() == "":
                continue
            pid = int(raw)
        except (TypeError, ValueError, OSError):
            continue
        if _pid_alive(pid):
            candidates.append((pid, label))

    discovered = find_parallel_paper_daemon_pids(project_dir=project_dir) if allow_process_discovery else []
    # Only promote discovery when artifacts already reference that pid or artifacts are empty/stale.
    artifact_pids = {c[0] for c in candidates}
    if allow_process_discovery:
        for dpid in discovered:
            if dpid in artifact_pids:
                candidates.append((dpid, "discovered"))
            elif not artifact_pids:
                # Fresh/empty SSOT under these paths — do not claim host daemon for temp fixtures.
                # Only accept discovery when heartbeat/status files live under the project runtime root.
                try:
                    hb_path = p["heartbeat"].resolve()
                    project_runtime = (project_dir / "runtime_outputs" / "parallel_paper").resolve()
                    if project_runtime in hb_path.parents or hb_path.parent == project_runtime:
                        if _pid_alive(dpid):
                            candidates.append((dpid, "discovered"))
                except OSError:
                    pass

    ordered: list[tuple[int, str]] = []
    seen: set[int] = set()
    for pid, src in candidates:
        if pid in seen:
            continue
        seen.add(pid)
        ordered.append((pid, src))

    if len(discovered) > 1:
        return (ordered[0][0] if ordered else discovered[0], [x for x in discovered[1:]], "duplicate")

    if not ordered:
        return None, [], "absent"
    return ordered[0][0], [], ordered[0][1]


LEARNING_FILL_ACTIONS = frozenset({"BUY", "SELL", "OPEN", "ADD", "CLOSE"})


def record_execution_learning_feedback(
    *,
    arm: str,
    execution_id: str,
    decision_id: str,
    action: str,
    ticker: str,
    price: float,
    shares: float,
    value: float,
    reason: str | None = None,
    realized_pnl: float | None = None,
    fees: float = 0.0,
    slippage: float = 0.0,
    holding_duration_sec: float | None = None,
    strategy_variant: str | None = None,
    position_id: str | None = None,
    p: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Feed executed V1/V2 fills into arm-local learning SSOT (idempotent by execution_id).

    Uses existing tae_learning_persistence.atomic_write_json — no new learning engine.
    HOLD / mirror / non-fill actions are ignored.
    """
    arm_u = _s(arm).upper()
    action_u = _s(action).upper()
    if action_u not in LEARNING_FILL_ACTIONS:
        return {"ok": True, "consumed": False, "reason": "NON_FILL_ACTION", "action": action_u}
    if not execution_id:
        return {"ok": False, "consumed": False, "reason": "MISSING_EXECUTION_ID"}

    paths_map = p or paths()
    arm_l = arm_u.lower()
    # Fail-closed: never silently remap unknown arms onto another arm's
    # learning journals. v3 added alongside v1/v2 (Phase 3) — routes through
    # the generic paths_map["arms"][arm_l] map (paths() builds this for every
    # configured arm) rather than a v3_learning_events flat alias, since only
    # v1/v2 get flat aliases today.
    arm_paths_entry = paths_map.get("arms", {}).get(arm_l) if arm_l == "v3" else None
    if arm_l not in {"v1", "v2"} and not arm_paths_entry:
        return {
            "ok": False,
            "consumed": False,
            "reason": "UNKNOWN_ARM_LEARNING_ROUTE",
            "arm": arm_u,
        }
    if arm_paths_entry:
        events_path = arm_paths_entry["learning_events"]
        state_path = arm_paths_entry["learning_state"]
    else:
        events_key = f"{arm_l}_learning_events"
        state_key = f"{arm_l}_learning_state"
        events_path = paths_map[events_key]
        state_path = paths_map[state_key]

    from tae_learning_persistence import atomic_write_json, load_json_safe

    state, _ = load_json_safe(state_path)
    if not isinstance(state, dict):
        state = {
            "schema": "tae.parallel_paper.learning_state.v1",
            "arm": arm_u,
            "consumed_execution_ids": [],
            "event_count": 0,
            "updated_at": None,
        }
    consumed = [str(x) for x in (state.get("consumed_execution_ids") or [])]
    if str(execution_id) in consumed:
        return {
            "ok": True,
            "consumed": False,
            "duplicate": True,
            "execution_id": execution_id,
            "reason": "DUPLICATE_EXECUTION_ID",
        }

    event = {
        "schema": "tae.parallel_paper.learning_event.v1",
        "event_type": "EXECUTION_OUTCOME",
        "arm": arm_u,
        "execution_id": str(execution_id),
        "decision_id": str(decision_id),
        "position_id": position_id or f"{arm_u}:{_s(ticker).upper()}",
        "ticker": _s(ticker).upper(),
        "action": action_u,
        "price": _f(price),
        "shares": _f(shares),
        "value": _f(value),
        "realized_pnl": None if realized_pnl is None else _f(realized_pnl),
        "fees": _f(fees),
        "slippage": _f(slippage),
        "holding_duration_sec": holding_duration_sec,
        "exit_reason": reason,
        "strategy_variant": strategy_variant or arm_u,
        "ts": _now(),
        "economic": True,
    }
    _append_jsonl(events_path, event)
    consumed.append(str(execution_id))
    state.update(
        {
            "schema": "tae.parallel_paper.learning_state.v1",
            "arm": arm_u,
            "consumed_execution_ids": consumed[-5000:],
            "event_count": int(state.get("event_count") or 0) + 1,
            "last_execution_id": str(execution_id),
            "last_decision_id": str(decision_id),
            "updated_at": _now(),
        }
    )
    atomic_write_json(state_path, state)
    return {
        "ok": True,
        "consumed": True,
        "duplicate": False,
        "execution_id": execution_id,
        "learning_state": str(state_path),
        "learning_events": str(events_path),
        "event": event,
    }


def health_snapshot(
    cfg: dict[str, Any] | None = None,
    *,
    allow_process_discovery: bool = True,
    project_dir: Path | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_parallel_paper_config()
    p = paths()
    project = Path(project_dir or Path.cwd()).resolve()
    v1 = load_v1_portfolio(cfg)
    v2p = load_portfolio(p["v2_portfolio"], starting=float(cfg["V2_STARTING_CAPITAL"]), arm="V2")
    rt: dict[str, Any] = {}
    for key in ("status", "runtime_status"):
        if p[key].is_file():
            try:
                rt = json.loads(p[key].read_text(encoding="utf-8"))
                break
            except (OSError, json.JSONDecodeError):
                continue
    hb: dict[str, Any] = {}
    if p["heartbeat"].is_file():
        try:
            hb = json.loads(p["heartbeat"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            hb = {}

    pid, duplicates, pid_source = _resolve_parallel_daemon_pid(
        p=p,
        hb=hb,
        rt=rt,
        project_dir=project,
        allow_process_discovery=allow_process_discovery,
    )
    pid_alive = _pid_alive(pid)
    runtime_running = bool(pid_alive)
    if duplicates:
        runtime_running = True

    # Reconcile pid file when a valid process is known.
    if runtime_running and pid is not None:
        try:
            p["pid"].parent.mkdir(parents=True, exist_ok=True)
            tmp = p["pid"].with_suffix(p["pid"].suffix + ".tmp")
            tmp.write_text(str(pid) + "\n", encoding="utf-8")
            os.replace(tmp, p["pid"])
        except OSError:
            pass

    hb_ts = hb.get("updated_at") or hb.get("last_heartbeat") or rt.get("last_heartbeat")
    hb_age = _parse_iso_age_sec(hb_ts if isinstance(hb_ts, str) else None)
    max_age = float(cfg.get("HEARTBEAT_MAX_AGE_SEC") or 660)
    heartbeat_fresh = bool(runtime_running and hb_age is not None and hb_age <= max_age)
    if runtime_running and hb_age is None:
        started_age = _parse_iso_age_sec(rt.get("started_at") if isinstance(rt.get("started_at"), str) else None)
        heartbeat_fresh = bool(started_age is not None and started_age <= 30.0)

    a1 = accounting_pass(v1)
    a2 = accounting_pass(v2p)
    accounting_ok = bool(a1 and a2)

    def _account_fields(arm: str, portfolio: dict[str, Any]) -> dict[str, Any]:
        """Prefer last cycle account.json for account_value (portfolio may omit it)."""
        acct: dict[str, Any] = {}
        acct_path = p["v1_account"] if arm == "V1" else p["v2_account"]
        if acct_path.is_file():
            try:
                raw = json.loads(acct_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    acct = raw
            except (OSError, json.JSONDecodeError):
                acct = {}
        av = _f(
            acct.get("account_value")
            or portfolio.get("account_value")
            or portfolio.get("total_value")
        )
        return {
            "account_value": av,
            "invested": _f(acct.get("invested")),
            "reconciliation_pass": bool(
                acct.get("reconciliation_pass") if "reconciliation_pass" in acct else accounting_pass(portfolio)
            ),
        }

    v1_acct = _account_fields("V1", v1)
    v2_acct = _account_fields("V2", v2p)

    state_ok = True
    try:
        if str(cfg.get("V1_MODE") or "").upper() == "CANONICAL_PAPER_MIRROR":
            state_ok = bool(Path(str(cfg.get("CANONICAL_PAPER_PORTFOLIO") or CANONICAL_PAPER_DEFAULT)).is_file()) and bool(
                p["v2_portfolio"].is_file()
            )
        else:
            state_ok = bool(p["v1_portfolio"].is_file() and p["v2_portfolio"].is_file())
    except OSError:
        state_ok = False

    data_ok = True
    data_notes: list[str] = []
    if not p["v2_cycles"].is_file():
        data_notes.append("missing_v2_cycles")

    clean_shutdown = bool(rt.get("stopped_at")) and not runtime_running and rt.get("running") is False

    if duplicates:
        process_status = "DUPLICATE"
        overall = "DUPLICATE"
        heartbeat_status = "DUPLICATE"
    elif runtime_running and heartbeat_fresh:
        process_status = "RUNNING_HEALTHY"
        overall = "RUNNING_HEALTHY"
        heartbeat_status = "FRESH"
    elif runtime_running and not heartbeat_fresh:
        process_status = "RUNNING_HEARTBEAT_STALE"
        overall = "RUNNING_HEARTBEAT_STALE"
        heartbeat_status = "STALE"
    elif not runtime_running and clean_shutdown and (hb_age is None or hb_age <= max_age * 2):
        process_status = "STOPPED_CLEAN"
        overall = "STOPPED_CLEAN" if state_ok and accounting_ok else "FAILED"
        heartbeat_status = "CLEAN_SHUTDOWN"
    elif not runtime_running:
        process_status = "STOPPED_STALE_STATE"
        # Back-compat alias used by older tests/docs
        overall = "STOPPED_HEALTHY_STATE" if state_ok and accounting_ok else "FAILED"
        if state_ok and accounting_ok:
            # Prefer explicit STOPPED_CLEAN when status artifact says stopped.
            if clean_shutdown:
                overall = "STOPPED_CLEAN"
                process_status = "STOPPED_CLEAN"
            else:
                overall = "STOPPED_STALE_STATE" if (hb_age is not None and hb_age > max_age) else "STOPPED_HEALTHY_STATE"
        heartbeat_status = "STALE" if hb_age is not None else "ABSENT"
    else:
        process_status = "STOPPED"
        overall = "FAILED"
        heartbeat_status = "UNKNOWN"

    if not state_ok or (not accounting_ok and not runtime_running):
        overall = "FAILED"

    state_status = "HEALTHY" if state_ok else "FAILED"
    accounting_status = "PASS" if accounting_ok else "FAIL"
    data_status = "PASS" if data_ok else "DEGRADED"

    last_cycle_at = hb.get("last_cycle_at") or rt.get("last_cycle_at")
    next_cycle = hb.get("next_cycle_expected_at") or rt.get("next_cycle_expected_at")
    interval = int(cfg.get("RUNTIME_INTERVAL_SEC") or 300)

    out = {
        "schema": "tae.parallel_paper.health.v2",
        "generated_at": _now(),
        "overall_status": overall,
        "status": overall,
        "process_health": {
            "status": process_status,
            "runtime_running": runtime_running,
            "pid": pid if pid_alive else None,
            "pid_alive": pid_alive,
            "pid_source": pid_source,
            "duplicates": duplicates,
            "heartbeat_fresh": heartbeat_fresh,
            "heartbeat_status": heartbeat_status,
            "heartbeat_age_sec": hb_age,
            "last_cycle_at": last_cycle_at,
            "next_cycle_expected_at": next_cycle,
            "interval_sec": interval,
        },
        "state_health": {"status": state_status, "ok": state_ok},
        "accounting_health": {
            "status": accounting_status,
            "v1_pass": a1,
            "v2_pass": a2,
        },
        "data_health": {"status": data_status, "ok": data_ok, "notes": data_notes},
        "runtime_running": runtime_running,
        "pid": pid if pid_alive else None,
        "pid_alive": pid_alive,
        "heartbeat_fresh": heartbeat_fresh,
        "heartbeat_status": heartbeat_status,
        "heartbeat_age_sec": hb_age,
        "last_cycle_at": last_cycle_at,
        "next_cycle_expected_at": next_cycle,
        "state_status": state_status,
        "accounting_status": accounting_status,
        "PARALLEL_PAPER_ENABLED": bool(cfg.get("PARALLEL_PAPER_ENABLED")),
        "V2_ACTIVATION_SCOPE": cfg.get("V2_ACTIVATION_SCOPE"),
        "V2_LIVE_ENABLED": False,
        "V2_CANONICAL_PAPER_ENABLED": False,
        "V1_MODE": cfg.get("V1_MODE"),
        "V2_MODE": cfg.get("V2_MODE") or "ISOLATED_PARALLEL_PAPER",
        "v1": {
            "cash": _f(v1.get("cash")),
            "positions": len(v1.get("positions") or {}),
            "realized_pnl": _f(v1.get("realized_pnl")),
            "unrealized_pnl": _f(v1.get("unrealized_pnl") if v1.get("unrealized_pnl") is not None else None),
            "account_value": v1_acct["account_value"],
            "invested": v1_acct["invested"],
            "total_pnl": _f(v1.get("total_pnl")),
            "starting_value": _f(v1.get("starting_value") or v1.get("starting_capital")),
            "inception_date": v1.get("inception_date") or v1.get("created_at"),
            "source": v1.get("source") or ("CANONICAL_PAPER" if cfg.get("V1_MODE") == "CANONICAL_PAPER_MIRROR" else "ISOLATED"),
            "v1_mode": v1.get("v1_mode") or cfg.get("V1_MODE"),
            "read_only": bool(v1.get("read_only")),
            "accounting_pass": bool(v1_acct["reconciliation_pass"] and a1),
            "path": str(
                cfg.get("CANONICAL_PAPER_PORTFOLIO")
                if str(cfg.get("V1_MODE") or "").upper() == "CANONICAL_PAPER_MIRROR"
                else p["v1_portfolio"]
            ),
        },
        "v2": {
            "cash": _f(v2p.get("cash")),
            "positions": len(v2p.get("positions") or {}),
            "realized_pnl": _f(v2p.get("realized_pnl")),
            "account_value": v2_acct["account_value"],
            "invested": v2_acct["invested"],
            "accounting_pass": bool(v2_acct["reconciliation_pass"] and a2),
            "starting_capital": _f(v2p.get("starting_capital"), float(cfg["V2_STARTING_CAPITAL"])),
            "v2_mode": "ISOLATED_PARALLEL_PAPER",
            "inception_date": v2p.get("created_at"),
            "path": str(p["v2_portfolio"]),
            "cycles_path": str(p["v2_cycles"]),
        },
        "latest_conclusion": str(p["latest_conclusion"]),
        "reports_dir": str(p["reports"]),
        "log_path": str(p["log"]),
        "heartbeat_path": str(p["heartbeat"]),
        "status_path": str(p["status"]),
    }
    _atomic_write_json(p["v1_health"], {"arm": "V1", **out["v1"], "at": _now()})
    _atomic_write_json(p["v2_health"], {"arm": "V2", **out["v2"], "at": _now()})
    return out


def _watchlist(cfg: dict[str, Any], marks: dict[str, dict[str, Any]], v1: dict, v2p: dict) -> list[str]:
    wl = set(cfg.get("WATCHLIST") or [])
    wl |= set(marks.keys())
    wl |= set((v1.get("positions") or {}).keys())
    wl |= set((v2p.get("positions") or {}).keys())
    return sorted(t for t in wl if t)


def _run_v1_arm(
    *,
    portfolio: dict[str, Any],
    ticker: str,
    snap: dict[str, Any],
    cfg: dict[str, Any],
    p: dict[str, Path],
    decision_id: str,
    phase: str = PHASE_ALL,
) -> dict[str, Any]:
    # Optional offline mirror mode — not the V1/V2 experiment default
    if str(cfg.get("V1_MODE") or portfolio.get("v1_mode") or "").upper() == "CANONICAL_PAPER_MIRROR":
        mark = _f(snap.get("mark_price"))
        pos = (portfolio.get("positions") or {}).get(ticker)
        if pos and _f(pos.get("shares")) > 0:
            if mark > 0:
                pos["current_price"] = mark
            action, reason = "HOLD", "V1_MIRROR_OBSERVE_OPEN"
            qty = _f(pos.get("shares"))
            value = qty * mark if mark else _f(pos.get("current_value"))
        else:
            action, reason = "HOLD", "V1_MIRROR_OBSERVE_FLAT"
            qty, value = 0.0, 0.0
        dec = {
            "ts": _now(),
            "decision_id": decision_id,
            "arm": "V1",
            "ticker": ticker,
            "action": action,
            "reason": reason,
            "quantity": qty,
            "value": value,
            "score": snap.get("score"),
            "signal": snap.get("signal"),
            "v1_mode": "CANONICAL_PAPER_MIRROR",
            "mutates_portfolio": False,
            "mutates_canonical_paper": False,
        }
        _append_jsonl(p["v1_decisions"], dec)
        return dec

    _assert_paper_isolation(cfg)
    phase_n = _s(phase).lower() or PHASE_ALL
    mark_ok, mark_status, mark = _mark_is_usable(snap)
    score = snap.get("score") if isinstance(snap, dict) else None
    signal = _s((snap or {}).get("signal"))
    favorable = signal in {"STRONG BUY", "BUY"} or (score is not None and float(score) >= V1_V2_ENTRY_MIN_SCORE)
    pos = (portfolio.get("positions") or {}).get(ticker)
    action = "HOLD"
    reason = "V1_HOLD"
    value = 0.0
    qty = 0.0
    executed = False
    execution_id: str | None = None
    realized_pnl_fill: float | None = None
    has_pos = bool(pos and _f(pos.get("shares")) > 0)

    # Two-pass capital cycle: manage=exits only; entry=buys only; all=legacy combined.
    if phase_n == PHASE_MANAGE and not has_pos:
        dec = {
            "decision_id": decision_id,
            "arm": "V1",
            "ticker": ticker,
            "action": "HOLD",
            "reason": "V1_MANAGE_FLAT",
            "score": score,
            "quantity": 0.0,
            "value": 0.0,
            "mark_price": mark if mark_ok else None,
            "mark_status": mark_status,
            "ts": _now(),
            "v1_mode": "ISOLATED_PARALLEL_PAPER",
            "mutates_portfolio": False,
            "mutates_canonical_paper": False,
            "executor_called": False,
            "execution_id": None,
            "realized_pnl": None,
            "phase": phase_n,
        }
        _append_jsonl(p["v1_decisions"], dec)
        return dec
    if phase_n == PHASE_ENTRY and has_pos:
        dec = {
            "decision_id": decision_id,
            "arm": "V1",
            "ticker": ticker,
            "action": "HOLD",
            "reason": "V1_ENTRY_ALREADY_OPEN",
            "score": score,
            "quantity": _f(pos.get("shares")),
            "value": 0.0,
            "mark_price": mark if mark_ok else None,
            "mark_status": mark_status,
            "ts": _now(),
            "v1_mode": "ISOLATED_PARALLEL_PAPER",
            "mutates_portfolio": False,
            "mutates_canonical_paper": False,
            "executor_called": False,
            "execution_id": None,
            "realized_pnl": None,
            "phase": phase_n,
        }
        _append_jsonl(p["v1_decisions"], dec)
        return dec

    if has_pos and phase_n in {PHASE_MANAGE, PHASE_ALL}:
        if not mark_ok:
            action = "HOLD"
            reason = mark_status  # MARK_UNAVAILABLE / MARK_STALE
            qty = _f(pos.get("shares"))
            value = qty * _f(pos.get("last_valid_mark") or pos.get("current_price") or 0.0)
        else:
            v1_stop_pct, v1_vol_diag = v1volstop.vol_adjusted_stop_pct(
                v1volstop.fetch_recent_closes(ticker)
            )
            act, rsn = v1trail.v1_trailing_exit_action(
                pos,
                avg_price=_f(pos.get("avg_price")),
                current_price=mark,
                now_iso=_now(),
                stop_loss_pct=v1_stop_pct,
            )
            pos["v1_vol_stop_diag"] = v1_vol_diag
            if act:
                shares = _f(pos.get("shares"))
                avg = _f(pos.get("avg_price"))
                cash_before = _f(portfolio.get("cash"))
                pos_snapshot = dict(pos)
                cost_cfg = _paper_tx_cost_cfg(cfg)
                realized, gross, after = pe._sell_shares(
                    portfolio,
                    ticker,
                    shares,
                    mark,
                    apply_paper_tx_costs=True,
                    paper_tx_cost_cfg=cost_cfg,
                )
                eco = _take_fill_economics(portfolio)
                cash_after = _f(portfolio.get("cash"))
                net_credit = _f(eco.get("net_proceeds"), cash_after - cash_before)
                credited = abs((cash_after - cash_before) - net_credit) <= 1e-3
                fully_closed = after is None and ticker not in (portfolio.get("positions") or {})
                if not (credited and fully_closed):
                    # Fail closed — restore pre-sell cash/position; block replacement BUY this cycle.
                    portfolio["cash"] = cash_before
                    portfolio.setdefault("positions", {})[ticker] = pos_snapshot
                    portfolio["realized_pnl"] = _f(portfolio.get("realized_pnl")) - _f(realized)
                    action = "ERROR"
                    reason = "V1_SELL_SETTLEMENT_FAILED"
                    _append_jsonl(
                        p["v1_errors"],
                        {
                            "ts": _now(),
                            "ticker": ticker,
                            "error": reason,
                            "cash_before": cash_before,
                            "cash_after": cash_after,
                            "gross": gross,
                        },
                    )
                else:
                    action = "SELL"
                    reason = rsn or act
                    qty = shares
                    value = net_credit
                    realized_pnl_fill = round(float(realized), 6)
                    executed = True
                    execution_id = f"V1EX-{uuid.uuid4().hex[:16].upper()}"
                    cost_fields = _trade_cost_fields(eco, gross=gross, side="SELL")
                    _append_jsonl(
                        p["v1_trades"],
                        {
                            "ts": _now(),
                            "ticker": ticker,
                            "action": "SELL",
                            "reason": reason,
                            "shares": shares,
                            "price": mark,
                            "decision_id": decision_id,
                            "arm": "V1",
                            "execution_id": execution_id,
                            "realized_pnl": realized_pnl_fill,
                            "gross": gross,
                            "net": net_credit,
                            "cash_before": cash_before,
                            "cash_after": cash_after,
                            **cost_fields,
                        },
                    )
                    record_execution_learning_feedback(
                        arm="V1",
                        execution_id=execution_id,
                        decision_id=decision_id,
                        action="SELL",
                        ticker=ticker,
                        price=mark,
                        shares=shares,
                        value=value,
                        reason=reason,
                        realized_pnl=realized_pnl_fill,
                        strategy_variant="V1",
                        p=p,
                    )
                    tx_cost = _f(eco.get("total_transaction_cost"))
                    _log_capital_event(
                        "V1_SELL_EXECUTED",
                        arm="V1",
                        ticker=ticker,
                        quantity=shares,
                        price=mark,
                        gross=gross,
                        costs=tx_cost,
                        net=net_credit,
                        realized_pnl=realized_pnl_fill,
                        cash_before=cash_before,
                        cash_after=cash_after,
                        decision_id=decision_id,
                        execution_id=execution_id,
                        reason=reason,
                    )
                    _log_capital_event(
                        "V1_CAPITAL_RELEASED",
                        arm="V1",
                        ticker=ticker,
                        quantity=shares,
                        price=mark,
                        net=net_credit,
                        realized_pnl=realized_pnl_fill,
                        cash_before=cash_before,
                        cash_after=cash_after,
                        decision_id=decision_id,
                        execution_id=execution_id,
                    )
            else:
                action = "HOLD"
                reason = "V1_HOLD_OPEN"
                pos["current_price"] = mark
                pos["last_valid_mark"] = mark
                pos["mark_status"] = mark_status if mark_status else "FRESH"
                pos["mark_timestamp"] = _now()
    elif (not has_pos) and phase_n in {PHASE_ENTRY, PHASE_ALL} and favorable and (snap or {}).get("eligible") is not False:
        entry_ok, entry_reason = _entry_price_allowed(snap, mark_status)
        if not mark_ok:
            action = "HOLD"
            reason = mark_status
        elif not entry_ok:
            action = "BLOCKED"
            reason = entry_reason
        else:
            reserve = float(cfg["V1_MIN_CASH_RESERVE"])
            cash = _f(portfolio.get("cash"))
            notional = min(2500.0, max(0.0, cash - reserve) * 0.25)
            deployment_meta: dict[str, Any] = {}
            try:
                import tae_adaptive_deployment as adep

                sizing = adep.resolve_buy_notional(
                    control_notional=notional,
                    inputs={
                        "cash_available": cash,
                        "cash_reserve": reserve,
                        "maximum_position_notional": 2500.0,
                        "current_open_positions": len(
                            [
                                x
                                for x in (portfolio.get("positions") or {}).values()
                                if _f((x or {}).get("shares")) > 0
                            ]
                        ),
                        "maximum_positions": 8,
                        "confidence": _f((snap or {}).get("confidence"), 0.5) if isinstance(snap, dict) else 0.5,
                    },
                    ticker=ticker,
                    arm="V1",
                )
                deployment_meta = dict(sizing.get("deployment") or {})
                if sizing.get("blocked"):
                    action = "BLOCKED"
                    reason = _s(sizing.get("reason_code")) or "BLOCKED_ADAPTIVE_DEPLOYMENT"
                    notional = 0.0
                else:
                    notional = _f(sizing.get("executed_notional"), notional)
            except Exception:
                deployment_meta = {}
            if notional >= 250.0 and mark > 0:
                cash_before = cash
                portfolio_before = {
                    "cash": cash_before,
                    "positions": deepcopy(portfolio.get("positions") or {}),
                }
                cost_cfg = _paper_tx_cost_cfg(cfg)
                shares, after = pe._buy_shares(
                    portfolio,
                    ticker,
                    notional,
                    mark,
                    apply_paper_tx_costs=True,
                    paper_tx_cost_cfg=cost_cfg,
                )
                if shares > 0 and after:
                    after["strategy_version"] = "V1"
                    after["current_price"] = mark
                    after["last_valid_mark"] = mark
                    after["mark_status"] = "FRESH"
                    after["mark_timestamp"] = _now()
                    action = "BUY"
                    reason = "V1_SIGNAL_BUY"
                    if deployment_meta.get("experiment_arm") == "CHALLENGER":
                        reason = "V1_SIGNAL_BUY_ADAPTIVE_CHALLENGER"
                    qty = shares
                    value = shares * mark
                    executed = True
                    execution_id = f"V1EX-{uuid.uuid4().hex[:16].upper()}"
                    cash_after = _f(portfolio.get("cash"))
                    eco = _take_fill_economics(portfolio)
                    cost_fields = _trade_cost_fields(eco, gross=value, side="BUY")
                    entry_ts = _now()
                    risk_snap = _v1_entry_risk_snapshot(
                        ticker=ticker,
                        execution_id=execution_id,
                        decision_id=decision_id,
                        entry_ts=entry_ts,
                        mark=mark,
                        shares=shares,
                        notional_requested=notional,
                        cash_before=cash_before,
                        reserve=reserve,
                        portfolio_before=portfolio_before,
                        snap=snap if isinstance(snap, dict) else None,
                    )
                    if deployment_meta:
                        risk_snap = dict(risk_snap)
                        risk_snap["adaptive_deployment"] = deployment_meta
                        if deployment_meta.get("formula_id"):
                            risk_snap["sizing_formula_id"] = deployment_meta.get("formula_id")
                            risk_snap["sizing_formula_version"] = deployment_meta.get("formula_version")
                    _append_jsonl(
                        p["v1_trades"],
                        {
                            "ts": entry_ts,
                            "ticker": ticker,
                            "action": "BUY",
                            "shares": shares,
                            "price": mark,
                            "decision_id": decision_id,
                            "arm": "V1",
                            "execution_id": execution_id,
                            "cash_before": cash_before,
                            "cash_after": cash_after,
                            "risk_snapshot": risk_snap,
                            **deployment_meta,
                            **cost_fields,
                        },
                    )
                    _record_adaptive_exposure_if_challenger(
                        deployment_meta, value, arm="V1", ticker=ticker
                    )
                    record_execution_learning_feedback(
                        arm="V1",
                        execution_id=execution_id,
                        decision_id=decision_id,
                        action="BUY",
                        ticker=ticker,
                        price=mark,
                        shares=shares,
                        value=value,
                        reason=reason,
                        strategy_variant="V1",
                        p=p,
                    )
                    buy_event = (
                        "V1_CAPITAL_REDEPLOYED"
                        if _f(portfolio.get("realized_pnl")) != 0.0
                        else "V1_BUY_EXECUTED"
                    )
                    tx_cost = _f(eco.get("total_transaction_cost"))
                    net_debit = abs(_f(eco.get("net_cash_movement"), value + tx_cost))
                    _log_capital_event(
                        "V1_BUY_EXECUTED",
                        arm="V1",
                        ticker=ticker,
                        quantity=shares,
                        price=mark,
                        gross=value,
                        costs=tx_cost,
                        net=net_debit,
                        cash_before=cash_before,
                        cash_after=cash_after,
                        decision_id=decision_id,
                        execution_id=execution_id,
                        reason=reason,
                    )
                    if buy_event == "V1_CAPITAL_REDEPLOYED":
                        _log_capital_event(
                            "V1_CAPITAL_REDEPLOYED",
                            arm="V1",
                            ticker=ticker,
                            quantity=shares,
                            price=mark,
                            net=net_debit,
                            cash_before=cash_before,
                            cash_after=cash_after,
                            decision_id=decision_id,
                            execution_id=execution_id,
                        )
                else:
                    action = "BLOCKED"
                    eco = _take_fill_economics(portfolio)
                    reason = (
                        "V1_INSUFFICIENT_CASH_FOR_COST"
                        if eco.get("blocked") == "INSUFFICIENT_CASH_FOR_COST"
                        else "V1_INSUFFICIENT_CASH"
                    )
            elif action != "BLOCKED":
                action = "BLOCKED"
                reason = "V1_INSUFFICIENT_CASH"
    else:
        if phase_n == PHASE_MANAGE:
            action = "HOLD"
            reason = "V1_MANAGE_NO_EXIT"
        elif phase_n == PHASE_ENTRY:
            action = "HOLD"
            reason = "V1_NO_SIGNAL"
        else:
            action = "HOLD"
            reason = "V1_NO_SIGNAL"

    dec = {
        "decision_id": decision_id,
        "arm": "V1",
        "ticker": ticker,
        "action": action,
        "reason": reason,
        "score": score,
        "quantity": qty,
        "value": value,
        "mark_price": mark if mark_ok else None,
        "mark_status": mark_status,
        "ts": _now(),
        "v1_mode": "ISOLATED_PARALLEL_PAPER",
        "mutates_portfolio": bool(executed),
        "mutates_canonical_paper": False,
        "executor_called": bool(executed),
        "execution_id": execution_id,
        "realized_pnl": realized_pnl_fill,
        "phase": phase_n,
        "writes_live": False,
        "writes_broker": False,
    }
    _append_jsonl(p["v1_decisions"], dec)
    _append_jsonl(
        p["v1_executions"],
        {
            **dec,
            "executed": executed,
        },
    )
    return dec


def _run_v2_arm(
    *,
    portfolio: dict[str, Any],
    ticker: str,
    snap: dict[str, Any],
    cfg_par: dict[str, Any],
    p: dict[str, Path],
    decision_id: str,
    phase: str = PHASE_ALL,
) -> dict[str, Any]:
    if not v2_parallel_mutation_allowed(cfg_par):
        return {
            "decision_id": decision_id,
            "arm": "V2",
            "ticker": ticker,
            "action": "BLOCKED",
            "reason": "V2_SCOPE_DISABLED",
            "ts": _now(),
        }

    try:
        _assert_paper_isolation(cfg_par)
    except RuntimeError:
        return {
            "decision_id": decision_id,
            "arm": "V2",
            "ticker": ticker,
            "action": "BLOCKED",
            "reason": BLOCKED_PAPER_ISOLATION,
            "ts": _now(),
            "writes_live": False,
            "writes_broker": False,
        }

    phase_n = _s(phase).lower() or PHASE_ALL
    v2_cfg = load_strategy_v2_config()
    v2_kelly_fraction, v2_kelly_diag = v2kelly.v2_tranche_fraction_from_edge(p["v2_trades"])
    v2_cfg["tranche_fraction"] = v2_kelly_fraction
    v2_cfg["_v2_kelly_diag"] = v2_kelly_diag
    v2_cfg["max_tranches"] = 5
    v2_cfg["add_tranche_drop_pct"] = 0.03
    v2_cfg["minimum_cycle_profit_pct"] = 0.10
    v2_cfg["TRAILING_ACTIVATE_PCT"] = 5.0
    v2_cfg["TRAILING_DISTANCE_PCT"] = 2.0
    v2_cfg["V2_STOP_LOSS_PCT"] = -3.0
    v2_cfg["MIN_CASH_RESERVE_USD"] = float(cfg_par["V2_MIN_CASH_RESERVE"])

    store = v2.load_cycle_store(p["v2_cycles"])
    cycle = v2.find_open_cycle_for_ticker(store, ticker)
    mark_ok, mark_status, mark = _mark_is_usable(snap)
    score = snap.get("score") if isinstance(snap, dict) else None
    signal = _s((snap or {}).get("signal"))
    favorable = signal in {"STRONG BUY", "BUY"} or (score is not None and float(score) >= V1_V2_ENTRY_MIN_SCORE)
    # Consume canonical Decision Brain / PDE action — do not invent BUY over SKIP.
    try:
        from tae_paper_execution import (
            is_decision_brain_skip,
            normalize_decision_brain_action,
            resolve_decision_brain_verdict,
        )

        resolved = resolve_decision_brain_verdict(ticker=ticker)
        if resolved.get("verdict") == "SKIP_PAPER":
            pde_action = "SKIP_PAPER"
        elif resolved.get("raw"):
            pde_action = normalize_decision_brain_action(resolved.get("raw"))
        else:
            # No SKIP evidence: keep signal-based favorable mapping (legacy challenger path).
            pde_action = "BUY_PAPER" if favorable else "HOLD_PAPER"
        # When signal is favorable but Decision Brain is SKIP, keep SKIP — binding gate consumes it.
        if is_decision_brain_skip(pde_action):
            pde_action = "SKIP_PAPER"
    except Exception:
        pde_action = "BUY_PAPER" if favorable else "HOLD_PAPER"
    pos = (portfolio.get("positions") or {}).get(ticker) or {}
    action = "HOLD"
    reason = "V2_HOLD"
    thesis = "WATCH"
    cycle_id = None
    tranche = 0
    tranche_gate: str | None = None
    qty = 0.0
    value = 0.0
    execution_id: str | None = None
    realized_pnl_fill: float | None = None
    order: dict[str, Any] | None = None

    try:
        # Phase gates: manage = exits only; entry = ADD/OPEN/reentry only.
        if phase_n == PHASE_MANAGE and not cycle and _f(pos.get("shares")) <= 0:
            action = "HOLD"
            reason = "V2_MANAGE_FLAT"
            raise _PhaseComplete()
        if not mark_ok:
            # Open positions / cycles: never invent exit or ADD economics from stale/missing marks
            # Protective SELL cannot fire without usable mark; entry blocked as stale.
            if cycle or _f(pos.get("shares")) > 0:
                action = "HOLD"
                reason = mark_status
                thesis = "WATCH"
                cycle_id = (cycle or {}).get("cycle_id")
                tranche = int((cycle or {}).get("tranche_count") or 0)
                qty = _f(pos.get("shares"))
            elif favorable:
                action = "HOLD"
                reason = (
                    reentry.V2_REENTRY_BLOCKED_STALE_PRICE
                    if mark_status in {"MARK_STALE", "STALE"}
                    else mark_status
                )
            else:
                action = "HOLD"
                reason = "V2_NO_ENTRY_SIGNAL"
            raise _PhaseComplete()
        allow_exit = phase_n in {PHASE_MANAGE, PHASE_ALL}
        allow_add = phase_n in {PHASE_ENTRY, PHASE_ALL}
        allow_open = phase_n in {PHASE_ENTRY, PHASE_ALL}
        if cycle and allow_exit:
            cycle_id = cycle.get("cycle_id")
            tranche = int(cycle.get("tranche_count") or 0)
            avg = _f(pos.get("avg_price") or cycle.get("average_cost"))
            hr = classify_hard_risk_for_v2(
                ticker=ticker,
                avg_price=avg,
                current_price=mark,
                shares=_f(pos.get("shares") or 1.0),
                mark_freshness=_s(snap.get("mark_freshness") or "FRESH"),
                mark_age_seconds=_f(snap.get("mark_age_seconds")),
            )
            # Exit first
            xin = xp.ExitPolicyInput(
                ticker=ticker,
                timestamp=_now(),
                mark_price=mark,
                mark_freshness=_s((snap or {}).get("mark_freshness") or "FRESH"),
                mark_age_seconds=_f((snap or {}).get("mark_age_seconds")),
                average_cost=avg,
                quantity=_f(pos.get("shares")),
                score=score if score is not None else None,
                pde_action=pde_action,
                candidate_eligible=(snap or {}).get("eligible"),
                data_fresh=bool((snap or {}).get("data_fresh", True)),
                session_valid=True,
                accounting_valid=True,
                cycle=cycle,
                hard_risk_class=hr["class"],
                hard_risk_payload=hr,
                decision_id=decision_id + "-EX",
            )
            xd = xp.evaluate_exit_policy(xin, cfg=v2_cfg, enabled=True)
            # Persist trailing state on open cycle / position every tick (SSOT fields).
            trail_patch = {
                k: xd.get(k)
                for k in (
                    "trailing_armed",
                    "highest_price",
                    "trailing_stop",
                    "armed_at",
                    "updated_at",
                    "partial_profit_taken",
                )
                if k in xd
            }
            if trail_patch and cycle:
                cycle = dict(cycle)
                cycle.update(trail_patch)
                store = v2.load_cycle_store(p["v2_cycles"])
                store.setdefault("cycles", {})[cycle["cycle_id"]] = cycle
                v2.save_cycle_store(store, p["v2_cycles"])
                pos_ref = (portfolio.get("positions") or {}).get(ticker)
                if isinstance(pos_ref, dict):
                    pos_ref.update(trail_patch)
                xin.cycle = cycle
            xact = _s(xd.get("action")).upper()
            if xact == "CLOSE_CYCLE":
                cash_before = _f(portfolio.get("cash"))
                pos_snapshot = dict(pos) if pos else {}
                shares_before = _f(pos.get("shares"))
                exec_dec = xp.materialize_close_decision(xd, xin, cfg=v2_cfg)
                if exec_dec:
                    cost_cfg = _paper_tx_cost_cfg(cfg_par)
                    order = pe.execute_decision(
                        exec_dec,
                        portfolio,
                        accounting=None,
                        all_decisions=[exec_dec],
                        strategy_v2_enabled_override=True,
                        strategy_v2_cycle_path=p["v2_cycles"],
                        strategy_v2_journal_path=p["v2_tranches"],
                        apply_paper_tx_costs=True,
                        paper_tx_cost_cfg=cost_cfg,
                    )
                    if order.get("status") == "EXECUTED":
                        cash_after = _f(portfolio.get("cash"))
                        eco = order.get("fill_economics") if isinstance(order.get("fill_economics"), dict) else _take_fill_economics(portfolio)
                        gross = _f(order.get("filled_value_usd") or eco.get("gross_proceeds") or (shares_before * mark))
                        net_credit = _f(eco.get("net_proceeds") or eco.get("net_cash_movement") or (cash_after - cash_before))
                        tx_cost = _f(eco.get("total_transaction_cost") or order.get("total_transaction_cost"))
                        credited = abs((cash_after - cash_before) - net_credit) <= 1e-3
                        rem = (portfolio.get("positions") or {}).get(ticker)
                        closed = rem is None or _f((rem or {}).get("shares")) <= 1e-9
                        if closed and rem is not None:
                            # Normalize zero-share leftovers to fully closed position state.
                            (portfolio.get("positions") or {}).pop(ticker, None)
                            closed = True
                        if not (credited and closed):
                            portfolio["cash"] = cash_before
                            if pos_snapshot:
                                portfolio.setdefault("positions", {})[ticker] = pos_snapshot
                            action = "ERROR"
                            reason = "V2_SELL_SETTLEMENT_FAILED"
                            _append_jsonl(
                                p["v2_errors"],
                                {
                                    "ts": _now(),
                                    "ticker": ticker,
                                    "error": reason,
                                    "cash_before": cash_before,
                                    "cash_after": cash_after,
                                    "net": net_credit,
                                },
                            )
                        else:
                            action = "CLOSE"
                            reason = _s(xd.get("close_reason") or xd.get("reason_code"))
                            thesis = _s(xd.get("thesis_state"))
                            value = net_credit
                            qty = _f(order.get("fill_shares") or shares_before)
                            realized_pnl_fill = _f(order.get("realized_pnl_net") or order.get("realized_pnl"))
                            execution_id = _s(order.get("execution_id")) or f"V2EX-{uuid.uuid4().hex[:16].upper()}"
                            _append_jsonl(
                                p["v2_trades"],
                                {
                                    "ts": _now(),
                                    "ticker": ticker,
                                    "action": "CLOSE",
                                    "shares": qty,
                                    "price": mark,
                                    "decision_id": decision_id,
                                    "arm": "V2",
                                    "execution_id": execution_id,
                                    "realized_pnl": realized_pnl_fill,
                                    "gross": gross,
                                    "net": net_credit,
                                    "cash_before": cash_before,
                                    "cash_after": cash_after,
                                    **_trade_cost_fields(eco, gross=gross, side="SELL"),
                                },
                            )
                            _log_capital_event(
                                "V2_SELL_EXECUTED",
                                arm="V2",
                                ticker=ticker,
                                quantity=qty,
                                price=mark,
                                gross=gross,
                                costs=tx_cost,
                                net=net_credit,
                                realized_pnl=realized_pnl_fill,
                                cash_before=cash_before,
                                cash_after=cash_after,
                                cycle_id=cycle_id,
                                decision_id=decision_id,
                                execution_id=execution_id,
                                reason=reason,
                            )
                            _log_capital_event(
                                "V2_CAPITAL_RELEASED",
                                arm="V2",
                                ticker=ticker,
                                quantity=qty,
                                price=mark,
                                net=net_credit,
                                realized_pnl=realized_pnl_fill,
                                cash_before=cash_before,
                                cash_after=cash_after,
                                cycle_id=cycle_id,
                                decision_id=decision_id,
                                execution_id=execution_id,
                            )
                            # Profit trailing → REENTRY_WATCH (capital already returned via _sell_shares).
                            if reason == V2_PROFIT_TRAILING_REASON or reason == xp.REASON_CLOSE_TRAILING:
                                rstore = reentry.load_reentry_store(p.get("v2_reentry"))
                                peak = _f(
                                    (cycle or {}).get("highest_price"),
                                    (pos or {}).get("highest_price") or mark,
                                )
                                reentry.mark_profit_captured(
                                    rstore,
                                    ticker=ticker,
                                    exit_price=float(mark),
                                    exit_at=_now(),
                                    realized_pnl=float(realized_pnl_fill or 0.0),
                                    peak_price=peak,
                                    cycle_id=cycle_id or (cycle or {}).get("cycle_id"),
                                    cfg=v2_cfg,
                                    persist_path=p.get("v2_reentry"),
                                    released_capital=float(net_credit),
                                )
                                _log_capital_event(
                                    "V2_REENTRY_WATCH",
                                    arm="V2",
                                    ticker=ticker,
                                    price=mark,
                                    net=net_credit,
                                    realized_pnl=realized_pnl_fill,
                                    cycle_id=cycle_id,
                                    decision_id=decision_id,
                                    reason=reason,
                                )
                    else:
                        action = "BLOCKED"
                        reason = _s(order.get("status") or order.get("reason") or "V2_CLOSE_NOT_EXECUTED")
                else:
                    action = "BLOCKED"
                    reason = "V2_CLOSE_MATERIALIZE_FAILED"
            elif xact == "STOP_ACCUMULATION":
                v2.apply_stop_accumulation(cycle, store, persist=True, cycle_path=p["v2_cycles"])
                action = "STOP_ACCUMULATION"
                reason = _s(xd.get("reason_code"))
                thesis = _s(xd.get("thesis_state"))
            elif allow_add:
                # Buy reeval (ADD) — only on entry/all phases after protective exit HOLD
                hr_active, hr_status = buy_policy_hard_risk_fields(hr)
                store = v2.load_cycle_store(p["v2_cycles"])
                cycle = v2.find_open_cycle_for_ticker(store, ticker)
                if cycle:
                    binp = pol.BuyPolicyInput(
                        ticker=ticker,
                        timestamp=_now(),
                        mark_price=mark,
                        mark_freshness=_s((snap or {}).get("mark_freshness") or "FRESH"),
                        mark_age_seconds=_f((snap or {}).get("mark_age_seconds")),
                        score=score if score is not None else None,
                        pde_action=pde_action,
                        hard_risk_active=hr_active,
                        hard_risk_status=hr_status,
                        session_valid=True,
                        data_fresh=bool((snap or {}).get("data_fresh", True)),
                        candidate_eligible=(snap or {}).get("eligible"),
                        held=_f(pos.get("shares")) > 0,
                        quantity=_f(pos.get("shares")),
                        average_cost=avg,
                        cash=_f(portfolio.get("cash")),
                        cycle=cycle,
                        decision_id=decision_id + "-BUY",
                        hard_risk_class=_s(hr.get("class") or "SAFE"),
                        allow_position_growth=not fill_time_blocks_add(hr),
                    )
                    # Existing PCE signals → profit-first ADD gate (no new engine).
                    pol.apply_profit_context_to_input(
                        binp,
                        pol.extract_profit_context_for_ticker(
                            pol.load_profit_context_document(),
                            ticker,
                        ),
                    )
                    bd = pol.evaluate_buy_policy(binp, cfg=v2_cfg, enabled=True, store=store)
                    bact = _s(bd.get("action")).upper()
                    reason = _s(bd.get("reason_code"))
                    thesis = _s(bd.get("thesis_state"))
                    tranche_gate = _s(bd.get("tranche_gate_code"))
                    if bact == "ADD_TRANCHE":
                        bd, adep_meta, adep_block = _apply_adaptive_deployment_to_v2_buy(
                            bd,
                            binp,
                            ticker=ticker,
                            portfolio=portfolio,
                            v2_cfg=v2_cfg,
                            v2_add_authorized=True,
                        )
                        if adep_block:
                            action = "BLOCKED"
                            reason = adep_block
                            exec_dec = None
                        else:
                            exec_dec = pol.materialize_v2_execution_decision(bd, binp, cfg=v2_cfg)
                        if exec_dec:
                            cash_before = _f(portfolio.get("cash"))
                            portfolio_before = {
                                "cash": cash_before,
                                "positions": deepcopy(portfolio.get("positions") or {}),
                            }
                            order = pe.execute_decision(
                                exec_dec,
                                portfolio,
                                accounting=None,
                                all_decisions=[exec_dec],
                                strategy_v2_enabled_override=True,
                                strategy_v2_cycle_path=p["v2_cycles"],
                                strategy_v2_journal_path=p["v2_tranches"],
                                apply_paper_tx_costs=True,
                                paper_tx_cost_cfg=_paper_tx_cost_cfg(cfg_par),
                            )
                            if order.get("status") == "EXECUTED":
                                action = "ADD"
                                value = _f(order.get("filled_value_usd"))
                                qty = _f(order.get("fill_shares"))
                                execution_id = _s(order.get("execution_id")) or f"V2EX-{uuid.uuid4().hex[:16].upper()}"
                                eco = order.get("fill_economics") if isinstance(order.get("fill_economics"), dict) else _take_fill_economics(portfolio)
                                cash_after = _f(portfolio.get("cash"))
                                entry_ts = _now()
                                risk_snap = _v2_entry_risk_snapshot(
                                    ticker=ticker,
                                    execution_id=execution_id,
                                    decision_id=decision_id,
                                    entry_ts=entry_ts,
                                    mark=mark,
                                    shares=qty,
                                    filled_value=value,
                                    entry_kind="ADD",
                                    cash_before=cash_before,
                                    portfolio_before=portfolio_before,
                                    v2_cfg=v2_cfg,
                                    bd=bd,
                                    order=order,
                                    cycle_id=cycle_id,
                                    snap=snap if isinstance(snap, dict) else None,
                                )
                                risk_snap = _persist_v2_cycle_risk_snapshot(p, cycle_id, risk_snap)
                                if adep_meta:
                                    risk_snap = dict(risk_snap)
                                    risk_snap["adaptive_deployment"] = adep_meta
                                    if adep_meta.get("formula_id"):
                                        risk_snap["sizing_formula_id"] = adep_meta.get("formula_id")
                                        risk_snap["sizing_formula_version"] = adep_meta.get("formula_version")
                                _append_jsonl(
                                    p["v2_trades"],
                                    {
                                        "ts": entry_ts,
                                        "ticker": ticker,
                                        "action": "ADD",
                                        "shares": qty,
                                        "price": mark,
                                        "decision_id": decision_id,
                                        "arm": "V2",
                                        "execution_id": execution_id,
                                        "cycle_id": cycle_id,
                                        "cash_before": cash_before,
                                        "cash_after": cash_after,
                                        "risk_snapshot": risk_snap,
                                        **(adep_meta or {}),
                                        **_trade_cost_fields(eco, gross=value, side="BUY"),
                                    },
                                )
                                _record_adaptive_exposure_if_challenger(
                                    adep_meta, value, arm="V2", ticker=ticker
                                )
                                _log_capital_event(
                                    "V2_TRANCHE_EXECUTED",
                                    arm="V2",
                                    ticker=ticker,
                                    quantity=qty,
                                    price=mark,
                                    gross=value,
                                    costs=_f(eco.get("total_transaction_cost")),
                                    net=abs(_f(eco.get("net_cash_movement"), value)),
                                    cash_before=cash_before,
                                    cash_after=cash_after,
                                    cycle_id=cycle_id,
                                    decision_id=decision_id,
                                    execution_id=execution_id,
                                    reason=reason,
                                )
                            else:
                                action = "BLOCKED"
                                reason = _s(order.get("status") or order.get("reason"))
                        else:
                            action = "HOLD"
                    elif bact == "STOP_ACCUMULATION":
                        v2.apply_stop_accumulation(cycle, store, persist=True, cycle_path=p["v2_cycles"])
                        action = "STOP_ACCUMULATION"
                    else:
                        action = "HOLD"
                    if tranche_gate:
                        reason = reason or tranche_gate
            else:
                action = "HOLD"
                reason = "V2_HOLD_OPEN"
        elif cycle and allow_add and not allow_exit:
            # Entry-only pass on open cycle: ADD path (no CLOSE this pass)
            cycle_id = cycle.get("cycle_id")
            tranche = int(cycle.get("tranche_count") or 0)
            avg = _f(pos.get("avg_price") or cycle.get("average_cost"))
            entry_ok, entry_reason = _entry_price_allowed(snap, mark_status)
            if not entry_ok:
                action = "BLOCKED"
                reason = entry_reason
            else:
                hr = classify_hard_risk_for_v2(
                    ticker=ticker,
                    avg_price=avg,
                    current_price=mark,
                    shares=_f(pos.get("shares") or 1.0),
                    mark_freshness=_s(snap.get("mark_freshness") or "FRESH"),
                    mark_age_seconds=_f(snap.get("mark_age_seconds")),
                )
                hr_active, hr_status = buy_policy_hard_risk_fields(hr)
                store = v2.load_cycle_store(p["v2_cycles"])
                cycle = v2.find_open_cycle_for_ticker(store, ticker)
                if cycle:
                    binp = pol.BuyPolicyInput(
                        ticker=ticker,
                        timestamp=_now(),
                        mark_price=mark,
                        mark_freshness=_s((snap or {}).get("mark_freshness") or "FRESH"),
                        mark_age_seconds=_f((snap or {}).get("mark_age_seconds")),
                        score=score if score is not None else None,
                        pde_action=pde_action,
                        hard_risk_active=hr_active,
                        hard_risk_status=hr_status,
                        session_valid=True,
                        data_fresh=bool((snap or {}).get("data_fresh", True)),
                        candidate_eligible=(snap or {}).get("eligible"),
                        held=_f(pos.get("shares")) > 0,
                        quantity=_f(pos.get("shares")),
                        average_cost=avg,
                        cash=_f(portfolio.get("cash")),
                        cycle=cycle,
                        decision_id=decision_id + "-BUY",
                        hard_risk_class=_s(hr.get("class") or "SAFE"),
                        allow_position_growth=not fill_time_blocks_add(hr),
                    )
                    pol.apply_profit_context_to_input(
                        binp,
                        pol.extract_profit_context_for_ticker(
                            pol.load_profit_context_document(),
                            ticker,
                        ),
                    )
                    bd = pol.evaluate_buy_policy(binp, cfg=v2_cfg, enabled=True, store=store)
                    bact = _s(bd.get("action")).upper()
                    reason = _s(bd.get("reason_code"))
                    thesis = _s(bd.get("thesis_state"))
                    tranche_gate = _s(bd.get("tranche_gate_code"))
                    if bact == "ADD_TRANCHE":
                        bd, adep_meta, adep_block = _apply_adaptive_deployment_to_v2_buy(
                            bd,
                            binp,
                            ticker=ticker,
                            portfolio=portfolio,
                            v2_cfg=v2_cfg,
                            v2_add_authorized=True,
                        )
                        if adep_block:
                            action = "BLOCKED"
                            reason = adep_block
                            exec_dec = None
                        else:
                            exec_dec = pol.materialize_v2_execution_decision(bd, binp, cfg=v2_cfg)
                        if exec_dec:
                            cash_before = _f(portfolio.get("cash"))
                            portfolio_before = {
                                "cash": cash_before,
                                "positions": deepcopy(portfolio.get("positions") or {}),
                            }
                            order = pe.execute_decision(
                                exec_dec,
                                portfolio,
                                accounting=None,
                                all_decisions=[exec_dec],
                                strategy_v2_enabled_override=True,
                                strategy_v2_cycle_path=p["v2_cycles"],
                                strategy_v2_journal_path=p["v2_tranches"],
                                apply_paper_tx_costs=True,
                                paper_tx_cost_cfg=_paper_tx_cost_cfg(cfg_par),
                            )
                            if order.get("status") == "EXECUTED":
                                action = "ADD"
                                value = _f(order.get("filled_value_usd"))
                                qty = _f(order.get("fill_shares"))
                                execution_id = _s(order.get("execution_id")) or f"V2EX-{uuid.uuid4().hex[:16].upper()}"
                                eco = order.get("fill_economics") if isinstance(order.get("fill_economics"), dict) else _take_fill_economics(portfolio)
                                cash_after = _f(portfolio.get("cash"))
                                entry_ts = _now()
                                risk_snap = _v2_entry_risk_snapshot(
                                    ticker=ticker,
                                    execution_id=execution_id,
                                    decision_id=decision_id,
                                    entry_ts=entry_ts,
                                    mark=mark,
                                    shares=qty,
                                    filled_value=value,
                                    entry_kind="ADD",
                                    cash_before=cash_before,
                                    portfolio_before=portfolio_before,
                                    v2_cfg=v2_cfg,
                                    bd=bd,
                                    order=order,
                                    cycle_id=cycle_id,
                                    snap=snap if isinstance(snap, dict) else None,
                                )
                                risk_snap = _persist_v2_cycle_risk_snapshot(p, cycle_id, risk_snap)
                                if adep_meta:
                                    risk_snap = dict(risk_snap)
                                    risk_snap["adaptive_deployment"] = adep_meta
                                    if adep_meta.get("formula_id"):
                                        risk_snap["sizing_formula_id"] = adep_meta.get("formula_id")
                                        risk_snap["sizing_formula_version"] = adep_meta.get("formula_version")
                                _append_jsonl(
                                    p["v2_trades"],
                                    {
                                        "ts": entry_ts,
                                        "ticker": ticker,
                                        "action": "ADD",
                                        "shares": qty,
                                        "price": mark,
                                        "decision_id": decision_id,
                                        "arm": "V2",
                                        "execution_id": execution_id,
                                        "cycle_id": cycle_id,
                                        "cash_before": cash_before,
                                        "cash_after": cash_after,
                                        "risk_snapshot": risk_snap,
                                        **(adep_meta or {}),
                                        **_trade_cost_fields(eco, gross=value, side="BUY"),
                                    },
                                )
                                _record_adaptive_exposure_if_challenger(
                                    adep_meta, value, arm="V2", ticker=ticker
                                )
                                _log_capital_event(
                                    "V2_TRANCHE_EXECUTED",
                                    arm="V2",
                                    ticker=ticker,
                                    quantity=qty,
                                    price=mark,
                                    gross=value,
                                    costs=_f(eco.get("total_transaction_cost")),
                                    net=abs(_f(eco.get("net_cash_movement"), value)),
                                    cash_before=cash_before,
                                    cash_after=cash_after,
                                    cycle_id=cycle_id,
                                    decision_id=decision_id,
                                    execution_id=execution_id,
                                    reason=reason,
                                )
                            else:
                                action = "BLOCKED"
                                reason = _s(order.get("status") or order.get("reason"))
                    elif bact == "STOP_ACCUMULATION":
                        v2.apply_stop_accumulation(cycle, store, persist=True, cycle_path=p["v2_cycles"])
                        action = "STOP_ACCUMULATION"
                    else:
                        action = "HOLD"
                    if tranche_gate:
                        reason = reason or tranche_gate
        elif allow_open:
            # OPEN (fresh or validated reentry after profit trailing)
            entry_ok, entry_reason = _entry_price_allowed(snap, mark_status)
            rstore = reentry.load_reentry_store(p.get("v2_reentry"))
            rrow = reentry.get_ticker_reentry(rstore, ticker)
            in_watch = _s(rrow.get("reentry_state")).upper() == "WATCH"
            reentry_gate_code: str | None = None
            reentry_allowed = False
            if not entry_ok:
                action = "BLOCKED"
                reason = (
                    reentry.V2_REENTRY_BLOCKED_STALE_PRICE
                    if entry_reason == "MARK_STALE"
                    else entry_reason
                )
            elif in_watch:
                pce_fields = pol.extract_profit_context_for_ticker(
                    pol.load_profit_context_document(),
                    ticker,
                )
                hr = classify_hard_risk_for_v2(
                    ticker=ticker,
                    avg_price=_f(rrow.get("last_profit_exit_price") or mark),
                    current_price=mark,
                    shares=1.0,
                    mark_freshness=_s(snap.get("mark_freshness") or "FRESH"),
                    mark_age_seconds=_f(snap.get("mark_age_seconds")),
                )
                hard_ok = not fill_time_blocks_add(hr)
                gate = reentry.evaluate_reentry_policy(
                    ticker=ticker,
                    mark_price=float(mark) if mark_ok else 0.0,
                    timestamp=_now(),
                    cash=_f(portfolio.get("cash")),
                    reentry_row=rrow,
                    market_regime=_s(pce_fields.get("market_regime") or "UNKNOWN"),
                    decline_class=_s(pce_fields.get("decline_class") or "UNCLASSIFIED"),
                    relative_strength_state=_s(pce_fields.get("relative_strength_state") or "UNKNOWN"),
                    quarantined=bool(pce_fields.get("quarantined")),
                    company_risk_blocked=bool(pce_fields.get("company_risk_blocked")),
                    hard_risk_allows=hard_ok,
                    momentum_context=_s(pce_fields.get("momentum_context") or "UNKNOWN"),
                    trend_context=_s(pce_fields.get("trend_context") or "UNKNOWN"),
                    signal_id=decision_id + "-REENTRY",
                    cfg=v2_cfg,
                )
                reentry_gate_code = gate.code
                if not gate.ok:
                    action = "HOLD" if gate.code == reentry.V2_REENTRY_WATCH else "BLOCKED"
                    reason = gate.code
                else:
                    reentry_allowed = True
            if entry_ok and _open_position_count(portfolio) >= V2_MAX_POSITIONS and (
                (not in_watch and favorable and snap.get("eligible") is not False)
                or (in_watch and reentry_allowed)
            ):
                action = "BLOCKED"
                reason = "V2_MAX_POSITIONS_REACHED"
            elif entry_ok and (
                (not in_watch and favorable and snap.get("eligible") is not False)
                or (in_watch and reentry_allowed)
            ):
                binp = pol.BuyPolicyInput(
                    ticker=ticker,
                    timestamp=_now(),
                    mark_price=mark,
                    mark_freshness=_s(snap.get("mark_freshness") or "FRESH"),
                    mark_age_seconds=_f(snap.get("mark_age_seconds")),
                    score=score if score is not None else None,
                    pde_action=pde_action,
                    hard_risk_active=False,
                    hard_risk_status="OK",
                    session_valid=True,
                    data_fresh=bool(snap.get("data_fresh", True)),
                    candidate_eligible=True if snap.get("eligible") is None else bool(snap.get("eligible")),
                    held=False,
                    cash=_f(portfolio.get("cash")),
                    decision_id=decision_id + ("-REOPEN" if in_watch else "-OPEN"),
                )
                if in_watch:
                    pol.apply_profit_context_to_input(
                        binp,
                        pol.extract_profit_context_for_ticker(
                            pol.load_profit_context_document(),
                            ticker,
                        ),
                    )
                bd = pol.evaluate_buy_policy(binp, cfg=v2_cfg, enabled=True, store=store)
                if _s(bd.get("action")).upper() == "OPEN_CYCLE":
                    bd, adep_meta, adep_block = _apply_adaptive_deployment_to_v2_buy(
                        bd, binp, ticker=ticker, portfolio=portfolio, v2_cfg=v2_cfg
                    )
                    if adep_block:
                        action = "BLOCKED"
                        reason = adep_block
                        exec_dec = None
                    else:
                        exec_dec = pol.materialize_v2_execution_decision(bd, binp, cfg=v2_cfg)
                    if exec_dec:
                        cash_before = _f(portfolio.get("cash"))
                        portfolio_before = {
                            "cash": cash_before,
                            "positions": deepcopy(portfolio.get("positions") or {}),
                        }
                        cost_cfg = _paper_tx_cost_cfg(cfg_par)
                        order = pe.execute_decision(
                            exec_dec,
                            portfolio,
                            accounting=None,
                            all_decisions=[exec_dec],
                            strategy_v2_enabled_override=True,
                            strategy_v2_cycle_path=p["v2_cycles"],
                            strategy_v2_journal_path=p["v2_tranches"],
                            apply_paper_tx_costs=True,
                            paper_tx_cost_cfg=cost_cfg,
                        )
                        if order.get("status") == "EXECUTED":
                            action = "OPEN"
                            reason = (
                                reentry_gate_code
                                if in_watch and reentry_gate_code
                                else _s(bd.get("reason_code"))
                            )
                            thesis = _s(bd.get("thesis_state"))
                            value = _f(order.get("filled_value_usd"))
                            qty = _f(order.get("fill_shares"))
                            eco = order.get("fill_economics") if isinstance(order.get("fill_economics"), dict) else _take_fill_economics(portfolio)
                            cost = _f(eco.get("total_transaction_cost") or order.get("total_transaction_cost"))
                            execution_id = _s(order.get("execution_id")) or f"V2EX-{uuid.uuid4().hex[:16].upper()}"
                            pos2 = (portfolio.get("positions") or {}).get(ticker)
                            if pos2:
                                pos2["strategy_version"] = "V2"
                            store2 = v2.load_cycle_store(p["v2_cycles"])
                            cyc = v2.find_open_cycle_for_ticker(store2, ticker)
                            cycle_id = (cyc or {}).get("cycle_id")
                            tranche = 1
                            cash_after = _f(portfolio.get("cash"))
                            buy_label = "V2_REBUY_EXECUTED" if in_watch else "V2_BUY_EXECUTED"
                            cost_fields = _trade_cost_fields(eco, gross=value, side="BUY")
                            entry_ts = _now()
                            risk_snap = _v2_entry_risk_snapshot(
                                ticker=ticker,
                                execution_id=execution_id,
                                decision_id=decision_id,
                                entry_ts=entry_ts,
                                mark=mark,
                                shares=qty,
                                filled_value=value,
                                entry_kind="REENTRY" if in_watch else "INITIAL",
                                cash_before=cash_before,
                                portfolio_before=portfolio_before,
                                v2_cfg=v2_cfg,
                                bd=bd,
                                order=order,
                                cycle_id=cycle_id,
                                snap=snap if isinstance(snap, dict) else None,
                                in_reentry=bool(in_watch),
                            )
                            risk_snap = _persist_v2_cycle_risk_snapshot(p, cycle_id, risk_snap)
                            if adep_meta:
                                risk_snap = dict(risk_snap)
                                risk_snap["adaptive_deployment"] = adep_meta
                                if adep_meta.get("formula_id"):
                                    risk_snap["sizing_formula_id"] = adep_meta.get("formula_id")
                                    risk_snap["sizing_formula_version"] = adep_meta.get("formula_version")
                            _append_jsonl(
                                p["v2_trades"],
                                {
                                    "ts": entry_ts,
                                    "ticker": ticker,
                                    "action": "REBUY" if in_watch else "BUY",
                                    "shares": qty,
                                    "price": mark,
                                    "decision_id": decision_id,
                                    "arm": "V2",
                                    "execution_id": execution_id,
                                    "cycle_id": cycle_id,
                                    "cash_before": cash_before,
                                    "cash_after": cash_after,
                                    "risk_snapshot": risk_snap,
                                    **(adep_meta or {}),
                                    **cost_fields,
                                },
                            )
                            _record_adaptive_exposure_if_challenger(
                                adep_meta, value, arm="V2", ticker=ticker
                            )
                            _log_capital_event(
                                buy_label,
                                arm="V2",
                                ticker=ticker,
                                quantity=qty,
                                price=mark,
                                gross=value,
                                costs=cost,
                                net=abs(_f(eco.get("net_cash_movement"), value + cost)),
                                cash_before=cash_before,
                                cash_after=cash_after,
                                cycle_id=cycle_id,
                                decision_id=decision_id,
                                execution_id=execution_id,
                                reason=reason,
                            )
                            if in_watch:
                                reentry.consume_reentry(
                                    rstore,
                                    ticker=ticker,
                                    signal_id=decision_id + "-REENTRY",
                                    new_cycle_id=cycle_id,
                                    persist_path=p.get("v2_reentry"),
                                )
                        else:
                            action = "BLOCKED"
                            reason = _s(order.get("status") or order.get("reason"))
                else:
                    action = "BLOCKED"
                    reason = _s(bd.get("reason_code"))
            elif in_watch and not reentry_allowed:
                pass  # reason already set from gate
            elif not entry_ok:
                pass  # reason already set
            else:
                action = "HOLD"
                reason = "V2_NO_ENTRY_SIGNAL"
        else:
            action = "HOLD"
            reason = "V2_PHASE_SKIP"
    except _PhaseComplete:
        pass
    except Exception as exc:
        _append_jsonl(
            p["v2_errors"],
            {"ts": _now(), "ticker": ticker, "error": str(exc), "trace": traceback.format_exc()[-2000:]},
        )
        return {
            "decision_id": decision_id,
            "arm": "V2",
            "ticker": ticker,
            "action": "ERROR",
            "reason": "V2_ARM_EXCEPTION",
            "error": str(exc),
            "ts": _now(),
        }

    if action in {"OPEN", "ADD", "CLOSE"} and execution_id:
        # Trade row already persisted on fill paths with cost fields when available.
        # Do not append a second cost-poor duplicate for the same execution_id.
        record_execution_learning_feedback(
            arm="V2",
            execution_id=execution_id,
            decision_id=decision_id,
            action=action,
            ticker=ticker,
            price=mark if mark_ok else 0.0,
            shares=qty,
            value=value,
            reason=reason,
            realized_pnl=realized_pnl_fill,
            strategy_variant="V2",
            position_id=str(cycle_id) if cycle_id else f"V2:{ticker}",
            p=p,
        )

    dec = {
        "decision_id": decision_id,
        "arm": "V2",
        "ticker": ticker,
        "action": action,
        "reason": reason,
        "thesis_state": thesis,
        "cycle_id": cycle_id,
        "tranche": tranche,
        "tranche_gate_code": tranche_gate,
        "score": score,
        "quantity": qty,
        "value": value,
        "mark_price": mark if mark_ok else None,
        "mark_status": mark_status,
        "ts": _now(),
        "mutates_portfolio": action in {"OPEN", "ADD", "CLOSE"},
        "executor_called": action in {"OPEN", "ADD", "CLOSE"},
        "execution_id": execution_id,
        "realized_pnl": realized_pnl_fill,
        "phase": phase_n,
        "writes_live": False,
        "writes_broker": False,
    }
    _append_jsonl(p["v2_decisions"], dec)
    _append_jsonl(p["v2_executions"], {**dec, "executed": action in {"OPEN", "ADD", "CLOSE"}})
    return dec


def classify_divergence(v1: dict[str, Any], v2d: dict[str, Any]) -> str:
    a1 = _s(v1.get("action")).upper()
    a2 = _s(v2d.get("action")).upper()
    if a1 == a2 or (a1 == "HOLD" and a2 == "HOLD"):
        if a1 in {"BLOCKED", "ERROR"} and a2 in {"BLOCKED", "ERROR"} and _s(v1.get("reason")) != _s(v2d.get("reason")):
            return "BOTH_BLOCKED_DIFFERENT_REASON"
        return "SAME_ACTION"
    if a1 == "BUY" and a2 == "OPEN":
        return "V1_BUY_V2_OPEN"
    if a1 == "HOLD" and a2 == "ADD":
        return "V1_HOLD_V2_ADD"
    if a1 == "SELL" and a2 == "HOLD":
        return "V1_SELL_V2_HOLD"
    if a1 == "SELL" and a2 == "ADD":
        return "V1_SELL_V2_ADD"
    if a1 == "HOLD" and a2 == "CLOSE":
        return "V1_HOLD_V2_CLOSE"
    if a1 == "BUY" and a2 in {"BLOCKED", "HOLD"}:
        return "V1_BUY_V2_BLOCKED"
    if a1 in {"BLOCKED", "HOLD"} and a2 == "OPEN":
        return "V1_BLOCKED_V2_OPEN"
    if a1 in {"BUY", "SELL"} and a2 in {"OPEN", "ADD", "CLOSE"} and a1 != a2:
        return "EXECUTION_DIVERGENCE"
    return "EXECUTION_DIVERGENCE"


def _open_position_count(portfolio: dict[str, Any]) -> int:
    return len(
        [x for x in (portfolio.get("positions") or {}).values() if _f((x or {}).get("shares")) > 0]
    )


_PAPER_DECISIONS_PATH = Path("runtime_outputs/paper_decisions/paper_decisions.jsonl")


def _load_today_pde_signals(day: str | None = None) -> dict[str, dict[str, Any]]:
    """
    V3's decide_v3() scores on growth_score/capital_efficiency/
    horizon_alignment_score/confidence — but the market snapshot V1/V2/V3
    all consume (default_mark_provider, sourced from signals.csv/
    live_signals.csv) only carries Price/Score/Signal. Those richer fields
    are computed by the CANONICAL PDE pass (tae.py full-paper-cycle) into
    runtime_outputs/paper_decisions/paper_decisions.jsonl — which the hourly
    script already runs before parallel-paper-run-once, so same-day data is
    reliably present by the time this is called.

    Found in the Phase 5 soak: without this, every ticker's snap had no
    horizon_alignment_score (defaulted near 0), and because that feature has
    by far the largest learned weight, every BUY prediction was suppressed
    below the 0.5 floor — V3 never traded in its first two days. This wires
    real same-day PDE signal in; tae_strategy_v3_learning_policy.py also got
    a neutral (not 0.0) fallback default as a safety net for tickers this
    lookup still misses.
    """
    day = day or _now()[:10]
    out: dict[str, dict[str, Any]] = {}
    if not _PAPER_DECISIONS_PATH.is_file():
        return out
    try:
        with _PAPER_DECISIONS_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = _s(rec.get("timestamp") or rec.get("ts"))
                if not ts.startswith(day):
                    continue
                t = _s(rec.get("ticker")).upper()
                if not t:
                    continue
                out[t] = {
                    "confidence": rec.get("confidence"),
                    "horizon_alignment_score": rec.get("horizon_alignment_score"),
                    "horizon_conflict_flag": rec.get("horizon_conflict_flag"),
                }
    except OSError:
        return {}
    return out


def _enrich_snap_for_v3(
    snap: dict[str, Any], ticker: str, pde_signals: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """
    Merge same-day canonical PDE signal (if any) into a copy of `snap`.
    Always stamps `_v3_pde_enriched` (True/False) on the result so callers
    can tell, per ticker per decision, whether the scored features came from
    real same-day data or the neutral fallback in
    tae_strategy_v3_learning_policy._extract_features. This is the exact
    signal that was missing when horizon_alignment_score silently defaulted
    to 0 for two days — surfaced now so a future gap of the same shape shows
    up in the decision journal instead of only in a HOLD that looks
    ordinary. See _run_v3_arm's decision record and tae_daily_check.sh's
    "V3 feature coverage" section.
    """
    sig = pde_signals.get(_s(ticker).upper())
    merged = dict(snap)
    merged["_v3_pde_enriched"] = bool(sig)
    if sig:
        merged.update({k: v for k, v in sig.items() if v is not None})
    return merged


def _run_v3_arm(
    *,
    portfolio: dict[str, Any],
    ticker: str,
    snap: dict[str, Any],
    cfg: dict[str, Any],
    p: dict[str, Any],
    decision_id: str,
    scorer: "v3pol.LearningScorer",
    candidate_pool_p_profit: list[float] | None,
    phase: str = PHASE_ALL,
    blocked_rebuy: bool = False,
    pde_signals: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    V3 ("V_learning") — isolated parallel PAPER arm (Phase 3). No fixed
    entry/exit thresholds: BUY/HOLD/SELL and size come entirely from
    tae_strategy_v3_learning_policy.decide_v3 (logistic scorer trained on
    realized longitudinal_memory outcomes + fractional-Kelly/vol-target
    sizing). Guardrails (MAX_POSITIONS, cash reserve, MIN/MAX_TRADE_USD) are
    the same constants V1/V2 already operate under — see
    tae_strategy_v3_learning_policy.py module docstring.

    Execution mechanics (buy/sell fills, transaction costs, error rollback)
    are intentionally copy-pattern from _run_v1_arm rather than a shared
    helper — V1/V2 don't share one either, and introducing one now would
    touch their hot path for no benefit to this change.

    Known Phase-3 simplification: `regime.trend` / `regime.vol_tercile`
    default to "UNKNOWN" (see below) — this runtime has no per-ticker
    historical-closes feed today (`snap` is a single current-mark snapshot,
    not a price series; V1/V2 don't retain one either). This matches
    training-data reality: market_regime was constant "BULL" and
    volatility_regime constant "UNKNOWN" across all historical decisions
    (the scorer was never trained on real regime variation), so this is not
    a regression versus what the model can actually use today. Follow-up:
    wire a real closes feed once one exists in this runtime, then this
    function needs no change — only the `regime =` line below moves.
    """
    _assert_paper_isolation(cfg)
    phase_n = _s(phase).lower() or PHASE_ALL
    snap = _enrich_snap_for_v3(snap, ticker, pde_signals or {})
    mark_ok, mark_status, mark = _mark_is_usable(snap)
    pos = (portfolio.get("positions") or {}).get(ticker)
    has_pos = bool(pos and _f(pos.get("shares")) > 0)
    ts_now = _now()

    regime = v3pol.RegimeGrid(trend="UNKNOWN", vol_tercile="UNKNOWN", realized_vol_annualized=None)

    def _record(
        action: str,
        reason: str,
        *,
        qty: float = 0.0,
        value: float = 0.0,
        p_profit: float | None = None,
        executed: bool = False,
        execution_id: str | None = None,
        realized_pnl_fill: float | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dec = {
            "decision_id": decision_id,
            "arm": "V3",
            "ticker": ticker,
            "action": action,
            "reason": reason,
            "quantity": qty,
            "value": value,
            "p_profit": p_profit,
            "mark_price": mark if mark_ok else None,
            "mark_status": mark_status,
            "ts": ts_now,
            "phase": phase_n,
            "mutates_portfolio": executed,
            "mutates_canonical_paper": False,
            "executor_called": executed,
            "execution_id": execution_id,
            "realized_pnl": realized_pnl_fill,
            "pde_enriched": snap.get("_v3_pde_enriched"),
            "diagnostics": diagnostics or {},
        }
        _append_jsonl(p["arms"]["v3"]["decisions"], dec)
        return dec

    # Two-pass capital cycle, same convention as V1/V2 (_arm_pass calls this
    # once with phase="manage" — exits only — then once with phase="entry").
    if phase_n == PHASE_MANAGE and not has_pos:
        return _record("HOLD", "V3_MANAGE_FLAT")
    if phase_n == PHASE_ENTRY and has_pos:
        return _record("HOLD", "V3_ENTRY_ALREADY_OPEN", qty=_f(pos.get("shares")))
    if not mark_ok:
        return _record("HOLD", mark_status, qty=_f(pos.get("shares")) if has_pos else 0.0)

    if has_pos and phase_n in {PHASE_MANAGE, PHASE_ALL}:
        decision = v3pol.decide_v3(
            ticker=ticker,
            snap=snap,
            scorer=scorer,
            regime=regime,
            has_position=True,
            cash_available=_f(portfolio.get("cash")),
            open_positions=_open_position_count(portfolio),
        )
        if decision.action != "SELL":
            return _record(
                "HOLD", decision.reason, qty=_f(pos.get("shares")),
                p_profit=decision.p_profit, diagnostics=decision.diagnostics,
            )

        shares = _f(pos.get("shares"))
        cash_before = _f(portfolio.get("cash"))
        pos_snapshot = dict(pos)
        cost_cfg = _paper_tx_cost_cfg(cfg)
        realized, gross, after = pe._sell_shares(
            portfolio, ticker, shares, mark,
            apply_paper_tx_costs=True, paper_tx_cost_cfg=cost_cfg,
        )
        eco = _take_fill_economics(portfolio)
        cash_after = _f(portfolio.get("cash"))
        net_credit = _f(eco.get("net_proceeds"), cash_after - cash_before)
        credited = abs((cash_after - cash_before) - net_credit) <= 1e-3
        fully_closed = after is None and ticker not in (portfolio.get("positions") or {})
        if not (credited and fully_closed):
            # Fail closed — restore pre-sell cash/position, same as V1.
            portfolio["cash"] = cash_before
            portfolio.setdefault("positions", {})[ticker] = pos_snapshot
            portfolio["realized_pnl"] = _f(portfolio.get("realized_pnl")) - _f(realized)
            _append_jsonl(
                p["arms"]["v3"]["errors"],
                {
                    "ts": ts_now, "ticker": ticker, "error": "V3_SELL_SETTLEMENT_FAILED",
                    "cash_before": cash_before, "cash_after": cash_after, "gross": gross,
                },
            )
            return _record("ERROR", "V3_SELL_SETTLEMENT_FAILED", qty=shares)

        execution_id = f"V3EX-{uuid.uuid4().hex[:16].upper()}"
        realized_pnl_fill = round(float(realized), 6)
        cost_fields = _trade_cost_fields(eco, gross=gross, side="SELL")
        _append_jsonl(
            p["arms"]["v3"]["trades"],
            {
                "ts": ts_now, "ticker": ticker, "action": "SELL", "shares": shares,
                "price": mark, "decision_id": decision_id, "arm": "V3",
                "execution_id": execution_id, "realized_pnl": realized_pnl_fill,
                "gross": gross, "net": net_credit, "cash_before": cash_before,
                "cash_after": cash_after, **cost_fields,
            },
        )
        record_execution_learning_feedback(
            arm="V3", execution_id=execution_id, decision_id=decision_id,
            action="SELL", ticker=ticker, price=mark, shares=shares, value=net_credit,
            reason=decision.reason, realized_pnl=realized_pnl_fill,
            strategy_variant="V3", p=p,
        )
        return _record(
            "SELL", decision.reason, qty=shares, value=net_credit,
            p_profit=decision.p_profit, executed=True, execution_id=execution_id,
            realized_pnl_fill=realized_pnl_fill, diagnostics=decision.diagnostics,
        )

    if (not has_pos) and phase_n in {PHASE_ENTRY, PHASE_ALL}:
        if blocked_rebuy:
            # Same-run churn guard: this ticker was SOLD earlier in this
            # exact cycle (manage phase) — don't let the entry phase reopen
            # it a moment later. Matches the existing V1/V2 precedent
            # ("Block same-run BUY after SELL on same ticker", 93d8f23).
            return _record("HOLD", "V3_BLOCKED_SAME_RUN_REBUY_AFTER_SELL")
        decision = v3pol.decide_v3(
            ticker=ticker,
            snap=snap,
            scorer=scorer,
            regime=regime,
            has_position=False,
            cash_available=_f(portfolio.get("cash")),
            open_positions=_open_position_count(portfolio),
            candidate_pool_p_profit=candidate_pool_p_profit,
        )
        if decision.action != "BUY":
            return _record(
                "HOLD", decision.reason, p_profit=decision.p_profit,
                diagnostics=decision.diagnostics,
            )

        notional = decision.quantity_usd
        cash_before = _f(portfolio.get("cash"))
        cost_cfg = _paper_tx_cost_cfg(cfg)
        shares, after = pe._buy_shares(
            portfolio, ticker, notional, mark,
            apply_paper_tx_costs=True, paper_tx_cost_cfg=cost_cfg,
        )
        if shares <= 0 or not after:
            return _record(
                "HOLD", "V3_BUY_FILL_REJECTED", p_profit=decision.p_profit,
                diagnostics=decision.diagnostics,
            )

        after["strategy_version"] = "V3"
        after["current_price"] = mark
        after["last_valid_mark"] = mark
        after["mark_status"] = "FRESH"
        after["mark_timestamp"] = ts_now
        eco = _take_fill_economics(portfolio)
        cash_after = _f(portfolio.get("cash"))
        execution_id = f"V3EX-{uuid.uuid4().hex[:16].upper()}"
        value = shares * mark
        cost_fields = _trade_cost_fields(eco, gross=value, side="BUY")
        _append_jsonl(
            p["arms"]["v3"]["trades"],
            {
                "ts": ts_now, "ticker": ticker, "action": "BUY", "shares": shares,
                "price": mark, "decision_id": decision_id, "arm": "V3",
                "execution_id": execution_id, "gross": value, "cash_before": cash_before,
                "cash_after": cash_after, **cost_fields,
            },
        )
        record_execution_learning_feedback(
            arm="V3", execution_id=execution_id, decision_id=decision_id,
            action="BUY", ticker=ticker, price=mark, shares=shares, value=value,
            reason=decision.reason, strategy_variant="V3", p=p,
        )
        return _record(
            "BUY", decision.reason, qty=shares, value=value,
            p_profit=decision.p_profit, executed=True, execution_id=execution_id,
            diagnostics=decision.diagnostics,
        )

    return _record("HOLD", "V3_NO_ACTION")


def run_cycle(
    *,
    cfg: dict[str, Any] | None = None,
    mark_provider: MarkProvider | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    """
    One deterministic parallel cycle.

    Order:
      1 session/config validation
      2 market snapshot (frozen)
      3 V1 decisions+exec (isolated)
      4 V2 decisions+exec (isolated)
      5 accounting both
      6 divergence events
      7 health
    """
    cfg = cfg or load_parallel_paper_config()
    p = paths(cfg)
    bootstrap(cfg)
    ts = _now()
    result: dict[str, Any] = {
        "schema": "tae.parallel_paper.cycle.v1",
        "ts": ts,
        "ok": True,
        "v1_ok": True,
        "v2_ok": True,
        "v3_ok": True,
        "errors": [],
        "divergences": [],
        "n_arm_topology": True,
        "enabled_arm_ids": list(cfg.get("enabled_arm_ids") or []),
        "configured_arm_ids": list(cfg.get("configured_arm_ids") or []),
        "processing_order": [
            "1_session_validation",
            "2_market_data_snapshot",
            "3_manage_protective_sell_settle",
            "4_entry_buy_rebuy_after_capital_release",
            "5_v1_accounting",
            "6_v2_accounting",
            "7_divergence_events",
            "8_health_snapshot",
        ],
    }

    if not cfg.get("PARALLEL_PAPER_ENABLED"):
        result["ok"] = False
        result["errors"].append("PARALLEL_PAPER_DISABLED")
        return result

    v1 = load_v1_portfolio(cfg)
    v2p = load_portfolio(p["v2_portfolio"], starting=float(cfg["V2_STARTING_CAPITAL"]), arm="V2")
    v1_before_cash = _f(v1.get("cash"))
    v2_before_cash = _f(v2p.get("cash"))
    v1_mirror = str(cfg.get("V1_MODE") or "").upper() == "CANONICAL_PAPER_MIRROR"
    canonical_hash_before = None
    if v1_mirror:
        import hashlib

        canonical_hash_before = hashlib.sha256(
            Path(str(cfg.get("CANONICAL_PAPER_PORTFOLIO") or CANONICAL_PAPER_DEFAULT)).read_bytes()
        ).hexdigest()

    provider = mark_provider or default_mark_provider
    base_tickers = tickers or _watchlist(cfg, {}, v1, v2p)
    if not base_tickers:
        # Seed from signals if empty
        marks0 = provider([])
        base_tickers = sorted(marks0.keys())[:30]
    marks = provider(base_tickers)
    # Freeze snapshot
    snap_id = snapshot_id(marks, ts)
    snap_path = p["snapshots"]
    snap_path.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(snap_path / f"{snap_id}.json", {"snapshot_id": snap_id, "ts": ts, "marks": marks})
    result["snapshot_id"] = snap_id
    # Experimental arms consume the same frozen marks and are strictly fail-isolated.
    try:
        from tae_self_improve_experimental import run_experimental_arms_on_snapshot

        result["experimental_arms"] = run_experimental_arms_on_snapshot(
            snap_id, ts, marks, cfg
        )
    except Exception as exc:
        result["experimental_arms"] = {
            "ok": False,
            "status": "FAIL_ISOLATED",
            "error": str(exc),
        }

    tickers_run = _watchlist(cfg, marks, v1, v2p)
    v1_decisions: list[dict[str, Any]] = []
    v2_decisions: list[dict[str, Any]] = []
    v3_decisions: list[dict[str, Any]] = []
    v1_by_ticker: dict[str, dict[str, Any]] = {}
    v2_by_ticker: dict[str, dict[str, Any]] = {}
    v3_by_ticker: dict[str, dict[str, Any]] = {}

    # Deep copies so failures cannot cross-contaminate mid-flight
    v1_work = deepcopy(v1)
    v2_work = deepcopy(v2p)

    # V3 ("V_learning") — additive third arm (Phase 3). Gated on the generic
    # arms[]/enabled_arm_ids topology (not a V3_PARALLEL_ENABLED legacy flag —
    # v1/v2 predate the arms[] mechanism and keep their own flags for
    # backward compat, v3 doesn't need to). A scorer-fit failure disables v3
    # for this cycle only (fail-isolated) — never touches v1_work/v2_work.
    v3_enabled = "v3" in (cfg.get("enabled_arm_ids") or [])
    v3_scorer: "v3pol.LearningScorer | None" = None
    v3_before_cash = 0.0
    v3_work: dict[str, Any] = {}
    v3_pde_signals: dict[str, dict[str, Any]] = {}
    if v3_enabled:
        try:
            v3_starting_capital = next(
                (
                    _f(a.get("starting_capital"), 30000.0)
                    for a in (cfg.get("arms") or [])
                    if a.get("arm_id") == "v3"
                ),
                30000.0,
            )
            v3p = load_portfolio(p["arms"]["v3"]["portfolio"], starting=v3_starting_capital, arm="V3")
            v3_before_cash = _f(v3p.get("cash"))
            v3_work = deepcopy(v3p)
            v3_scorer = v3pol.LearningScorer().fit()
            v3_pde_signals = _load_today_pde_signals()
        except Exception as exc:
            v3_enabled = False
            result["v3_ok"] = False
            result["errors"].append(f"V3:SETUP:{exc}")
            _append_jsonl(p["arms"]["v3"]["errors"], {"ts": ts, "error": f"SETUP:{exc}"})

    v3_candidate_pool: list[float] = []
    v3_sold_this_cycle: set[str] = set()

    def _arm_pass(phase: str) -> None:
        for t in tickers_run:
            snap = marks.get(t)
            if not snap:
                continue
            did = f"PP-{snap_id}-{t}"
            d1: dict[str, Any]
            d2: dict[str, Any]
            if cfg.get("V1_PARALLEL_ENABLED"):
                try:
                    d1 = _run_v1_arm(
                        portfolio=v1_work,
                        ticker=t,
                        snap=snap,
                        cfg=cfg,
                        p=p,
                        decision_id=f"{did}-V1-{phase}",
                        phase=phase,
                    )
                except Exception as exc:
                    result["v1_ok"] = False
                    result["errors"].append(f"V1:{t}:{phase}:{exc}")
                    _append_jsonl(p["v1_errors"], {"ts": ts, "ticker": t, "phase": phase, "error": str(exc)})
                    if not cfg.get("FAIL_ISOLATION_ENABLED"):
                        raise
                    d1 = {"action": "ERROR", "reason": str(exc), "ticker": t, "arm": "V1", "phase": phase}
            else:
                d1 = {"action": "SKIP", "reason": "V1_DISABLED", "ticker": t, "arm": "V1", "phase": phase}

            if cfg.get("V2_PARALLEL_ENABLED"):
                try:
                    d2 = _run_v2_arm(
                        portfolio=v2_work,
                        ticker=t,
                        snap=snap,
                        cfg_par=cfg,
                        p=p,
                        decision_id=f"{did}-V2-{phase}",
                        phase=phase,
                    )
                except Exception as exc:
                    result["v2_ok"] = False
                    result["errors"].append(f"V2:{t}:{phase}:{exc}")
                    _append_jsonl(p["v2_errors"], {"ts": ts, "ticker": t, "phase": phase, "error": str(exc)})
                    if not cfg.get("FAIL_ISOLATION_ENABLED"):
                        raise
                    d2 = {"action": "ERROR", "reason": str(exc), "ticker": t, "arm": "V2", "phase": phase}
            else:
                d2 = {"action": "SKIP", "reason": "V2_DISABLED", "ticker": t, "arm": "V2", "phase": phase}

            d3: dict[str, Any]
            if v3_enabled and v3_scorer is not None:
                try:
                    d3 = _run_v3_arm(
                        portfolio=v3_work,
                        ticker=t,
                        snap=snap,
                        cfg=cfg,
                        p=p,
                        decision_id=f"{did}-V3-{phase}",
                        scorer=v3_scorer,
                        candidate_pool_p_profit=v3_candidate_pool if phase == PHASE_ENTRY else None,
                        phase=phase,
                        blocked_rebuy=t in v3_sold_this_cycle,
                        pde_signals=v3_pde_signals,
                    )
                except Exception as exc:
                    result["v3_ok"] = False
                    result["errors"].append(f"V3:{t}:{phase}:{exc}")
                    _append_jsonl(
                        p["arms"]["v3"]["errors"], {"ts": ts, "ticker": t, "phase": phase, "error": str(exc)}
                    )
                    if not cfg.get("FAIL_ISOLATION_ENABLED"):
                        raise
                    d3 = {"action": "ERROR", "reason": str(exc), "ticker": t, "arm": "V3", "phase": phase}
            else:
                d3 = {"action": "SKIP", "reason": "V3_DISABLED", "ticker": t, "arm": "V3", "phase": phase}

            # Prefer capital-mutating decisions when merging manage+entry passes.
            prev1 = v1_by_ticker.get(t)
            if prev1 is None or _s(d1.get("action")).upper() in {"BUY", "SELL", "ERROR"}:
                v1_by_ticker[t] = d1
            prev2 = v2_by_ticker.get(t)
            if prev2 is None or _s(d2.get("action")).upper() in {
                "OPEN",
                "ADD",
                "CLOSE",
                "ERROR",
                "BLOCKED",
            }:
                v2_by_ticker[t] = d2
            prev3 = v3_by_ticker.get(t)
            if prev3 is None or _s(d3.get("action")).upper() in {"BUY", "SELL", "ERROR"}:
                v3_by_ticker[t] = d3

    # Capital cycle order: settle all SELL/CLOSE first, then BUY/REBUY/ADD.
    _assert_paper_isolation(cfg)
    _arm_pass(PHASE_MANAGE)
    v3_sold_this_cycle = {
        t for t, d in v3_by_ticker.items() if _s(d.get("action")).upper() == "SELL"
    }

    if v3_enabled and v3_scorer is not None:
        # Pre-pass: score today's V3 entry candidates (no open position) so
        # decide_v3 can calibrate its BUY threshold from *this cycle's* own
        # distribution instead of a fixed constant (research note §5). Must
        # run after the manage phase (which may have closed positions) and
        # before the entry phase (which consumes this pool).
        regime = v3pol.RegimeGrid(trend="UNKNOWN", vol_tercile="UNKNOWN", realized_vol_annualized=None)
        for t in tickers_run:
            snap = marks.get(t)
            if not snap:
                continue
            pos = (v3_work.get("positions") or {}).get(t)
            if pos and _f(pos.get("shares")) > 0:
                continue
            enriched_snap = _enrich_snap_for_v3(snap, t, v3_pde_signals)
            pseudo = v3pol.build_pseudo_record(enriched_snap, regime)
            p_profit, _diag = v3_scorer.predict_proba("BUY_PAPER", pseudo)
            v3_candidate_pool.append(p_profit)

    _arm_pass(PHASE_ENTRY)

    for t in tickers_run:
        d1 = v1_by_ticker.get(t) or {"action": "HOLD", "ticker": t, "arm": "V1"}
        d2 = v2_by_ticker.get(t) or {"action": "HOLD", "ticker": t, "arm": "V2"}
        d3 = v3_by_ticker.get(t) or {"action": "HOLD", "ticker": t, "arm": "V3"}
        v1_decisions.append(d1)
        v2_decisions.append(d2)
        v3_decisions.append(d3)
        # V1-vs-V2 divergence journal is unchanged/not extended to V3 in
        # Phase 3 — that schema (V1_action/V2_action columns) is specific to
        # the 2-arm comparison already relied on by existing reports; a
        # 3-way divergence view is a separate follow-up, not silently
        # folded in here.
        klass = classify_divergence(d1, d2)
        div = {
            "timestamp": ts,
            "ticker": t,
            "market_snapshot_id": snap_id,
            "V1_action": d1.get("action"),
            "V1_reason": d1.get("reason"),
            "V1_score": d1.get("score"),
            "V1_quantity": d1.get("quantity"),
            "V1_value": d1.get("value"),
            "V2_action": d2.get("action"),
            "V2_reason": d2.get("reason"),
            "V2_thesis_state": d2.get("thesis_state"),
            "V2_cycle_id": d2.get("cycle_id"),
            "V2_tranche": d2.get("tranche"),
            "V2_quantity": d2.get("quantity"),
            "V2_value": d2.get("value"),
            "action_divergence": klass,
            "capital_divergence": abs(_f(d1.get("value")) - _f(d2.get("value"))) > 1e-6,
            "risk_divergence": _s(d1.get("reason")) != _s(d2.get("reason")),
            "execution_divergence": klass == "EXECUTION_DIVERGENCE",
        }
        _append_jsonl(p["divergences"], div)
        result["divergences"].append(div)

    # Persist arms separately — isolated V1 writes only v1/portfolio.json; never canonical/LIVE
    mark_px: dict[str, float] = {}
    mark_meta: dict[str, dict[str, Any]] = {}
    for t, m in marks.items():
        ok, status, px = _mark_is_usable(m)
        mark_meta[t] = {
            "mark_freshness": status if not ok else _s(m.get("mark_freshness") or "FRESH"),
            "mark_timestamp": m.get("mark_timestamp") or ts,
            "data_fresh": bool(m.get("data_fresh", ok)),
        }
        if ok:
            mark_px[t] = px
    if v1_mirror:
        # Refresh economics from canonical (ignore in-memory observe marks for ledger identity)
        v1_work = load_v1_portfolio(cfg)
        av1 = _f(v1_work.get("account_value") or v1_work.get("total_value"))
        inv1 = _f(v1_work.get("open_positions_value"))
        assert_canonical_paper_untouched(before_hash=canonical_hash_before)
    else:
        av1, inv1 = portfolio_mtm(v1_work, mark_px, mark_meta=mark_meta)
        save_portfolio(p["v1_portfolio"], v1_work)
    av2, inv2 = portfolio_mtm(v2_work, mark_px, mark_meta=mark_meta)
    save_portfolio(p["v2_portfolio"], v2_work)
    av3 = inv3 = 0.0
    if v3_enabled:
        av3, inv3 = portfolio_mtm(v3_work, mark_px, mark_meta=mark_meta)
        save_portfolio(p["arms"]["v3"]["portfolio"], v3_work)

    acct1 = {
        "arm": "V1",
        "ts": ts,
        "V1_MODE": "CANONICAL_PAPER_MIRROR" if v1_mirror else "ISOLATED_PARALLEL_PAPER",
        "source": "CANONICAL_PAPER" if v1_mirror else "ISOLATED",
        "cash": _f(v1_work.get("cash")),
        "invested": inv1,
        "account_value": av1,
        "realized_pnl": _f(v1_work.get("realized_pnl")),
        "unrealized_pnl": _f(v1_work.get("unrealized_pnl")),
        "total_pnl": _f(v1_work.get("total_pnl")),
        "starting_value": _f(v1_work.get("starting_value") or v1_work.get("starting_capital")),
        "inception_date": v1_work.get("inception_date") or v1_work.get("created_at"),
        "reconciliation_pass": accounting_pass(v1_work),
        "cash_delta_vs_cycle_start": _f(v1_work.get("cash")) - v1_before_cash,
        "writes_canonical_paper": False,
        "transaction_cost_metrics": accumulate_tx_cost_metrics(p["v1_trades"]),
    }
    acct2 = {
        "arm": "V2",
        "ts": ts,
        "cash": _f(v2_work.get("cash")),
        "invested": inv2,
        "account_value": av2,
        "realized_pnl": _f(v2_work.get("realized_pnl")),
        "unrealized_pnl": _f(v2_work.get("unrealized_pnl")),
        "reconciliation_pass": accounting_pass(v2_work),
        "cash_delta_vs_cycle_start": _f(v2_work.get("cash")) - v2_before_cash,
        "transaction_cost_metrics": accumulate_tx_cost_metrics(p["v2_trades"]),
    }
    acct3: dict[str, Any] | None = None
    if v3_enabled:
        acct3 = {
            "arm": "V3",
            "ts": ts,
            "cash": _f(v3_work.get("cash")),
            "invested": inv3,
            "account_value": av3,
            "realized_pnl": _f(v3_work.get("realized_pnl")),
            "unrealized_pnl": _f(v3_work.get("unrealized_pnl")),
            "reconciliation_pass": accounting_pass(v3_work),
            "cash_delta_vs_cycle_start": _f(v3_work.get("cash")) - v3_before_cash,
            "transaction_cost_metrics": accumulate_tx_cost_metrics(p["arms"]["v3"]["trades"]),
        }
        _atomic_write_json(p["arms"]["v3"]["accounting"], acct3)
        _atomic_write_json(p["arms"]["v3"]["account"], acct3)

    _atomic_write_json(p["v1_accounting"], acct1)
    _atomic_write_json(p["v2_accounting"], acct2)
    _atomic_write_json(p["v1_account"], acct1)
    _atomic_write_json(p["v2_account"], acct2)

    # Observability-only economic attribution (no decision / fill mutation).
    try:
        from tae_paper_economic_attribution import refresh_parallel_attribution

        attr = refresh_parallel_attribution(p, cfg=cfg)
        summary = attr.get("summary") or {}
        acct1["economic_attribution"] = summary.get("v1")
        acct2["economic_attribution"] = summary.get("v2")
        _atomic_write_json(p["v1_accounting"], acct1)
        _atomic_write_json(p["v2_accounting"], acct2)
        _atomic_write_json(p["v1_account"], acct1)
        _atomic_write_json(p["v2_account"], acct2)
        result["economic_attribution"] = {
            "schema_version": summary.get("schema_version"),
            "authority": "OBSERVABILITY_ONLY",
            "v1": summary.get("v1"),
            "v2": summary.get("v2"),
            "comparison": summary.get("comparison"),
            "store_path": attr.get("store_path"),
            "summary_path": attr.get("summary_path"),
            "rebuild_stats": attr.get("stats"),
        }
    except Exception as exc:
        result["economic_attribution"] = {"ok": False, "error": str(exc)}

    # Isolation proof in result
    result["isolation"] = {
        "v1_cash_unchanged_by_v2": True,  # separate objects
        "v1_cash": _f(v1_work.get("cash")),
        "v2_cash": _f(v2_work.get("cash")),
        "v3_cash": _f(v3_work.get("cash")) if v3_enabled else None,
        "v1_cash_before": v1_before_cash,
        "v2_cash_before": v2_before_cash,
        "v3_cash_before": v3_before_cash if v3_enabled else None,
        "shared_snapshot_id": snap_id,
    }
    result["accounting_v1"] = acct1
    result["accounting_v2"] = acct2
    result["accounting_v3"] = acct3
    result["v1_decisions"] = v1_decisions
    result["v2_decisions"] = v2_decisions
    result["v3_decisions"] = v3_decisions
    # Profit-first tranche gate tallies (ADD path evaluations only).
    gate_counts: dict[str, int] = {
        pol.V2_TRANCHE_ALLOWED: 0,
        pol.V2_TRANCHE_BLOCKED_MARKET: 0,
        pol.V2_TRANCHE_BLOCKED_RELATIVE_STRENGTH: 0,
        pol.V2_TRANCHE_BLOCKED_COMPANY_RISK: 0,
        pol.V2_TRANCHE_BLOCKED_FALLING_KNIFE: 0,
        pol.V2_TRANCHE_BLOCKED_CAPITAL: 0,
    }
    evaluated = 0
    for d in v2_decisions:
        code = _s(d.get("tranche_gate_code") or d.get("reason"))
        if code in gate_counts:
            evaluated += 1
            gate_counts[code] += 1
        elif _s(d.get("action")).upper() == "ADD":
            evaluated += 1
            gate_counts[pol.V2_TRANCHE_ALLOWED] += 1
    result["v2_tranche_gate"] = {
        "evaluated": evaluated,
        "allowed": gate_counts[pol.V2_TRANCHE_ALLOWED],
        "blocked_by_reason": {k: v for k, v in gate_counts.items() if k != pol.V2_TRANCHE_ALLOWED},
        "counts": gate_counts,
    }
    result["health"] = health_snapshot(cfg)
    result["ok"] = bool(
        result["v1_ok"] or result["v2_ok"] or result["v3_ok"]
    )  # any arm healthy is ok under isolation
    return result
