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
    build_decision,
    build_decisions,
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
            "signals": {"SPY": {"signal": "STRONG BUY", "score": 100.0}},
            "top_growth": ["MRK", "SPY"],
            "policy_state": "HIGH_RISK",
            "suggested_policy": "CAPITAL_PRESERVATION_SHADOW",
            "preferred_philosophy": "COLLABORATIVE",
            "cash_hint": 5000.0,
            "exp_by_ticker": {},
        }

    def test_hold_for_healthy_winner(self) -> None:
        action, scores, _ = score_actions_for_ticker("MRK", self._ctx())
        self.assertEqual(action, "HOLD_PAPER")
        self.assertGreater(scores["HOLD_PAPER"], scores["SELL_PAPER"])

    def test_protect_or_rotate_for_risky(self) -> None:
        action, _, _ = score_actions_for_ticker("HSBA.L", self._ctx())
        self.assertIn(action, {"PROTECT_PAPER", "ROTATE_PAPER", "REDUCE_PAPER", "SELL_PAPER"})

    def test_buy_for_strong_signal(self) -> None:
        action, _, _ = score_actions_for_ticker("SPY", self._ctx())
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
        action, _, _ = score_actions_for_ticker("AMAT", ctx)
        self.assertEqual(action, "REDUCE_PAPER")

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


if __name__ == "__main__":
    unittest.main()
