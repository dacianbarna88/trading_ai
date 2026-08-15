#!/usr/bin/env python3
"""
Strategy V2 hard-risk adapter — classify guardian output for V2 cycles.

Separates:
  SAFE
  STRATEGY_STOP_V1_ONLY   — guardian STOP_LOSS_BREACHED (−3%); V2 continues
  PRICE_DRAWDOWN_INFORMATIONAL — CRITICAL_LOSS (−5% price vs avg); audit-only for V2
  CRITICAL_HARD_RISK      — non-price critical (exposure breach, extreme gap)
  DATA_SAFETY_BLOCK       — invalid/NaN mark, severe stale, accounting corruption

Price percentage drawdown (−3% / −5%) must not veto ADD, STOP accumulation,
or CLOSE a V2 cycle. Non-price integrity blocks remain authoritative.
"""

from __future__ import annotations

import math
from typing import Any

from hard_risk_guardian import CRITICAL_LIMIT, STOP_LIMIT, evaluate_position_risk

CLASS_SAFE = "SAFE"
CLASS_STRATEGY_STOP_V1_ONLY = "STRATEGY_STOP_V1_ONLY"
CLASS_PRICE_DRAWDOWN_INFO = "PRICE_DRAWDOWN_INFORMATIONAL"
CLASS_CRITICAL = "CRITICAL_HARD_RISK"
CLASS_DATA_SAFETY = "DATA_SAFETY_BLOCK"

# Price-percentage reasons (informational for V2 accumulation / exit)
PRICE_DRAWDOWN_REASONS = frozenset(
    {
        "HARD_CRITICAL_STOP_-5",
        "HARD_STOP_LOSS_-3",
        "CRITICAL_LOSS",
        "STOP_LOSS_BREACHED",
        "PRICE_DRAWDOWN_INFORMATIONAL",
    }
)

# Non-price critical reasons that may still block capital / require close
NON_PRICE_CRITICAL_REASONS = frozenset(
    {
        "EXPOSURE_BREACH",
        "GAP_EXTREME",
    }
)

# Exact mapping documented for the report
RULE_MAP = {
    "HARD_STOP_LOSS_-3": CLASS_STRATEGY_STOP_V1_ONLY,
    "HARD_CRITICAL_STOP_-5": CLASS_PRICE_DRAWDOWN_INFO,
    "STOP_LOSS_BREACHED": CLASS_STRATEGY_STOP_V1_ONLY,
    "CRITICAL_LOSS": CLASS_PRICE_DRAWDOWN_INFO,
    "INVALID_MARK": CLASS_DATA_SAFETY,
    "STALE_MARK_SEVERE": CLASS_DATA_SAFETY,
    "ACCOUNTING_CORRUPTION": CLASS_DATA_SAFETY,
    "EXPOSURE_BREACH": CLASS_CRITICAL,
    "GAP_EXTREME": CLASS_CRITICAL,
}


def _s(v: Any) -> str:
    return str(v or "").strip()


def _f(v: Any, default: float = float("nan")) -> float:
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return float(default) if not (math.isnan(default) or math.isinf(default)) else float("nan")
        return x
    except (TypeError, ValueError):
        return float("nan")


def is_finite_positive(x: float) -> bool:
    return math.isfinite(x) and x > 0


def is_price_drawdown_class(cls: str) -> bool:
    return _s(cls).upper() in {CLASS_STRATEGY_STOP_V1_ONLY, CLASS_PRICE_DRAWDOWN_INFO}


def is_price_drawdown_reason(reason: str) -> bool:
    return _s(reason).upper() in {r.upper() for r in PRICE_DRAWDOWN_REASONS}


