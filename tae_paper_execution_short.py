"""Short-selling + margin accounting primitives — new, isolated capability.

Exists only for the new experimental short/margin arm
(runtime_outputs/parallel_paper/exp_short_margin/), driven by
tae_parallel_paper_short_margin.py. Does NOT modify, get imported by, or
import privately from tae_paper_execution.py's existing long-only
_buy_shares/_sell_shares/validate_trade_record — those hard-assert
fill_shares > 0 and "SELL requires an existing long position" as integrity
gates, not just conventions (tae_paper_execution.py:4005-4009, 4060-4066,
4854), so loosening them in place would risk every V1/V2/V3 long-only trade
record. This module is new and additive; V1/V2/V3 code never calls it.

Position representation: a short position has NEGATIVE `shares`. The
existing valuation math elsewhere in the system (portfolio_mtm,
accounting_pass, validate_portfolio_reconciliation — all reducing to
`cash + sum(shares * price)`-shaped formulas) is sign-agnostic and revalues
a negative-share position correctly, PROVIDED cash was credited (not
debited) at entry — which is exactly what _open_short does below. Verified
directly against tae_parallel_paper_runtime.portfolio_mtm's actual formula
before relying on it (see Phase 5 of the implementation plan).
"""

from __future__ import annotations

import math
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _open_short(
    portfolio: dict[str, Any],
    ticker: str,
    notional: float,
    price: float,
    *,
    margin_requirement_pct: float = 0.5,
) -> tuple[float, dict[str, Any] | None]:
    """Opens (or adds to) a short position. Returns (shares_shorted, position).

    Credits cash by the short-sale proceeds (notional); reserves
    `notional * margin_requirement_pct` as locked, non-spendable
    `margin_reserved` at both the position and portfolio level. Refuses to
    short a ticker this portfolio is currently long on (mixing sides on one
    ticker is out of scope for this arm) or on invalid price/notional.
    """
    if price <= 0 or notional <= 0:
        return 0.0, None
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if pos and _f(pos.get("shares")) > 0:
        return 0.0, pos  # already long here — refuse to flip sides in this arm
    shares = round(notional / price, 6)
    if shares <= 0:
        return 0.0, pos

    margin_reserved_delta = round(notional * margin_requirement_pct, 4)
    prev_shares = _f(pos.get("shares")) if pos else 0.0  # <= 0 (short or flat)
    prev_avg = _f(pos.get("avg_price")) if pos else 0.0
    prev_short_shares = abs(prev_shares)
    new_short_shares = prev_short_shares + shares
    avg_price = round(((prev_short_shares * prev_avg) + notional) / new_short_shares, 6)

    if pos is None:
        pos = {"ticker": ticker, "status": "OPEN", "side": "SHORT", "margin_reserved": 0.0}
        positions[ticker] = pos
    pos["shares"] = round(-new_short_shares, 6)
    pos["avg_price"] = avg_price
    pos["current_price"] = round(price, 6)
    pos["status"] = "OPEN"
    pos["side"] = "SHORT"
    pos["margin_reserved"] = round(_f(pos.get("margin_reserved")) + margin_reserved_delta, 4)

    portfolio["cash"] = round(_f(portfolio.get("cash")) + notional, 4)
    portfolio["margin_reserved"] = round(_f(portfolio.get("margin_reserved")) + margin_reserved_delta, 4)
    return shares, pos


def _cover_short(
    portfolio: dict[str, Any],
    ticker: str,
    shares_to_cover: float,
    price: float,
) -> tuple[float, float, dict[str, Any] | None]:
    """Buys back (covers) shares of an existing short.

    Returns (realized_pnl, gross_cost, after_position_or_none). Debits cash
    to buy back; releases the proportional margin_reserved;
    realized_pnl = (entry_avg_price - cover_price) * shares_covered — the
    mirror of a long close's sign (profit when price fell since entry).
    """
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if not pos or _f(pos.get("shares")) >= 0 or price <= 0:
        return 0.0, 0.0, pos  # nothing short to cover, or invalid price

    short_shares_before = abs(_f(pos.get("shares")))
    avg_price = _f(pos.get("avg_price"))
    shares_to_cover = min(max(0.0, shares_to_cover), short_shares_before)
    if shares_to_cover <= 0:
        return 0.0, 0.0, pos

    gross_cost = round(shares_to_cover * price, 4)
    realized = round((avg_price - price) * shares_to_cover, 4) if avg_price > 0 else 0.0
    short_shares_after = round(short_shares_before - shares_to_cover, 6)

    margin_before = _f(pos.get("margin_reserved"))
    margin_release = (
        round(margin_before * (shares_to_cover / short_shares_before), 4)
        if short_shares_before > 0
        else 0.0
    )

    portfolio["cash"] = round(_f(portfolio.get("cash")) - gross_cost, 4)
    portfolio["realized_pnl"] = round(_f(portfolio.get("realized_pnl")) + realized, 4)
    portfolio["margin_reserved"] = round(
        max(0.0, _f(portfolio.get("margin_reserved")) - margin_release), 4
    )

    if short_shares_after <= 0.000001:
        positions.pop(ticker, None)
        return realized, gross_cost, None

    pos["shares"] = round(-short_shares_after, 6)
    pos["margin_reserved"] = round(max(0.0, margin_before - margin_release), 4)
    pos["status"] = "OPEN"
    return realized, gross_cost, pos


