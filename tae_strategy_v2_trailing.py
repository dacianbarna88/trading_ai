"""Strategy V2 PAPER trailing helpers (isolated from LIVE core/trailing SSOT).

Restored from validated x12b trailing logic for V2 exit policy only.
Does NOT replace core/trailing.py (LIVE update_trailing_state remains HEAD SSOT).
LIVE_PROFIT_TRAILING_5_2_ENABLED remains False conceptually — this module is PAPER V2 only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# --- Canonical trailing policy (SSOT) ---
STOP_LOSS_PCT = -3.0
TRAILING_ACTIVATE_PCT = 5.0
TRAILING_DISTANCE_PCT = 2.0
# Legacy name retained for importers; floor is no longer applied to Trailing_Stop.
# Stop is always Highest_Price * (1 - TRAILING_DISTANCE_PCT/100).
MIN_LOCKED_PROFIT_PCT = 0.0

# LIVE feature flag — keep False until explicit promotion. Path is repaired for 5/2.
LIVE_PROFIT_TRAILING_5_2_ENABLED = False

TRAILING_SELL_REASON = "PROFIT TRAILING -2% FROM PEAK"
V2_PROFIT_TRAILING_REASON = "V2_PROFIT_TRAILING_5_2"
V2_STOP_LOSS_REASON = "V2_STOP_LOSS_UNARMED"
TRAILING_COLUMNS = ("Highest_Price", "Trailing_Active", "Trailing_Stop")
V2_TRAILING_PERSIST_KEYS = (
    "trailing_armed",
    "highest_price",
    "trailing_stop",
    "armed_at",
    "updated_at",
)


@dataclass(frozen=True)
class TrailingState:
    highest_price: float
    trailing_active: bool
    trailing_stop: float | None = None
    armed_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class ExitDecision:
    action: str  # HOLD | SELL_STOP_LOSS | SELL_TRAILING
    reason: str | None
    state: TrailingState
    pnl_pct: float


def pnl_percent(avg_price: float, current_price: float) -> float:
    if not avg_price:
        return 0.0
    return ((float(current_price) - float(avg_price)) / float(avg_price)) * 100.0


def _is_valid_price(value: Any) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and x > 0.0


def initial_trailing_state(avg_price: float) -> TrailingState:
    price = float(avg_price) if _is_valid_price(avg_price) else 0.0
    return TrailingState(highest_price=price, trailing_active=False, trailing_stop=None)


def trailing_stop_from_peak(highest_price: float, *, distance_pct: float = TRAILING_DISTANCE_PCT) -> float:
    return float(highest_price) * (1.0 - float(distance_pct) / 100.0)


def trailing_state_from_mapping(mapping: dict[str, Any] | None, avg_price: float) -> TrailingState:
    """Read V2-style persistence fields (trailing_armed / highest_price / …)."""
    m = mapping or {}
    avg = float(avg_price) if _is_valid_price(avg_price) else 0.0
    highest = m.get("highest_price", m.get("Highest_Price", avg))
    if not _is_valid_price(highest):
        highest = avg
    else:
        highest = max(float(highest), avg)
    armed_raw = m.get("trailing_armed", m.get("Trailing_Active", False))
    if isinstance(armed_raw, str):
        trailing_active = armed_raw.strip().upper() in {"TRUE", "1", "YES"}
    else:
        trailing_active = bool(armed_raw)
    stop_raw = m.get("trailing_stop", m.get("Trailing_Stop"))
    trailing_stop = float(stop_raw) if _is_valid_price(stop_raw) else None
    return TrailingState(
        highest_price=highest,
        trailing_active=trailing_active,
        trailing_stop=trailing_stop,
        armed_at=(str(m["armed_at"]) if m.get("armed_at") not in (None, "") else None),
        updated_at=(str(m["updated_at"]) if m.get("updated_at") not in (None, "") else None),
    )


def persist_fields_from_decision(
    prior: TrailingState,
    decision: ExitDecision,
    *,
    now_iso: str,
) -> dict[str, Any]:
    """Canonical V2 persistence payload for cycle / position JSON."""
    newly_armed = decision.state.trailing_active and not prior.trailing_active
    armed_at = prior.armed_at
    if decision.state.trailing_active:
        armed_at = armed_at or (now_iso if newly_armed else prior.armed_at) or now_iso
    else:
        armed_at = None
    return {
        "trailing_armed": bool(decision.state.trailing_active),
        "highest_price": round(float(decision.state.highest_price), 6),
        "trailing_stop": (
            None
            if decision.state.trailing_stop is None
            else round(float(decision.state.trailing_stop), 6)
        ),
        "armed_at": armed_at,
        "updated_at": now_iso,
    }


def clear_v2_trailing_persist_fields(mapping: dict[str, Any]) -> dict[str, Any]:
    out = dict(mapping)
    out["trailing_armed"] = False
    out["highest_price"] = None
    out["trailing_stop"] = None
    out["armed_at"] = None
    out["updated_at"] = out.get("updated_at")
    return out


def evaluate_position_exit(
    avg_price: float,
    current_price: float,
    state: TrailingState,
    *,
    stop_loss_pct: float = STOP_LOSS_PCT,
    activate_pct: float = TRAILING_ACTIVATE_PCT,
    trail_distance_pct: float = TRAILING_DISTANCE_PCT,
    min_locked_profit_pct: float = MIN_LOCKED_PROFIT_PCT,  # noqa: ARG001 — retained for API compat
    sell_reason: str | None = None,
    now_iso: str | None = None,
) -> ExitDecision:
    """Arm / ratchet / trailing sell; entry stop only while unarmed."""
    if not _is_valid_price(avg_price) or not _is_valid_price(current_price):
        return ExitDecision(
            action="HOLD",
            reason=None,
            state=state,
            pnl_pct=0.0,
        )

    avg = float(avg_price)
    price = float(current_price)
    pnl_pct = pnl_percent(avg, price)
    reason_trail = sell_reason or TRAILING_SELL_REASON

    trailing_active = bool(state.trailing_active)
    prior_highest = float(state.highest_price) if _is_valid_price(state.highest_price) else avg
    armed_at = state.armed_at
    stamp = now_iso or state.updated_at

    # Arm / ratchet peak first so an armed winner is never converted to entry stop-loss.
    highest = max(prior_highest, price, avg)
    if not trailing_active and pnl_pct >= float(activate_pct):
        trailing_active = True
        armed_at = armed_at or stamp

    if trailing_active:
        new_stop = trailing_stop_from_peak(highest, distance_pct=trail_distance_pct)
        if state.trailing_stop is not None and _is_valid_price(state.trailing_stop):
            new_stop = max(new_stop, float(state.trailing_stop))
        updated = TrailingState(
            highest_price=highest,
            trailing_active=True,
            trailing_stop=new_stop,
            armed_at=armed_at,
            updated_at=stamp,
        )
        if price <= new_stop + 1e-12:
            return ExitDecision(
                action="SELL_TRAILING",
                reason=reason_trail,
                state=updated,
                pnl_pct=pnl_pct,
            )
        return ExitDecision(action="HOLD", reason=None, state=updated, pnl_pct=pnl_pct)

    # Unarmed: entry stop-loss may fire.
    if pnl_pct <= float(stop_loss_pct):
        return ExitDecision(
            action="SELL_STOP_LOSS",
            reason=f"STOP LOSS {pnl_pct:.2f}%",
            state=state,
            pnl_pct=pnl_pct,
        )

    updated = TrailingState(
        highest_price=highest,
        trailing_active=False,
        trailing_stop=None,
        armed_at=None,
        updated_at=stamp,
    )
    return ExitDecision(action="HOLD", reason=None, state=updated, pnl_pct=pnl_pct)

