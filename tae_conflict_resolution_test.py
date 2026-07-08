#!/usr/bin/env python3
"""Tests for tae_conflict_resolution.py."""

from __future__ import annotations

import unittest

from tae_conflict_resolution import (
    apply_conflict_resolution_bias,
    risk_adjusted_ev,
    resolve_ticker,
)


class ConflictResolutionTest(unittest.TestCase):
    def test_risk_adjusted_ev_formula(self) -> None:
        raev = risk_adjusted_ev(100.0, 0.6, 5.0)
        self.assertAlmostEqual(raev, 54.25, places=2)

    def test_hard_risk_forces_sell_winner(self) -> None:
        ctx = {
            "hard_risk_by": {
                "QQQ": {
                    "status": "STOP_LOSS_BREACHED",
                    "hard_rule": "HARD_STOP_LOSS_-3",
                    "pnl_pct": -3.5,
                    "required_action": "SELL_REQUIRED",
                }
            },
            "paper_positions": {"QQQ": {"shares": 10}},
            "gii_by": {"QQQ": {"missed_usd": 0, "capital_efficiency": 50}},
            "signals": {},
            "exp_by_ticker": {},
            "policy_state": "NORMAL",
            "suggested_policy": "OBSERVE",
            "cash_hint": 5000,
            "horizon_ssot": {"historical_returns": {}},
            "historical_runtime": {},
        }
        row = resolve_ticker("QQQ", ctx, recon_ok=True)
        self.assertEqual(row["winning_scenario"], "SELL_PAPER")
        self.assertEqual(row["final_authority"], "HARD_RULE")

    def test_high_risk_buy_allowed_with_positive_ev(self) -> None:
        ctx = {
            "hard_risk_by": {},
            "paper_positions": {},
            "gii_by": {
                "AAPL": {
                    "missed_usd": 50,
                    "capital_efficiency": 60,
                    "growth_score": 80,
                    "collapse_probability": 0.1,
                }
            },
            "signals": {"AAPL": {"signal": "STRONG BUY", "score": 95}},
            "exp_by_ticker": {"AAPL": [{"verdict": "PROMISING", "hypothesis_id": "H1"}]},
            "policy_state": "HIGH_RISK",
            "suggested_policy": "CAPITAL_PRESERVATION",
            "cash_hint": 12000,
            "dpe_eval": {"overall": {"confidence_pct": 72, "winner": "COLLABORATIVE"}},
            "dpe_adaptive": {"preferred_philosophy": "COLLABORATIVE", "confidence": 0.7},
            "horizon_ssot": {"historical_returns": {"AAPL": {"7D": 1.2, "1M": 2.0}}},
            "historical_runtime": {},
            "adaptation_hints": {},
            "paper_action_weights": {"weights": {"BUY_PAPER": 1.05}},
            "decision_replay": {},
            "rule_lifecycle": {"rules": {}},
            "top_growth": ["AAPL"],
        }
        row = resolve_ticker("AAPL", ctx, recon_ok=True)
        buy = next(s for s in row["scenario_ev_table"] if s["action"] == "BUY_PAPER")
        self.assertGreater(buy["risk_adjusted_EV"], 0)
        if row.get("high_risk_buy_allowed"):
            self.assertEqual(row["winning_scenario"], "BUY_PAPER")

    def test_apply_bias_boosts_ev_winner(self) -> None:
        scores = {a: 10.0 for a in ("BUY_PAPER", "SKIP_PAPER", "HOLD_PAPER", "SELL_PAPER", "PROTECT_PAPER", "REDUCE_PAPER", "ROTATE_PAPER")}
        ctx = {
            "conflict_resolution_by_ticker": {
                "MSFT": {
                    "winning_scenario": "BUY_PAPER",
                    "final_authority": "EV_OPTIMIZER",
                    "high_risk_buy_allowed": True,
                    "idle_cash_usd": 8000,
                    "scenario_ev_table": [
                        {
                            "action": "BUY_PAPER",
                            "risk_adjusted_EV": 12.5,
                            "expected_drawdown": 3.0,
                            "hard_rule_status": {"blocked": False},
                        },
                        {"action": "SKIP_PAPER", "risk_adjusted_EV": 1.0, "hard_rule_status": {"blocked": False}},
                    ],
                }
            }
        }
        evidence: list[str] = []
        detail = apply_conflict_resolution_bias("MSFT", scores, evidence, ctx)
        self.assertGreater(scores["BUY_PAPER"], scores["SKIP_PAPER"])
        self.assertEqual(detail.get("winning_scenario"), "BUY_PAPER")


if __name__ == "__main__":
    unittest.main()