def validate_short_trade_record(record: dict[str, Any], *, before_shares: float) -> tuple[bool, str | None]:
    """New, separate integrity check for SHORT_PAPER/COVER_PAPER records —
    mirrors the long-only invariants in tae_paper_execution's
    validate_trade_record/validate_execution_run (fill_shares > 0,
    before.shares > 0 to sell) without touching that function at all.
    """
    action = str(record.get("action") or "").upper()
    fill_shares = _f(record.get("fill_shares") if "fill_shares" in record else record.get("shares"))
    if fill_shares <= 0:
        return False, "fill_shares must be > 0"
    if action == "SHORT_PAPER" and before_shares > 0:
        return False, "SHORT_PAPER requires before.shares <= 0 (cannot short an existing long)"
    if action == "COVER_PAPER" and before_shares >= 0:
        return False, "COVER_PAPER requires before.shares < 0 (nothing short to cover)"
    return True, None


def margin_utilization_pct(portfolio: dict[str, Any]) -> float:
    """Fraction of account value currently locked as margin (0..1+)."""
    account_value = _f(portfolio.get("account_value"))
    if account_value <= 0:
        account_value = _f(portfolio.get("cash")) + _f(portfolio.get("open_positions_value"))
    if account_value <= 0:
        return 0.0
    return _f(portfolio.get("margin_reserved")) / account_value


def check_margin_call(pos: dict[str, Any], *, current_price: float, maintenance_margin_pct: float) -> bool:
    """True if a short position's equity has fallen below the maintenance
    threshold and must be force-covered.

    Equity on a short = collateral (margin_reserved) minus the unrealized
    loss (price has risen since entry). Maintenance requirement is a
    percent of the CURRENT market value of the short (standard broker
    convention — mark-to-market, not the original entry notional).
    """
    shares = _f(pos.get("shares"))
    if shares >= 0 or current_price <= 0:
        return False
    avg_price = _f(pos.get("avg_price"))
    short_shares = abs(shares)
    unrealized_loss = max(0.0, (current_price - avg_price) * short_shares)
    equity = _f(pos.get("margin_reserved")) - unrealized_loss
    maintenance_required = maintenance_margin_pct * (current_price * short_shares)
    return equity < maintenance_required


def pnl_pct_short(avg_price: float, current_price: float) -> float:
    """Percent gain on a short: positive when current_price has fallen
    below avg_price (the mirror of the long-side pnl_percent)."""
    if not avg_price:
        return 0.0
    return ((float(avg_price) - float(current_price)) / float(avg_price)) * 100.0


def evaluate_short_exit(
    avg_price: float,
    current_price: float,
    state: dict[str, Any] | None,
    *,
    stop_loss_pct: float = 3.0,
    activate_pct: float = 5.0,
    trail_distance_pct: float = 2.0,
) -> tuple[str, float, dict[str, Any]]:
    """Armed trailing cover for a SHORT position — the mirror of
    tae_strategy_v2_trailing.evaluate_position_exit, expressed directly in
    short-favorable terms rather than via long-style signed percentages:
    - stop_loss_pct: price rising this many % AGAINST the short (unarmed) covers.
    - activate_pct: price falling this many % IN FAVOR of the short arms trailing.
    - trail_distance_pct: cover if price rebounds this many % off the lowest
      point reached since arming.

    Returns (action, pnl_pct, new_state) where action is one of
    HOLD / SELL_STOP_LOSS / SELL_TRAILING (kept as "SELL_*" so callers can
    branch identically to the long-side adapters — the actual execution is
    always a cover/buy-to-close, never a sale of owned shares).
    """
    s = state or {}
    pnl_pct = pnl_pct_short(avg_price, current_price)
    lowest = min(_f(s.get("lowest_price"), avg_price) or avg_price, current_price, avg_price)
    trailing_active = bool(s.get("trailing_armed"))
    prior_stop = s.get("trailing_stop")

    if not trailing_active and pnl_pct >= float(activate_pct):
        trailing_active = True

    if trailing_active:
        new_stop = lowest * (1.0 + float(trail_distance_pct) / 100.0)
        if prior_stop is not None:
            new_stop = min(new_stop, float(prior_stop))
        new_state = {"lowest_price": lowest, "trailing_armed": True, "trailing_stop": new_stop}
        if current_price >= new_stop - 1e-12:
            return "SELL_TRAILING", pnl_pct, new_state
        return "HOLD", pnl_pct, new_state

    new_state = {"lowest_price": lowest, "trailing_armed": False, "trailing_stop": None}
    if pnl_pct <= -float(stop_loss_pct):
        return "SELL_STOP_LOSS", pnl_pct, new_state
    return "HOLD", pnl_pct, new_state
