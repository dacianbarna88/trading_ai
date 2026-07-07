#!/usr/bin/env python3
"""Tests for tae_learning_to_profit_bridge.py — PAPER_ONLY hypothesis generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_learning_to_profit_bridge import (
    build_bridge_report,
    build_paper_queue,
    generate_capital_efficiency_hypotheses,
    generate_dpe_philosophy_hypotheses,
    generate_opportunity_cost_hypotheses,
    generate_profit_protection_hypotheses,
    generate_stale_learning_hypotheses,
    generate_winner_lifecycle_hypotheses,
    load_sources,
)


class LearningToProfitBridgeTest(unittest.TestCase):
    def test_capital_efficiency_from_gii(self) -> None:
        gii = {
            "tickers": [
                {
                    "ticker": "LOW.L",
                    "capital_efficiency": 18.0,
                    "current_pct": 2.5,
                    "missed_usd": 40.0,
                    "recommended_shadow_strategy": "REDUCE_EXPOSURE_SHADOW",
                },
                {
                    "ticker": "GOOD.L",
                    "capital_efficiency": 72.0,
                    "current_pct": 5.0,
                    "missed_usd": 5.0,
                    "recommended_shadow_strategy": "KEEP_GROWING_SHADOW",
                },
            ]
        }
        hyps = generate_capital_efficiency_hypotheses(gii, loaded=True)
        self.assertEqual(len(hyps), 1)
        self.assertEqual(hyps[0]["hypothesis_type"], "CAPITAL_EFFICIENCY")
        self.assertEqual(hyps[0]["affected_tickers"], ["LOW.L"])
        self.assertFalse(hyps[0]["live_promotion_allowed"])
        self.assertEqual(hyps[0]["mode"], "PAPER_ONLY")

    def test_profit_protection_from_shadow(self) -> None:
        shadow = {
            "positions": [
                {
                    "ticker": "HSBA.L",
                    "protection_signal": "TRAILING_PROTECTION_SHADOW",
                    "suggested_shadow_action": "TIGHTEN_TRAIL_SHADOW",
                    "missed_opportunity_usd": 55.0,
                }
            ]
        }
        hyps = generate_profit_protection_hypotheses(shadow, None, shadow_loaded=True, ppg_loaded=False)
        self.assertGreaterEqual(len(hyps), 1)
        self.assertEqual(hyps[0]["paper_experiment"]["action"], "PAPER_TRAILING_PROTECT_TRIM")

    def test_opportunity_cost_from_ledger(self) -> None:
        ledger = {
            "ledger": [
                {
                    "ticker": "BARC.L",
                    "missed_usd": 80.0,
                    "opportunity_cost_category": "CAPITAL_LOCKED",
                    "opportunity_cost_severity": "HIGH",
                    "recommended_shadow_fix": "REDUCE_EXPOSURE_SHADOW",
                }
            ]
        }
        hyps = generate_opportunity_cost_hypotheses(ledger, None, ledger_loaded=True, gii_loaded=False)
        self.assertEqual(len(hyps), 1)
        self.assertEqual(hyps[0]["hypothesis_type"], "OPPORTUNITY_COST")

    def test_winner_lifecycle_from_profiler(self) -> None:
        lifecycle = {
            "profiles": [
                {
                    "ticker": "VOD.L",
                    "lifecycle_stage": "MATURE_WINNER",
                    "optimal_shadow_action": "KEEP_GROWING_SHADOW",
                    "lifecycle_score": 78.0,
                    "missed_usd": 30.0,
                    "confidence": 0.72,
                }
            ]
        }
        hyps = generate_winner_lifecycle_hypotheses(lifecycle, None, lifecycle_loaded=True, gii_loaded=False)
        self.assertEqual(len(hyps), 1)
        self.assertEqual(hyps[0]["paper_experiment"]["action"], "PAPER_LIFECYCLE_HOLD")

    def test_dpe_philosophy_hypothesis(self) -> None:
        adaptive = {
            "preferred_philosophy": "COLLABORATIVE",
            "competitive_pct": 31.2,
            "collaborative_pct": 68.8,
            "confidence": 62.0,
            "reason": "Collaborative wins on capture rate",
        }
        evaluation = {"overall": {"winner": "COLLABORATIVE", "confidence_pct": 65.0, "reason": "capture"}}
        learning = {"records": [{"evaluation_id": "e1"}], "summary": {"dominant_philosophy": "COLLABORATIVE"}}
        hyps = generate_dpe_philosophy_hypotheses(
            adaptive, evaluation, learning, adaptive_loaded=True, evaluation_loaded=True, learning_loaded=True
        )
        self.assertEqual(len(hyps), 1)
        self.assertEqual(hyps[0]["hypothesis_type"], "DPE_PHILOSOPHY")
        self.assertEqual(hyps[0]["paper_experiment"]["action"], "PAPER_DPE_PHILOSOPHY_WEIGHT")

    def test_stale_learning_when_sources_missing(self) -> None:
        loaded = {k: False for k in ("growth_intelligence", "dpe_adaptive", "dpe_learning")}
        with mock.patch("tae_learning_to_profit_bridge.FRESHNESS_HOURS", {"growth_intelligence": (Path("x.json"), 24)}):
            hyps = generate_stale_learning_hypotheses(loaded)
        self.assertEqual(len(hyps), 1)
        self.assertEqual(hyps[0]["hypothesis_type"], "STALE_LEARNING")

    def test_build_bridge_report_integrated(self) -> None:
        payloads = {
            "growth_intelligence": {
                "tickers": [
                    {
                        "ticker": "T1.L",
                        "capital_efficiency": 10.0,
                        "current_pct": 1.0,
                        "missed_usd": 50.0,
                        "recommended_shadow_strategy": "REDUCE_EXPOSURE_SHADOW",
                        "lifecycle_stage": "WEAKENING",
                        "opportunity_category": "CAPITAL_LOCKED",
                    }
                ]
            },
            "opportunity_ledger": None,
            "winner_lifecycle": None,
            "ppg": None,
            "appe": None,
            "profit_protection_shadow": None,
            "profit_protection_validation": None,
            "dpe_evaluation": None,
            "dpe_learning": None,
            "dpe_adaptive": None,
            "decision_replay": None,
            "confidence_evolution": None,
            "pattern_discovery_present": {"present": False},
        }
        loaded = {
            "growth_intelligence": True,
            "opportunity_ledger": False,
            "winner_lifecycle": False,
            "ppg": False,
            "appe": False,
            "profit_protection_shadow": False,
            "profit_protection_validation": False,
            "dpe_evaluation": False,
            "dpe_learning": False,
            "dpe_adaptive": False,
            "decision_replay": False,
            "confidence_evolution": False,
            "pattern_discovery": False,
        }
        report = build_bridge_report(payloads, loaded)
        self.assertGreater(report["hypothesis_count"], 0)
        self.assertFalse(report["live_promotion_allowed"])
        self.assertEqual(report["mode"], "PAPER_ONLY")
        queue = build_paper_queue(report["hypotheses"])
        self.assertEqual(len(queue), report["hypothesis_count"])
        self.assertTrue(all(not q["live_promotion_allowed"] for q in queue))

    def test_write_outputs_safe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out_dir = base / "runtime_outputs" / "learning_to_profit"
            report_md = base / "TAE_LEARNING_TO_PROFIT_BRIDGE_REPORT.md"
            with mock.patch("tae_learning_to_profit_bridge.OUTPUT_DIR", out_dir), mock.patch(
                "tae_learning_to_profit_bridge.HYPOTHESES_JSON", out_dir / "hypotheses.json"
            ), mock.patch("tae_learning_to_profit_bridge.QUEUE_JSONL", out_dir / "paper_experiment_queue.jsonl"), mock.patch(
                "tae_learning_to_profit_bridge.REPORT_MD", report_md
            ):
                from tae_learning_to_profit_bridge import write_outputs

                report = {
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "hypothesis_count": 1,
                    "sources_loaded_count": 1,
                    "hypotheses": [
                        {
                            "hypothesis_id": "LTB-TEST-001",
                            "hypothesis_type": "CAPITAL_EFFICIENCY",
                            "rank": 1,
                            "priority_score": 10,
                            "confidence": 0.5,
                            "risk_level": "LOW",
                            "target_metric": "capital_efficiency",
                            "expected_profit_mechanism": "test",
                            "validation_rule": "test",
                            "rejection_rule": "test",
                            "required_paper_duration": 21,
                            "affected_tickers": ["X.L"],
                            "source_systems": ["test"],
                            "paper_experiment": {"action": "PAPER_TEST", "description": "test"},
                            "created_at": "2026-01-01T00:00:00+00:00",
                        }
                    ],
                    "summary": {"by_type": {"CAPITAL_EFFICIENCY": 1}, "required_types_present": {}},
                }
                paths = write_outputs(report)
                self.assertTrue(paths[0].is_file())
                self.assertTrue(paths[1].is_file())
                data = json.loads(paths[0].read_text(encoding="utf-8"))
                self.assertEqual(data["hypothesis_count"], 1)


if __name__ == "__main__":
    unittest.main()
