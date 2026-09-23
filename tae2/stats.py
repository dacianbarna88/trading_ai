"""Performance statistics, including the deflated Sharpe ratio.

The deflated Sharpe ratio (Bailey & López de Prado, 2014) asks how likely a
Sharpe ratio is to be real given how many variants were tried to find it,
and given the returns' skew and fat tails. Trying 50 variants and keeping
the best one inflates the Sharpe; this undoes that.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

TRADING_DAYS = 252
_N = NormalDist()
_EULER_GAMMA = 0.5772156649015329


def sharpe(r: pd.Series) -> float:
    sd = r.std()
    return float(r.mean() / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else 0.0


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    return float((eq / eq.cummax() - 1).min())


def cagr(r: pd.Series) -> float:
    years = len(r) / TRADING_DAYS
    growth = float((1 + r).prod())
    return growth ** (1 / years) - 1 if years > 0 and growth > 0 else -1.0


def summary(r: pd.Series, turnover: pd.Series | None = None, split: str | None = None) -> dict[str, float]:
    down = r[r < 0].std()
    years = len(r) / TRADING_DAYS
    out = {
        "years": years,
        "cagr": cagr(r),
        "vol": float(r.std() * math.sqrt(TRADING_DAYS)),
        "sharpe": sharpe(r),
        "sortino": float(r.mean() / down * math.sqrt(TRADING_DAYS)) if down > 0 else 0.0,
        "max_dd": max_drawdown(r),
        "worst_year": float(r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1).min()),
        "turnover_per_year": float(turnover.sum() / years) if turnover is not None and years > 0 else 0.0,
    }
    out["calmar"] = out["cagr"] / abs(out["max_dd"]) if out["max_dd"] < 0 else 0.0
    if split:
        cut = pd.Timestamp(split)
        out["sharpe_first_half"] = sharpe(r[r.index < cut])
        out["sharpe_second_half"] = sharpe(r[r.index >= cut])
    return out


def deflated_sharpe(r: pd.Series, n_trials: int, trial_sharpes: list[float] | None = None) -> float:
    """Probability the true (per-period) Sharpe of `r` is above what luck alone
    would produce as the best of `n_trials` tries.

    `trial_sharpes` are the annualized Sharpes of every variant tried; their
    spread sets how big "luck" is. Without them, the variance of a Sharpe
    estimate under zero skill is used.
    """
    t = len(r)
    if t < 3 or r.std() == 0:
        return 0.0
    sr = r.mean() / r.std()  # per period
    skew = float(((r - r.mean()) ** 3).mean() / r.std(ddof=0) ** 3)
    kurt = float(((r - r.mean()) ** 4).mean() / r.std(ddof=0) ** 4)
    if trial_sharpes and len(trial_sharpes) > 1:
        var_sr = float(np.var(np.asarray(trial_sharpes) / math.sqrt(TRADING_DAYS), ddof=1))
    else:
        var_sr = 1.0 / t
    n = max(1, int(n_trials))
    if n == 1:
        sr0 = 0.0
    else:
        sr0 = math.sqrt(var_sr) * (
            (1 - _EULER_GAMMA) * _N.inv_cdf(1 - 1 / n) + _EULER_GAMMA * _N.inv_cdf(1 - 1 / (n * math.e))
        )
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr**2))
    return float(_N.cdf((sr - sr0) * math.sqrt(t - 1) / denom))
