#!/usr/bin/env python3
"""Regression coverage for tae_earnings_surprise_backtest.py's pure
join/bucketing logic -- roadmap item 5 follow-up (2026-09-17): tests
whether the free yfinance earnings-surprise history has any real edge on
V1/V2 closed trades, before ever considering paid data."""

from __future__ import annotations

import unittest

import pandas as pd

import tae_earnings_surprise_backtest as esbt


def _earnings_df(rows: list[tuple[str, float | None, float | None]]) -> pd.DataFrame:
    """rows: (date_str, eps_estimate, reported_eps). Surprise(%) computed
    the same way yfinance does, NaN when reported_eps is None (unreported/
    future quarter)."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _, _ in rows], name="Earnings Date")
    est = [e for _, e, _ in rows]
    rep = [r for _, _, r in rows]
    surprise = [
        ((r - e) / abs(e) * 100.0) if (e is not None and r is not None) else float("nan")
        for e, r in zip(est, rep)
    ]
    return pd.DataFrame({"EPS Estimate": est, "Reported EPS": rep, "Surprise(%)": surprise}, index=idx)


class MostRecentSurpriseBeforeTest(unittest.TestCase):
    def test_picks_the_latest_reported_surprise_strictly_before_entry(self) -> None:
        df = _earnings_df(
            [
                ("2026-01-15", 1.0, 1.1),  # +10%
                ("2026-04-15", 1.0, 0.9),  # -10%
            ]
        )
        result = esbt.most_recent_surprise_before(df, pd.Timestamp("2026-05-01"))
        self.assertAlmostEqual(result, -10.0)

    def test_no_lookahead_ignores_surprises_on_or_after_entry(self) -> None:
        df = _earnings_df([("2026-01-15", 1.0, 1.1), ("2026-04-15", 1.0, 0.9)])
        result = esbt.most_recent_surprise_before(df, pd.Timestamp("2026-02-01"))
        self.assertAlmostEqual(result, 10.0)

    def test_unreported_future_quarter_is_never_eligible(self) -> None:
        """The upcoming quarter (Reported EPS still NaN) must never be
        treated as a real surprise -- that would be a lookahead bug."""
        df = _earnings_df([("2026-01-15", 1.0, 1.1), ("2026-07-30", 1.2, None)])
        result = esbt.most_recent_surprise_before(df, pd.Timestamp("2026-08-01"))
        self.assertAlmostEqual(result, 10.0)

    def test_no_prior_reported_quarter_returns_none(self) -> None:
        df = _earnings_df([("2026-04-15", 1.0, 0.9)])
        result = esbt.most_recent_surprise_before(df, pd.Timestamp("2026-01-01"))
        self.assertIsNone(result)

    def test_empty_or_missing_history_returns_none_not_a_crash(self) -> None:
        self.assertIsNone(esbt.most_recent_surprise_before(pd.DataFrame(), pd.Timestamp("2026-01-01")))
        self.assertIsNone(esbt.most_recent_surprise_before(None, pd.Timestamp("2026-01-01")))

    def test_handles_tz_aware_index_like_the_real_yfinance_shape(self) -> None:
        idx = pd.DatetimeIndex(["2026-01-15 16:00:00-04:00", "2026-04-15 16:00:00-04:00"], name="Earnings Date")
        df = pd.DataFrame({"EPS Estimate": [1.0, 1.0], "Reported EPS": [1.1, 0.9], "Surprise(%)": [10.0, -10.0]}, index=idx)
        result = esbt.most_recent_surprise_before(df, pd.Timestamp("2026-05-01"))
        self.assertAlmostEqual(result, -10.0)


class EnrichWithPriorSurpriseTest(unittest.TestCase):
    def test_trades_without_a_usable_prior_surprise_are_dropped(self) -> None:
        history = {"AAPL": _earnings_df([("2026-04-15", 1.0, 0.9)])}
        trades = [
            {"ticker": "AAPL", "entry_ts": "2026-01-01T00:00:00Z", "pnl": 5.0},  # before any report
            {"ticker": "MSFT", "entry_ts": "2026-05-01T00:00:00Z", "pnl": 5.0},  # no history at all
        ]
        self.assertEqual(esbt.enrich_with_prior_surprise(trades, history), [])

    def test_matched_trade_gets_the_surprise_field_attached(self) -> None:
        history = {"AAPL": _earnings_df([("2026-01-15", 1.0, 1.1)])}
        trades = [{"ticker": "AAPL", "entry_ts": "2026-02-01T00:00:00Z", "pnl": 5.0}]
        result = esbt.enrich_with_prior_surprise(trades, history)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["prior_surprise_pct"], 10.0)
        self.assertEqual(result[0]["pnl"], 5.0)


class SpearmanTest(unittest.TestCase):
    def test_perfectly_correlated_series_is_one(self) -> None:
        self.assertAlmostEqual(esbt._spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)

    def test_perfectly_anticorrelated_series_is_minus_one(self) -> None:
        self.assertAlmostEqual(esbt._spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)

    def test_too_few_points_returns_zero_not_a_crash(self) -> None:
        self.assertEqual(esbt._spearman([1, 2], [1, 2]), 0.0)


if __name__ == "__main__":
    unittest.main()
