from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from tae2 import backtest


def _prices(values: list[float]) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=len(values))
    return pd.DataFrame({"A": values, "B": [100.0] * len(values)}, index=idx)


class LagTest(unittest.TestCase):
    """A decision can never earn the move of the day it was made on."""

    def setUp(self) -> None:
        # A jumps +10% on day 3 (index 3), flat otherwise.
        self.prices = _prices([100, 100, 100, 110, 110, 110])

    def _run(self, decide_on: int) -> pd.Series:
        day = self.prices.index[decide_on]
        targets = pd.DataFrame({"A": [1.0], "B": [0.0]}, index=[day])
        return backtest.run("t", self.prices, targets, cost_bps=0, start=None).returns

    def test_deciding_on_the_jump_day_misses_it(self) -> None:
        self.assertAlmostEqual(self._run(decide_on=3).sum(), 0.0)

    def test_deciding_two_days_before_catches_it(self) -> None:
        # Decided day 1, executed at day 2's close, so it holds A over day 3.
        self.assertAlmostEqual(self._run(decide_on=1).sum(), 0.10)


class CostsAndWeightsTest(unittest.TestCase):
    def test_turnover_pays_costs_on_the_execution_day(self) -> None:
        prices = _prices([100, 100, 100, 100])
        targets = pd.DataFrame({"A": [1.0], "B": [0.0]}, index=[prices.index[0]])
        res = backtest.run("t", prices, targets, cost_bps=10, start=None)
        self.assertAlmostEqual(res.turnover.iloc[1], 1.0)
        self.assertAlmostEqual(res.returns.iloc[1], -0.001)
        self.assertAlmostEqual(res.returns.drop(res.returns.index[1]).abs().sum(), 0.0)

    def test_leverage_is_rejected(self) -> None:
        prices = _prices([100, 101, 102])
        targets = pd.DataFrame({"A": [0.8], "B": [0.4]}, index=[prices.index[0]])
        with self.assertRaises(ValueError):
            backtest.run("t", prices, targets)

    def test_weights_drift_between_rebalances(self) -> None:
        prices = _prices([100, 100, 200, 200])
        targets = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=[prices.index[0]])
        res = backtest.run("t", prices, targets, cost_bps=0, start=None)
        # After A doubles: A = 1.0/1.5, B = 0.5/1.5.
        np.testing.assert_allclose(res.weights.iloc[2].values, [2 / 3, 1 / 3])
        self.assertAlmostEqual(res.returns.iloc[2], 0.5)

    def test_month_ends_are_last_trading_days(self) -> None:
        idx = pd.bdate_range("2021-01-01", "2021-03-31")
        ends = backtest.month_ends(idx)
        self.assertEqual([d.strftime("%Y-%m-%d") for d in ends], ["2021-01-29", "2021-02-26", "2021-03-31"])


if __name__ == "__main__":
    unittest.main()
