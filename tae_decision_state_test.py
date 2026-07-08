#!/usr/bin/env python3
"""Tests for tae_decision_state.py — switch gating and STOP_REENTRY_CHURN."""

from __future__ import annotations

import unittest

from tae_decision_state import evaluate_action_switch, ev_margin_actual


class DecisionStateTest(unittest.TestCase):
    def test_ev_margin_actual_relative(self) -> None:
        self.assertAlmostEqual(ev_margin_actual(115.0, 100.0), 0.15, places=4)

    def test_hard_rule_bypasses_buy_to_sell(self) -> None:
        state = {"last_executed_action": "BUY_PAPER", "churn_risk": "HIGH"}
        result = evaluate_action_switch(
            "HD",
            "SELL_PAPER",
            state=state,
            hard_rule_override=True,
            scenario_raev={"SELL_PAPER": 50.0, "BUY_PAPER": 80.0},
            held=True,
        )
        self.assertTrue(result["decision_switch_authorized"])
        self.assertEqual(result["switch_reason"], "hard_rule_bypass")

    def test_buy_to_sell_blocked_without_margin(self) -> None:
        state = {"last_executed_action": "BUY_PAPER", "churn_risk": "MEDIUM"}
        result = evaluate_action_switch(
            "DIA",
            "SELL_PAPER",
            state=state,
            hard_rule_override=False,
            scenario_raev={"SELL_PAPER": 52.0, "HOLD_PAPER": 50.0, "BUY_PAPER": 51.0},
            held=True,
        )
        self.assertFalse(result["decision_switch_authorized"])
        self.assertEqual(result["final_action"], "HOLD_PAPER")

    def test_stop_reentry_churn_enforced(self) -> None:
        state = {
            "last_executed_action": "SELL_PAPER",
            "churn_risk": "HIGH",
            "cooldown_status": {"active": True, "minutes_remaining": 20},
        }
        result = evaluate_action_switch(
            "GE",
            "BUY_PAPER",
            state=state,
            hard_rule_override=False,
            scenario_raev={"BUY_PAPER": 60.0, "SKIP_PAPER": 55.0},
            held=False,
        )
        self.assertFalse(result["decision_switch_authorized"])
        self.assertEqual(result["switch_reason"], "STOP_REENTRY_CHURN_ENFORCED")
        self.assertEqual(result["final_action"], "SKIP_PAPER")

    def test_loss_breach_allows_sell_after_buy(self) -> None:
        state = {"last_executed_action": "BUY_PAPER"}
        result = evaluate_action_switch(
            "AMAT",
            "SELL_PAPER",
            state=state,
            hard_rule_override=False,
            scenario_raev={"SELL_PAPER": 40.0, "BUY_PAPER": 60.0},
            loss_context={"current_pct": -3.5},
            held=True,
        )
        self.assertTrue(result["decision_switch_authorized"])
        self.assertEqual(result["switch_reason"], "loss_breach_or_risk_deterioration")


if __name__ == "__main__":
    unittest.main()
