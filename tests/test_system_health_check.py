from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

import system_health_check as shc
from tae2.data import Issue


@dataclass
class _FakeReport:
    status: str
    decision_date: str = "2026-10-01"
    detail: str = ""


class CheckDataTest(unittest.TestCase):
    def test_passes_with_no_issues(self) -> None:
        def load(refresh: bool):
            return "PRICES", []

        check, prices = shc.check_data("x", load)
        self.assertTrue(check.ok)
        self.assertEqual(prices, "PRICES")

    def test_jump_alone_does_not_block(self) -> None:
        def load(refresh: bool):
            return "PRICES", [Issue("SPY", "JUMP", "2020-01-01 moved 30%")]

        check, prices = shc.check_data("x", load)
        self.assertTrue(check.ok)
        self.assertIn("tolerate", check.detail)

    def test_gap_blocks(self) -> None:
        def load(refresh: bool):
            return "PRICES", [Issue("SPY", "GAP", "5 days missing")]

        check, prices = shc.check_data("x", load)
        self.assertFalse(check.ok)
        self.assertIn("GAP", check.detail)

    def test_fetch_exception_is_captured_not_raised(self) -> None:
        def load(refresh: bool):
            raise RuntimeError("yfinance down")

        check, prices = shc.check_data("x", load)
        self.assertFalse(check.ok)
        self.assertIsNone(prices)
        self.assertIn("yfinance down", check.detail)


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
