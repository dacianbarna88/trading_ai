from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import system_health_check as shc
from tae2.data import Issue


@dataclass
class _FakeReport:
    status: str
    decision_date: str = "2026-10-01"
    detail: str = ""


class RunTestsTest(unittest.TestCase):
    def test_uses_sys_executable_not_a_bare_python3(self) -> None:
        # Bug found 2026-10-12: launchd's minimal PATH resolves a bare
        # "python3" to macOS's own system Python (no pandas), not this
        # project's venv -- every pandas-importing test file then errors
        # on import, reported as 14/14 "failing" tests that were actually
        # never really run. sys.executable is always the interpreter
        # already running this process, which run_health_check.sh already
        # resolved correctly.
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd

            class _Proc:
                returncode = 0
                stdout = ""
                stderr = ""

            return _Proc()

        with patch.object(subprocess, "run", fake_run):
            shc.run_tests()
        self.assertEqual(captured["cmd"][0], sys.executable)
        self.assertNotEqual(captured["cmd"][0], "python3")


class CheckDataTest(unittest.TestCase):
    def test_passes_with_no_issues(self) -> None:
        def load(refresh: bool):
            return "PRICES", []

        check, prices = shc.check_data("x", load)
        self.assertTrue(check.ok)
        self.assertEqual(prices, "PRICES")

    def test_old_jump_does_not_block_and_is_not_reported(self) -> None:
        # 529 historical JUMPs were printed every single day: history, not news.
        def load(refresh: bool):
            return "PRICES", [Issue("SPY", "JUMP", "2020-01-01 moved 30%")]

        check, prices = shc.check_data("x", load, now=datetime(2026, 10, 29, tzinfo=timezone.utc))
        self.assertTrue(check.ok)
        self.assertEqual(check.detail, "OK")

    def test_recent_jump_is_reported_by_ticker_but_does_not_block(self) -> None:
        def load(refresh: bool):
            return "PRICES", [
                Issue("AAA", "JUMP", "2026-10-27 moved 31%"),
                Issue("BBB", "JUMP", "2020-03-16 moved 40%"),
            ]

        check, _ = shc.check_data("x", load, now=datetime(2026, 10, 29, tzinfo=timezone.utc))
        self.assertTrue(check.ok)
        self.assertIn("AAA", check.detail)
        self.assertNotIn("BBB", check.detail)

    def test_gap_blocks(self) -> None:
        def load(refresh: bool):
            return "PRICES", [Issue("SPY", "GAP", "5 days missing")]

        check, prices = shc.check_data("x", load)
        self.assertFalse(check.ok)
        self.assertIn("GAP", check.detail)

    def test_stocks_policy_tolerates_a_dead_ticker_and_says_so(self) -> None:
        from stocks import data as stocks_data

        def load(refresh: bool):
            return "PRICES", [Issue("GILD", "NO_DATA", "no prices at all")]

        check, _ = shc.check_data("x", load, split=stocks_data.split_issues)
        self.assertTrue(check.ok)
        self.assertIn("GILD", check.detail)
        self.assertIn("excluse", check.detail)

    def test_stocks_policy_still_blocks_on_the_cash_ticker(self) -> None:
        from stocks import data as stocks_data

        def load(refresh: bool):
            return "PRICES", [Issue("SHY", "STALE", "last bar 2026-10-05")]

        check, _ = shc.check_data("x", load, split=stocks_data.split_issues)
        self.assertFalse(check.ok)
        self.assertIn("SHY", check.detail)

    def test_fetch_exception_is_captured_not_raised(self) -> None:
        def load(refresh: bool):
            raise RuntimeError("yfinance down")

        check, prices = shc.check_data("x", load)
        self.assertFalse(check.ok)
        self.assertIsNone(prices)
        self.assertIn("yfinance down", check.detail)


class HeartbeatTest(unittest.TestCase):
    """2026-10-28: the Mac slept 36h, no evening job ran, and the morning check said
    'TOTUL OK' because self-heal quietly caught up. The journal shows the miss."""

    def _journal(self, tmp: Path, *iso_utc: str) -> Path:
        p = tmp / "runs.jsonl"
        p.write_text("".join(json.dumps({"at": t}) + "\n" for t in iso_utc))
        return p

    def test_a_run_at_the_scheduled_time_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            # Wed 2026-10-28 21:42 EET (UTC+2 after DST ended 10-25) = 19:42 UTC; checked Thu 10:20 EET.
            j = self._journal(Path(d), "2026-10-28T19:42:00+00:00")
            now = datetime(2026, 10, 29, 8, 20, tzinfo=timezone.utc)
            check = shc.check_heartbeat("stocks", j, 21, 40, now)
        self.assertTrue(check.ok, check.detail)

    def test_a_missed_evening_is_flagged_even_if_a_later_catch_up_exists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            # Nothing on 10-28 evening; only a run the next morning at 10:56 (the self-heal / wake-up).
            j = self._journal(Path(d), "2026-10-27T19:42:00+00:00", "2026-10-29T08:56:00+00:00")
            now = datetime(2026, 10, 29, 8, 58, tzinfo=timezone.utc)
            check = shc.check_heartbeat("stocks", j, 21, 40, now)
        self.assertFalse(check.ok)
        self.assertIn("NU a rulat", check.detail)
        self.assertIn("întârziere 13.3 h", check.detail)  # 10-28 21:40 EET -> 10-29 10:56 EET = 13h16m

    def test_monday_morning_expects_friday_evening_not_the_weekend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            j = self._journal(Path(d), "2026-10-23T18:31:00+00:00")  # Fri 21:31 EEST
            now = datetime(2026, 10, 26, 8, 20, tzinfo=timezone.utc)  # Mon 10:20 EET... EEST ended 10-25 -> 10:20
            check = shc.check_heartbeat("tae2", j, 21, 30, now)
        self.assertTrue(check.ok, check.detail)

    def test_a_missing_journal_is_a_problem_not_a_crash(self) -> None:
        check = shc.check_heartbeat("tae2", Path("/nonexistent/runs.jsonl"), 21, 30, datetime.now(timezone.utc))
        self.assertFalse(check.ok)

    def test_the_window_of_the_latest_run_must_have_fully_passed(self) -> None:
        # At 21:45 Bucharest on a weekday, tonight's 21:40 run isn't "due" yet (window ends +90 min).
        now = datetime(2026, 10, 28, 19, 45, tzinfo=timezone.utc)  # Wed 21:45 EET
        expected = shc.last_expected_run(now, 21, 40)
        self.assertEqual((expected.day, expected.month), (27, 10))


