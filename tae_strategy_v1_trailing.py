"""Strategy V1 PAPER trailing-stop exit (isolated parallel-paper arm only).

Reuses the generic V2 trailing primitives (tae_strategy_v2_trailing.py) —
that module has no V2-specific coupling; it operates on plain floats and a
state mapping. This module only adds V1-specific reason strings and adapts
the ExitDecision back into the (action, reason) tuple shape V1's runtime
call site expects (previously produced by
tae_strategy_v2_routing.v1_mechanical_exit_action).

Scope: replaces V1's fixed +5%/-3% bracket with an armed trailing stop
(arm at +5% unrealized, trail 2% off the peak once armed) so winners are not
capped at exactly +5%. The unarmed entry stop-loss stays a caller-supplied
percent (default -3%, matching V1's prior behavior; Phase 3 makes this
volatility-adjusted per ticker).

This is the isolated V1 parallel-paper arm ONLY — canonical live_bot.py is
untouched.
"""

from __future__ import annotations

from typing import Any

from tae_strategy_v2_trailing import (
    STOP_LOSS_PCT as _DEFAULT_STOP_LOSS_PCT,
    TRAILING_ACTIVATE_PCT,
    TRAILING_DISTANCE_PCT,
    evaluate_position_exit,
    persist_fields_from_decision,
    trailing_state_from_mapping,
)

V1_PROFIT_TRAILING_REASON = "V1_PROFIT_TRAILING_5_2"
V1_STOP_LOSS_REASON = "STRATEGY_STOP_V1"


def v1_trailing_exit_action(
    pos: dict[str, Any],
    *,
    avg_price: float,
    current_price: float,
    now_iso: str,
    stop_loss_pct: float = _DEFAULT_STOP_LOSS_PCT,
) -> tuple[str | None, str | None]:
    """Evaluate V1's trailing-stop exit and persist trailing state onto `pos`.

    Mutates `pos` in place (trailing_armed/highest_price/trailing_stop/
    armed_at/updated_at) on every call, mirroring V2's per-tick persistence
    (tae_parallel_paper_runtime.py's _run_v2_arm). Returns an (action, reason)
    tuple shaped like the old v1_mechanical_exit_action: a truthy action means
    the caller should sell; (None, None) means hold.
    """
    prior_state = trailing_state_from_mapping(pos, avg_price)
    decision = evaluate_position_exit(
        avg_price,
        current_price,
        prior_state,
        stop_loss_pct=stop_loss_pct,
        activate_pct=TRAILING_ACTIVATE_PCT,
        trail_distance_pct=TRAILING_DISTANCE_PCT,
        sell_reason=V1_PROFIT_TRAILING_REASON,
        now_iso=now_iso,
    )
    patch = persist_fields_from_decision(prior_state, decision, now_iso=now_iso)
    pos.update(patch)

    if decision.action == "SELL_STOP_LOSS":
        return "SELL_STOP_LOSS", V1_STOP_LOSS_REASON
    if decision.action == "SELL_TRAILING":
        return "SELL_TRAILING", V1_PROFIT_TRAILING_REASON
    return None, None
