"""Build SignalDataset from universe — shared by discovery and future modules."""

from __future__ import annotations

import pandas as pd

from typing import Callable

from research_core.config.base import BaseResearchConfig
from research_core.features.registry import FeatureBinRegistry
from research_core.metrics.performance import compute_metrics
from research_core.services.market_data import MarketDataService
from research_core.signals.collector import SignalCollector
from research_core.types import SignalDataset
from research_core.universe import load_universe


class SignalDatasetBuilder:
    """Loads universe, collects signals, applies feature bins, computes baseline."""

    def __init__(
        self,
        config: BaseResearchConfig,
        collector: SignalCollector | None = None,
        market_data: MarketDataService | None = None,
        feature_registry: FeatureBinRegistry | None = None,
    ) -> None:
        self._config = config
        self._collector = collector or SignalCollector(config)
        self._market_data = market_data or MarketDataService(config)
        self._feature_registry = feature_registry or FeatureBinRegistry()

    def build(
        self,
        on_ticker_loaded: Callable[[str, int, int], None] | None = None,
    ) -> SignalDataset | None:
        universe = load_universe(self._config)
        sector_map = self._config.sector_map()
        spy_ctx = self._market_data.load_spy_context()
        if spy_ctx is None:
            return None

        rows: list[dict] = []
        loaded = 0
        hold = self._config.hold_days

        for ticker in universe:
            raw = self._market_data.download(ticker)
            if raw.empty or not self._market_data.has_sufficient_history(raw, hold):
                continue
            df = self._market_data.enrich_ticker(raw)
            sector = sector_map.get(ticker, "Other")
            batch = self._collector.collect(ticker, df, spy_ctx, sector)
            if batch:
                loaded += 1
                rows.extend(batch)
                if on_ticker_loaded:
                    on_ticker_loaded(ticker, loaded, len(rows))

        if not rows:
            return None

        self._feature_registry.register_defaults()
        signals = self._feature_registry.apply(pd.DataFrame(rows))
        signals["Signal_Date"] = pd.to_datetime(signals["Signal_Date"])

        baseline_rets = signals[self._config.return_column].astype(float).values
        baseline = compute_metrics(baseline_rets, {"Avg_Return": 0, "Win_Rate": 0})
        baseline["MAE_Median"] = round(float(signals["MAE"].median()), 4)
        baseline["MFE_Median"] = round(float(signals["MFE"].median()), 4)

        return SignalDataset(
            signals=signals,
            baseline_metrics=baseline,
            universe_size=len(universe),
            tickers_loaded=loaded,
        )
