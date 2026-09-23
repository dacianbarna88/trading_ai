from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tae2 import config, strategies
from tests.helpers import random_prices

BUILDERS = {
    "fixed_mix": lambda p: strategies.fixed_mix(p, {"SPY": 0.6, "IEF": 0.4}),
    "gtaa": lambda p: strategies.gtaa(p, sma_months=10),
    "dual_momentum": lambda p: strategies.dual_momentum(p, lookback_months=12),
    "relative_momentum": lambda p: strategies.relative_momentum(p, lookback_months=6, top_n=3),
    "inverse_volatility": lambda p: strategies.inverse_volatility(p),
    "vol_target": lambda p: strategies.vol_target(p, strategies.gtaa(p, sma_months=10), target=0.05),
    "trend_filtered_mix": lambda p: strategies.trend_filtered_mix(p, sma_months=10),
    "core_plus_gtaa": lambda p: strategies.core_plus_sleeve(p, strategies.gtaa(p, sma_months=10), 0.5),
    "core_plus_dual": lambda p: strategies.core_plus_sleeve(p, strategies.dual_momentum(p), 0.7),
}


class NoLookaheadTest(unittest.TestCase):
    """Changing prices after a date must not change any decision up to that date."""

    def test_every_strategy_ignores_the_future(self) -> None:
        prices = random_prices()
        cut = prices.index[600]
        future = prices.copy()
        future.loc[future.index > cut] *= np.linspace(0.5, 2.0, (future.index > cut).sum())[:, None]
        for name, build in BUILDERS.items():
            with self.subTest(strategy=name):
                a = build(prices)
                b = build(future)
                pd.testing.assert_frame_equal(a.loc[:cut], b.loc[:cut])


class WeightsTest(unittest.TestCase):
    def test_rows_are_long_only_and_sum_to_one(self) -> None:
        prices = random_prices()
        for name, build in BUILDERS.items():
            with self.subTest(strategy=name):
                w = build(prices)
                self.assertGreater(len(w), 0)
                self.assertTrue((w >= -1e-12).all().all())
                np.testing.assert_allclose(w.sum(axis=1).values, 1.0, atol=1e-9)

    def test_gtaa_moves_an_asset_below_its_average_to_cash(self) -> None:
        prices = random_prices()
        prices["DBC"] = np.linspace(200, 50, len(prices))  # steady decline
        w = strategies.gtaa(prices, sma_months=10)
        self.assertTrue((w["DBC"] == 0).all())
        self.assertTrue((w[config.CASH] >= 1 / len(strategies.GTAA_ASSETS) - 1e-12).all())

    def test_dual_momentum_holds_bonds_when_stocks_trail_cash(self) -> None:
        prices = random_prices()
        prices["SPY"] = np.linspace(200, 100, len(prices))
        prices[config.CASH] = np.linspace(100, 105, len(prices))
        w = strategies.dual_momentum(prices)
        self.assertTrue((w["IEF"] == 1.0).all())

    def test_trend_filter_parks_the_equity_slice_in_cash(self) -> None:
        prices = random_prices()
        prices["SPY"] = np.linspace(200, 100, len(prices))
        w = strategies.trend_filtered_mix(prices, sma_months=10)
        self.assertTrue((w["SPY"] == 0).all())
        np.testing.assert_allclose(w[config.CASH].values, 0.6)
        np.testing.assert_allclose(w["IEF"].values, 0.4)

    def test_blend_keeps_the_core_share(self) -> None:
        prices = random_prices()
        w = strategies.core_plus_sleeve(prices, strategies.gtaa(prices, sma_months=10), core_weight=0.7)
        self.assertTrue((w["SPY"] >= 0.42 - 1e-12).all())  # 0.7 * 0.6 from the core alone
        self.assertTrue((w["IEF"] >= 0.28 - 1e-12).all())

    def test_vol_target_only_scales_down(self) -> None:
        prices = random_prices()
        base = strategies.gtaa(prices, sma_months=10)
        scaled = strategies.vol_target(prices, base, target=0.01)
        risky = [c for c in base.columns if c != config.CASH]
        self.assertTrue((scaled[risky] <= base[risky] + 1e-12).all().all())


if __name__ == "__main__":
    unittest.main()
