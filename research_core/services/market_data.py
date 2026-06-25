"""Centralized market data access for all research modules."""

from __future__ import annotations

import pandas as pd

from momentum_continuation_research_v11 import MIN_HISTORY_BARS, download_history

from research_core.config.base import BaseResearchConfig
from research_core.data.loader import enrich_spy_market, enrich_ticker


class MarketDataService:
    """
    Single entry point for OHLCV download and enrichment.
    Future modules should use this instead of calling yfinance directly.
    """

    def __init__(self, config: BaseResearchConfig) -> None:
        self._config = config

    @property
    def min_history_bars(self) -> int:
        return MIN_HISTORY_BARS

    def download(self, ticker: str) -> pd.DataFrame:
        return download_history(ticker)

    def enrich_ticker(self, df: pd.DataFrame) -> pd.DataFrame:
        return enrich_ticker(df, self._config)

    def enrich_spy(self, df: pd.DataFrame) -> pd.DataFrame:
        return enrich_spy_market(df)

    def load_spy_context(self) -> pd.DataFrame | None:
        spy_raw = self.download("SPY")
        if spy_raw.empty:
            return None
        return self.enrich_spy(spy_raw)

    def has_sufficient_history(self, df: pd.DataFrame, hold_days: int | None = None) -> bool:
        hold = hold_days or self._config.hold_days
        return len(df) >= MIN_HISTORY_BARS + hold
