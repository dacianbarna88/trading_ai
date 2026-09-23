"""Synthetic prices for hermetic tests (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tae2 import config


def random_prices(days: int = 900, seed: int = 7, start: str = "2015-01-01") -> pd.DataFrame:
    """Geometric random walks for every ticker in the universe, on business days."""
    rng = np.random.default_rng(seed)
    index = pd.bdate_range(start, periods=days)
    cols = list(config.UNIVERSE)
    drift = rng.uniform(-0.0002, 0.0006, len(cols))
    vol = rng.uniform(0.002, 0.02, len(cols))
    rets = rng.normal(drift, vol, (days, len(cols)))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=index, columns=cols)
