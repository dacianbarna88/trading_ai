"""Target-weight backtester.

A strategy only says which weights it wants on each rebalance date, using
prices up to and including that date's close. The engine trades at the next
day's close, pays COST_BPS on every dollar of turnover and lets weights drift
with prices between rebalances. That lag is the one rule that keeps a
backtest from seeing the future, so it lives here and nowhere else.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tae2 import config


@dataclass
class Result:
    name: str
    returns: pd.Series  # daily net returns
    weights: pd.DataFrame  # daily weights actually held (after drift)
    turnover: pd.Series  # daily traded fraction of the portfolio

    @property
    def equity(self) -> pd.Series:
        return (1 + self.returns).cumprod()


def month_ends(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each month in `index`."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby([index.year, index.month]).max().values)


def run(
    name: str,
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    cost_bps: float = config.COST_BPS,
    start: str | None = config.EVAL_START,
) -> Result:
    """Simulate holding `targets` (rows = decision dates, columns = tickers, rows sum to <= 1).

    Any weight not allocated is held in cash earning 0. A decision made at the
    close of day t is executed at the close of day t+1.
    """
    prices = prices.sort_index()
    rets = prices.pct_change().fillna(0.0)
    cols = list(prices.columns)
    targets = targets.reindex(columns=cols, fill_value=0.0).fillna(0.0)
    if (targets.sum(axis=1) > 1 + 1e-9).any():
        raise ValueError(f"{name}: target weights sum above 1 (no leverage)")
    # Decision at t -> trade at the next trading day's close.
    pos = prices.index.searchsorted(targets.index, side="right")
    exec_orders = {prices.index[p]: targets.iloc[i].values for i, p in enumerate(pos) if p < len(prices.index)}

    w = np.zeros(len(cols))
    held = np.zeros((len(prices), len(cols)))
    turnover = np.zeros(len(prices))
    daily = np.zeros(len(prices))
    r = rets.values
    for i, day in enumerate(prices.index):
        # Today's return accrues on yesterday's holdings.
        gross = float(w @ r[i])
        grown = w * (1 + r[i])
        total = 1 + gross
        w = grown / total if total > 0 else grown
        if day in exec_orders:
            new = np.asarray(exec_orders[day], dtype=float)
            turnover[i] = float(np.abs(new - w).sum())
            w = new
        daily[i] = gross - turnover[i] * cost_bps / 1e4
        held[i] = w
    out = Result(
        name=name,
        returns=pd.Series(daily, index=prices.index),
        weights=pd.DataFrame(held, index=prices.index, columns=cols),
        turnover=pd.Series(turnover, index=prices.index),
    )
    if start:
        out = Result(name, out.returns.loc[start:], out.weights.loc[start:], out.turnover.loc[start:])
    return out