def classify_hard_risk_for_v2(
    *,
    ticker: str = "",
    avg_price: float,
    current_price: float,
    shares: float = 1.0,
    mark_freshness: str = "FRESH",
    mark_age_seconds: float = 0.0,
    mark_max_age_seconds: float = 3600.0,
    accounting_valid: bool = True,
    guardian_result: dict[str, Any] | None = None,
    extreme_gap_pct: float | None = None,
    extreme_gap_threshold_pct: float = 20.0,
) -> dict[str, Any]:
    """
    Classify risk for a Strategy V2 cycle.

    −3% vs avg → STRATEGY_STOP_V1_ONLY (informational; V2 may ADD).
    −5% vs avg → PRICE_DRAWDOWN_INFORMATIONAL (audit-only; no STOP/CLOSE/ADD veto).
    Non-price CRITICAL (exposure / extreme gap) retained as blocking.
    """
    ticker = _s(ticker).upper()
    avg = _f(avg_price)
    px = _f(current_price)
    sh = _f(shares, 0.0)

    if not accounting_valid:
        return _payload(
            CLASS_DATA_SAFETY,
            reason="ACCOUNTING_CORRUPTION",
            guardian_status="ACCOUNTING_CORRUPTION",
            pnl_pct=None,
            ticker=ticker,
        )

    if not is_finite_positive(px) or math.isnan(px):
        return _payload(
            CLASS_DATA_SAFETY,
            reason="INVALID_MARK",
            guardian_status="INVALID_MARK",
            pnl_pct=None,
            ticker=ticker,
        )

    freshness = _s(mark_freshness).upper()
    age = _f(mark_age_seconds, 0.0)
    if freshness in {"STALE", "UNKNOWN"} or (math.isfinite(age) and age > float(mark_max_age_seconds)):
        return _payload(
            CLASS_DATA_SAFETY,
            reason="STALE_MARK_SEVERE",
            guardian_status="STALE_MARK_SEVERE",
            pnl_pct=None,
            ticker=ticker,
        )

    if extreme_gap_pct is not None and abs(float(extreme_gap_pct)) >= float(extreme_gap_threshold_pct):
        return _payload(
            CLASS_CRITICAL,
            reason="GAP_EXTREME",
            guardian_status="GAP_EXTREME",
            pnl_pct=_pnl(avg, px),
            ticker=ticker,
        )

    g = guardian_result
    if g is None and is_finite_positive(avg) and sh > 0:
        g = evaluate_position_risk(ticker or "UNK", avg_price=avg, current_price=px, shares=sh)
    g = g or {}
    status = _s(g.get("status")).upper()
    hard_rule = _s(g.get("hard_rule")).upper()
    pnl = g.get("pnl_pct")
    if pnl is None:
        pnl = _pnl(avg, px)

    # Non-price critical from guardian (if ever emitted)
    if hard_rule in NON_PRICE_CRITICAL_REASONS or status in NON_PRICE_CRITICAL_REASONS:
        return _payload(
            CLASS_CRITICAL,
            reason=hard_rule or status,
            guardian_status=status or hard_rule,
            pnl_pct=pnl,
            ticker=ticker,
            guardian=g,
        )

    if status == "CRITICAL_LOSS" or hard_rule == "HARD_CRITICAL_STOP_-5":
        return _payload(
            CLASS_PRICE_DRAWDOWN_INFO,
            reason="HARD_CRITICAL_STOP_-5",
            guardian_status=status or "CRITICAL_LOSS",
            pnl_pct=pnl,
            ticker=ticker,
            guardian=g,
        )

    if status == "STOP_LOSS_BREACHED" or hard_rule == "HARD_STOP_LOSS_-3":
        return _payload(
            CLASS_STRATEGY_STOP_V1_ONLY,
            reason="HARD_STOP_LOSS_-3",
            guardian_status=status or "STOP_LOSS_BREACHED",
            pnl_pct=pnl,
            ticker=ticker,
            guardian=g,
        )

    # Explicit numeric fallback if guardian missing status but prices present
    if is_finite_positive(avg) and is_finite_positive(px) and sh > 0:
        p = ((px - avg) / avg) * 100.0
        if p <= CRITICAL_LIMIT:
            return _payload(
                CLASS_PRICE_DRAWDOWN_INFO,
                reason="HARD_CRITICAL_STOP_-5",
                guardian_status="CRITICAL_LOSS",
                pnl_pct=p,
                ticker=ticker,
            )
        if p <= STOP_LIMIT:
            return _payload(
                CLASS_STRATEGY_STOP_V1_ONLY,
                reason="HARD_STOP_LOSS_-3",
                guardian_status="STOP_LOSS_BREACHED",
                pnl_pct=p,
                ticker=ticker,
            )

    return _payload(CLASS_SAFE, reason="OK", guardian_status=status or "OK", pnl_pct=pnl, ticker=ticker, guardian=g)


