"""Turn target weights into orders. Pure: no broker, no network.

Sells come first (they free the cash the buys need). Small differences are
left alone so a rebalance doesn't churn on rounding, and buys never spend
more than the cash available after the sells, minus a small buffer.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tae2.broker import Position

MIN_TRADE_FRACTION = 0.005  # ignore differences under 0.5% of equity
MIN_TRADE_USD = 25.0
CASH_BUFFER = 0.005  # keep 0.5% of equity uninvested for price moves while orders fill


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str  # "buy" | "sell"
    notional: float | None = None
    qty: float | None = None
    reason: str = ""


def plan(targets: pd.Series, positions: list[Position], equity: float, cash: float) -> list[Order]:
    """Orders that move the account from `positions` to `targets` (weights of equity)."""
    if equity <= 0:
        raise ValueError("equity must be positive")
    if (targets < -1e-12).any() or targets.sum() > 1 + 1e-9:
        raise ValueError("targets must be long-only and sum to at most 1")
    held = {p.symbol: p for p in positions}
    symbols = sorted(set(held) | set(targets[targets > 0].index))
    threshold = max(MIN_TRADE_USD, MIN_TRADE_FRACTION * equity)
    sells: list[Order] = []
    buys: list[tuple[str, float]] = []
    freed = 0.0
    for s in symbols:
        want = float(targets.get(s, 0.0)) * equity
        pos = held.get(s)
        have = pos.market_value if pos else 0.0
        diff = want - have
        if abs(diff) < threshold and not (want == 0 and have > 0):
            continue
        if diff < 0 and pos:
            if want == 0:
                sells.append(Order(s, "sell", qty=pos.qty, reason="exit"))
            else:
                qty = pos.qty * (-diff / have)
                sells.append(Order(s, "sell", qty=qty, reason=f"trim to {want / equity:.1%}"))
            freed += -diff
        elif diff > 0:
            buys.append((s, diff))
    budget = cash + freed - CASH_BUFFER * equity
    wanted = sum(d for _, d in buys)
    scale = min(1.0, budget / wanted) if wanted > 0 and budget > 0 else (0.0 if wanted > 0 else 1.0)
    orders = sells + [
        Order(s, "buy", notional=round(d * scale, 2), reason=f"to {targets.get(s, 0.0):.1%}")
        for s, d in buys
        if d * scale >= MIN_TRADE_USD
    ]
    return orders
