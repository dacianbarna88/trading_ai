from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from stocks import strategies

TICKERS = [f"T{i:02d}" for i in range(20)] + ["SPY", "SHY"]
STOCKS = [t for t in TICKERS if t not in ("SPY", "SHY")]


def _random_prices(days: int = 900, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2015-01-01", periods=days)
    drift = rng.uniform(-0.0002, 0.0006, len(TICKERS))
    vol = rng.uniform(0.005, 0.03, len(TICKERS))
    rets = rng.normal(drift, vol, (days, len(TICKERS)))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=index, columns=TICKERS)


class MomentumTest(unittest.TestCase):
    def test_ignores_the_future(self) -> None:
        prices = _random_prices()
        cut = prices.index[600]
        future = prices.copy()
        future.loc[future.index > cut] *= np.linspace(0.5, 2.0, (future.index > cut).sum())[:, None]
        a = strategies.momentum(prices, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        b = strategies.momentum(future, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        pd.testing.assert_frame_equal(a.loc[:cut], b.loc[:cut])

    def test_rows_are_long_only_and_sum_to_at_most_one(self) -> None:
        prices = _random_prices()
        w = strategies.momentum(prices, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        self.assertGreater(len(w), 0)
        self.assertTrue((w >= -1e-12).all().all())
        # Leftover (names that failed the beat-cash filter) goes to SHY, so rows sum to 1 even when fewer than top_n qualify.
        np.testing.assert_allclose(w.sum(axis=1).values, 1.0, atol=1e-9)

    def test_picks_the_highest_formation_return_names(self) -> None:
        # Fully deterministic (not layered on random noise, which occasionally
        # lets a lucky random walk outrun a modest deterministic trend over a
        # single 6-month window): flat prices except T00, which jumps once,
        # well before the decision date, so its formation return is unambiguous.
        idx = pd.bdate_range("2015-01-01", periods=400)
        prices = pd.DataFrame(100.0, index=idx, columns=TICKERS)
        prices.loc[idx >= idx[100], "T00"] = 500.0  # +400% jump, then flat
        w = strategies.momentum(prices, assets=STOCKS, cash="SHY", lookback_months=6, top_n=3)
        self.assertGreater(len(w), 0)
        # Only unambiguous while the jump is inside the formation window; once
        # both endpoints are past it, T00 ties everyone else's flat 0% return.
        self.assertTrue((w["T00"] > 0).any())

    def test_a_partially_listed_universe_still_produces_decisions(self) -> None:
        """Bug found 2026-09-24: requiring every asset to have history at once
        (like tae2.strategies.relative_momentum does) leaves zero decision
        dates once a real ~500-stock universe has any IPOs/spinoffs in it.
        A name missing its early history must simply be excluded from
        ranking on dates before it existed, not block the whole strategy."""
        prices = _random_prices()
        late_ipo = "T00"
        prices.loc[prices.index < prices.index[400], late_ipo] = np.nan
        w = strategies.momentum(prices, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        self.assertGreater(len(w), 0)
        # Before the IPO, the name must never be picked (no data to rank it on).
        early_rows = w.loc[w.index < prices.index[400]]
        self.assertTrue((early_rows[late_ipo] == 0).all())

    def test_only_names_beating_cash_are_chosen(self) -> None:
        # Deterministic: every stock is flat (0% return), cash (SHY) steadily
        # rises -- no stock can ever beat cash, so none should be chosen and
        # the whole allocation should sit in SHY instead.
        idx = pd.bdate_range("2015-01-01", periods=400)
        prices = pd.DataFrame(100.0, index=idx, columns=TICKERS)
        prices["SHY"] = 100 * np.exp(np.linspace(0, 1.0, len(idx)))
        w = strategies.momentum(prices, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        self.assertGreater(len(w), 0)
        self.assertTrue((w[STOCKS] == 0).all().all())
        np.testing.assert_allclose(w["SHY"].values, 1.0, atol=1e-9)


class VolTargetTest(unittest.TestCase):
    def test_ignores_the_future(self) -> None:
        prices = _random_prices()
        base = strategies.momentum(prices, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        cut = prices.index[700]
        future = prices.copy()
        future.loc[future.index > cut] *= np.linspace(0.5, 2.0, (future.index > cut).sum())[:, None]
        base_future = strategies.momentum(future, assets=STOCKS, cash="SHY", lookback_months=6, top_n=5)
        a = strategies.vol_target(prices, base, cash="SHY", target=0.10, window=63)
        b = strategies.vol_target(future, base_future, cash="SHY", target=0.10, window=63)
        common = a.index[a.index <= cut].intersection(b.index)
        pd.testing.assert_frame_equal(a.loc[common], b.loc[common])

    def test_never_scales_above_the_base_weight(self) -> None:
        # Deterministic near-zero-volatility holding: scale should cap at 1.0, never lever up.
        idx = pd.bdate_range("2015-01-01", periods=400)
        prices = pd.DataFrame(100.0, index=idx, columns=TICKERS)
        prices["T00"] = 100 * np.exp(np.linspace(0, 0.001, len(idx)))  # near-flat
        base = pd.DataFrame(0.0, index=[idx[350]], columns=TICKERS)
        base.loc[idx[350], "T00"] = 1.0
        w = strategies.vol_target(prices, base, cash="SHY", target=0.50, window=63)
        self.assertLessEqual(float(w.loc[idx[350], "T00"]), 1.0 + 1e-9)

    def test_scales_down_a_high_volatility_holding(self) -> None:
        rng = np.random.default_rng(3)
        idx = pd.bdate_range("2015-01-01", periods=400)
        prices = pd.DataFrame(100.0, index=idx, columns=TICKERS)
        loud = 100 * np.exp(np.cumsum(rng.normal(0, 0.05, len(idx))))  # ~79% annualized vol
        prices["T00"] = loud
        base = pd.DataFrame(0.0, index=[idx[350]], columns=TICKERS)
        base.loc[idx[350], "T00"] = 1.0
        w = strategies.vol_target(prices, base, cash="SHY", target=0.10, window=63)
        scale = float(w.loc[idx[350], "T00"])
        self.assertLess(scale, 1.0)
        self.assertAlmostEqual(float(w.loc[idx[350], "SHY"]), 1 - scale, places=6)

    def test_a_zero_weighted_gappy_column_does_not_poison_the_result(self) -> None:
        """Bug found 2026-09-24 in tae2.strategies.vol_target: `hist @ w.values`
        multiplies every column, including zero-weighted ones -- and
        0.0 * float('nan') is nan, not 0, in IEEE 754. A ~500-stock universe
        has hundreds of zero-weighted columns with real historical NaN gaps
        (pre-IPO); tae2's own 8-13 ETFs never have gaps so it never bites
        there. This function must restrict the dot product to held (nonzero
        weight) names only, so an unrelated NaN column can't silently force
        scale back to 1.0 (no scaling applied) via an all-NaN realized-vol read."""
        rng = np.random.default_rng(5)
        idx = pd.bdate_range("2015-01-01", periods=400)
        prices = pd.DataFrame(100.0, index=idx, columns=TICKERS)
        loud = 100 * np.exp(np.cumsum(rng.normal(0, 0.05, len(idx))))
        prices["T00"] = loud
        # T01 is zero-weighted but has a NaN gap covering the whole vol window.
        prices.loc[idx[:360], "T01"] = np.nan
        base = pd.DataFrame(0.0, index=[idx[380]], columns=TICKERS)
        base.loc[idx[380], "T00"] = 1.0  # T01 stays at 0 weight
        w = strategies.vol_target(prices, base, cash="SHY", target=0.10, window=63)
        scale = float(w.loc[idx[380], "T00"])
        self.assertLess(scale, 1.0, "a zero-weighted NaN column silently disabled vol targeting (scale defaulted to 1.0)")


class LowVolatilityTest(unittest.TestCase):
    def test_ignores_the_future(self) -> None:
        prices = _random_prices()
        cut = prices.index[600]
        future = prices.copy()
        future.loc[future.index > cut] *= np.linspace(0.5, 2.0, (future.index > cut).sum())[:, None]
        a = strategies.low_volatility(prices, assets=TICKERS, top_n=5, window=63)
        b = strategies.low_volatility(future, assets=TICKERS, top_n=5, window=63)
        pd.testing.assert_frame_equal(a.loc[:cut], b.loc[:cut])

    def test_rows_are_long_only_and_sum_to_one(self) -> None:
        prices = _random_prices()
        w = strategies.low_volatility(prices, assets=TICKERS, top_n=5, window=63)
        self.assertGreater(len(w), 0)
        self.assertTrue((w >= -1e-12).all().all())
        np.testing.assert_allclose(w.sum(axis=1).values, 1.0, atol=1e-9)

    def test_picks_the_lowest_volatility_names(self) -> None:
        prices = _random_prices()
        # T00 is engineered to be far calmer than everything else for the whole window.
        idx = prices.index
        prices["T00"] = 100 + np.linspace(0, 1, len(idx))  # near-zero daily moves
        w = strategies.low_volatility(prices, assets=TICKERS, top_n=3, window=63)
        self.assertTrue((w["T00"] > 0).all())

    def test_top_n_larger_than_available_history_yields_no_rows(self) -> None:
        prices = _random_prices(days=50)
        w = strategies.low_volatility(prices, assets=TICKERS, top_n=5, window=63)
        self.assertEqual(len(w), 0)


if __name__ == "__main__":
    unittest.main()
