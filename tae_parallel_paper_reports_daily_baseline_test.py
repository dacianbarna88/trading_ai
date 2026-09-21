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
import unittest.mock
from pathlib import Path

import tae_parallel_paper_reports as reports


def _cfg() -> dict:
    return {
        "V1_STARTING_CAPITAL": 30000.0,
        "V1_MIN_CASH_RESERVE": 500.0,
        "V2_STARTING_CAPITAL": 30000.0,
        "V2_MIN_CASH_RESERVE": 500.0,
        "V3_STARTING_CAPITAL": 30000.0,
        "V3_MIN_CASH_RESERVE": 500.0,
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

    def test_arm_with_no_recorded_key_on_prior_day_returns_none_not_zero(self) -> None:
        """Bug found 2026-09-21: a prior day existed (V1/V2 ran), but V3 had
        no key on it at all (update_cumulative_report() never wrote V3_av).
        _f(None) defaults to 0.0, so this used to silently return 0.0 instead
        of None -- making _arm_day_metrics() treat "no baseline recorded" as
        "baseline of exactly zero" and report daily_total_pnl == ending_av."""
        self._write_days([{"date": "2026-09-20", "V1_av": 28460.0, "V2_av": 30305.34}])
        self.assertIsNone(reports._prior_day_av("V3", "2026-09-21", self.cum_path))

    def test_arm_with_recorded_zero_is_still_zero(self) -> None:
        """A genuinely recorded 0.0 baseline must not be confused with 'missing'."""
        self._write_days([{"date": "2026-09-20", "V3_av": 0.0}])
        self.assertEqual(reports._prior_day_av("V3", "2026-09-21", self.cum_path), 0.0)


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

    def test_reproduces_the_real_v3_bug_scenario_when_fixed(self) -> None:
        """Real 2026-09-21 numbers: V1/V2 had a prior-day row (from
        update_cumulative_report(), which never writes V3_av), V3 had none.
        Old behavior: daily_total_pnl == ending_av (30601.27), because
        _prior_day_av returned 0.0 instead of None. Fixed behavior: no V3
        baseline yet -> fall back to start_cap, same as V1/V2's own first day."""
        self._write_days([{"date": "2026-09-20", "V1_av": 28459.99, "V2_av": 30305.34}])
        portfolio = _portfolio(av=30601.268601)
        m = reports._arm_day_metrics(
            "V3", portfolio, _cfg(), {}, day="2026-09-21", cum_path=self.cum_path,
        )
        self.assertNotAlmostEqual(m["daily_total_pnl"], 30601.268601, places=0)
        self.assertAlmostEqual(m["daily_total_pnl"], 601.268601, places=2)


class RecordExtraArmBaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cum_path = Path(self._tmp.name) / "cumulative.json"

    def test_creates_todays_row_when_none_exists(self) -> None:
        reports._record_extra_arm_baseline("V3", "2026-09-21", 30601.27, self.cum_path)
        cum = json.loads(self.cum_path.read_text(encoding="utf-8"))
        row = next(d for d in cum["days"] if d["date"] == "2026-09-21")
        self.assertEqual(row["V3_av"], 30601.27)

    def test_merges_into_existing_row_without_disturbing_v1_v2_keys(self) -> None:
        self.cum_path.write_text(
            json.dumps({"days": [{"date": "2026-09-21", "V1_av": 28473.38, "V2_av": 30499.01}]}),
            encoding="utf-8",
        )
        reports._record_extra_arm_baseline("V3", "2026-09-21", 30601.27, self.cum_path)
        cum = json.loads(self.cum_path.read_text(encoding="utf-8"))
        row = next(d for d in cum["days"] if d["date"] == "2026-09-21")
        self.assertEqual(row["V1_av"], 28473.38)
        self.assertEqual(row["V2_av"], 30499.01)
        self.assertEqual(row["V3_av"], 30601.27)

    def test_update_cumulative_report_preserves_v3_av_written_first(self) -> None:
        """Ordering hazard: if the 3-way report runs before generate_daily_report
        on a given day, update_cumulative_report() must not wipe out V3_av when
        it rebuilds today's row for V1/V2 (update_cumulative_report() resolves
        its own paths via paths(), so that's monkeypatched to this temp dir)."""
        reports._record_extra_arm_baseline("V3", "2026-09-21", 30601.27, self.cum_path)
        day_report = {
            "date": "2026-09-21",
            "executive_conclusion": {"verdict": "V2_WIN"},
            "v1": {"ending_av": 28473.38, "daily_total_pnl": 414.34, "drawdown": 0.0,
                   "realized_pnl_cumulative": -2104.33, "unrealized_pnl": 577.71},
            "v2": {"ending_av": 30499.01, "daily_total_pnl": 193.66, "drawdown": 0.0,
                   "realized_pnl_cumulative": 212.90, "unrealized_pnl": 286.10},
        }
        fake_paths = {
            "cumulative_json": self.cum_path,
            "cumulative_md": Path(self._tmp.name) / "cumulative.md",
            "daily_metrics_csv": Path(self._tmp.name) / "daily_metrics.csv",
        }
        with unittest.mock.patch.object(reports, "paths", return_value=fake_paths):
            reports.update_cumulative_report(day_report=day_report, cfg=_cfg())
        cum = json.loads(self.cum_path.read_text(encoding="utf-8"))
        row = next(d for d in cum["days"] if d["date"] == "2026-09-21")
        self.assertEqual(row["V3_av"], 30601.27)
        self.assertEqual(row["V1_av"], 28473.38)
        self.assertEqual(row["V2_av"], 30499.01)


if __name__ == "__main__":
    unittest.main()