class CheckPlanTest(unittest.TestCase):
    """Found 2026-10-29: sub-$1 remainders made plan() emit qty-0.000000 sells Alpaca would reject."""

    class _Broker:
        def __init__(self, positions):
            self._p = positions

        def account(self):
            from tae2.broker import Account

            return Account(10_000.0, 500.0, 500.0, "ACTIVE", False)

        def positions(self):
            return self._p

    def _prices(self):
        from tests.helpers import random_prices

        return random_prices(days=1600, start="2020-09-01").loc[:"2026-09-30"]

    _NOW = datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc)

    @staticmethod
    def _engine(weights):
        import pandas as pd

        class _E:
            @staticmethod
            def targets_for(name, prices, decision):
                return pd.Series(weights)

        return _E

    def test_a_clean_plan_passes(self) -> None:
        from tae2.broker import Position
        from tae2 import rebalance

        broker = self._Broker([Position("SPY", 10, 5_000.0), Position("IEF", 50, 4_500.0)])
        check = shc.check_plan("tae2", "s", self._engine({"SPY": 0.5, "IEF": 0.5}), rebalance, lambda: broker,
                               self._prices(), self._NOW)
        self.assertTrue(check.ok, check.detail)
        self.assertIn("ordine ipotetice", check.detail)

    def test_a_sell_that_floors_to_zero_is_flagged(self) -> None:
        from tae2.broker import Position
        from tae2.rebalance import Order

        class _Naive:  # the planner as it was before the dust fix
            @staticmethod
            def plan(targets, positions, equity, cash):
                return [Order("ADI", "sell", qty=3.25e-07, reason="exit")]

        broker = self._Broker([Position("ADI", 3.25e-07, 0.000138)])
        check = shc.check_plan("stocks", "s", self._engine({"SHY": 1.0}), _Naive, lambda: broker,
                               self._prices(), self._NOW)
        self.assertFalse(check.ok)
        self.assertIn("ADI", check.detail)
        self.assertIn("0.000000", check.detail)

    def test_the_real_planners_now_pass_with_dust_in_the_account(self) -> None:
        from tae2.broker import Position
        from stocks import rebalance as stocks_rebalance

        broker = self._Broker([Position("SPY", 10, 5_000.0), Position("IEF", 50, 4_500.0), Position("EFA", 4e-07, 0.00003)])
        check = shc.check_plan("stocks", "s", self._engine({"SPY": 0.5, "IEF": 0.5}), stocks_rebalance,
                               lambda: broker, self._prices(), self._NOW)
        self.assertTrue(check.ok, check.detail)

    def test_a_simulation_error_is_a_problem_not_a_crash(self) -> None:
        def boom():
            raise RuntimeError("no keys")

        check = shc.check_plan("tae2", "s", self._engine({"SPY": 1.0}), None, boom, self._prices(), self._NOW)
        self.assertFalse(check.ok)
        self.assertIn("no keys", check.detail)


class SelfHealTest(unittest.TestCase):
    def test_already_done_counts_as_ok(self) -> None:
        class _Module:
            @staticmethod
            def run(strategy, submit, prices, now):
                return _FakeReport("already_done")

        check = shc.self_heal("tae2", "core_gtaa_50", _Module(), "PRICES", datetime.now(timezone.utc))
        self.assertTrue(check.ok)

    def test_blocked_data_counts_as_a_problem(self) -> None:
        class _Module:
            @staticmethod
            def run(strategy, submit, prices, now):
                return _FakeReport("blocked_data", detail="SPY GAP")

        check = shc.self_heal("tae2", "core_gtaa_50", _Module(), "PRICES", datetime.now(timezone.utc))
        self.assertFalse(check.ok)

    def test_exception_is_captured_not_raised(self) -> None:
        class _Module:
            @staticmethod
            def run(strategy, submit, prices, now):
                raise RuntimeError("boom")

        check = shc.self_heal("tae2", "core_gtaa_50", _Module(), "PRICES", datetime.now(timezone.utc))
        self.assertFalse(check.ok)
        self.assertIn("boom", check.detail)


class HealthReportTest(unittest.TestCase):
    def test_ok_only_when_every_check_passes(self) -> None:
        report = shc.HealthReport()
        report.add("a", True, "fine")
        report.add("b", True, "fine")
        self.assertTrue(report.ok)
        report.add("c", False, "broken")
        self.assertFalse(report.ok)

    def test_markdown_flags_the_failing_check(self) -> None:
        report = shc.HealthReport()
        report.add("Teste", True, "OK")
        report.add("Cont tae2", False, "inaccesibil: timeout")
        text = shc.to_markdown(report, datetime(2026, 10, 9, tzinfo=timezone.utc))
        self.assertIn("PROBLEMĂ", text)
        self.assertIn("inaccesibil: timeout", text)
        self.assertIn("NECESITĂ ATENȚIE", text)


if __name__ == "__main__":
    unittest.main()
