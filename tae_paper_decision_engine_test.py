#!/usr/bin/env python3
"""Tests for tae_paper_decision_engine.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_paper_decision_engine import (
    PAPER_ACTIONS,
    apply_dpe_evaluator_bias,
    apply_knowledge_base_bias,
    apply_named_confidence_rules,
    apply_named_rule,
    apply_rule_lifecycle_bias,
    build_decision,
    build_decisions,
    build_horizon_context,
    enforce_loss_discipline,
    enforce_position_discipline,
    score_actions_for_ticker,
)


class PaperDecisionEngineTest(unittest.TestCase):
    def _ctx(self) -> dict:
        return {
            "gii_by": {
                "MRK": {
                    "ticker": "MRK",
                    "recommended_shadow_strategy": "KEEP_GROWING_SHADOW",
                    "lifecycle_stage": "SURVIVED",
                    "capital_efficiency": 96.0,
                    "growth_score": 94.0,
                    "missed_usd": 2.0,
                    "current_pct": 5.0,
                    "collapse_probability": 0.05,
                    "opportunity_score": 10.0,
                    "opportunity_category": "UNKNOWN",
                },
                "HSBA.L": {
                    "ticker": "HSBA.L",
                    "recommended_shadow_strategy": "TIGHTEN_TRAIL_SHADOW",
                    "lifecycle_stage": "WEAKENING",
                    "capital_efficiency": 22.0,
                    "growth_score": 30.0,
                    "missed_usd": 45.0,
                    "current_pct": 3.0,
                    "collapse_probability": 0.4,
                    "opportunity_score": 70.0,
                    "opportunity_category": "CAPITAL_LOCKED",
                },
            },
            "shadow_by": {
                "HSBA.L": {
                    "protection_signal": "TRAILING_PROTECTION_SHADOW",
                    "missed_opportunity_usd": 45.0,
                    "current_pct": 3.0,
                }
            },
            "ppg_by": {
                "HSBA.L": {"governor_posture": "TRAIL_SHADOW"},
            },
            "live_positions": {"MRK": {"shares": 10}, "HSBA.L": {"shares": 5}},
            "paper_positions": {
                "MRK": {"shares": 10.0, "unrealized_pct": 5.0},
                "HSBA.L": {"shares": 5.0, "unrealized_pct": 3.0},
            },
            "signals": {"SPY": {"signal": "STRONG BUY", "score": 100.0}},
            "top_growth": ["MRK", "SPY"],
            "policy_state": "HIGH_RISK",
            "suggested_policy": "CAPITAL_PRESERVATION_SHADOW",
            "preferred_philosophy": "COLLABORATIVE",
            "cash_hint": 5000.0,
            "exp_by_ticker": {},
            "horizon_ssot": {
                "historical_returns": {
                    "MRK": {"2Y": 20.0, "5Y": 50.0, "10Y": 100.0, "20Y": 200.0},
                    "HSBA.L": {"2Y": -5.0, "5Y": 10.0, "10Y": 30.0, "20Y": 50.0},
                    "SPY": {"2Y": 15.0, "5Y": 40.0, "10Y": 90.0, "20Y": 180.0},
                },
                "strategic_returns": {"SPY": {"1M": 2.0, "1Y": 8.0}, "EWU": {"1M": -1.0, "1Y": 3.0}},
                "intraday_by_ticker": {},
                "cross_horizon_consistency": 97.0,
            },
        }

    def test_hold_for_healthy_winner(self) -> None:
        action, scores, _, _, _, _, _, _, _ = score_actions_for_ticker("MRK", self._ctx())
        self.assertEqual(action, "HOLD_PAPER")
        self.assertGreater(scores["HOLD_PAPER"], scores["SELL_PAPER"])

    def test_protect_or_rotate_for_risky(self) -> None:
        action, _, _, _, _, _, _, _, _ = score_actions_for_ticker("HSBA.L", self._ctx())
        self.assertIn(action, {"PROTECT_PAPER", "ROTATE_PAPER", "REDUCE_PAPER", "SELL_PAPER"})

    def test_buy_for_strong_signal(self) -> None:
        action, _, _, _, _, _, _, _, _ = score_actions_for_ticker("SPY", self._ctx())
        self.assertIn(action, {"BUY_PAPER", "SKIP_PAPER"})

    def test_decision_fields_complete(self) -> None:
        decision = build_decision("MRK", self._ctx(), seq=1)
        self.assertIn(decision["action"], PAPER_ACTIONS)
        self.assertFalse(decision["live_promotion_allowed"])
        self.assertEqual(decision["mode"], "PAPER_ONLY")
        self.assertTrue(decision["decision_id"].startswith("PDEC-MRK-"))
        self.assertIn("rejection_rule", decision)
        self.assertIn("promotion_rule", decision)

    def test_reduce_for_protect_shadow(self) -> None:
        ctx = self._ctx()
        ctx["ppg_by"]["AMAT"] = {"governor_posture": "PROTECT_SHADOW"}
        ctx["gii_by"]["AMAT"] = {
            "recommended_shadow_strategy": "PROTECT_PROFIT_SHADOW",
            "lifecycle_stage": "MATURE_WINNER",
            "capital_efficiency": 55.0,
            "growth_score": 50.0,
            "missed_usd": 25.0,
            "current_pct": 4.0,
            "collapse_probability": 0.2,
            "opportunity_score": 40.0,
            "opportunity_category": "LATE_PROTECTION",
        }
        ctx["live_positions"]["AMAT"] = {"shares": 3}
        ctx.setdefault("paper_positions", {})["AMAT"] = {"shares": 3.0, "unrealized_pct": 4.0, "current_pct": 4.0}
        action, _, _, _, _, _, _, _, _ = score_actions_for_ticker("AMAT", ctx)
        self.assertEqual(action, "REDUCE_PAPER")

    def test_hypothesis_reject_forces_skip(self) -> None:
        ctx = self._ctx()
        ctx["hypotheses"] = {
            "hypotheses": [
                {
                    "hypothesis_id": "LTB-TEST",
                    "affected_tickers": ["SPY"],
                    "validation_rule": "test",
                    "rejection_rule": "reject on fail",
                }
            ]
        }
        ctx["exp_by_ticker"] = {"SPY": [{"verdict": "REJECT", "hypothesis_id": "LTB-TEST"}]}
        action, _, _, applied, _, _, _, _, _ = score_actions_for_ticker("SPY", ctx)
        self.assertEqual(action, "SKIP_PAPER")
        self.assertTrue(applied)

    def test_knowledge_consumption_evidence(self) -> None:
        ctx = self._ctx()
        ctx["knowledge_base"] = {
            "entries": [
                {
                    "id": "kb_test",
                    "pattern_type": "MISSED_PROFIT_PROTECTION",
                    "recommendation": "TEST_TRAILING_SHADOW",
                    "shadow_only": True,
                    "subject": "MRK",
                }
            ]
        }
        ctx["longitudinal_knowledge"] = {
            "rules": [{"rule_id": "KNOW-SELL_PAPER", "confidence": 0.8, "category": "action_reliability"}]
        }
        ctx["confidence_evolution"] = {
            "confidence_evolution_entries": [
                {"hypothesis": "STOP_REENTRY_CHURN", "recommendation": "TEST_15M_COOLDOWN_SHADOW"}
            ],
            "final_recommendation": {"DO_NOT_PROMOTE": ["DO_NOT_PROMOTE_TO_LIVE"]},
        }
        ctx["dpe_eval"] = {"overall": {"winner": "COLLABORATIVE", "confidence_pct": 70.0}}
        ctx["ppg"] = {"portfolio_verdict": "PORTFOLIO_HIGH_RISK"}
        decision = build_decision("MRK", ctx, seq=99)
        self.assertIsNotNone(decision.get("knowledge_evidence"))
        self.assertIsNotNone(decision.get("longitudinal_knowledge_evidence"))
        self.assertIsNotNone(decision.get("dpe_evaluator_evidence"))
        self.assertFalse(decision["live_promotion_allowed"])
        self.assertIn("MISSED_PROFIT_PROTECTION", decision["knowledge_evidence"].get("rules_applied", []))

    def test_named_rules_change_scores(self) -> None:
        scores = {a: 50.0 for a in PAPER_ACTIONS}
        before_buy = scores["BUY_PAPER"]
        apply_named_rule(scores, "SCORE_DECAY_SHADOW")
        self.assertLess(scores["BUY_PAPER"], before_buy)

    def test_decision_includes_horizon_fields(self) -> None:
        decision = build_decision("MRK", self._ctx(), seq=1)
        for field in (
            "horizon_context",
            "short_term_trend_7d",
            "monthly_trend",
            "yearly_trend",
            "long_term_trend",
            "horizon_alignment_score",
            "horizon_conflict_flag",
            "horizon_reason",
        ):
            self.assertIn(field, decision)
        self.assertIn("7D", decision["horizon_context"])
        self.assertIn("20Y", decision["horizon_context"])
        self.assertIsNotNone(decision["horizon_reason"])

    def test_horizon_context_structure(self) -> None:
        hz = build_horizon_context("MRK", self._ctx())
        self.assertIn("horizon_context", hz)
        self.assertIsInstance(hz["horizon_conflict_flag"], bool)
        self.assertGreaterEqual(hz["horizon_alignment_score"], 0.0)

    def test_write_outputs_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out_dir = base / "runtime_outputs" / "paper_decisions"
            report_md = base / "TAE_PAPER_DECISION_ENGINE_REPORT.md"
            with mock.patch("tae_paper_decision_engine.OUTPUT_DIR", out_dir), mock.patch(
                "tae_paper_decision_engine.DECISIONS_JSON", out_dir / "paper_decisions.json"
            ), mock.patch(
                "tae_paper_decision_engine.DECISIONS_JSONL", out_dir / "paper_decisions.jsonl"
            ), mock.patch("tae_paper_decision_engine.REPORT_MD", report_md):
                from tae_paper_decision_engine import build_report_payload, write_outputs

                ctx = self._ctx()
                decisions = build_decisions(ctx)
                report = build_report_payload(decisions, ctx)
                paths = write_outputs(report)
                data = json.loads(paths[0].read_text(encoding="utf-8"))
                self.assertGreater(data["decision_count"], 0)
                self.assertFalse(data["live_promotion_allowed"])

    def test_position_discipline_blocks_protect_without_paper_position(self) -> None:
        ctx = self._ctx()
        ctx["paper_positions"] = {"MRK": {"shares": 10.0, "unrealized_pct": 2.0}}
        ctx["live_positions"] = {"MRK": {"shares": 10}, "ABBV": {"shares": 5}}
        scores = {"PROTECT_PAPER": 50.0, "SELL_PAPER": 10.0, "SKIP_PAPER": 5.0}
        evidence: list[str] = []
        result = enforce_position_discipline("ABBV", scores, evidence, ctx)
        self.assertIn("PROTECT_PAPER", result["blocked"])
        self.assertEqual(scores["PROTECT_PAPER"], 0.0)

    def test_loss_discipline_favors_sell_on_deep_loss(self) -> None:
        ctx = self._ctx()
        ctx["paper_positions"] = {
            "AMAT": {"shares": 3.0, "unrealized_pct": -7.5, "current_pct": -7.5},
        }
        ctx["gii_by"]["AMAT"] = {
            "lifecycle_stage": "PROFIT_DECAY",
            "capital_efficiency": 10.0,
            "current_pct": -7.5,
            "collapse_probability": 0.6,
        }
        scores = {"PROTECT_PAPER": 80.0, "SELL_PAPER": 20.0, "HOLD_PAPER": 5.0}
        evidence: list[str] = []
        result = enforce_loss_discipline("AMAT", scores, evidence, ctx, rule_states={"SCORE_DECAY_SHADOW": "DISABLED"})
        self.assertTrue(result["evaluated"])
        self.assertGreater(scores["SELL_PAPER"], scores["PROTECT_PAPER"])

    def test_disabled_rule_lifecycle_blocks_positive_influence(self) -> None:
        scores = {"SKIP_PAPER": 20.0, "BUY_PAPER": 10.0}
        evidence: list[str] = []
        ctx = {
            "rule_lifecycle": {
                "rules": {
                    "SCORE_DECAY_SHADOW": {"state": "DISABLED", "influence_multiplier": 0.0},
                }
            }
        }
        apply_rule_lifecycle_bias(scores, evidence, ctx, ["SCORE_DECAY_SHADOW"])
        self.assertLess(scores["SKIP_PAPER"], 20.0)


if __name__ == "__main__":
    unittest.main()
