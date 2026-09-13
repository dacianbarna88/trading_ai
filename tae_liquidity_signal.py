"""Shared volume/liquidity signal math — Sprint 3 Phase 2.

Two measures, both computable from a plain OHLCV volume series (no new
data source beyond what's already fetched by the batched downloads used
elsewhere this sprint — tae_meanreversion_backtest.fetch_history already
keeps the Volume column, just unused until now):

- relative_volume: today's volume vs. its own trailing 20-day average —
  is this ticker seeing unusually high/low participation right now?
- average_volume: the trailing 20-day average itself, as a plain
  liquidity floor (a name that trades $50k/day is a different risk than
  one that trades $50m/day, regardless of any entry signal quality).

Backtest-first, same discipline as tae_mean_reversion_signal.py /
tae_macro_regime.py: built to test whether relative volume at entry
correlates with realized PnL on the real V1/V2 trade history
(tae_liquidity_backtest.py) before this gates or sizes anything live.
"""

from __future__ import annotations

AVG_VOLUME_WINDOW = 20

# Backtested 2026-09-13 (tae_liquidity_backtest.py) on 151 real V1+V2
# closed trades, bucketed by trailing-20d average volume at entry:
#   LOW  (avg_vol <= ~2.76M/day, n=50): win_rate=20.0% PF=0.39
#   MED  (~2.76M-7.47M/day,      n=50): win_rate=28.0% PF=0.49
#   HIGH (avg_vol >= ~7.47M/day, n=51): win_rate=54.9% PF=0.92
# The cleanest, strongest split found this sprint. Threshold set just
# below the LOW/MED boundary (~2.76M) rather than exactly on it, so the
# filter isn't overfit to this one sample's precise cut point.
MIN_AVG_VOLUME = 2_500_000.0


def average_volume(volumes: list[float], window: int = AVG_VOLUME_WINDOW) -> float | None:
    """Trailing `window`-bar average volume, EXCLUDING the latest bar (so
    "today's volume vs. its own recent average" doesn't include today in
    the average it's compared against)."""
    if len(volumes) < window + 1:
        return None
    history = volumes[-(window + 1):-1]
    if not history:
        return None
    return sum(history) / len(history)


def relative_volume(volumes: list[float], window: int = AVG_VOLUME_WINDOW) -> float | None:
    """Latest bar's volume divided by its own trailing `window`-bar
    average (excluding today). >1 = above-average participation."""
    if not volumes:
        return None
    avg = average_volume(volumes, window=window)
    if avg is None or avg <= 0:
        return None
    return volumes[-1] / avg


def is_liquid_enough(avg_volume: float | None, *, min_avg_volume: float = MIN_AVG_VOLUME) -> bool:
    """True when avg_volume clears the floor OR is unknown — missing data
    fails OPEN (doesn't block a trade), consistent with every other
    fail-soft fetch in this codebase; it is not evidence of illiquidity."""
    if avg_volume is None:
        return True
    return avg_volume >= min_avg_volume
