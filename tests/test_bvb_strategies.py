from __future__ import annotations

import unittest

import pandas as pd

from bvb.strategies import trend_filter


def _month_end_prices(months: int, values: dict[str, list[float]], cash_col: str = "CASH") -> pd.DataFrame:
    idx = pd.date_range("2020-01-31", periods=months, freq="ME")
    data = {t: v for t, v in values.items()}
    data[cash_col] = [100.0] * months
    return pd.DataFrame(data, index=idx)


class TrendFilterTest(unittest.TestCase):
    def test_above_average_gets_equal_weight_below_goes_to_cash(self) -> None:
        # 8 months: A trends steadily up (always above its own trailing avg
        # once ready), B trends steadily down (always below).
        a = [100 + 5 * i for i in range(8)]
        b = [100 - 5 * i for i in range(8)]
        prices = _month_end_prices(8, {"A": a, "B": b})
        out = trend_filter(prices, ["A", "B"], cash="CASH", sma_months=3)
        last = out.iloc[-1]
        self.assertAlmostEqual(last["A"], 0.5)
        self.assertAlmostEqual(last["B"], 0.0)
        self.assertAlmostEqual(last["CASH"], 0.5)

    def test_rows_sum_to_one(self) -> None:
        a = [100, 102, 101, 105, 103, 108]
        b = [100, 98, 99, 95, 97, 93]
        prices = _month_end_prices(6, {"A": a, "B": b})
        out = trend_filter(prices, ["A", "B"], cash="CASH", sma_months=3)
        totals = out.sum(axis=1)
        for v in totals:
            self.assertAlmostEqual(v, 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
