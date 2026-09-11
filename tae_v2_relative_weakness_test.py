#!/usr/bin/env python3
"""
Regression coverage for V2's relative-weakness trim (2026-09-09), built
after a real day (2026-09-09) where V2 lost -$259.87 unrealized while the
broad market (SPY/QQQ/DIA) was flat -- pure stock-selection weakness the
existing count-based concentration trim can't see (it only fires when
position count exceeds a target, regardless of how badly a name is
lagging the market).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import tae_strategy_v2_relative_weakness as rw


def _old_cycle_id(ticker: str, hours_ago: float) -> str:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y%m%dT%H%M%S")
    return f"PPC-{ticker}-{ts}-DEADBEEF"


class PctReturnTest(unittest.TestCase):
    def test_simple_return(self) -> None:
        self.assertAlmostEqual(rw._pct_return([100.0, 110.0], 1), 10.0)

    def test_none_on_empty_or_single_point(self) -> None:
        self.assertIsNone(rw._pct_return([], 5))
        self.assertIsNone(rw._pct_return([100.0], 5))
        self.assertIsNone(rw._pct_return(None, 5))

    def test_lookback_longer_than_series_clamps(self) -> None:
        # Only 3 points available but asked for 10 days back -- must use
        # the oldest point available, not crash or index out of range.
        result = rw._pct_return([100.0, 105.0, 110.0], 10)
        self.assertAlmostEqual(result, 10.0)


class RelativeUnderperformanceTest(unittest.TestCase):
    def test_lagging_ticker_yields_negative_relative_return(self) -> None:
        with mock.patch(
            "tae_strategy_v1_vol_stop.fetch_recent_closes",
            side_effect=lambda ticker, **kw: {
                "ZZZ": [100.0] * 5 + [90.0],  # -10% over the window
                "SPY": [100.0] * 5 + [101.0],  # +1% over the window
            }[ticker],
        ):
            rel = rw.relative_underperformance_pct("ZZZ", now=datetime.now(timezone.utc))
        self.assertAlmostEqual(rel, -11.0, places=4)

    def test_missing_ticker_history_returns_none(self) -> None:
        with mock.patch("tae_strategy_v1_vol_stop.fetch_recent_closes", return_value=None):
            self.assertIsNone(rw.relative_underperformance_pct("ZZZ"))


class ShouldTrimTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.trades_path = Path(self._tmp.name) / "trades.jsonl"
        rw._benchmark_cache.clear()

    def _patch_rel(self, value: float | None):
        return mock.patch.object(rw, "relative_underperformance_pct", return_value=value)

    def test_no_trim_when_no_position(self) -> None:
        self.assertIsNone(
            rw.should_relative_weakness_trim(
                pos=None, cycle=None, ticker="ZZZ", trades_path=self.trades_path
            )
        )

    def test_no_trim_when_trailing_armed(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48), "trailing_armed": True}
        with self._patch_rel(-20.0):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path
            )
        self.assertIsNone(result)

    def test_no_trim_when_too_young(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 1.0)}
        with self._patch_rel(-20.0):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path
            )
        self.assertIsNone(result)

    def test_no_trim_when_underperformance_not_below_threshold(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48)}
        with self._patch_rel(-3.0):  # lagging, but not past -8.0 threshold
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path
            )
        self.assertIsNone(result)

    def test_trims_when_lagging_past_threshold_and_old_enough(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48)}
        with self._patch_rel(-15.0):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path
            )
        self.assertEqual(result, rw.V2_RELATIVE_WEAKNESS_REASON)

    def test_profitable_position_skips_fetch_entirely(self) -> None:
        pos = {
            "shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48),
            "avg_price": 100.0,
        }
        with mock.patch.object(
            rw, "relative_underperformance_pct", side_effect=AssertionError("must not be called")
        ):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path,
                current_price=110.0,  # +10% on its own price -> pre-filter should skip
            )
        self.assertIsNone(result)

    def test_losing_position_still_checks_relative_performance(self) -> None:
        pos = {
            "shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48),
            "avg_price": 100.0,
        }
        with self._patch_rel(-15.0):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path,
                current_price=95.0,  # -5% on its own price -> must still check
            )
        self.assertEqual(result, rw.V2_RELATIVE_WEAKNESS_REASON)

    def test_no_signal_means_no_trim(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48)}
        with self._patch_rel(None):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path
            )
        self.assertIsNone(result)

    def test_rate_limited_by_own_reason_not_concentration_trims(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48)}
        now = datetime.now(timezone.utc)
        with self.trades_path.open("w") as fh:
            # A concentration trim 1 minute ago must NOT block this
            # independent reason's rate limiter.
            fh.write(json.dumps({"reason": "V2_CONCENTRATION_TRIM", "ts": now.isoformat()}) + "\n")
        with self._patch_rel(-15.0):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path, now=now
            )
        self.assertEqual(result, rw.V2_RELATIVE_WEAKNESS_REASON)

    def test_rate_limited_by_its_own_recent_trim(self) -> None:
        pos = {"shares": 10.0, "position_cycle_id": _old_cycle_id("ZZZ", 48)}
        now = datetime.now(timezone.utc)
        with self.trades_path.open("w") as fh:
            fh.write(
                json.dumps({"reason": rw.V2_RELATIVE_WEAKNESS_REASON, "ts": now.isoformat()}) + "\n"
            )
        with self._patch_rel(-15.0):
            result = rw.should_relative_weakness_trim(
                pos=pos, cycle=None, ticker="ZZZ", trades_path=self.trades_path, now=now
            )
        self.assertIsNone(result)


class RuntimeWiringSmokeTest(unittest.TestCase):
    def test_runtime_imports_relative_weakness_module(self) -> None:
        import tae_parallel_paper_runtime as ppr

        self.assertTrue(hasattr(ppr, "v2relweak"))
        self.assertTrue(hasattr(ppr.v2relweak, "should_relative_weakness_trim"))


if __name__ == "__main__":
    unittest.main()
