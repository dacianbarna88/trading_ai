#!/usr/bin/env python3
"""
Regression coverage for V1's volatility-adjusted entry stop-loss.

Context: V1's entry stop was a flat -3% for every ticker regardless of how
volatile that name actually trades — likely getting tripped by ordinary
noise on volatile names while being needlessly loose on calm ones. This
replaces the flat percentage with one derived from the ticker's own
trailing realized volatility (tae_strategy_v3_learning_policy's
realized_vol_annualized(), already generic/pure), clamped to [-6%, -2%].

vol_adjusted_stop_pct() takes a plain closes list, not a ticker symbol, so
these tests are pure/offline — no network calls, no yfinance mocking
needed for the formula itself. fetch_recent_closes() (the one function that
does hit the network) gets a narrow smoke test only.
"""

from __future__ import annotations

import math
import unittest

import tae_strategy_v1_vol_stop as v1vol


def _closes_with_daily_vol(daily_pct_stdev: float, n: int = 40, start: float = 100.0) -> list[float]:
    """Deterministic synthetic closes series with a known daily log-return
    stdev, alternating +x/-x so the realized stdev matches daily_pct_stdev
    closely without needing randomness (keeps the test deterministic)."""
    closes = [start]
    step = daily_pct_stdev / 100.0
    for i in range(n):
        mult = (1 + step) if i % 2 == 0 else (1 - step)
        closes.append(closes[-1] * mult)
    return closes


class NoDataFallbackTest(unittest.TestCase):
    def test_empty_closes_returns_default(self) -> None:
        stop_pct, diag = v1vol.vol_adjusted_stop_pct(None)
        self.assertEqual(stop_pct, v1vol.DEFAULT_STOP_LOSS_PCT)
        self.assertEqual(diag["source"], "DEFAULT_NO_CLOSES")

    def test_too_short_history_returns_default(self) -> None:
        stop_pct, diag = v1vol.vol_adjusted_stop_pct([100.0, 101.0, 99.0])
        self.assertEqual(stop_pct, v1vol.DEFAULT_STOP_LOSS_PCT)
        self.assertEqual(diag["source"], "DEFAULT_INSUFFICIENT_HISTORY")


class ClampBoundsTest(unittest.TestCase):
    def test_very_low_volatility_clamps_to_min_pct(self) -> None:
        closes = _closes_with_daily_vol(0.05)  # near-flat series
        stop_pct, diag = v1vol.vol_adjusted_stop_pct(closes)
        self.assertEqual(stop_pct, -v1vol.VOL_STOP_MIN_PCT)
        self.assertEqual(diag["source"], "VOLATILITY_ADJUSTED")

    def test_very_high_volatility_clamps_to_max_pct(self) -> None:
        closes = _closes_with_daily_vol(5.0)  # wildly volatile series
        stop_pct, diag = v1vol.vol_adjusted_stop_pct(closes)
        self.assertEqual(stop_pct, -v1vol.VOL_STOP_MAX_PCT)


class MonotonicityTest(unittest.TestCase):
    def test_higher_volatility_ticker_gets_wider_stop(self) -> None:
        calm = _closes_with_daily_vol(0.3)
        volatile = _closes_with_daily_vol(1.5)
        calm_stop, _ = v1vol.vol_adjusted_stop_pct(calm)
        volatile_stop, _ = v1vol.vol_adjusted_stop_pct(volatile)
        # both are negative; a "wider" stop is more negative (further from 0)
        self.assertLess(volatile_stop, calm_stop)


class StopIsAlwaysNegativeTest(unittest.TestCase):
    def test_result_is_always_negative_within_bounds(self) -> None:
        for pct in (0.1, 0.5, 1.0, 2.0, 4.0):
            closes = _closes_with_daily_vol(pct)
            stop_pct, _ = v1vol.vol_adjusted_stop_pct(closes)
            self.assertLess(stop_pct, 0.0)
            self.assertGreaterEqual(stop_pct, -v1vol.VOL_STOP_MAX_PCT)
            self.assertLessEqual(stop_pct, -v1vol.VOL_STOP_MIN_PCT)


class ComposesWithTrailingAdapterTest(unittest.TestCase):
    """Confirms Phase 1's adapter actually honors a computed stop (already
    covered generically in tae_v1_trailing_stop_test.py's
    CustomStopLossPctTest, repeated here with a value this module would
    realistically produce)."""

    def test_computed_stop_feeds_trailing_adapter(self) -> None:
        import tae_strategy_v1_trailing as v1trail

        closes = _closes_with_daily_vol(1.2)
        stop_pct, _ = v1vol.vol_adjusted_stop_pct(closes)
        pos = {"avg_price": 100.0, "shares": 1.0}
        current_price = 100.0 * (1 + (stop_pct - 0.5) / 100.0)  # breach the computed stop
        act, reason = v1trail.v1_trailing_exit_action(
            pos,
            avg_price=100.0,
            current_price=current_price,
            now_iso="2026-09-02T10:00:00Z",
            stop_loss_pct=stop_pct,
        )
        self.assertEqual(act, "SELL_STOP_LOSS")
        self.assertEqual(reason, "STRATEGY_STOP_V1")


class FetchClosesSmokeTest(unittest.TestCase):
    """Narrow smoke test for the one network-touching function — skips
    cleanly if offline rather than failing the suite."""

    def test_fetch_returns_a_list_or_none(self) -> None:
        try:
            result = v1vol.fetch_recent_closes("AAPL")
        except Exception:
            self.skipTest("network unavailable in this environment")
        if result is None:
            self.skipTest("yfinance returned no data (network/rate-limit) — not a code defect")
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(x, float) for x in result))


class RuntimeWiringSmokeTest(unittest.TestCase):
    def test_runtime_imports_v1volstop_module(self) -> None:
        import tae_parallel_paper_runtime as ppr

        self.assertTrue(hasattr(ppr, "v1volstop"))
        self.assertTrue(hasattr(ppr.v1volstop, "vol_adjusted_stop_pct"))


if __name__ == "__main__":
    unittest.main()
