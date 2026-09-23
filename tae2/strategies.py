"""Strategies as pure functions: prices in, target weights out.

Each returns a DataFrame indexed by month-end decision dates. A row may only
use prices up to that date's close; the backtester adds the one-day lag.
Weights are long-only and sum to 1, with anything unallocated put in CASH.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from tae2 import config
from tae2.backtest import month_ends

RISK_ASSETS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "DBC", "GLD")
BOND_ASSETS = ("TLT", "IEF", "LQD", "TIP")
GTAA_ASSETS = ("SPY", "EFA", "IEF", "DBC", "VNQ")  # Faber's original five


def _frame(dates: pd.DatetimeIndex, cols: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=dates, columns=list(cols))


def _monthly(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.loc[month_ends(prices.index)]


def fixed_mix(prices: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Constant weights, rebalanced monthly (buy-and-hold when one asset)."""
    dates = month_ends(prices.index)
    out = _frame(dates, prices.columns)
    for t, w in weights.items():
        out[t] = w
    return out


def gtaa(prices: pd.DataFrame, sma_months: int = 10, assets: Sequence[str] = GTAA_ASSETS) -> pd.DataFrame:
    """Each asset gets 1/n when its month-end close is above its N-month average, else that slice goes to cash."""
    m = _monthly(prices)
    out = _frame(m.index, prices.columns)
    above = m[list(assets)] > m[list(assets)].rolling(sma_months).mean()
    ready = m[list(assets)].rolling(sma_months).mean().notna().all(axis=1)
    for d in m.index[ready]:
        on = above.loc[d]
        for t in assets:
            out.loc[d, t] = 1 / len(assets) if on[t] else 0.0
        out.loc[d, config.CASH] += 1 - out.loc[d, list(assets)].sum()
    return out.loc[ready[ready].index]


def dual_momentum(prices: pd.DataFrame, lookback_months: int = 12) -> pd.DataFrame:
    """Antonacci-style: equities (best of SPY/EFA) when US stocks beat cash, else bonds."""
    m = _monthly(prices)
    ret = m / m.shift(lookback_months) - 1
    out = _frame(m.index, prices.columns)
    ready = ret[["SPY", "EFA", config.CASH]].notna().all(axis=1)
    for d in m.index[ready]:
        r = ret.loc[d]
        if r["SPY"] > r[config.CASH]:
            out.loc[d, "SPY" if r["SPY"] >= r["EFA"] else "EFA"] = 1.0
        else:
            out.loc[d, "IEF"] = 1.0
    return out.loc[ready[ready].index]


def relative_momentum(
    prices: pd.DataFrame,
    lookback_months: int = 12,
    top_n: int = 3,
    assets: Sequence[str] = RISK_ASSETS + BOND_ASSETS,
) -> pd.DataFrame:
    """Top N assets by past return, each only if it beat cash (absolute momentum)."""
    m = _monthly(prices)
    ret = m / m.shift(lookback_months) - 1
    out = _frame(m.index, prices.columns)
    ready = ret[list(assets) + [config.CASH]].notna().all(axis=1)
    for d in m.index[ready]:
        r = ret.loc[d]
        for t in r[list(assets)].nlargest(top_n).index:
            if r[t] > r[config.CASH]:
                out.loc[d, t] = 1 / top_n
        out.loc[d, config.CASH] += 1 - out.loc[d].sum()
    return out.loc[ready[ready].index]


def inverse_volatility(prices: pd.DataFrame, assets: Sequence[str] = GTAA_ASSETS, window: int = 63) -> pd.DataFrame:
    """Weights proportional to 1 / recent volatility (a simple risk-parity)."""
    vol = prices[list(assets)].pct_change().rolling(window).std()
    dates = month_ends(prices.index)
    out = _frame(dates, prices.columns)
    ready = vol.loc[dates].notna().all(axis=1)
    for d in dates[ready.values]:
        iv = 1 / vol.loc[d]
        out.loc[d, list(assets)] = (iv / iv.sum()).values
    return out.loc[dates[ready.values]]


def vol_target(prices: pd.DataFrame, base: pd.DataFrame, target: float = 0.10, window: int = 63) -> pd.DataFrame:
    """Scale `base` so its recent volatility is at most `target` a year; the rest goes to cash.

    Never levers above the base weights (scale is capped at 1).
    """
    rets = prices.pct_change()
    out = base.copy()
    for d in base.index:
        w = base.loc[d].drop(config.CASH, errors="ignore")
        hist = rets.loc[:d, w.index].tail(window)
        if len(hist) < window:
            continue
        realized = float((hist @ w.values).std() * np.sqrt(252))
        scale = min(1.0, target / realized) if realized > 0 else 1.0
        out.loc[d, w.index] = w.values * scale
        out.loc[d, config.CASH] = 1 - out.loc[d, w.index].sum()
    return out
