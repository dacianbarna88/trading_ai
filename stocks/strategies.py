"""Stock strategies as pure functions: prices in, target weights out.

Same contract tae2/strategies.py uses: a row may only use prices up to that
date's close, the backtester adds the one-day lag, weights are long-only and
sum to 1 with the remainder in CASH.

Momentum and low-volatility are NOT tae2.strategies.relative_momentum /
inverse_volatility reused as-is, even though those looked asset-count-
agnostic. Bug found 2026-09-24: relative_momentum requires the ENTIRE
`assets` list to have a non-NaN return on a date before it will act
(`ret[...].notna().all(axis=1)`). tae2's own 8-13 ETFs have all existed
since ~2006, so that never bites. A ~500-stock universe is constantly
refreshed by IPOs, spinoffs and delistings (465 of 505 current S&P 500
tickers have a gap somewhere in 2006-2026 -- COIN, HOOD, RDDT, GEV, KVUE,
etc.); requiring all 505 simultaneously valid left zero usable decision
dates across the whole 18-year window (silently: CAGR/Sharpe both read
0.0%/0.00, not an error). The functions below rank only among tickers that
already have enough valid history *on that date* -- the same
per-date-availability pattern low_volatility already used correctly.

Deliberately NOT included in this first pass, and why:
- Value / quality (Piotroski F-score, P/E, P/B): need point-in-time
  fundamentals history. yfinance only exposes today's fundamentals, and
  applying that retroactively over 15+ years would be lookahead bias --
  exactly the class of bug tae2's own no-lookahead tests exist to catch.
  Deferred until a real point-in-time fundamentals source is lined up.
- Naive post-earnings-announcement drift: documented in the literature as
  decayed since markets got faster at pricing earnings surprises; a naive
  version is not worth building without the more sophisticated revival
  approach (using long earnings-history patterns), which needs the same
  fundamentals data this pass doesn't have.
- Any ad-hoc technical-indicator signal (RSI/SMA-crossover style): this is
  exactly the legacy bot's failure mode (4%/yr backtest vs 20.6% for
  holding the same stocks, retired 2026-09-23). Not repeating it.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from tae2.backtest import month_ends
from tae2.strategies import blend  # noqa: F401 (re-exported for research.py)


def momentum(
    prices: pd.DataFrame,
    assets: Sequence[str],
    cash: str,
    lookback_months: int = 12,
    top_n: int = 50,
    skip_months: int = 1,
) -> pd.DataFrame:
    """Equal-weight the `top_n` highest-formation-return names each month.

    Classic "12-1" construction (Jegadeesh & Titman): formation return is
    measured over `lookback_months` ending `skip_months` before the
    decision date, skipping the most recent month to avoid short-term
    reversal contamination. A name is only included if its formation return
    also beat `cash` over the same window (absolute-momentum filter, same
    spirit as tae2.strategies.relative_momentum) -- a long-only crash
    control, not a claim the filter alone prevents momentum crashes. A date
    is only skipped when there isn't enough ranked history yet; once ranking
    is possible, the date always gets a decision -- 100% cash when zero
    names beat it, same as tae2.strategies.relative_momentum's convention
    (an explicit all-cash row, not a missing one the backtester could
    misread as "no change from the prior decision").
    """
    m = prices.loc[month_ends(prices.index)]
    ref_far = m.shift(lookback_months + skip_months)
    ref_near = m.shift(skip_months)
    ret = ref_near / ref_far - 1
    out = pd.DataFrame(0.0, index=m.index, columns=prices.columns)
    rows = []
    for d in m.index:
        row = ret.loc[d, list(assets)].dropna()
        if len(row) < top_n or pd.isna(ret.loc[d, cash]):
            continue
        cash_ret = ret.loc[d, cash]
        chosen = row[row > cash_ret].nlargest(top_n).index
        if len(chosen):
            out.loc[d, chosen] = 1 / len(chosen)
        out.loc[d, cash] += 1 - out.loc[d, chosen].sum()
        rows.append(d)
    return out.loc[rows]


def vol_target(prices: pd.DataFrame, base: pd.DataFrame, cash: str, target: float = 0.10, window: int = 63) -> pd.DataFrame:
    """Scale `base` so its recent realized volatility is at most `target` a
    year; the rest goes to `cash`. Never levers above the base weights
    (scale capped at 1) -- the literature's standard fix for momentum's
    crash risk (see strategies.momentum's docstring).

    NOT tae2.strategies.vol_target reused as-is. That function computes
    `hist[w.index] @ w.values` over ALL non-cash columns of `base`, including
    the ~400+ zero-weighted tickers that don't exist yet in early years of a
    ~500-stock universe. Confirmed by hand: `0.0 * float('nan') == nan` in
    IEEE 754, so a single NaN in a zero-weighted column still poisons that
    day's sum even though it should contribute nothing -- tae2's own 8-13
    ETFs have all existed since ~2006 so this never bites there. Fixed here
    by restricting the returns matrix to only the names actually held
    (nonzero weight) on each date, before the dot product.
    """
    rets = prices.pct_change()
    out = base.copy()
    for d in base.index:
        w = base.loc[d].drop(cash, errors="ignore")
        held = w[w != 0]
        if held.empty:
            continue
        hist = rets.loc[:d, held.index].tail(window)
        if len(hist) < window or hist.isna().any().any():
            continue
        realized = float((hist @ held.values).std() * np.sqrt(252))
        scale = min(1.0, target / realized) if realized > 0 else 1.0
        out.loc[d, held.index] = held.values * scale
        out.loc[d, cash] = 1 - out.loc[d, held.index].sum()
    return out


def low_volatility(
    prices: pd.DataFrame,
    assets: Sequence[str],
    top_n: int = 50,
    window: int = 126,
) -> pd.DataFrame:
    """Equal-weight the `top_n` lowest-realized-volatility names each month.

    Mirrors relative_momentum's shape (rank, cut at top_n, equal-weight,
    remainder to cash) with volatility instead of trailing return. No
    valuation filter -- the literature's caveat ("low-vol only works when
    it's cheap") needs fundamentals data this pass doesn't have; see the
    module docstring.
    """
    m = prices.loc[month_ends(prices.index)]
    vol = prices[list(assets)].pct_change().rolling(window).std()
    vol_m = vol.loc[m.index]
    out = pd.DataFrame(0.0, index=m.index, columns=prices.columns)
    ready = vol_m.notna().sum(axis=1) >= top_n
    for d in m.index[ready]:
        chosen = vol_m.loc[d].nsmallest(top_n).index
        out.loc[d, chosen] = 1 / top_n
    return out.loc[ready[ready].index]