def buy_policy_hard_risk_fields(classification: dict[str, Any]) -> tuple[bool, str]:
    """
    Map adapter class → (hard_risk_active, hard_risk_status) for buy policy.

    Price drawdown (−3% / −5%) never activates buy-policy STOP.
    Only non-price CRITICAL_HARD_RISK activates hard_risk_active.
    """
    cls = _s(classification.get("class")).upper()
    reason = _s(classification.get("reason")).upper()
    if cls == CLASS_CRITICAL and reason in NON_PRICE_CRITICAL_REASONS:
        return True, reason or "CRITICAL_NON_PRICE"
    if cls == CLASS_DATA_SAFETY:
        return False, "DATA_SAFETY_BLOCK"
    if cls == CLASS_STRATEGY_STOP_V1_ONLY:
        return False, "STRATEGY_STOP_V1_ONLY"
    if cls == CLASS_PRICE_DRAWDOWN_INFO:
        return False, "PRICE_DRAWDOWN_INFORMATIONAL"
    # Legacy CRITICAL class with price reason → informational
    if cls == CLASS_CRITICAL and is_price_drawdown_reason(reason):
        return False, "PRICE_DRAWDOWN_INFORMATIONAL"
    return False, "OK"


def fill_time_blocks_add(classification: dict[str, Any]) -> bool:
    """ADD/OPEN capital mutation blocked on DATA_SAFETY or non-price CRITICAL only."""
    cls = _s(classification.get("class")).upper()
    if cls == CLASS_DATA_SAFETY:
        return True
    if cls == CLASS_CRITICAL:
        reason = _s(classification.get("reason")).upper()
        return reason in NON_PRICE_CRITICAL_REASONS
    return False


def requires_close(classification: dict[str, Any]) -> bool:
    """CLOSE required only for non-price critical hard-risk."""
    cls = _s(classification.get("class")).upper()
    if cls != CLASS_CRITICAL:
        return False
    reason = _s(classification.get("reason")).upper()
    return reason in NON_PRICE_CRITICAL_REASONS


def _pnl(avg: float, px: float) -> float | None:
    if not is_finite_positive(avg) or not is_finite_positive(px):
        return None
    return round(((px - avg) / avg) * 100.0, 4)


def _payload(
    cls: str,
    *,
    reason: str,
    guardian_status: str,
    pnl_pct: float | None,
    ticker: str,
    guardian: dict[str, Any] | None = None,
) -> dict[str, Any]:
    price_info = cls in {CLASS_SAFE, CLASS_STRATEGY_STOP_V1_ONLY, CLASS_PRICE_DRAWDOWN_INFO}
    non_price_crit = cls == CLASS_CRITICAL and _s(reason).upper() in NON_PRICE_CRITICAL_REASONS
    return {
        "schema": "tae.strategy_v2.hard_risk_adapter.v2",
        "ticker": ticker,
        "class": cls,
        "reason": reason,
        "guardian_status": guardian_status,
        "pnl_pct": pnl_pct,
        "stop_limit_pct": STOP_LIMIT,
        "critical_limit_pct": CRITICAL_LIMIT,
        "guardian": guardian,
        "allows_v2_hold_add": price_info or (cls == CLASS_CRITICAL and not non_price_crit),
        "requires_close": non_price_crit,
        "blocks_capital_mutation": cls == CLASS_DATA_SAFETY or non_price_crit,
        "price_drawdown_informational": cls == CLASS_PRICE_DRAWDOWN_INFO
        or (cls == CLASS_STRATEGY_STOP_V1_ONLY),
        "audit_only_for_accumulation": cls
        in {CLASS_PRICE_DRAWDOWN_INFO, CLASS_STRATEGY_STOP_V1_ONLY},
    }
