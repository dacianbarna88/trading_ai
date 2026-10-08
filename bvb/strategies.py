"""BVB strategies: thin wrappers reusing tae2/the stocks lab's own tested
logic, not reinvented. Each is a direct, unmodified mechanism from a system
already live elsewhere in this project -- see bvb/__init__.py for why.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from tae2.backtest import month_ends


def trend_filter(
    prices: pd.DataFrame, assets: Sequence[str], cash: str, sma_months: int = 6, freq: str = "M"
) -> pd.DataFrame:
    """Each asset gets 1/n when its close is above its N-month trailing
    average, else that slice goes to `cash`. Exactly tae2.strategies.gtaa's
    mechanism (same sma_months=6 core_gtaa_50 runs live), rewritten standalone
    with an explicit `cash` column instead of gtaa()'s hardcoded
    tae2.config.CASH ("SHY") -- BVB has no such column. Same reason
    stocks.strategies.momentum() doesn't reuse tae2.strategies.relative_momentum
    as-is."""
    if freq != "M":
        raise ValueError("only monthly decisions are supported here")
    dates = month_ends(prices.index)
    m = prices.loc[dates, list(assets)]
    avg = m.rolling(sma_months).mean()
    out = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    above = m > avg
    ready = avg.notna().all(axis=1)
    for d in m.index[ready]:
        on = above.loc[d]
        for t in assets:
            out.loc[d, t] = 1 / len(assets) if on[t] else 0.0
        out.loc[d, cash] += 1 - out.loc[d, list(assets)].sum()
    return out.loc[ready[ready].index]
