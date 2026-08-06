#!/usr/bin/env python3
"""
PAPER shadow sizing observability — evaluate alternate formulas without execution.

PAPER_ONLY | OBSERVABILITY_ONLY | NO_BROKER | NO_LIVE | NO_QUANTITY_MUTATION

Extends entry-risk observability: for each PAPER fill, record what alternate
sizing formulas *would recommend* from pre-fill inputs only.
Does not authorize orders, mutate cash/portfolio, or invent counterfactual PnL.
Does not connect core/risk to canonical execution.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "tae.paper.shadow_sizing_evaluation.v1"
EXPERIMENT_ID = "TAE_SHADOW_SIZING_COMPARISON_V1"
FORMULA_VERSION = "shadow_sizing_formula.v1"

# Common PAPER capital deployment band (V1/V2/Vx control path).
PAPER_DEPLOYABLE_FRACTION = 0.40
PAPER_CONFIDENCE_MIN_FRACTION = 0.08
PAPER_CONFIDENCE_MULT = 0.18
PAPER_CONFIDENCE_MAX_FRACTION = 0.30
PAPER_MIN_ORDER_USD = 250.0
PAPER_MAX_POSITION_NOTIONAL = 2500.0
CAPITAL_UTILIZATION_TARGET_MIN = 0.50
CAPITAL_UTILIZATION_TARGET_MAX = 0.70


def paper_deployable_notional(
    cash_available: float,
    *,
    cash_reserve: float = 500.0,
    cap: float = PAPER_MAX_POSITION_NOTIONAL,
) -> float:
    """Investable cash × deploy fraction, capped — shared V1/V2/Vx control sizing."""
    investable = max(0.0, float(cash_available) - float(cash_reserve))
    return round(min(float(cap), investable * PAPER_DEPLOYABLE_FRACTION), 6)


def paper_confidence_notional(
    cash_available: float,
    confidence: float,
    *,
    cash_reserve: float = 0.0,
    max_pos: float = PAPER_MAX_POSITION_NOTIONAL,
) -> float:
    """Canonical PAPER confidence-weighted notional — shared execution path."""
    cash = float(cash_available)
    conf = float(confidence)
    investable = max(0.0, cash - float(cash_reserve))
    return round(
        min(
            cash * max(PAPER_CONFIDENCE_MIN_FRACTION, conf * PAPER_CONFIDENCE_MULT),
            cash * PAPER_CONFIDENCE_MAX_FRACTION,
            float(max_pos),
            investable,
        ),
        6,
    )

# Reuse canonical formula IDs from entry risk snapshot.
from tae_paper_entry_risk_snapshot import (
    FORMULA_V1_DEPLOYABLE_25PCT,
    FORMULA_V2_ADD_BUDGET_TRANCHE,
    FORMULA_V2_INITIAL_BUDGET_TRANCHE,
    FORMULA_V2_REENTRY_BUDGET_TRANCHE,
    SOURCE_V1,
    SOURCE_V2_BUY_POLICY,
)

FORMULA_LIVE_EQUAL_SPLIT = "LIVE_EQUAL_SPLIT_CASH_OVER_CANDIDATES"
FORMULA_CORE_RISK = "CORE_RISK_GET_DYNAMIC_TRADE_SIZE"
FORMULA_OFFLINE_B1_VOL = "OFFLINE_RISK_WEIGHTED_B1_VOL"
FORMULA_OFFLINE_B2_CONF = "OFFLINE_RISK_WEIGHTED_B2_CONFIDENCE"
FORMULA_OFFLINE_B3_DD = "OFFLINE_RISK_WEIGHTED_B3_DRAWDOWN"
FORMULA_CANON_PAPER_CONF = "CANONICAL_PAPER_CONFIDENCE_PCT"

SOURCE_LIVE = "live_bot.get_dynamic_trade_size"
SOURCE_CORE_RISK = "core.risk.get_dynamic_trade_size"
SOURCE_OFFLINE_RW = "tae_risk_weighted_sizing_ab.size_b*"
SOURCE_CANON_PAPER = "tae_paper_execution.execute_decision.BUY"

ROLE_EXECUTED = "EXECUTED"
ROLE_SHADOW = "SHADOW"
ROLE_OFFLINE_REFERENCE = "OFFLINE_REFERENCE"

FS_ACTIVE_EXECUTED = "ACTIVE_EXECUTED"
FS_ACTIVE_SHADOW = "ACTIVE_SHADOW"
FS_OFFLINE_ONLY = "OFFLINE_ONLY"
FS_NOT_APPLICABLE = "NOT_APPLICABLE"
FS_INVALID = "INVALID"
FS_LEGACY = "LEGACY"

ES_COMPLETE = "COMPLETE"
ES_PARTIAL = "PARTIAL"
ES_NOT_EVALUATED = "NOT_EVALUATED"
ES_INVALID_OUTPUT = "INVALID_OUTPUT"
ES_NOT_APPLICABLE = "NOT_APPLICABLE"

CS_DIRECT_QTY = "DIRECT_QUANTITY_COMPARISON"
CS_DIRECT_NOTIONAL = "DIRECT_NOTIONAL_COMPARISON"
CS_RISK_AVAILABLE = "RISK_COMPARISON_AVAILABLE"
CS_RISK_UNAVAILABLE = "RISK_COMPARISON_UNAVAILABLE"
CS_REQUIRES_CF = "REQUIRES_COUNTERFACTUAL"
CS_INSUFFICIENT = "INSUFFICIENT_INPUTS"

SHADOW_DATA_NOT_PERSISTED = "SHADOW_DATA_NOT_PERSISTED_AT_ENTRY"
OFFLINE_NO_EDGE_NOTE = "RISK_WEIGHTED_SIZING_NO_EDGE"


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


def evaluation_id(*, experiment_id: str, execution_id: str, formula_id: str, tranche_id: str | None = None) -> str:
    """Deterministic unique id — stable across reruns."""
    raw = f"{experiment_id}|{execution_id}|{_s(tranche_id)}|{formula_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper()
    return f"SSE-{digest}"


def _delta(a: float | None, b: float | None) -> tuple[float | None, float | None]:
    if a is None or b is None:
        return None, None
    d = round(float(a) - float(b), 8)
    pct = None
    if float(b) != 0.0:
        pct = round(100.0 * d / float(b), 8)
    return d, pct


def _hyp_risk(
    *,
    shadow_qty: float | None,
    stop_distance: float | None,
    equity: float | None,
) -> tuple[float | None, float | None, str]:
    if shadow_qty is None or stop_distance is None:
        return None, None, CS_RISK_UNAVAILABLE
    if shadow_qty < 0 or stop_distance < 0:
        return None, None, CS_RISK_UNAVAILABLE
    amt = round(float(shadow_qty) * float(stop_distance), 6)
    pct = None
    if equity is not None and equity > 0:
        pct = round(100.0 * amt / float(equity), 8)
    return amt, pct, CS_RISK_AVAILABLE


def _base_record(
    *,
    identity: dict[str, Any],
    formula_id: str,
    formula_source_path: str,
    formula_role: str,
    formula_status: str,
    executed_formula: bool,
    eligible_for_path: bool,
    inputs: dict[str, Any],
    executed_quantity: float | None,
    executed_notional: float | None,
) -> dict[str, Any]:
    eid = evaluation_id(
        experiment_id=EXPERIMENT_ID,
        execution_id=_s(identity.get("execution_id")),
        formula_id=formula_id,
        tranche_id=_s(identity.get("tranche_id")) or None,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_id": eid,
        "experiment_id": EXPERIMENT_ID,
        "strategy_arm": identity.get("strategy_arm"),
        "ticker": identity.get("ticker"),
        "cycle_id": identity.get("cycle_id"),
        "family_id": identity.get("family_id"),
        "parent_cycle_id": identity.get("parent_cycle_id"),
        "decision_id": identity.get("decision_id"),
        "execution_id": identity.get("execution_id"),
        "tranche_id": identity.get("tranche_id"),
        "reentry_sequence": identity.get("reentry_sequence"),
        "entry_type": identity.get("entry_type"),
        "evaluated_at": identity.get("evaluated_at") or _now(),
        "formula_id": formula_id,
        "formula_version": FORMULA_VERSION,
        "formula_source_path": formula_source_path,
        "formula_role": formula_role,
        "formula_status": formula_status,
        "executed_formula": bool(executed_formula),
        "eligible_for_path": bool(eligible_for_path),
        "price": inputs.get("price"),
        "cash_available": inputs.get("cash_available"),
        "account_equity": inputs.get("account_equity"),
        "portfolio_value": inputs.get("portfolio_value"),
        "current_position_quantity": inputs.get("current_position_quantity"),
        "current_position_notional": inputs.get("current_position_notional"),
        "company_budget": inputs.get("company_budget"),
        "tranche_budget": inputs.get("tranche_budget"),
        "cash_reserve": inputs.get("cash_reserve"),
        "maximum_position_notional": inputs.get("maximum_position_notional"),
        "maximum_positions": inputs.get("maximum_positions"),
        "current_open_positions": inputs.get("current_open_positions"),
        "atr": inputs.get("atr"),
        "atr_pct": inputs.get("atr_pct"),
        "volatility": inputs.get("volatility"),
        "confidence": inputs.get("confidence"),
        "signal_score": inputs.get("signal_score"),
        "market_regime": inputs.get("market_regime"),
        "account_drawdown": inputs.get("account_drawdown"),
        "stop_price": inputs.get("stop_price"),
        "stop_distance": inputs.get("stop_distance"),
        "total_exposure": inputs.get("total_exposure"),
        "ticker_exposure": inputs.get("ticker_exposure"),
        "sector_exposure": inputs.get("sector_exposure"),
        "region_exposure": inputs.get("region_exposure"),
        "shadow_recommended_quantity": None,
        "shadow_recommended_notional": None,
        "executed_quantity": executed_quantity,
        "executed_notional": executed_notional,
        "quantity_delta": None,
        "quantity_delta_pct": None,
        "notional_delta": None,
        "notional_delta_pct": None,
        "hypothetical_initial_risk_amount": None,
        "hypothetical_initial_risk_pct_of_equity": None,
        "evaluation_status": ES_NOT_EVALUATED,
        "missing_inputs": [],
        "invalid_inputs": [],
        "data_quality_flags": [],
        "comparability_status": CS_INSUFFICIENT,
        "exclusion_reason": None,
        # Explicit: never invent path PnL
        "hypothetical_gross_pnl": "REQUIRES_COUNTERFACTUAL",
        "hypothetical_net_pnl": "REQUIRES_COUNTERFACTUAL",
        "hypothetical_realized_pnl": "REQUIRES_COUNTERFACTUAL",
    }


def _finalize_result(
    rec: dict[str, Any],
    *,
    notional: float | None,
    price: float | None,
    stop_distance: float | None,
    equity: float | None,
    evaluation_status: str,
    missing: list[str] | None = None,
    invalid: list[str] | None = None,
    flags: list[str] | None = None,
    exclusion_reason: str | None = None,
) -> dict[str, Any]:
    rec = dict(rec)
    rec["missing_inputs"] = list(missing or [])
    rec["invalid_inputs"] = list(invalid or [])
    rec["data_quality_flags"] = list(flags or [])
    rec["exclusion_reason"] = exclusion_reason
    rec["evaluation_status"] = evaluation_status

    if evaluation_status in {ES_NOT_APPLICABLE, ES_NOT_EVALUATED, ES_INVALID_OUTPUT}:
        if evaluation_status == ES_NOT_APPLICABLE:
            rec["comparability_status"] = CS_INSUFFICIENT
        elif missing:
            rec["comparability_status"] = CS_INSUFFICIENT
        else:
            rec["comparability_status"] = CS_REQUIRES_CF if "OFFLINE" in _s(rec.get("formula_status")) else CS_INSUFFICIENT
        return rec

    if notional is None or notional < 0:
        # Keep PARTIAL when pre-fill inputs are missing — do not invent output.
        if evaluation_status == ES_PARTIAL and (missing or []):
            rec["comparability_status"] = CS_INSUFFICIENT
            return rec
        rec["evaluation_status"] = ES_INVALID_OUTPUT
        rec["invalid_inputs"] = list(rec["invalid_inputs"]) + ["shadow_recommended_notional"]
        rec["comparability_status"] = CS_INSUFFICIENT
        return rec

    px = _f_or_none(price)
    qty = None
    if px is not None and px > 0:
        qty = round(float(notional) / px, 6)
    rec["shadow_recommended_notional"] = round(float(notional), 6)
    rec["shadow_recommended_quantity"] = qty

    qd, qdp = _delta(qty, _f_or_none(rec.get("executed_quantity")))
    nd, ndp = _delta(rec["shadow_recommended_notional"], _f_or_none(rec.get("executed_notional")))
    rec["quantity_delta"] = qd
    rec["quantity_delta_pct"] = qdp
    rec["notional_delta"] = nd
    rec["notional_delta_pct"] = ndp

    hyp, hyp_pct, risk_cs = _hyp_risk(
        shadow_qty=qty,
        stop_distance=_f_or_none(stop_distance),
        equity=_f_or_none(equity),
    )
    rec["hypothetical_initial_risk_amount"] = hyp
    rec["hypothetical_initial_risk_pct_of_equity"] = hyp_pct

    comps = []
    if qty is not None and rec.get("executed_quantity") is not None:
        comps.append(CS_DIRECT_QTY)
    if rec.get("executed_notional") is not None:
        comps.append(CS_DIRECT_NOTIONAL)
    comps.append(risk_cs)
    # Primary comparability: prefer risk if available else notional/qty
    if risk_cs == CS_RISK_AVAILABLE:
        rec["comparability_status"] = CS_RISK_AVAILABLE
    elif CS_DIRECT_QTY in comps:
        rec["comparability_status"] = CS_DIRECT_QTY
    elif CS_DIRECT_NOTIONAL in comps:
        rec["comparability_status"] = CS_DIRECT_NOTIONAL
    else:
        rec["comparability_status"] = CS_INSUFFICIENT

    # PnL always CF
    rec["data_quality_flags"] = list(rec["data_quality_flags"]) + ["NO_COUNTERFACTUAL_PNL"]
    return rec


def _na(
    identity: dict[str, Any],
    inputs: dict[str, Any],
    *,
    formula_id: str,
    source: str,
    executed_quantity: float | None,
    executed_notional: float | None,
    reason: str,
    formula_status: str = FS_NOT_APPLICABLE,
) -> dict[str, Any]:
    rec = _base_record(
        identity=identity,
        formula_id=formula_id,
        formula_source_path=source,
        formula_role=ROLE_SHADOW if formula_status != FS_OFFLINE_ONLY else ROLE_OFFLINE_REFERENCE,
        formula_status=formula_status,
        executed_formula=False,
        eligible_for_path=False,
        inputs=inputs,
        executed_quantity=executed_quantity,
        executed_notional=executed_notional,
    )
    return _finalize_result(
        rec,
        notional=None,
        price=inputs.get("price"),
        stop_distance=inputs.get("stop_distance"),
        equity=inputs.get("account_equity"),
        evaluation_status=ES_NOT_APPLICABLE,
        exclusion_reason=reason,
        flags=["PATH_INCOMPATIBLE"] if formula_status == FS_NOT_APPLICABLE else ["OFFLINE_REFERENCE_ONLY"],
    )


def eval_v1_deployable(inputs: dict[str, Any]) -> tuple[float | None, list[str], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    cash = _f_or_none(inputs.get("cash_available"))
    reserve = _f_or_none(inputs.get("cash_reserve"))
    if cash is None:
        missing.append("cash_available")
    if reserve is None:
        reserve = 500.0
    if missing:
        return None, missing, invalid
    notional = paper_deployable_notional(float(cash), cash_reserve=float(reserve))
    if notional < PAPER_MIN_ORDER_USD:
        # Formula still yields a number; gate would block execution — report raw recommendation
        pass
    return round(notional, 6), missing, invalid


def eval_v2_tranche(inputs: dict[str, Any], *, entry_type: str) -> tuple[float | None, list[str], list[str]]:
    """INITIAL uses company_budget; ADD uses tranche_budget/remaining; REENTRY like INITIAL."""
    missing: list[str] = []
    invalid: list[str] = []
    cash = _f_or_none(inputs.get("cash_available"))
    reserve = _f_or_none(inputs.get("cash_reserve")) or 500.0
    max_order = _f_or_none(inputs.get("maximum_position_notional")) or 2500.0
    frac = 0.20
    et = _s(entry_type).upper()
    if cash is None:
        missing.append("cash_available")
    if et in {"ADD"}:
        rem = _f_or_none(inputs.get("tranche_budget"))
        budget = _f_or_none(inputs.get("company_budget"))
        if rem is None:
            missing.append("tranche_budget")
        if missing:
            return None, missing, invalid
        prop = min(float(budget or rem) * frac if budget is not None else float(rem) * frac, float(rem), float(max_order))
        # Prefer remaining-based: company_budget * frac capped by remaining
        if budget is not None:
            prop = min(float(budget) * frac, float(rem), float(max_order))
        return round(max(0.0, prop), 6), missing, invalid
    # INITIAL / REENTRY
    budget = _f_or_none(inputs.get("company_budget"))
    if budget is None and cash is not None:
        investable = max(0.0, float(cash) - float(reserve))
        budget = min(2500.0, max(500.0, investable * 0.5))
    if budget is None:
        missing.append("company_budget")
        return None, missing, invalid
    prop = min(float(budget) * frac, float(max_order))
    if cash is not None and float(cash) - prop < float(reserve) - 1e-9:
        prop = max(0.0, float(cash) - float(reserve))
        prop = min(prop, float(max_order))
    return round(prop, 6), missing, invalid


def eval_live_equal_split(inputs: dict[str, Any]) -> tuple[float | None, list[str], list[str]]:
    """Shadow of LIVE equal-split for a *single* concurrent candidate (N=1 semantics)."""
    missing: list[str] = []
    cash = _f_or_none(inputs.get("cash_available"))
    open_n = inputs.get("current_open_positions")
    max_pos = inputs.get("maximum_positions")
    if cash is None:
        missing.append("cash_available")
    if missing:
        return None, missing, []
    # Without full candidate set, treat as one slot if capacity remains
    if max_pos is not None and open_n is not None:
        slots = max(int(max_pos) - int(open_n), 0)
        if slots <= 0:
            return 0.0, missing, []
    # LIVE clamps in buy_position
    trade = float(cash)  # N=1 → cash/1
    trade = min(max(trade, 0.0), 2500.0)
    if trade < 250.0:
        return round(trade, 6), missing, []
    return round(trade, 6), missing, []


def eval_canonical_paper_confidence(inputs: dict[str, Any]) -> tuple[float | None, list[str], list[str]]:
    missing: list[str] = []
    cash = _f_or_none(inputs.get("cash_available"))
    conf = _f_or_none(inputs.get("confidence"))
    if cash is None:
        missing.append("cash_available")
    if conf is None:
        missing.append("confidence")
        return None, missing, []
    if missing:
        return None, missing, []
    notional = paper_confidence_notional(float(cash), float(conf))
    return round(notional, 6), missing, []


def eval_core_risk_adapter(
    *,
    ticker: str,
    inputs: dict[str, Any],
    portfolio_before: dict[str, Any] | None,
    path: str,
) -> tuple[float | None, list[str], list[str], str | None]:
    """
    Observability-only mirror of core.risk.get_dynamic_trade_size math using
    pre-fill cash/positions — does NOT call get_cash_available (LIVE SSOT) and
    does NOT mutate core/risk or execution.
    """
    del portfolio_before  # pre-fill inputs only; avoid LIVE portfolio helpers
    path_u = _s(path).upper()
    if path_u in {"ADD", "ADD_TRANCHE"}:
        return None, [], [], "core_risk_excludes_open_positions_and_lacks_tranche_budget_model"

    missing: list[str] = []
    score = _f_or_none(inputs.get("signal_score"))
    cash = _f_or_none(inputs.get("cash_available"))
    regime = _s(inputs.get("market_regime")) or "NEUTRAL"
    if score is None:
        missing.append("signal_score")
    if cash is None:
        missing.append("cash_available")
    if missing:
        return None, missing, [], None

    held_qty = _f_or_none(inputs.get("current_position_quantity")) or 0.0
    if held_qty > 0:
        return None, [], [], "core_risk_excludes_tickers_already_held"

    try:
        from config.settings import MIN_CASH_RESERVE
        from core.allocation import get_allocation_weight
        from core.entry_filter import get_dynamic_min_score_to_buy
        from core.forecast_risk import get_forecast_multiplier
        from core.historical_risk import get_risk_multiplier
        from core.market_regime import get_max_positions
    except Exception as exc:  # pragma: no cover
        return None, missing, [f"import_error:{exc}"], "core_risk_import_failed"

    min_score = float(get_dynamic_min_score_to_buy())
    if float(score) < min_score:
        return 0.0, missing, [], None

    if regime == "BEAR":
        return 0.0, missing, [], None

    reserve = _f_or_none(inputs.get("cash_reserve"))
    if reserve is None:
        reserve = float(MIN_CASH_RESERVE)
    investable = max(float(cash) - float(reserve), 0.0)
    open_n = int(inputs.get("current_open_positions") or 0)
    try:
        slots = max(int(get_max_positions(regime)) - open_n, 0)
    except Exception:
        slots = max(0, 8 - open_n)  # NEUTRAL default table fallback
        missing.append("max_positions_regime")

    if slots <= 0 or investable <= 0:
        return 0.0, missing, [], None

    weight = float(get_allocation_weight(float(score)))
    if weight <= 0:
        return 0.0, missing, [], None

    # Single-candidate shadow: investable/weight (same as core/risk with one weighted name)
    trade_size = investable / weight
    trade_size *= float(get_risk_multiplier())
    trade_size *= float(get_forecast_multiplier())
    if math.isnan(trade_size) or math.isinf(trade_size):
        return None, missing, ["nan_inf_size"], None
    return round(trade_size, 2), missing, [], None


def eval_offline_risk_weighted(
    *,
    formula_id: str,
    inputs: dict[str, Any],
    base_notional: float | None,
) -> tuple[float | None, list[str], list[str], str | None]:
    """
    Reuse offline A/B sizing helpers when inputs allow; otherwise NOT_EVALUATED.
    Does not claim live edge — OFFLINE_ONLY / NO_EDGE reference.
    Separates PAPER_ENTRY_SHADOW_OBSERVATION from OFFLINE_RESULT.
    """
    missing: list[str] = []
    if base_notional is None or base_notional <= 0:
        missing.append("base_notional")
        return None, missing, [], None
    try:
        import tae_risk_weighted_sizing_ab as rws
    except Exception as exc:  # pragma: no cover
        return None, missing, [f"import:{exc}"], "offline_module_unavailable"

    # Minimal duck-typed state: size_b* only need .cash (no LIVE/EngineState coupling).
    class _CashOnly:
        def __init__(self, cash: float) -> None:
            self.cash = float(cash)

    ev = {
        "ts": inputs.get("evaluated_at") or _now(),
        "intent_notional": float(base_notional),
        "price": inputs.get("price") or 0.0,
        "shares": 0.0,
        "score": inputs.get("signal_score"),
    }
    import pandas as pd

    feat = pd.DataFrame()
    st = _CashOnly(float(inputs.get("cash_available") or 0.0))
    cash = float(inputs.get("cash_available") or 0.0)

    if formula_id == FORMULA_OFFLINE_B1_VOL:
        atr = _f_or_none(inputs.get("atr_pct"))
        if atr is None:
            return None, ["atr_pct"], [], None
        # Reuse B1 clamp/factor math without inventing ATR bars.
        median = float(getattr(rws, "B1_MEDIAN_ATR_PCT", 2.0) or 2.0)
        target_risk = 0.01
        factor = (median / float(atr)) * (target_risk / 0.01)
        factor = float(max(0.4, min(1.6, factor)))
        n = rws._clamp_notional(float(base_notional) * factor, cash)
        return round(float(n), 6), [], [], None
    if formula_id == FORMULA_OFFLINE_B2_CONF:
        score = _f_or_none(inputs.get("signal_score"))
        if score is None:
            return None, ["signal_score"], [], None
        bands = {"low": 0.7, "mid": 1.0, "high": 1.2}
        d = rws.size_b2_confidence(ev, feat, st, bands=bands)
        return _f_or_none(d.get("notional")), [], [], None
    if formula_id == FORMULA_OFFLINE_B3_DD:
        dd = _f_or_none(inputs.get("account_drawdown"))
        if dd is None:
            return None, ["account_drawdown"], [], None
        # Apply documented B3 scales from offline module constants when present.
        scales = getattr(rws, "B3_SCALES", None)
        mild, deep = 0.85, 0.70
        if scales and isinstance(scales, (list, tuple)) and scales:
            first = scales[0]
            if isinstance(first, dict):
                mild = float(first.get("mild", mild))
                deep = float(first.get("deep", deep))
        if dd >= 0.10:
            factor = deep
        elif dd >= 0.05:
            factor = mild
        else:
            factor = 1.0
        n = rws._clamp_notional(float(base_notional) * factor, cash)
        return round(float(n), 6), [], [], None
    return None, missing, [], "unknown_offline_formula"


def build_prefill_inputs(
    *,
    price: float | None,
    cash_available: float | None,
    account_equity: float | None,
    portfolio_value: float | None = None,
    current_position_quantity: float | None = None,
    current_position_notional: float | None = None,
    company_budget: float | None = None,
    tranche_budget: float | None = None,
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
    stop_price: float | None = None,
    stop_distance: float | None = None,
    total_exposure: float | None = None,
    ticker_exposure: float | None = None,
    sector_exposure: float | None = None,
    region_exposure: float | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "price": _f_or_none(price),
        "cash_available": _f_or_none(cash_available),
        "account_equity": _f_or_none(account_equity),
        "portfolio_value": _f_or_none(portfolio_value if portfolio_value is not None else account_equity),
        "current_position_quantity": _f_or_none(current_position_quantity),
        "current_position_notional": _f_or_none(current_position_notional),
        "company_budget": _f_or_none(company_budget),
        "tranche_budget": _f_or_none(tranche_budget),
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
        "stop_price": _f_or_none(stop_price),
        "stop_distance": _f_or_none(stop_distance),
        "total_exposure": _f_or_none(total_exposure),
        "ticker_exposure": _f_or_none(ticker_exposure),
        "sector_exposure": _f_or_none(sector_exposure),
        "region_exposure": _f_or_none(region_exposure),
        "evaluated_at": evaluated_at or _now(),
    }


def evaluate_shadow_sizing(
    *,
    identity: dict[str, Any],
    inputs: dict[str, Any],
    executed_formula_id: str,
    executed_quantity: float | None,
    executed_notional: float | None,
    portfolio_before: dict[str, Any] | None = None,
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Build full inventory of shadow evaluations for one entry fill.
    Idempotent: if existing evaluations present for same evaluation_ids, reuse them.
    """
    if existing:
        # Immutable reuse
        return [dict(x) for x in existing if isinstance(x, dict)]

    path = _s(identity.get("entry_type")).upper() or "INITIAL"
    arm = _s(identity.get("strategy_arm")).upper()
    out: list[dict[str, Any]] = []

    def add_executed(formula_id: str, source: str, notional: float | None) -> None:
        rec = _base_record(
            identity=identity,
            formula_id=formula_id,
            formula_source_path=source,
            formula_role=ROLE_EXECUTED,
            formula_status=FS_ACTIVE_EXECUTED,
            executed_formula=True,
            eligible_for_path=True,
            inputs=inputs,
            executed_quantity=executed_quantity,
            executed_notional=executed_notional,
        )
        # Executed formula: shadow recommendation mirrors executed path recommendation intent
        use_n = notional if notional is not None else executed_notional
        out.append(
            _finalize_result(
                rec,
                notional=use_n,
                price=inputs.get("price"),
                stop_distance=inputs.get("stop_distance"),
                equity=inputs.get("account_equity"),
                evaluation_status=ES_COMPLETE if use_n is not None else ES_PARTIAL,
                flags=["EXECUTED_FORMULA_RECORD"],
            )
        )

    # --- Executed formula record ---
    if executed_formula_id == FORMULA_V1_DEPLOYABLE_25PCT:
        n, miss, inv = eval_v1_deployable(inputs)
        add_executed(FORMULA_V1_DEPLOYABLE_25PCT, SOURCE_V1, n if not miss else executed_notional)
    elif executed_formula_id == FORMULA_V2_INITIAL_BUDGET_TRANCHE:
        n, miss, inv = eval_v2_tranche(inputs, entry_type="INITIAL")
        add_executed(FORMULA_V2_INITIAL_BUDGET_TRANCHE, SOURCE_V2_BUY_POLICY, n if not miss else executed_notional)
    elif executed_formula_id == FORMULA_V2_ADD_BUDGET_TRANCHE:
        n, miss, inv = eval_v2_tranche(inputs, entry_type="ADD")
        add_executed(FORMULA_V2_ADD_BUDGET_TRANCHE, SOURCE_V2_BUY_POLICY, n if not miss else executed_notional)
    elif executed_formula_id == FORMULA_V2_REENTRY_BUDGET_TRANCHE:
        n, miss, inv = eval_v2_tranche(inputs, entry_type="REENTRY")
        add_executed(FORMULA_V2_REENTRY_BUDGET_TRANCHE, SOURCE_V2_BUY_POLICY, n if not miss else executed_notional)
    else:
        add_executed(executed_formula_id, "unknown", executed_notional)

    def add_shadow(
        formula_id: str,
        source: str,
        notional: float | None,
        missing: list[str],
        invalid: list[str],
        *,
        eligible: bool = True,
        exclusion: str | None = None,
        formula_status: str = FS_ACTIVE_SHADOW,
    ) -> None:
        if formula_id == executed_formula_id:
            return  # already recorded as executed
        rec = _base_record(
            identity=identity,
            formula_id=formula_id,
            formula_source_path=source,
            formula_role=ROLE_SHADOW if formula_status != FS_OFFLINE_ONLY else ROLE_OFFLINE_REFERENCE,
            formula_status=formula_status,
            executed_formula=False,
            eligible_for_path=eligible,
            inputs=inputs,
            executed_quantity=executed_quantity,
            executed_notional=executed_notional,
        )
        if not eligible:
            out.append(
                _finalize_result(
                    rec,
                    notional=None,
                    price=inputs.get("price"),
                    stop_distance=inputs.get("stop_distance"),
                    equity=inputs.get("account_equity"),
                    evaluation_status=ES_NOT_APPLICABLE,
                    exclusion_reason=exclusion or "not_eligible_for_path",
                    flags=["PATH_INCOMPATIBLE"],
                )
            )
            return
        if missing and notional is None:
            out.append(
                _finalize_result(
                    rec,
                    notional=None,
                    price=inputs.get("price"),
                    stop_distance=inputs.get("stop_distance"),
                    equity=inputs.get("account_equity"),
                    evaluation_status=ES_NOT_EVALUATED if formula_status == FS_OFFLINE_ONLY else ES_PARTIAL,
                    missing=missing,
                    invalid=invalid,
                    exclusion_reason=exclusion,
                    flags=["MISSING_PREFILL_INPUTS"],
                )
            )
            return
        status = ES_COMPLETE if not missing and not invalid else ES_PARTIAL
        out.append(
            _finalize_result(
                rec,
                notional=notional,
                price=inputs.get("price"),
                stop_distance=inputs.get("stop_distance"),
                equity=inputs.get("account_equity"),
                evaluation_status=status,
                missing=missing,
                invalid=invalid,
                exclusion_reason=exclusion,
            )
        )

    # --- Cross-path shadows ---
    # V1 formula as shadow (inventory always; NA when tranche state required)
    if executed_formula_id != FORMULA_V1_DEPLOYABLE_25PCT:
        if path == "ADD":
            out.append(
                _na(
                    identity,
                    inputs,
                    formula_id=FORMULA_V1_DEPLOYABLE_25PCT,
                    source=SOURCE_V1,
                    executed_quantity=executed_quantity,
                    executed_notional=executed_notional,
                    reason="v1_deployable_does_not_model_company_budget_remaining_or_tranche_state",
                )
            )
        else:
            n, miss, inv = eval_v1_deployable(inputs)
            add_shadow(FORMULA_V1_DEPLOYABLE_25PCT, SOURCE_V1, n, miss, inv)

    # V2 INITIAL as shadow
    if executed_formula_id != FORMULA_V2_INITIAL_BUDGET_TRANCHE:
        if path == "ADD":
            out.append(
                _na(
                    identity,
                    inputs,
                    formula_id=FORMULA_V2_INITIAL_BUDGET_TRANCHE,
                    source=SOURCE_V2_BUY_POLICY,
                    executed_quantity=executed_quantity,
                    executed_notional=executed_notional,
                    reason="v2_initial_formula_not_applicable_on_add_tranche_path",
                )
            )
        elif path in {"INITIAL", "REENTRY"} or arm == "V1":
            n, miss, inv = eval_v2_tranche(inputs, entry_type="INITIAL")
            add_shadow(FORMULA_V2_INITIAL_BUDGET_TRANCHE, SOURCE_V2_BUY_POLICY, n, miss, inv)

    # V2 ADD as shadow
    if executed_formula_id != FORMULA_V2_ADD_BUDGET_TRANCHE:
        if path != "ADD":
            out.append(
                _na(
                    identity,
                    inputs,
                    formula_id=FORMULA_V2_ADD_BUDGET_TRANCHE,
                    source=SOURCE_V2_BUY_POLICY,
                    executed_quantity=executed_quantity,
                    executed_notional=executed_notional,
                    reason="v2_add_formula_requires_open_cycle_remaining_budget",
                )
            )
        else:
            n, miss, inv = eval_v2_tranche(inputs, entry_type="ADD")
            add_shadow(FORMULA_V2_ADD_BUDGET_TRANCHE, SOURCE_V2_BUY_POLICY, n, miss, inv)

    # V2 REENTRY formula id as shadow when not executed
    if executed_formula_id != FORMULA_V2_REENTRY_BUDGET_TRANCHE:
        if path != "REENTRY":
            out.append(
                _na(
                    identity,
                    inputs,
                    formula_id=FORMULA_V2_REENTRY_BUDGET_TRANCHE,
                    source=SOURCE_V2_BUY_POLICY,
                    executed_quantity=executed_quantity,
                    executed_notional=executed_notional,
                    reason="v2_reentry_formula_not_applicable_outside_reentry_path",
                )
            )
        else:
            n, miss, inv = eval_v2_tranche(inputs, entry_type="REENTRY")
            add_shadow(FORMULA_V2_REENTRY_BUDGET_TRANCHE, SOURCE_V2_BUY_POLICY, n, miss, inv)

    # LIVE equal-split shadow
    if path == "ADD":
        out.append(
            _na(
                identity,
                inputs,
                formula_id=FORMULA_LIVE_EQUAL_SPLIT,
                source=SOURCE_LIVE,
                executed_quantity=executed_quantity,
                executed_notional=executed_notional,
                reason="live_equal_split_does_not_model_v2_tranche_accumulation",
            )
        )
    else:
        n, miss, inv = eval_live_equal_split(inputs)
        add_shadow(FORMULA_LIVE_EQUAL_SPLIT, SOURCE_LIVE, n, miss, inv)

    # Canonical paper confidence
    n, miss, inv = eval_canonical_paper_confidence(inputs)
    add_shadow(FORMULA_CANON_PAPER_CONF, SOURCE_CANON_PAPER, n, miss, inv)

    # core/risk — SHADOW only via adapter
    n, miss, inv, excl = eval_core_risk_adapter(
        ticker=_s(identity.get("ticker")),
        inputs=inputs,
        portfolio_before=portfolio_before,
        path=path,
    )
    if excl and n is None and not miss:
        out.append(
            _na(
                identity,
                inputs,
                formula_id=FORMULA_CORE_RISK,
                source=SOURCE_CORE_RISK,
                executed_quantity=executed_quantity,
                executed_notional=executed_notional,
                reason=excl,
            )
        )
    else:
        add_shadow(
            FORMULA_CORE_RISK,
            SOURCE_CORE_RISK,
            n,
            miss,
            inv,
            eligible=excl is None or n is not None,
            exclusion=excl,
        )

    # Offline risk-weighted references (never claim edge)
    base = executed_notional
    for fid in (FORMULA_OFFLINE_B1_VOL, FORMULA_OFFLINE_B2_CONF, FORMULA_OFFLINE_B3_DD):
        n, miss, inv, excl = eval_offline_risk_weighted(formula_id=fid, inputs=inputs, base_notional=base)
        rec = _base_record(
            identity=identity,
            formula_id=fid,
            formula_source_path=SOURCE_OFFLINE_RW,
            formula_role=ROLE_OFFLINE_REFERENCE,
            formula_status=FS_OFFLINE_ONLY,
            executed_formula=False,
            eligible_for_path=True,
            inputs=inputs,
            executed_quantity=executed_quantity,
            executed_notional=executed_notional,
        )
        if n is None:
            out.append(
                _finalize_result(
                    rec,
                    notional=None,
                    price=inputs.get("price"),
                    stop_distance=inputs.get("stop_distance"),
                    equity=inputs.get("account_equity"),
                    evaluation_status=ES_NOT_EVALUATED,
                    missing=miss,
                    invalid=inv,
                    exclusion_reason=excl or OFFLINE_NO_EDGE_NOTE,
                    flags=["OFFLINE_REFERENCE_ONLY", OFFLINE_NO_EDGE_NOTE],
                )
            )
        else:
            fr = _finalize_result(
                rec,
                notional=n,
                price=inputs.get("price"),
                stop_distance=inputs.get("stop_distance"),
                equity=inputs.get("account_equity"),
                evaluation_status=ES_PARTIAL if miss else ES_COMPLETE,
                missing=miss,
                invalid=inv,
                exclusion_reason=OFFLINE_NO_EDGE_NOTE,
                flags=["OFFLINE_REFERENCE_ONLY", OFFLINE_NO_EDGE_NOTE, "NOT_PROMOTION_EVIDENCE"],
            )
            out.append(fr)

    # Dedup by evaluation_id (deterministic)
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in out:
        eid = _s(row.get("evaluation_id"))
        if eid in seen:
            continue
        seen.add(eid)
        deduped.append(row)
    return deduped


