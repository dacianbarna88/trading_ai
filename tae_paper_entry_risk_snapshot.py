#!/usr/bin/env python3
"""
PAPER entry risk snapshot — schema + builders (observability EXTEND).

PAPER_ONLY | NO_BROKER | NO_LIVE | DOES_NOT_CHANGE_SIZING_OR_STRATEGY

Freezes identity, executed sizing, and the protective stop policy already used
by hard-risk / V2 stop config at the moment of a PAPER entry fill.
Does not invent ATR, volatility, confidence, or exposures when unavailable.
Does not alter quantity, notional, BUY/SELL thresholds, or LIVE.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "tae.paper.entry_risk_snapshot.v1"
SIZING_FORMULA_VERSION = "paper_sizing_formula_id.v1"

# Stable IDs for path-local formulas already executed (auditability only).
FORMULA_V1_DEPLOYABLE_25PCT = "PAPER_V1_DEPLOYABLE_25PCT_CAP2500_FLOOR250"
FORMULA_V2_INITIAL_BUDGET_TRANCHE = "PAPER_V2_INITIAL_COMPANY_BUDGET_TRANCHE20"
FORMULA_V2_ADD_BUDGET_TRANCHE = "PAPER_V2_ADD_COMPANY_BUDGET_TRANCHE20"
FORMULA_V2_REENTRY_BUDGET_TRANCHE = "PAPER_V2_REENTRY_COMPANY_BUDGET_TRANCHE20"

SOURCE_V1 = "tae_parallel_paper_runtime._run_v1_arm"
SOURCE_V2_BUY_POLICY = (
    "tae_strategy_v2_buy_policy.resolve_company_budget+"
    "proposed_tranche_value_usd→materialize_v2_execution_decision"
)

STATUS_COMPLETE = "COMPLETE"
STATUS_PARTIAL = "PARTIAL"
STATUS_MINIMUM_ONLY = "MINIMUM_ONLY"
STATUS_UNAVAILABLE = "UNAVAILABLE"

MIN_FIELDS = (
    "schema_version",
    "ticker",
    "strategy_arm",
    "execution_id",
    "entry_timestamp",
    "entry_price",
    "executed_quantity",
    "executed_notional",
    "sizing_formula_id",
    "snapshot_created_at",
    "snapshot_status",
    "missing_fields",
)

OPTIONAL_FIELDS = (
    "cycle_id",
    "family_id",
    "parent_cycle_id",
    "decision_id",
    "tranche_id",
    "reentry_sequence",
    "entry_type",
    "recommended_quantity",
    "authorized_quantity",
    "sizing_formula_version",
    "sizing_source_path",
    "stop_price",
    "stop_distance",
    "stop_distance_pct",
    "initial_risk_per_share",
    "initial_risk_amount",
    "initial_risk_pct_of_equity",
    "maximum_accepted_loss",
    "cash_available",
    "account_equity",
    "portfolio_value",
    "position_budget",
    "cash_reserve",
    "maximum_position_notional",
    "maximum_positions",
    "current_open_positions",
    "atr",
    "atr_pct",
    "volatility",
    "confidence",
    "signal_score",
    "market_regime",
    "account_drawdown",
    "total_exposure",
    "ticker_exposure",
    "sector_exposure",
    "region_exposure",
    "risk_multiplier",
    "confidence_multiplier",
    "volatility_multiplier",
    "regime_multiplier",
    "drawdown_multiplier",
    "snapshot_source",
    "data_quality_flags",
    "stop_policy_source",
    "stop_policy_version",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _s(v: Any) -> str:
    return str(v or "").strip()


def _f_or_none(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def portfolio_mark_equity(portfolio: dict[str, Any] | None) -> float | None:
    """Cash + Σ shares×mark (avg fallback). None if cash missing."""
    if not isinstance(portfolio, dict):
        return None
    cash = _f_or_none(portfolio.get("cash"))
    if cash is None:
        return None
    total = cash
    for pos in (portfolio.get("positions") or {}).values():
        if not isinstance(pos, dict):
            continue
        shares = _f_or_none(pos.get("shares")) or 0.0
        if shares <= 0:
            continue
        px = _f_or_none(pos.get("current_price"))
        if px is None or px <= 0:
            px = _f_or_none(pos.get("avg_price"))
        if px is None or px <= 0:
            continue
        total += shares * px
    return round(total, 6)


def open_position_count(portfolio: dict[str, Any] | None) -> int | None:
    if not isinstance(portfolio, dict):
        return None
    n = 0
    for pos in (portfolio.get("positions") or {}).values():
        if isinstance(pos, dict) and (_f_or_none(pos.get("shares")) or 0.0) > 0:
            n += 1
    return n


def protective_stop_from_pct(
    entry_price: float,
    stop_pct: float,
    *,
    policy_source: str,
) -> dict[str, Any]:
    """
    Freeze an already-active protective stop policy (negative or positive pct).

    stop_pct examples: hard_risk_guardian.STOP_LIMIT (-3) or V2_STOP_LOSS_PCT (-3).
    Does not invent a new strategy stop — documents the policy in force at entry.
    """
    ep = float(entry_price)
    sp = float(stop_pct)
    # Normalize to negative loss fraction of entry (e.g. -3.0 → 3% below entry).
    if sp > 0:
        sp = -sp
    distance_pct = abs(sp)
    stop_price = round(ep * (1.0 + sp / 100.0), 8)
    stop_distance = round(ep - stop_price, 8)
    return {
        "stop_price": stop_price,
        "stop_distance": stop_distance,
        "stop_distance_pct": round(distance_pct, 8),
        "initial_risk_per_share": stop_distance,
        "stop_policy_source": policy_source,
        "stop_policy_version": f"{policy_source}:{sp}",
    }


def v1_stop_policy_fields(entry_price: float) -> dict[str, Any]:
    from hard_risk_guardian import STOP_LIMIT

    return protective_stop_from_pct(
        entry_price,
        float(STOP_LIMIT),
        policy_source="hard_risk_guardian.STOP_LIMIT",
    )


def v2_stop_policy_fields(entry_price: float, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or {}
    raw = cfg.get("V2_STOP_LOSS_PCT")
    if raw is None:
        # Parallel runtime injects this; foundation config may omit — use hard-risk SSOT.
        from hard_risk_guardian import STOP_LIMIT

        return protective_stop_from_pct(
            entry_price,
            float(STOP_LIMIT),
            policy_source="hard_risk_guardian.STOP_LIMIT",
        )
    return protective_stop_from_pct(
        entry_price,
        float(raw),
        policy_source="parallel_v2.V2_STOP_LOSS_PCT",
    )


def _status_and_missing(payload: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    missing: list[str] = []
    flags: list[str] = []
    for key in OPTIONAL_FIELDS:
        if payload.get(key) is None:
            missing.append(key)
    for key in MIN_FIELDS:
        if key in {"snapshot_status", "missing_fields", "snapshot_created_at"}:
            continue
        if payload.get(key) is None or payload.get(key) == "":
            missing.append(key)
            flags.append(f"MISSING_MIN:{key}")
    # Deduplicate missing while preserving order
    seen: set[str] = set()
    missing_u: list[str] = []
    for m in missing:
        if m not in seen:
            seen.add(m)
            missing_u.append(m)

    min_ok = all(
        payload.get(k) is not None and payload.get(k) != ""
        for k in MIN_FIELDS
        if k not in {"snapshot_status", "missing_fields", "snapshot_created_at"}
    )
    if not min_ok:
        return STATUS_UNAVAILABLE, missing_u, flags
    risk_ok = (
        _f_or_none(payload.get("initial_risk_amount")) is not None
        and (_f_or_none(payload.get("initial_risk_amount")) or 0) > 0
        and payload.get("stop_price") is not None
    )
    sizing_ok = payload.get("recommended_quantity") is not None or payload.get("authorized_quantity") is not None
    context_ok = payload.get("cash_available") is not None
    if risk_ok and sizing_ok and context_ok and len(missing_u) <= 12:
        return STATUS_COMPLETE, missing_u, flags
    if risk_ok:
        return STATUS_PARTIAL, missing_u, flags + (["RISK_OK_CONTEXT_PARTIAL"] if not context_ok else [])
    return STATUS_MINIMUM_ONLY, missing_u, flags + ["STOP_OR_RISK_INCOMPLETE"]


def build_entry_risk_snapshot(
    *,
    ticker: str,
    strategy_arm: str,
    execution_id: str,
    entry_timestamp: str | None,
    entry_price: float | None,
    executed_quantity: float | None,
    executed_notional: float | None,
    sizing_formula_id: str,
    sizing_source_path: str,
    entry_type: str = "INITIAL",
    cycle_id: str | None = None,
    family_id: str | None = None,
    parent_cycle_id: str | None = None,
    decision_id: str | None = None,
    tranche_id: str | None = None,
    reentry_sequence: int | None = None,
    recommended_quantity: float | None = None,
    authorized_quantity: float | None = None,
    stop_fields: dict[str, Any] | None = None,
    cash_available: float | None = None,
    account_equity: float | None = None,
    portfolio_value: float | None = None,
    position_budget: float | None = None,
    cash_reserve: float | None = None,
    maximum_position_notional: float | None = None,
    maximum_positions: int | None = None,
    current_open_positions: int | None = None,
    atr: float | None = None,
    atr_pct: float | None = None,
    volatility: float | None = None,
    confidence: float | None = None,
    signal_score: float | None = None,
    market_regime: str | None = None,
    account_drawdown: float | None = None,
    total_exposure: float | None = None,
    ticker_exposure: float | None = None,
    sector_exposure: float | None = None,
    region_exposure: float | None = None,
    risk_multiplier: float | None = None,
    confidence_multiplier: float | None = None,
    volatility_multiplier: float | None = None,
    regime_multiplier: float | None = None,
    drawdown_multiplier: float | None = None,
    snapshot_source: str | None = None,
    snapshot_created_at: str | None = None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build immutable snapshot. If ``existing`` has same execution_id, return it unchanged."""
    eid = _s(execution_id)
    if isinstance(existing, dict) and _s(existing.get("execution_id")) == eid and existing.get("schema_version"):
        return dict(existing)

    created = _s(snapshot_created_at) or _now()
    ep = _f_or_none(entry_price)
    qty = _f_or_none(executed_quantity)
    notional = _f_or_none(executed_notional)
    if notional is None and ep is not None and qty is not None:
        notional = round(ep * qty, 6)

    stop = dict(stop_fields or {})
    initial_risk_per_share = _f_or_none(stop.get("initial_risk_per_share"))
    initial_risk_amount = None
    if initial_risk_per_share is not None and qty is not None and qty > 0 and initial_risk_per_share >= 0:
        initial_risk_amount = round(initial_risk_per_share * qty, 6)
    equity = _f_or_none(account_equity)
    if equity is None:
        equity = _f_or_none(portfolio_value)
    initial_risk_pct = None
    if initial_risk_amount is not None and equity is not None and equity > 0:
        initial_risk_pct = round(100.0 * initial_risk_amount / equity, 8)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ticker": _s(ticker).upper() or None,
        "strategy_arm": _s(strategy_arm).upper() or None,
        "cycle_id": _s(cycle_id) or None,
        "family_id": _s(family_id) or None,
        "parent_cycle_id": _s(parent_cycle_id) or None,
        "decision_id": _s(decision_id) or None,
        "execution_id": eid or None,
        "tranche_id": _s(tranche_id) or None,
        "reentry_sequence": reentry_sequence,
        "entry_type": _s(entry_type) or None,
        "entry_timestamp": _s(entry_timestamp) or created,
        "entry_price": ep,
        "recommended_quantity": _f_or_none(recommended_quantity),
        "authorized_quantity": _f_or_none(authorized_quantity),
        "executed_quantity": qty,
        "executed_notional": notional,
        "sizing_formula_id": _s(sizing_formula_id) or None,
        "sizing_formula_version": SIZING_FORMULA_VERSION,
        "sizing_source_path": _s(sizing_source_path) or None,
        "stop_price": _f_or_none(stop.get("stop_price")),
        "stop_distance": _f_or_none(stop.get("stop_distance")),
        "stop_distance_pct": _f_or_none(stop.get("stop_distance_pct")),
        "initial_risk_per_share": initial_risk_per_share,
        "initial_risk_amount": initial_risk_amount,
        "initial_risk_pct_of_equity": initial_risk_pct,
        "maximum_accepted_loss": initial_risk_amount,
        "cash_available": _f_or_none(cash_available),
        "account_equity": equity,
        "portfolio_value": _f_or_none(portfolio_value) if portfolio_value is not None else equity,
        "position_budget": _f_or_none(position_budget),
        "cash_reserve": _f_or_none(cash_reserve),
        "maximum_position_notional": _f_or_none(maximum_position_notional),
        "maximum_positions": maximum_positions,
        "current_open_positions": current_open_positions,
        "atr": _f_or_none(atr),
        "atr_pct": _f_or_none(atr_pct),
        "volatility": _f_or_none(volatility),
        "confidence": _f_or_none(confidence),
        "signal_score": _f_or_none(signal_score),
        "market_regime": _s(market_regime) or None,
        "account_drawdown": _f_or_none(account_drawdown),
        "total_exposure": _f_or_none(total_exposure),
        "ticker_exposure": _f_or_none(ticker_exposure),
        "sector_exposure": _f_or_none(sector_exposure),
        "region_exposure": _f_or_none(region_exposure),
        "risk_multiplier": _f_or_none(risk_multiplier),
        "confidence_multiplier": _f_or_none(confidence_multiplier),
        "volatility_multiplier": _f_or_none(volatility_multiplier),
        "regime_multiplier": _f_or_none(regime_multiplier),
        "drawdown_multiplier": _f_or_none(drawdown_multiplier),
        "snapshot_created_at": created,
        "snapshot_source": _s(snapshot_source) or _s(sizing_source_path) or None,
        "stop_policy_source": stop.get("stop_policy_source"),
        "stop_policy_version": stop.get("stop_policy_version"),
    }
    status, missing, flags = _status_and_missing(payload)
    payload["snapshot_status"] = status
    payload["missing_fields"] = missing
    payload["data_quality_flags"] = flags
    return payload


