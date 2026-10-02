"""Turn target weights into orders for a diversified stock book. Pure: no
broker, no network. Sells come first (they free the cash the buys need).

NOT tae2.rebalance.plan() reused as-is. That function's MIN_TRADE_FRACTION
(0.5% of equity) was calibrated for tae2's own few-large-ETF-position style
(2-8 holdings) -- fine there, but momentum_vt10 holds up to 75 names at
once, so a single position is legitimately under 1% of equity by design.
Confirmed on the real 2026-08-31 decision on the live MoVo10 paper account:
75 stocks at 0.46% each ($461 on the $100k account) all fell under tae2's
0.5%/$500 threshold -- a dry run would have bought only SHY and skipped
every single stock, defeating the whole strategy on its first real
rebalance. This file uses a threshold sized for a ~75-name book instead of
copying tae2's constant; monkeypatching tae2.rebalance's module-level
constant instead would have silently changed tae2's own live paper trading
too, since it's shared global state.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tae2.broker import Position

MIN_TRADE_FRACTION = 0.001  # ignore differences under 0.1% of equity (tae2 uses 0.5%, sized for 2-8 holdings)
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
                # Same fix as tae2.rebalance.plan() (bug found 2026-10-02 on
                # the real tae2 account): cap the sell qty at what's actually
                # held, since IEEE 754 rounding on a near-zero `want` can
                # push -diff/have fractionally above 1.0 and Alpaca rejects
                # a qty even a hair over the position's real size.
                qty = min(pos.qty, pos.qty * (-diff / have))
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
