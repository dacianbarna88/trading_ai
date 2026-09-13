"""Shared sector relative-strength math — Sprint 3 Phase 3.

Genuine cross-sectional relative strength: a ticker's trailing return
minus the average trailing return of its own sector peers (from
tae_fundamentals_snapshot's free `.info` `sector` field), covering the
WHOLE watchlist — not the legacy/broken `tae_sector_runtime.py` (all
sector scores 0.0, stale since June 30) and not V2's Profit Context
Engine (real data, but only 22 of ~97 watchlist tickers).

Backtest-first, same discipline as the rest of Sprint 3: built to test
whether relative-sector-strength at entry correlates with realized PnL
on real V1/V2 trade history (tae_sector_relative_strength_backtest.py)
before this gates or scores anything live.
"""

from __future__ import annotations

RETURN_WINDOW_DAYS = 20


def trailing_return_pct(closes: list[float], window: int = RETURN_WINDOW_DAYS) -> float | None:
    """% price change over the trailing `window` trading days, ending at
    the latest close in `closes` (no lookahead — caller controls how much
    history is passed in)."""
    if len(closes) < window + 1:
        return None
    start = closes[-1 - window]
    if start == 0:
        return None
    return (closes[-1] - start) / start * 100


def relative_strength(ticker_return: float | None, peer_returns: list[float]) -> float | None:
    """`ticker_return` minus the average of `peer_returns` (its sector
    peers' own trailing returns, excluding itself). Positive = outpacing
    its sector; negative = lagging it."""
    if ticker_return is None:
        return None
    peers = [r for r in peer_returns if r is not None]
    if not peers:
        return None
    peer_avg = sum(peers) / len(peers)
    return ticker_return - peer_avg