def merge_existing_snapshot(existing: dict[str, Any] | None, built: dict[str, Any]) -> dict[str, Any]:
    """Idempotent: never overwrite an existing snapshot for the same execution_id."""
    if not isinstance(existing, dict):
        return built
    if _s(existing.get("execution_id")) and _s(existing.get("execution_id")) == _s(built.get("execution_id")):
        return dict(existing)
    return built


def append_entry_risk_snapshot_to_cycle(
    cycle: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Append snapshot to cycle.entry_risk_snapshots without duplicates; update aggregates."""
    cycle = dict(cycle)
    snaps = list(cycle.get("entry_risk_snapshots") or [])
    eid = _s(snapshot.get("execution_id"))
    for s in snaps:
        if isinstance(s, dict) and _s(s.get("execution_id")) == eid:
            cycle["entry_risk_snapshots"] = snaps
            _refresh_cycle_risk_aggregate(cycle)
            return cycle
    snaps.append(dict(snapshot))
    cycle["entry_risk_snapshots"] = snaps
    _refresh_cycle_risk_aggregate(cycle)
    return cycle


def _refresh_cycle_risk_aggregate(cycle: dict[str, Any]) -> None:
    snaps = [s for s in (cycle.get("entry_risk_snapshots") or []) if isinstance(s, dict)]
    valid = []
    for s in snaps:
        amt = _f_or_none(s.get("initial_risk_amount"))
        if amt is not None and amt > 0:
            valid.append(amt)
    if not snaps:
        cycle["aggregated_initial_risk_amount"] = None
        cycle["risk_aggregation_status"] = STATUS_UNAVAILABLE
    elif len(valid) == len(snaps):
        cycle["aggregated_initial_risk_amount"] = round(sum(valid), 6)
        cycle["risk_aggregation_status"] = STATUS_COMPLETE
    elif valid:
        cycle["aggregated_initial_risk_amount"] = round(sum(valid), 6)
        cycle["risk_aggregation_status"] = STATUS_PARTIAL
    else:
        cycle["aggregated_initial_risk_amount"] = None
        cycle["risk_aggregation_status"] = STATUS_UNAVAILABLE


def persist_cycle_entry_risk_snapshot(
    cycle_path: Path | None,
    cycle_id: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Restart-safe append onto V2 cycle_state.json."""
    if cycle_path is None or not _s(cycle_id):
        return snapshot
    from tae_strategy_v2_foundation import load_cycle_store, save_cycle_store

    store = load_cycle_store(cycle_path)
    cycles = dict(store.get("cycles") or {})
    cycle = cycles.get(_s(cycle_id))
    if not isinstance(cycle, dict):
        return snapshot
    # Prefer existing immutable snapshot if present
    for s in cycle.get("entry_risk_snapshots") or []:
        if isinstance(s, dict) and _s(s.get("execution_id")) == _s(snapshot.get("execution_id")):
            return dict(s)
    updated = append_entry_risk_snapshot_to_cycle(cycle, snapshot)
    cycles[_s(cycle_id)] = updated
    store["cycles"] = cycles
    save_cycle_store(store, cycle_path)
    return snapshot


def collect_snapshots_from_cycle_sources(
    *,
    cycle: dict[str, Any] | None = None,
    fills: list[dict[str, Any]] | None = None,
    tranches: list[dict[str, Any]] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Dedup by execution_id; prefer first-seen (immutable journal order)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(snap: Any) -> None:
        if not isinstance(snap, dict):
            return
        if snap.get("schema_version") != SCHEMA_VERSION and not snap.get("execution_id"):
            return
        if snap.get("schema_version") and snap.get("schema_version") != SCHEMA_VERSION:
            # Accept only our schema
            if not snap.get("execution_id"):
                return
        eid = _s(snap.get("execution_id"))
        if not eid or eid in seen:
            return
        if snap.get("schema_version") != SCHEMA_VERSION:
            return
        seen.add(eid)
        out.append(dict(snap))

    if isinstance(cycle, dict):
        for s in cycle.get("entry_risk_snapshots") or []:
            _add(s)
    for row in fills or []:
        if isinstance(row, dict):
            _add(row.get("risk_snapshot"))
    for row in trades or []:
        if isinstance(row, dict):
            _add(row.get("risk_snapshot"))
    for row in tranches or []:
        if isinstance(row, dict):
            _add(row.get("risk_snapshot"))
    return out


def aggregate_initial_risk(snapshots: list[dict[str, Any]]) -> tuple[float | None, str]:
    if not snapshots:
        return None, "RISK_DATA_NOT_PERSISTED_AT_ENTRY"
    amts = []
    for s in snapshots:
        a = _f_or_none(s.get("initial_risk_amount"))
        if a is not None and a > 0:
            amts.append(a)
    if not amts:
        return None, "INVALID_INITIAL_RISK"
    if len(amts) < len(snapshots):
        return round(sum(amts), 6), "PARTIAL"
    return round(sum(amts), 6), "COMPLETE"


def r_multiple(pnl: float | None, initial_risk: float | None) -> float | None:
    if pnl is None or initial_risk is None:
        return None
    if initial_risk <= 0 or math.isnan(initial_risk) or math.isinf(initial_risk):
        return None
    if math.isnan(pnl) or math.isinf(pnl):
        return None
    return round(float(pnl) / float(initial_risk), 8)


__all__ = [
    "SCHEMA_VERSION",
    "SIZING_FORMULA_VERSION",
    "FORMULA_V1_DEPLOYABLE_25PCT",
    "FORMULA_V2_INITIAL_BUDGET_TRANCHE",
    "FORMULA_V2_ADD_BUDGET_TRANCHE",
    "FORMULA_V2_REENTRY_BUDGET_TRANCHE",
    "SOURCE_V1",
    "SOURCE_V2_BUY_POLICY",
    "build_entry_risk_snapshot",
    "merge_existing_snapshot",
    "append_entry_risk_snapshot_to_cycle",
    "persist_cycle_entry_risk_snapshot",
    "collect_snapshots_from_cycle_sources",
    "aggregate_initial_risk",
    "r_multiple",
    "portfolio_mark_equity",
    "open_position_count",
    "v1_stop_policy_fields",
    "v2_stop_policy_fields",
    "protective_stop_from_pct",
]
