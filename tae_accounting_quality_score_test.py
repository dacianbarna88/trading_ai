#!/usr/bin/env python3
"""Regression coverage for tae_accounting_quality_score.py — Sprint 3 Phase 5."""

from __future__ import annotations

import unittest

import tae_accounting_quality_score as fscore


def _row(latest: float | None, year_ago: float | None, *, extra: dict | None = None) -> dict:
    """period 0 = latest (2026-06-30), period 4 = year-ago (2025-06-30),
    with 3 filler quarters in between so _year_ago's lookback=4 lands
    exactly on the intended value."""
    row = {
        "2026-06-30": latest,
        "2026-03-31": None,
        "2025-12-31": None,
        "2025-09-30": None,
        "2025-06-30": year_ago,
    }
    if extra:
        row.update(extra)
    return row


class SingleCriterionTest(unittest.TestCase):
    def test_positive_net_income(self) -> None:
        self.assertEqual(fscore.positive_net_income(_row(10.0, 5.0)), 1)
        self.assertEqual(fscore.positive_net_income(_row(-10.0, 5.0)), 0)
        self.assertIsNone(fscore.positive_net_income({}))

    def test_positive_operating_cash_flow(self) -> None:
        self.assertEqual(fscore.positive_operating_cash_flow(_row(5.0, 1.0)), 1)
        self.assertEqual(fscore.positive_operating_cash_flow(_row(-5.0, 1.0)), 0)

    def test_roa_improving_requires_both_periods(self) -> None:
        ni = _row(20.0, 10.0)
        ta = _row(200.0, 200.0)  # ROA now=0.10, then=0.05 -> improving
        self.assertEqual(fscore.roa_improving(ni, ta), 1)
        self.assertIsNone(fscore.roa_improving(ni, {}))

    def test_cash_flow_exceeds_net_income(self) -> None:
        self.assertEqual(fscore.cash_flow_exceeds_net_income(_row(15.0, 0.0), _row(10.0, 0.0)), 1)
        self.assertEqual(fscore.cash_flow_exceeds_net_income(_row(5.0, 0.0), _row(10.0, 0.0)), 0)

    def test_leverage_decreasing(self) -> None:
        debt = _row(50.0, 80.0)
        assets = _row(200.0, 200.0)  # leverage now=0.25, then=0.40 -> decreasing
        self.assertEqual(fscore.leverage_decreasing(debt, assets), 1)

    def test_current_ratio_improving(self) -> None:
        ca = _row(120.0, 100.0)
        cl = _row(100.0, 100.0)  # ratio now=1.2, then=1.0
        self.assertEqual(fscore.current_ratio_improving(ca, cl), 1)

    def test_no_new_shares_issued(self) -> None:
        self.assertEqual(fscore.no_new_shares_issued(_row(1000.0, 1000.0)), 1)  # unchanged = pass
        self.assertEqual(fscore.no_new_shares_issued(_row(1100.0, 1000.0)), 0)  # diluted = fail

    def test_gross_margin_improving(self) -> None:
        gp = _row(60.0, 40.0)
        rev = _row(100.0, 100.0)  # margin now=0.60, then=0.40
        self.assertEqual(fscore.gross_margin_improving(gp, rev), 1)

    def test_asset_turnover_improving(self) -> None:
        rev = _row(120.0, 100.0)
        ta = _row(200.0, 200.0)
        self.assertEqual(fscore.asset_turnover_improving(rev, ta), 1)

    def test_zero_denominator_is_none_not_a_crash(self) -> None:
        self.assertIsNone(fscore.leverage_decreasing(_row(50.0, 80.0), _row(0.0, 200.0)))


class ComputeFScoreTest(unittest.TestCase):
    def test_full_statements_score_all_nine_criteria(self) -> None:
        statements = {
            "income": {
                "Net Income": _row(20.0, 10.0),
                "Total Revenue": _row(120.0, 100.0),
                "Gross Profit": _row(60.0, 40.0),
            },
            "balance_sheet": {
                "Total Assets": _row(200.0, 200.0),
                "Total Debt": _row(50.0, 80.0),
                "Current Assets": _row(120.0, 100.0),
                "Current Liabilities": _row(100.0, 100.0),
                "Ordinary Shares Number": _row(1000.0, 1000.0),
            },
            "cashflow": {
                "Operating Cash Flow": _row(25.0, 8.0),
            },
        }
        result = fscore.compute_f_score(statements)
        self.assertEqual(result["scoreable"], 9)
        self.assertEqual(result["points"], 9)
        self.assertEqual(result["score"], 1.0)

    def test_bank_shaped_statements_skip_unavailable_criteria_not_fail_them(self) -> None:
        """HSBA.L-shaped gap (verified live 2026-09-13): no Gross Profit,
        no cash-flow statement at all. Those 3 criteria (cash_flow_
        exceeds_net_income, positive_operating_cash_flow,
        gross_margin_improving) must be None, not 0 -- and must not
        shrink the denominator penalizing the ticker for a data gap."""
        statements = {
            "income": {
                "Net Income": _row(20.0, 10.0),
                "Total Revenue": _row(120.0, 100.0),
                # no Gross Profit key at all -- bank-shaped
            },
            "balance_sheet": {
                "Total Assets": _row(200.0, 200.0),
                "Total Debt": _row(50.0, 80.0),
                "Current Assets": _row(120.0, 100.0),
                "Current Liabilities": _row(100.0, 100.0),
                "Ordinary Shares Number": _row(1000.0, 1000.0),
            },
            "cashflow": {},  # no cash-flow statement at all
        }
        result = fscore.compute_f_score(statements)
        self.assertIsNone(result["criteria"]["positive_operating_cash_flow"])
        self.assertIsNone(result["criteria"]["cash_flow_exceeds_net_income"])
        self.assertIsNone(result["criteria"]["gross_margin_improving"])
        self.assertEqual(result["scoreable"], 6)  # 9 - 3 unscoreable
        self.assertIsNotNone(result["score"])

    def test_completely_empty_statements_is_none_score_not_zero(self) -> None:
        result = fscore.compute_f_score({})
        self.assertEqual(result["scoreable"], 0)
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
