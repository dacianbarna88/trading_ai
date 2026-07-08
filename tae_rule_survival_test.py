#!/usr/bin/env python3
"""Tests for tae_rule_survival.py."""

from __future__ import annotations

import unittest

from tae_rule_survival import classify_rule_state, build_rule_lifecycle


class RuleSurvivalTest(unittest.TestCase):
    def test_disabled_weak_rule(self) -> None:
        state, _ = classify_rule_state(
            {
                "total_decisions": 25,
                "wins": 1,
                "win_rate": 0.058,
                "net_pnl_impact": -176.0,
                "avg_actual_pnl": -7.04,
            }
        )
        self.assertEqual(state, "DISABLED")

    def test_trusted_rule(self) -> None:
        state, _ = classify_rule_state(
            {
                "total_decisions": 12,
                "wins": 8,
                "win_rate": 0.67,
                "net_pnl_impact": 120.0,
                "avg_actual_pnl": 10.0,
            }
        )
        self.assertEqual(state, "TRUSTED")

    def test_new_rule(self) -> None:
        state, _ = classify_rule_state({"total_decisions": 0})
        self.assertEqual(state, "NEW")

    def test_build_lifecycle(self) -> None:
        doc = build_rule_lifecycle(
            {
                "rules": {
                    "SCORE_DECAY_SHADOW": {
                        "total_decisions": 25,
                        "wins": 1,
                        "win_rate": 0.058,
                        "net_pnl_impact": -176.0,
                        "avg_actual_pnl": -7.04,
                    }
                }
            }
        )
        self.assertIn("SCORE_DECAY_SHADOW", doc["by_state"]["DISABLED"])


if __name__ == "__main__":
    unittest.main()
