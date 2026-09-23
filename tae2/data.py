"""Daily ETF prices: fetch, cache, validate.

Rules learned from the legacy bot (2026-09-23): a price is only as good as
the date it belongs to. Every series is checked against the latest US session
that has closed, gaps and impossible moves are reported, and a problem stops
the run instead of being papered over with an older value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from tae2 import config

NY = ZoneInfo("America/New_York")
SESSION_CLOSE = time(16, 0)
CACHE = Path("data_cache/prices.parquet")


@dataclass(frozen=True)
class Issue:
    ticker: str
    kind: str
    detail: str


def last_closed_session(now: datetime) -> date:
    """Date of the latest US regular session that has already closed.

    No exchange-holiday calendar is used: on the day after a holiday this
    expects a bar that doesn't exist, and validation reports it (fail closed).
    """
    local = now.astimezone(NY)
    day = local.date()
    if local.weekday() < 5 and local.time() >= SESSION_CLOSE:
        return day
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def validate(prices: pd.DataFrame, now: datetime, rules: config.DataRules = config.DATA_RULES) -> list[Issue]:
    """Every problem in `prices` (index = trading days, columns = tickers)."""
    issues: list[Issue] = []
    expected = last_closed_session(now)
    calendar = prices.index
    for ticker in prices.columns:
        s = prices[ticker]
        valid = s.dropna()
        if valid.empty:
            issues.append(Issue(ticker, "NO_DATA", "no prices at all"))
            continue
        if (valid <= 0).any():
            issues.append(Issue(ticker, "NON_POSITIVE", f"{int((valid <= 0).sum())} prices <= 0"))
        last = valid.index[-1].date()
        lag = len(pd.bdate_range(last, expected)) - 1
        if lag > rules.allowed_holiday_lag:
            issues.append(Issue(ticker, "STALE", f"last bar {last}, expected {expected}"))
        # Missing days inside the series' own history, on days the calendar traded.
        missing = s.loc[valid.index[0]:].isna()
        run = (missing.groupby((~missing).cumsum()).cumsum()).max()
        if run and run > rules.max_gap_days:
            issues.append(Issue(ticker, "GAP", f"{int(run)} consecutive trading days missing"))
        moves = valid.pct_change().abs()
        big = moves[moves > rules.max_daily_move]
        for day, move in big.items():
            issues.append(Issue(ticker, "JUMP", f"{day.date()} moved {move:.0%}"))
    if len(calendar) and calendar[-1].date() > expected:
        issues.append(Issue("*", "PARTIAL_BAR", f"bar for {calendar[-1].date()} before that session closed"))
    return issues


def drop_unclosed_session(prices: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Remove a bar for a session that hasn't closed yet (it is a moving intraday price)."""
    expected = pd.Timestamp(last_closed_session(now))
    return prices.loc[prices.index <= expected]


def fetch(tickers: list[str], start: str = config.DATA_START) -> pd.DataFrame:
    """Adjusted daily closes from Yahoo Finance on the SPY trading calendar."""
    import yfinance as yf

    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False, group_by="column")
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].set_axis(tickers, axis=1)
    closes = closes[closes[config.CALENDAR_TICKER].notna()]
    closes.index = pd.DatetimeIndex(closes.index).tz_localize(None).normalize()
    return closes[tickers]


def load(refresh: bool = False, now: datetime | None = None) -> tuple[pd.DataFrame, list[Issue]]:
    """Cached prices plus their validation issues; refetches when asked or missing."""
    now = now or datetime.now(timezone.utc)
    tickers = list(config.UNIVERSE)
    if refresh or not CACHE.is_file():
        prices = drop_unclosed_session(fetch(tickers), now)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(CACHE)
    else:
        prices = pd.read_parquet(CACHE)
    return prices, validate(prices, now)
