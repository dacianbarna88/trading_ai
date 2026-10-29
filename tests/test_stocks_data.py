"""Regression coverage for a real bug (found 2026-09-24): stocks.data.load()
crashed with KeyError('SPY') because SPY -- not an S&P 500 constituent, just
the fund that tracks the index -- was never added to the fetch list, while
tae2.data.fetch() hard-codes SPY as its trading-calendar reference column.
"""

from __future__ import annotations

import unittest
import unittest.mock

import numpy as np
import pandas as pd

from stocks import data
from tae2.data import Issue


class LoadTickerSetTest(unittest.TestCase):
    def test_fetch_is_called_with_spy_and_cash_included(self) -> None:
        with (
            unittest.mock.patch("stocks.data.universe.load", return_value=["AAPL", "MSFT"]),
            unittest.mock.patch("stocks.data._refill_missing", side_effect=lambda p, t: p),
            unittest.mock.patch("stocks.data.tae2_data.fetch") as fetch,
            unittest.mock.patch("stocks.data.tae2_data.drop_unclosed_session", side_effect=lambda p, now: p),
            unittest.mock.patch("stocks.data.tae2_data.validate", return_value=[]),
            unittest.mock.patch.object(data, "CACHE") as cache,
        ):
            cache.is_file.return_value = False
            fetch.return_value = unittest.mock.MagicMock()
            fetch.return_value.to_parquet = unittest.mock.MagicMock()
            data.load(refresh=True)
        called_tickers = set(fetch.call_args.args[0])
        self.assertIn("SPY", called_tickers)
        self.assertIn("SHY", called_tickers)
        self.assertIn("AAPL", called_tickers)


def _issue(ticker: str, kind: str = "NO_DATA") -> Issue:
    return Issue(ticker, kind, "x")


class SplitIssuesTest(unittest.TestCase):
    """Oct 2026: one ticker with bad data (HPE, PSKY, WBD, SW, GILD) blocked
    the whole rebalance. A few ordinary names are now excluded instead."""

    def test_a_single_ordinary_ticker_is_excluded_not_blocking(self) -> None:
        self.assertEqual(data.split_issues([_issue("HPE")]), ([], ["HPE"]))

    def test_two_issues_on_one_ticker_count_as_one_name(self) -> None:
        self.assertEqual(data.split_issues([_issue("PSKY", "GAP"), _issue("PSKY", "STALE")]), ([], ["PSKY"]))

    def test_jump_is_ignored_entirely(self) -> None:
        self.assertEqual(data.split_issues([_issue("AIG", "JUMP")]), ([], []))

    def test_cash_or_calendar_ticker_always_blocks(self) -> None:
        for critical in ("SHY", "SPY", "*"):
            blocking, excluded = data.split_issues([_issue("HPE"), _issue(critical, "STALE")])
            self.assertEqual(excluded, [], critical)
            self.assertEqual({i.ticker for i in blocking}, {"HPE", critical})

    def test_more_than_the_cap_blocks_everything(self) -> None:
        names = [f"T{i}" for i in range(data.MAX_EXCLUDED + 1)]
        blocking, excluded = data.split_issues([_issue(n) for n in names])
        self.assertEqual(excluded, [])
        self.assertEqual(len(blocking), len(names))

    def test_exactly_the_cap_is_still_tolerated(self) -> None:
        names = [f"T{i}" for i in range(data.MAX_EXCLUDED)]
        self.assertEqual(data.split_issues([_issue(n) for n in names]), ([], sorted(names)))


class RefillMissingTest(unittest.TestCase):
    """HPE failed at 13:33 on 2026-10-02 and was fine six minutes later."""

    def _prices(self) -> pd.DataFrame:
        idx = pd.bdate_range("2026-09-21", periods=5)
        df = pd.DataFrame({"SPY": np.arange(5.0) + 100, "AAA": np.arange(5.0) + 10, "BBB": np.arange(5.0) + 20}, index=idx)
        df.loc[idx[-1], "BBB"] = np.nan  # BBB is missing its latest bar
        return df

    def test_a_transiently_missing_bar_is_refetched_and_filled(self) -> None:
        prices = self._prices()
        retry = prices.copy()
        retry["BBB"] = np.arange(5.0) + 20
        with unittest.mock.patch("stocks.data.tae2_data.fetch", return_value=retry) as fetch:
            out = data._refill_missing(prices, ["AAA", "BBB", "SPY"])
        self.assertEqual(fetch.call_args.args[0], ["BBB", "SPY"])  # only the missing name, plus the calendar
        self.assertFalse(fetch.call_args.kwargs["threads"])
        self.assertEqual(out["BBB"].iloc[-1], 24.0)
        self.assertTrue(pd.isna(prices["BBB"].iloc[-1]))  # input untouched

    def test_nothing_missing_means_no_extra_download(self) -> None:
        prices = self._prices().drop(columns="BBB")
        with unittest.mock.patch("stocks.data.tae2_data.fetch") as fetch:
            out = data._refill_missing(prices, ["AAA", "SPY"])
        fetch.assert_not_called()
        self.assertIs(out, prices)

    def test_a_failed_retry_keeps_the_original_prices(self) -> None:
        prices = self._prices()
        with unittest.mock.patch("stocks.data.tae2_data.fetch", side_effect=RuntimeError("offline")):
            out = data._refill_missing(prices, ["AAA", "BBB", "SPY"])
        self.assertTrue(pd.isna(out["BBB"].iloc[-1]))


if __name__ == "__main__":
    unittest.main()
