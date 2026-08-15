#!/usr/bin/env python3
"""
Explicit Strategy V1 / V2 exit routing.

Uses strategy_version / cycle_id only — never implicit ticker detection.
When STRATEGY_V2_ENABLED is false, V2 payloads must not mutate capital.
"""

from __future__ import annotations

from typing import Any

from tae_strategy_v2_config import is_strategy_v2_enabled
from tae_strategy_v2_foundation import STRATEGY_VERSION

V1_STOP_LOSS_PCT = -3.0
V1_TAKE_PROFIT_PCT = 5.0


def _s(v: Any) -> str:
    return str(v or "").strip()


def is_strategy_v2_position(
    position: dict[str, Any] | None = None,
    *,
    cycle: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> bool:
    """True only with explicit V2 markers."""
    pos = position or {}
    cyc = cycle or {}
    dec = decision or {}
    v2 = dec.get("strategy_v2") if isinstance(dec.get("strategy_v2"), dict) else {}

    if _s(pos.get("strategy_version")).upper() == STRATEGY_VERSION:
        return True
    if _s(pos.get("strategy_v2_cycle_id")):
        return True
    if _s(cyc.get("strategy_version")).upper() == STRATEGY_VERSION and _s(cyc.get("cycle_id")):
        return True
    if _s(cyc.get("cycle_id")) and _s(cyc.get("cycle_id")).startswith("V2CYC-"):
        return True
    if _s(dec.get("strategy_version")).upper() == STRATEGY_VERSION:
        return True
    if _s(v2.get("strategy_version")).upper() == STRATEGY_VERSION:
        return True
    if _s(dec.get("strategy_v2_cycle_id")) or _s(v2.get("cycle_id")):
        return True
    return False


def should_apply_v1_mechanical_stop(
    *,
    position: dict[str, Any] | None = None,
    cycle: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> bool:
    """V1 mechanical −3% / +5% applies only to non-V2 positions."""
    if is_strategy_v2_position(position, cycle=cycle, decision=decision):
        return False
    return True


def should_apply_v1_trailing(
    *,
    position: dict[str, Any] | None = None,
    cycle: dict[str, Any] | None = None,
) -> bool:
    return should_apply_v1_mechanical_stop(position=position, cycle=cycle)


def v1_mechanical_exit_action(
    *,
    avg_price: float,
    current_price: float,
    stop_loss_pct: float = V1_STOP_LOSS_PCT,
    take_profit_pct: float = V1_TAKE_PROFIT_PCT,
) -> tuple[str | None, str | None]:
    try:
        avg = float(avg_price)
        px = float(current_price)
    except (TypeError, ValueError):
        return None, None
    if avg <= 0 or px <= 0:
        return None, None
    pnl_pct = ((px - avg) / avg) * 100.0
    if pnl_pct <= float(stop_loss_pct):
        return "SELL_STOP_LOSS", "STRATEGY_STOP_V1"
    if pnl_pct >= float(take_profit_pct):
        return "SELL_TAKE_PROFIT", "STRATEGY_TAKE_PROFIT_V1"
    return None, None


def v2_capital_mutation_allowed(*, enabled_override: bool | None = None) -> bool:
    return is_strategy_v2_enabled(override=enabled_override)


def route_exit_owner(
    *,
    position: dict[str, Any] | None = None,
    cycle: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
) -> str:
    if is_strategy_v2_position(position, cycle=cycle, decision=decision):
        return "V2_EXIT_POLICY"
    return "V1_MECHANICAL"


RISK_RULE_INVENTORY = {
    "STRATEGY_STOP_V1": [
        {
            "rule": "STOP_LOSS_PCT",
            "value": -3.0,
            "owners": ["core/trailing.py", "live_bot.py", "tae_strategy_v2_routing.py"],
        },
        {
            "rule": "TAKE_PROFIT_PCT / TRAILING_ACTIVATE",
            "value": 5.0,
            "owners": ["core/trailing.py", "live_bot.py", "tae_strategy_v2_routing.py"],
        },
        {"rule": "TRAILING_DISTANCE_PCT", "value": 2.0, "owners": ["core/trailing.py"]},
        {"rule": "MIN_LOCKED_PROFIT_PCT", "value": 0.0, "owners": ["core/trailing.py"]},
    ],
    "HARD_RISK_SAFETY": [
        {
            "rule": "HARD_CRITICAL_STOP_-5",
            "value": -5.0,
            "owners": ["hard_risk_guardian.py", "tae_strategy_v2_hard_risk_adapter.py"],
        },
        {"rule": "INVALID_MARK / STALE_MARK_SEVERE", "owners": ["tae_strategy_v2_hard_risk_adapter.py"]},
        {
            "rule": "ACCOUNTING_CORRUPTION",
            "owners": ["tae_strategy_v2_hard_risk_adapter.py", "tae_strategy_v2_exit_policy.py"],
        },
        {"rule": "GAP_EXTREME", "owners": ["tae_strategy_v2_hard_risk_adapter.py"]},
    ],
    "THESIS_INVALIDATION": [
        {"rule": "candidate_eligible=False", "owners": ["tae_strategy_v2_exit_policy.py"]},
        {"rule": "session_valid=False", "owners": ["tae_strategy_v2_exit_policy.py"]},
    ],
    "PORTFOLIO_LIMIT": [
        {
            "rule": "max_tranches",
            "value": 5,
            "owners": ["tae_strategy_v2_buy_policy.py", "tae_strategy_v2_exit_policy.py"],
        },
        {
            "rule": "company_budget / FULLY_ALLOCATED",
            "owners": ["tae_strategy_v2_buy_policy.py", "tae_strategy_v2_exit_policy.py"],
        },
        {"rule": "MIN_CASH_RESERVE_USD", "value": 500.0, "owners": ["tae_strategy_v2_config.py"]},
    ],
    "NOTE": (
        "Guardian HARD_STOP_LOSS_-3 is STRATEGY_STOP_V1_ONLY for V2 via adapter. "
        "It is not dual-classed as CRITICAL_HARD_RISK for V2."
    ),
}
