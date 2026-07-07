#!/usr/bin/env python3
"""Tests for tae_adaptive_paper_weights.py and tae_live_promotion_lock.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_adaptive_paper_weights import (
    clamp_delta,
    clamp_weight,
    compute_action_weight,
    effective_weight_for,
    run_adaptive_paper_weights,
)
from tae_live_promotion_lock import audit_promotion_gate, enforce_promotion_gate


class AdaptivePaperWeightsTest(unittest.TestCase):
    def test_clamp_weight_and_delta(self) -> None:
        self.assertEqual(clamp_weight(1.5), 1.15)
        self.assertEqual(clamp_weight(0.5), 0.85)
        self.assertEqual(clamp_delta(0.05), 0.02)
        self.assertEqual(clamp_delta(-0.05), -0.02)

    def test_promising_increases_weight(self) -> None:
        row = compute_action_weight(
            "SELL_PAPER",
            verdict_counts={"PROMISING": 2},
            previous_weight=1.0,
            hints=None,
            knowledge_doc=None,
            global_risk_adj=0.0,
            evidence_sources=[],
        )
        self.assertGreater(row["new_weight"], row["previous_weight"])

    def test_reject_decreases_weight(self) -> None:
        row = compute_action_weight(
            "BUY_PAPER",
            verdict_counts={"REJECT": 2},
            previous_weight=1.0,
            hints=None,
            knowledge_doc=None,
            global_risk_adj=0.0,
            evidence_sources=[],
        )
        self.assertLess(row["new_weight"], row["previous_weight"])

    def test_needs_more_data_does_not_promote(self) -> None:
        row = compute_action_weight(
            "HOLD_PAPER",
            verdict_counts={"NEEDS_MORE_DATA": 5},
            previous_weight=1.0,
            hints=None,
            knowledge_doc=None,
            global_risk_adj=0.0,
            evidence_sources=[],
        )
        self.assertLessEqual(row["new_weight"], 1.0)

    def test_effective_weight_ticker_cap(self) -> None:
        doc = {
            "weights": {"BUY_PAPER": {"new_weight": 1.05}},
            "ticker_weights": {"MRK": {"BUY_PAPER": {"adjustment": 0.008}}},
        }
        eff = effective_weight_for("BUY_PAPER", "MRK", doc)
        self.assertAlmostEqual(eff["effective_multiplier"], 1.058, places=3)

    def test_run_adaptive_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            val_dir = base / "runtime_outputs" / "paper_decisions"
            val_dir.mkdir(parents=True)
            (val_dir / "decision_validation_results.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {"action": "SELL_PAPER", "verdict": "PROMISING", "ticker": "HSBA.L"},
                            {"action": "SKIP_PAPER", "verdict": "NEEDS_MORE_DATA", "ticker": "MRK"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = base / "runtime_outputs" / "adaptive_weights"
            with mock.patch("tae_adaptive_paper_weights.VALIDATION_JSON", val_dir / "decision_validation_results.json"), mock.patch(
                "tae_adaptive_paper_weights.OUTPUT_DIR", out_dir
            ), mock.patch("tae_adaptive_paper_weights.WEIGHTS_JSON", out_dir / "paper_action_weights.json"), mock.patch(
                "tae_adaptive_paper_weights.HISTORY_JSONL", out_dir / "paper_action_weights_history.jsonl"
            ), mock.patch("tae_adaptive_paper_weights.ADAPTATION_HINTS_JSON", base / "missing.json"), mock.patch(
                "tae_adaptive_paper_weights.CONFIDENCE_JSON", base / "missing.json"
            ), mock.patch("tae_adaptive_paper_weights.DPE_ADAPTIVE_JSON", base / "missing.json"), mock.patch(
                "tae_adaptive_paper_weights.MEMORY_INDEX_JSON", base / "missing.json"
            ), mock.patch("tae_adaptive_paper_weights.LONGITUDINAL_KNOWLEDGE_JSON", base / "missing.json"), mock.patch(
                "tae_adaptive_paper_weights.REPORT_MD", base / "report.md"
            ):
                result = run_adaptive_paper_weights()
                self.assertTrue(result["ok"])
                self.assertIn("SELL_PAPER", result["document"]["weights"])


class LivePromotionLockTest(unittest.TestCase):
    def test_enforce_gate(self) -> None:
        gate = enforce_promotion_gate(
            {
                "live_promotion_allowed": True,
                "recommendations": [
                    {"promotion_recommendation": "PROMOTE_TO_LIVE", "ticker": "MRK", "action": "HOLD_PAPER"},
                ],
            }
        )
        self.assertFalse(gate["live_promotion_allowed"])
        self.assertEqual(gate["recommendations"][0]["promotion_recommendation"], "PROMOTE_TO_LIVE_CANDIDATE")

    def test_audit_clean_gate(self) -> None:
        audit = audit_promotion_gate(
            {
                "live_promotion_allowed": False,
                "recommendations": [
                    {"promotion_recommendation": "PROMOTE_TO_LIVE_CANDIDATE", "operator_approval_required": True},
                ],
            }
        )
        self.assertEqual(audit["violations"], [])


if __name__ == "__main__":
    unittest.main()
