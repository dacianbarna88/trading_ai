"""Regression coverage for a real bug (found 2026-09-24): stocks.data.load()
crashed with KeyError('SPY') because SPY -- not an S&P 500 constituent, just
the fund that tracks the index -- was never added to the fetch list, while
tae2.data.fetch() hard-codes SPY as its trading-calendar reference column.
"""

from __future__ import annotations

import unittest
import unittest.mock

from stocks import data


class LoadTickerSetTest(unittest.TestCase):
    def test_fetch_is_called_with_spy_and_cash_included(self) -> None:
        with (
            unittest.mock.patch("stocks.data.universe.load", return_value=["AAPL", "MSFT"]),
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


if __name__ == "__main__":
    unittest.main()
