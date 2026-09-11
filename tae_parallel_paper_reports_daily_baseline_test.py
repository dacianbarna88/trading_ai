#!/usr/bin/env python3
"""
Regression coverage for the "Daily total PnL" baseline bug (2026-09-11).

Root cause: _arm_day_metrics() computed `daily_total = av - start_cap`
UNCONDITIONALLY, every single day, since each arm's inception -- meaning
every TAE_PARALLEL_DAILY_REPORT and its V1_WIN/V2_WIN verdict was actually
comparing CUMULATIVE PnL since inception (mislabeled "daily"), not a real
day-over-day figure. Confirmed against real data: V1's reported "Daily
total PnL" on 2026-09-11 (-1785.45) was byte-identical to
(ending_av - 30000 starting_capital), while the correct same-day figure
(from tae_daily_check.sh's own capital table) was -245.45.

Fix: _arm_day_metrics(..., day=..., cum_path=...) now reads yesterday's
recorded ending AV from the same tae_parallel_cumulative_report.json this
module already maintains (one row per calendar day) and diffs against
that instead, falling back to start_cap only on an arm's very first
recorded day.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tae_parallel_paper_reports as reports


def _cfg() -> dict:
    return {
        "V1_STARTING_CAPITAL": 30000.0,
        "V1_MIN_CASH_RESERVE": 500.0,
        "V2_STARTING_CAPITAL": 30000.0,
        "V2_MIN_CASH_RESERVE": 500.0,
    }


def _portfolio(*, av: float, realized: float = 0.0, unreal: float = 0.0) -> dict:
    return {
        "starting_capital": 30000.0,
        "cash": av,
        "positions": {},
        "realized_pnl": realized,
        "unrealized_pnl": unreal,
        "created_at": "2026-07-24T00:00:00Z",
    }


class PriorDayAvTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cum_path = Path(self._tmp.name) / "cumulative.json"

    def _write_days(self, days: list[dict]) -> None:
        self.cum_path.write_text(json.dumps({"days": days}), encoding="utf-8")

    def test_no_file_returns_none(self) -> None:
        self.assertIsNone(reports._prior_day_av("V1", "2026-09-11", self.cum_path))

    def test_no_prior_day_returns_none(self) -> None:
        self._write_days([{"date": "2026-09-11", "V1_av": 30000.0}])
        self.assertIsNone(reports._prior_day_av("V1", "2026-09-11", self.cum_path))

    def test_returns_most_recent_prior_day(self) -> None:
        self._write_days([
            {"date": "2026-09-09", "V1_av": 28500.0},
            {"date": "2026-09-10", "V1_av": 28460.0},
        ])
        self.assertEqual(reports._prior_day_av("V1", "2026-09-11", self.cum_path), 28460.0)

    def test_ignores_same_or_future_days(self) -> None:
        self._write_days([
            {"date": "2026-09-10", "V1_av": 28460.0},
            {"date": "2026-09-11", "V1_av": 28214.55},  # today itself -- must not leak in
            {"date": "2026-09-12", "V1_av": 99999.0},   # future -- must not leak in
        ])
        self.assertEqual(reports._prior_day_av("V1", "2026-09-11", self.cum_path), 28460.0)


class ArmDayMetricsDailyBaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cum_path = Path(self._tmp.name) / "cumulative.json"

    def _write_days(self, days: list[dict]) -> None:
        self.cum_path.write_text(json.dumps({"days": days}), encoding="utf-8")

    def test_reproduces_the_real_v1_bug_scenario_when_fixed(self) -> None:
        """The exact real numbers from 2026-09-11: V1 ending AV 28214.5477,
        yesterday's close 28459.999921 -> true daily PnL is -245.45, NOT
        the old buggy -1785.45 (av - 30000 starting capital)."""
        self._write_days([{"date": "2026-09-10", "V1_av": 28459.999921}])
        portfolio = _portfolio(av=28214.5477)
        m = reports._arm_day_metrics(
            "V1", portfolio, _cfg(), {}, day="2026-09-11", cum_path=self.cum_path,
        )
        self.assertAlmostEqual(m["daily_total_pnl"], -245.452209, places=2)
        self.assertNotAlmostEqual(m["daily_total_pnl"], -1785.4523, places=0)

    def test_falls_back_to_starting_capital_on_the_very_first_day(self) -> None:
        # No cumulative history at all yet -- no prior day to diff against.
        portfolio = _portfolio(av=30193.5)
        m = reports._arm_day_metrics(
            "V1", portfolio, _cfg(), {}, day="2026-07-24", cum_path=self.cum_path,
        )
        self.assertAlmostEqual(m["daily_total_pnl"], 193.5, places=2)

    def test_without_day_or_cum_path_still_falls_back_safely(self) -> None:
        """Backward-compat: callers that don't pass day/cum_path (none, as
        of this fix, but future callers might) must not crash."""
        portfolio = _portfolio(av=30193.5)
        m = reports._arm_day_metrics("V1", portfolio, _cfg(), {})
        self.assertAlmostEqual(m["daily_total_pnl"], 193.5, places=2)


if __name__ == "__main__":
    unittest.main()