def attach_shadow_evaluations(snapshot: dict[str, Any], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach evaluations immutably; do not overwrite existing."""
    snap = dict(snapshot)
    existing = snap.get("shadow_sizing_evaluations")
    if isinstance(existing, list) and existing:
        return snap
    snap["shadow_sizing_evaluations"] = list(evaluations)
    snap["shadow_sizing_experiment_id"] = EXPERIMENT_ID
    snap["shadow_sizing_schema_version"] = SCHEMA_VERSION
    complete = sum(1 for e in evaluations if e.get("evaluation_status") == ES_COMPLETE)
    partial = sum(1 for e in evaluations if e.get("evaluation_status") == ES_PARTIAL)
    na = sum(1 for e in evaluations if e.get("evaluation_status") == ES_NOT_APPLICABLE)
    snap["shadow_sizing_observability_status"] = (
        "COMPLETE" if complete > 0 else ("PARTIAL" if partial > 0 else "NOT_EVALUATED")
    )
    snap["shadow_formula_count"] = len(evaluations)
    snap["shadow_complete_evaluations"] = complete
    snap["shadow_partial_evaluations"] = partial
    snap["shadow_not_applicable_evaluations"] = na
    return snap


def summarize_shadow_for_attribution(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate shadow evaluations across entry snapshots for a cycle."""
    evals: list[dict[str, Any]] = []
    for s in snapshots:
        if not isinstance(s, dict):
            continue
        for e in s.get("shadow_sizing_evaluations") or []:
            if isinstance(e, dict):
                evals.append(e)
    if not evals:
        return {
            "shadow_sizing_observability_status": SHADOW_DATA_NOT_PERSISTED,
            "shadow_sizing_evaluations": [],
            "shadow_formula_count": 0,
            "shadow_complete_evaluations": 0,
            "shadow_partial_evaluations": 0,
            "shadow_not_applicable_evaluations": 0,
            "shadow_quantity_deltas": [],
            "shadow_notional_deltas": [],
            "shadow_risk_deltas": [],
            "hypothetical_gross_pnl": "REQUIRES_COUNTERFACTUAL",
            "hypothetical_net_pnl": "REQUIRES_COUNTERFACTUAL",
        }

    q_deltas = []
    n_deltas = []
    r_deltas = []
    for e in evals:
        if e.get("executed_formula"):
            continue
        if e.get("quantity_delta") is not None:
            q_deltas.append(
                {
                    "formula_id": e.get("formula_id"),
                    "execution_id": e.get("execution_id"),
                    "quantity_delta": e.get("quantity_delta"),
                    "quantity_delta_pct": e.get("quantity_delta_pct"),
                }
            )
        if e.get("notional_delta") is not None:
            n_deltas.append(
                {
                    "formula_id": e.get("formula_id"),
                    "execution_id": e.get("execution_id"),
                    "notional_delta": e.get("notional_delta"),
                    "notional_delta_pct": e.get("notional_delta_pct"),
                }
            )
        if e.get("hypothetical_initial_risk_amount") is not None:
            r_deltas.append(
                {
                    "formula_id": e.get("formula_id"),
                    "execution_id": e.get("execution_id"),
                    "hypothetical_initial_risk_amount": e.get("hypothetical_initial_risk_amount"),
                    "comparability_status": e.get("comparability_status"),
                }
            )

    complete = sum(1 for e in evals if e.get("evaluation_status") == ES_COMPLETE)
    partial = sum(1 for e in evals if e.get("evaluation_status") == ES_PARTIAL)
    na = sum(1 for e in evals if e.get("evaluation_status") == ES_NOT_APPLICABLE)
    status = "COMPLETE" if complete > 0 else ("PARTIAL" if partial > 0 else "NOT_EVALUATED")
    return {
        "shadow_sizing_observability_status": status,
        "shadow_sizing_evaluations": evals,
        "shadow_formula_count": len(evals),
        "shadow_complete_evaluations": complete,
        "shadow_partial_evaluations": partial,
        "shadow_not_applicable_evaluations": na,
        "shadow_quantity_deltas": q_deltas,
        "shadow_notional_deltas": n_deltas,
        "shadow_risk_deltas": r_deltas,
        "shadow_sizing_experiment_id": EXPERIMENT_ID,
        "hypothetical_gross_pnl": "REQUIRES_COUNTERFACTUAL",
        "hypothetical_net_pnl": "REQUIRES_COUNTERFACTUAL",
        "note": "Static entry comparison only; alternate path PnL requires counterfactual engine.",
    }


__all__ = [
    "SCHEMA_VERSION",
    "EXPERIMENT_ID",
    "SHADOW_DATA_NOT_PERSISTED",
    "evaluation_id",
    "build_prefill_inputs",
    "evaluate_shadow_sizing",
    "attach_shadow_evaluations",
    "summarize_shadow_for_attribution",
    "FORMULA_LIVE_EQUAL_SPLIT",
    "FORMULA_CORE_RISK",
    "FORMULA_OFFLINE_B1_VOL",
    "FORMULA_OFFLINE_B2_CONF",
    "FORMULA_OFFLINE_B3_DD",
    "FORMULA_CANON_PAPER_CONF",
]
