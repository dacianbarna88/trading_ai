from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

import historical_projection as hp
from tae2.backtest import Result


def _result(monthly_returns: list[float], start: str = "2015-01-31") -> Result:
    """A synthetic daily Result whose month-end equity matches `monthly_returns`
    exactly -- one point per *distinct calendar month*, each the last day of
    that month, so backtest.month_ends() (groups by (year, month), keeps the
    max date) can't accidentally collapse two of them into one group."""
    idx = pd.date_range(start, periods=len(monthly_returns), freq="ME")
    returns = pd.Series(monthly_returns, index=idx)
    weights = pd.DataFrame(1.0, index=idx, columns=["X"])
    turnover = pd.Series(0.0, index=idx)
    return Result("test", returns, weights, turnover)


class MonthlySeriesTest(unittest.TestCase):
    def test_rebases_to_starting_capital_at_the_window_start(self) -> None:
        res = _result([0.0, 0.10, -0.05])
        rows = hp._monthly_series(res, start=pd.Timestamp(res.returns.index[0]))
        self.assertAlmostEqual(rows[0].value, hp.STARTING_CAPITAL, places=2)

    def test_compounds_monthly_returns_correctly(self) -> None:
        res = _result([0.0, 0.10, -0.05])
        rows = hp._monthly_series(res, start=pd.Timestamp(res.returns.index[0]))
        expected = hp.STARTING_CAPITAL * 1.10 * 0.95
        self.assertAlmostEqual(rows[-1].value, expected, places=2)

    def test_drawdown_is_measured_from_the_windows_own_peak(self) -> None:
        res = _result([0.0, 0.20, -0.10, -0.05])
        rows = hp._monthly_series(res, start=pd.Timestamp(res.returns.index[0]))
        # Peak is month 2 (index 1); month 4's drawdown is relative to that peak, not to month 1.
        peak = hp.STARTING_CAPITAL * 1.20
        expected_dd = (peak * 0.90 * 0.95) / peak - 1
        self.assertAlmostEqual(rows[-1].drawdown, expected_dd, places=6)

    def test_window_start_excludes_history_before_it(self) -> None:
        res = _result([0.0, 0.50, 0.01, 0.01])
        cutoff = pd.Timestamp(res.returns.index[2])
        rows = hp._monthly_series(res, start=cutoff)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0].value, hp.STARTING_CAPITAL, places=2)


class SummaryTest(unittest.TestCase):
    def test_counts_win_and_loss_months_separately_from_the_first_row(self) -> None:
        res = _result([0.0, 0.05, -0.02, 0.03])
        rows = hp._monthly_series(res, start=pd.Timestamp(res.returns.index[0]))
        summary = hp._summary(rows)
        # First row has monthly_return 0.0 by construction (no prior month) -- not counted as a win.
        self.assertEqual(summary["win_months"] + summary["loss_months"], len(rows) - 1)
        self.assertEqual(summary["win_months"], 2)
        self.assertEqual(summary["loss_months"], 1)

    def test_empty_rows_return_an_empty_summary(self) -> None:
        self.assertEqual(hp._summary([]), {})


if __name__ == "__main__":
    unittest.main()
