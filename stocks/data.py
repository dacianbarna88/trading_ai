"""Daily stock prices: fetch, cache, validate. Reuses tae2.data's fetch/validate
logic unchanged (it is already generic over any ticker list) -- only the
universe and cache path differ from tae2's ETF pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tae2 import data as tae2_data
from tae2.config import CALENDAR_TICKER  # tae2_data.fetch() hard-codes this as the trading-calendar reference
from tae2.data import Issue  # re-exported: same validation contract as tae2

from stocks import config, universe

CACHE = Path(config.CACHE)


def validate(prices: pd.DataFrame, now: datetime) -> list[Issue]:
    """Same validation tae2 uses (gaps, jumps, non-positive, stale sessions)."""
    return tae2_data.validate(prices, now, config.DATA_RULES)


# One ticker with bad data used to block the whole monthly rebalance (HPE,
# PSKY, WBD, SW, GILD in Oct 2026). Up to MAX_EXCLUDED ordinary names are now
# dropped from that run instead -- journaled, never silent. SPY (calendar), SHY
# (cash) and calendar-level issues ("*") are never tolerated, and the engine
# still refuses to run when an excluded name is currently held (it would be
# sold over a data glitch).
MAX_EXCLUDED = 5  # ~1% of the 503-name universe
CRITICAL = frozenset({config.CASH, CALENDAR_TICKER, "*"})


def split_issues(issues: list[Issue]) -> tuple[list[Issue], list[str]]:
    """(blocking issues, tickers to exclude): all-blocking when a critical series
    is bad or more than MAX_EXCLUDED names are; otherwise nothing blocks and the
    bad names are excluded. JUMP is never blocking (same as tae2)."""
    bad = [i for i in issues if i.kind != "JUMP"]
    names = sorted({i.ticker for i in bad})
    if any(i.ticker in CRITICAL for i in bad) or len(names) > MAX_EXCLUDED:
        return bad, []
    return [], names


def _refill_missing(prices: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """One sequential retry for tickers whose latest bar is missing: yfinance
    drops single names transiently (HPE 2026-10-02 failed at 13:33, fine at 13:39)."""
    last = prices.index[-1]
    missing = []
    for t in tickers:
        if t == CALENDAR_TICKER:
            continue
        seen = prices[t].last_valid_index()
        if seen is None or seen < last:
            missing.append(t)
    if not missing:
        return prices
    try:
        retry = tae2_data.fetch(missing + [CALENDAR_TICKER], start=config.DATA_START, threads=False)
    except Exception:  # network/Yahoo failure: keep what we have, validation reports the rest
        return prices
    out = prices.copy()
    for t in missing:
        out[t] = retry[t].reindex(out.index).combine_first(out[t])
    return out


def load(refresh: bool = False, now: datetime | None = None) -> tuple[pd.DataFrame, list[Issue]]:
    """Cached prices for today's S&P 500 + SHY (cash) + SPY (calendar/benchmark), plus validation issues.

    Survivorship-biased universe -- see stocks/universe.py's docstring. SPY
    is not an S&P 500 *constituent* (it tracks the index) so it must be
    added explicitly on top of the 503 company tickers universe.load() returns.
    """
    now = now or datetime.now(timezone.utc)
    tickers = sorted(set(universe.load(refresh=refresh)) | {config.CASH, CALENDAR_TICKER})
    if refresh or not CACHE.is_file():
        # threads=False: sequential fetch. Bug found 2026-09-25 -- yfinance's
        # default threaded download hit peewee.OperationalError on 322/505
        # tickers (shared SQLite tz-cache isn't safe under this much
        # concurrency; see tae2.data.fetch()'s docstring). Slower, but this
        # only runs once/day via launchd, so wall-clock time doesn't matter.
        prices = tae2_data.drop_unclosed_session(
            tae2_data.fetch(tickers, start=config.DATA_START, threads=False), now
        )
        prices = _refill_missing(prices, tickers)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(CACHE)
    else:
        prices = pd.read_parquet(CACHE)
    return prices, validate(prices, now)
