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


TRADING_DAYS_PER_MONTH = 21


def _monthly(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.loc[month_ends(prices.index)]


def decision_dates(index: pd.DatetimeIndex, freq: str = "M") -> pd.DatetimeIndex:
    """Rebalance dates: last trading day of each month ("M"), each week ("W") or every other week ("2W")."""
    if freq == "M":
        return month_ends(index)
    iso = index.isocalendar()
    weekly = pd.DatetimeIndex(pd.Series(index, index=index).groupby([iso.year.values, iso.week.values]).max().values)
    if freq == "W":
        return weekly
    if freq == "2W":
        return weekly[::2]
    raise ValueError(f"unknown rebalance frequency {freq!r}")


def _sampled(prices: pd.DataFrame, freq: str, lookback_months: int, how: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(prices at decision dates, their N-month moving average or N-month-ago price).

    Monthly keeps the original month-end calculation; weekly variants use the
    same horizon measured in trading days (N x 21) on daily prices.
    """
    if freq == "M":
        m = _monthly(prices)
        ref = m.rolling(lookback_months).mean() if how == "sma" else m.shift(lookback_months)
        return m, ref
    days = lookback_months * TRADING_DAYS_PER_MONTH
    dates = decision_dates(prices.index, freq)
    ref = prices.rolling(days).mean() if how == "sma" else prices.shift(days)
    return prices.loc[dates], ref.loc[dates]


def fixed_mix(prices: pd.DataFrame, weights: dict[str, float], freq: str = "M") -> pd.DataFrame:
    """Constant weights, rebalanced on each decision date (buy-and-hold when one asset)."""
    dates = decision_dates(prices.index, freq)
    out = _frame(dates, prices.columns)
    for t, w in weights.items():
        out[t] = w
    return out


def gtaa(
    prices: pd.DataFrame, sma_months: int = 10, assets: Sequence[str] = GTAA_ASSETS, freq: str = "M"
) -> pd.DataFrame:
    """Each asset gets 1/n when its close is above its N-month average, else that slice goes to cash."""
    m, avg = _sampled(prices[list(assets)], freq, sma_months, "sma")
    out = _frame(m.index, prices.columns)
    above = m > avg
    ready = avg.notna().all(axis=1)
    for d in m.index[ready]:
        on = above.loc[d]
        for t in assets:
            out.loc[d, t] = 1 / len(assets) if on[t] else 0.0
        out.loc[d, config.CASH] += 1 - out.loc[d, list(assets)].sum()
    return out.loc[ready[ready].index]


def dual_momentum(prices: pd.DataFrame, lookback_months: int = 12, freq: str = "M") -> pd.DataFrame:
    """Antonacci-style: equities (best of SPY/EFA) when US stocks beat cash, else bonds."""
    m, past = _sampled(prices, freq, lookback_months, "past")
    ret = m / past - 1
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


def blend(parts: Sequence[tuple[pd.DataFrame, float]]) -> pd.DataFrame:
    """Weighted sum of several strategies' targets, on the decision dates they all share."""
    dates = parts[0][0].index
    for targets, _ in parts[1:]:
        dates = dates.intersection(targets.index)
    cols = parts[0][0].columns
    return sum(targets.loc[dates, cols] * weight for targets, weight in parts)


def core_plus_sleeve(
    prices: pd.DataFrame, sleeve: pd.DataFrame, core_weight: float = 0.6, freq: str = "M"
) -> pd.DataFrame:
    """A 60/40 core holding `core_weight` of the money, the rest in `sleeve` (same rebalance dates)."""
    return blend([(fixed_mix(prices, {"SPY": 0.6, "IEF": 0.4}, freq), core_weight), (sleeve, 1 - core_weight)])


def trend_filtered_mix(
    prices: pd.DataFrame,
    sma_months: int = 10,
    equity: str = "SPY",
    bond: str = "IEF",
    equity_weight: float = 0.6,
) -> pd.DataFrame:
    """60/40 whose equity slice moves to cash while equities sit below their N-month average."""
    m = _monthly(prices)
    avg = m[equity].rolling(sma_months).mean()
    ready = avg.notna()
    out = _frame(m.index, prices.columns)
    out[bond] = 1 - equity_weight
    on = m[equity] > avg
    out[equity] = np.where(on, equity_weight, 0.0)
    out[config.CASH] += np.where(on, 0.0, equity_weight)
    return out.loc[ready[ready].index]
