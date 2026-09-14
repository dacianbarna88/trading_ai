#!/usr/bin/env python3
"""Regression coverage for tae_execution_realism_stress_test.py's pure
cost math — roadmap item 7 (2026-09-14)."""

from __future__ import annotations

import unittest

import tae_execution_realism_stress_test as stress


class ApplyCostTest(unittest.TestCase):
    def test_zero_bps_leaves_gross_pnl_unchanged(self) -> None:
        trade = {"gross_pnl": 100.0, "entry_notional": 1000.0, "exit_notional": 1100.0}
        self.assertAlmostEqual(stress._apply_cost(trade, 0.0), 100.0)

    def test_positive_bps_reduces_pnl(self) -> None:
        trade = {"gross_pnl": 100.0, "entry_notional": 1000.0, "exit_notional": 1000.0}
        # 10 bps round-trip = 5 bps/leg = 0.0005 * 1000 * 2 legs = 1.0 cost
        self.assertAlmostEqual(stress._apply_cost(trade, 10.0), 99.0)

    def test_cost_scales_with_notional(self) -> None:
        small = {"gross_pnl": 0.0, "entry_notional": 100.0, "exit_notional": 100.0}
        large = {"gross_pnl": 0.0, "entry_notional": 10000.0, "exit_notional": 10000.0}
        self.assertLess(stress._apply_cost(large, 50.0), stress._apply_cost(small, 50.0))


class DecisionScoreIndexTest(unittest.TestCase):
    def test_ignores_decisions_without_a_score(self) -> None:
        decisions = [{"decision_id": "A", "score": 80.0}, {"decision_id": "B", "score": None}]
        idx = stress._decision_score_index(decisions)
        self.assertEqual(idx.get("A"), 80.0)
        self.assertNotIn("B", idx)


if __name__ == "__main__":
    unittest.main()
