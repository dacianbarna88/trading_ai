#!/usr/bin/env python3
"""Tests for tae_paper_experiment_runner.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_paper_experiment_runner import (
    assign_verdict,
    build_report_payload,
    run_experiments,
    score_hypothesis,
    score_lifecycle_hold,
)


class PaperExperimentRunnerTest(unittest.TestCase):
    def test_assign_verdict_promising(self) -> None:
        verdict = assign_verdict(
            deltas={
                "expected_profit_delta_usd": 20.0,
                "risk_delta": -0.1,
                "capital_efficiency_delta": 3.0,
            },
            confidence=0.7,
            has_data=True,
            action="PAPER_LIFECYCLE_HOLD",
        )
        self.assertEqual(verdict, "PROMISING")

    def test_assign_verdict_needs_data(self) -> None:
        verdict = assign_verdict(
            deltas={"expected_profit_delta_usd": 0.0, "risk_delta": 0.0, "capital_efficiency_delta": 0.0},
            confidence=0.5,
            has_data=False,
            action="PAPER_MAINTENANCE_REFRESH",
        )
        self.assertEqual(verdict, "NEEDS_MORE_DATA")

    def test_score_lifecycle_hold_positive_delta(self) -> None:
        ctx = {
            "gii_by_ticker": {
                "PG": {
                    "missed_usd": 10.0,
                    "profit_capture_efficiency": 0.4,
                    "capital_efficiency": 50.0,
                    "survival_probability": 0.8,
                    "collapse_probability": 0.1,
                    "opportunity_score": 20.0,
                }
            },
            "shadow_by_ticker": {},
            "portfolio_gii": {},
        }
        deltas = score_lifecycle_hold(["PG"], ctx, 0.6)
        self.assertGreater(deltas["expected_profit_delta_usd"], 0)

    def test_run_experiments_all_get_verdict(self) -> None:
        queue = [
            {
                "queue_id": "PEQ-1",
                "hypothesis_id": "LTB-LIFE-PG-01",
                "hypothesis_type": "WINNER_LIFECYCLE",
                "paper_experiment_action": "PAPER_LIFECYCLE_HOLD",
                "affected_tickers": ["PG"],
                "confidence": 0.6,
                "validation_rule": "test",
                "rejection_rule": "test",
            }
        ]
        hypotheses = {
            "hypotheses": [
                {
                    "hypothesis_id": "LTB-LIFE-PG-01",
                    "hypothesis_type": "WINNER_LIFECYCLE",
                    "target_metric": "profit_capture_rate",
                    "paper_experiment": {"action": "PAPER_LIFECYCLE_HOLD"},
                }
            ]
        }
        ctx = {
            "gii_by_ticker": {
                "PG": {
                    "missed_usd": 5.0,
                    "profit_capture_efficiency": 0.5,
                    "capital_efficiency": 60.0,
                    "survival_probability": 0.7,
                    "collapse_probability": 0.1,
                    "opportunity_score": 15.0,
                }
            },
            "shadow_by_ticker": {},
            "portfolio_gii": {},
            "dpe_competitive_totals": {},
            "dpe_collaborative_totals": {},
            "dpe_evaluation": {},
            "sources_present": {},
        }
        results = run_experiments(queue, hypotheses, ctx)
        self.assertEqual(len(results), 1)
        self.assertIn(results[0]["verdict"], {"PROMISING", "CONTINUE_TESTING", "REJECT", "NEEDS_MORE_DATA"})
        self.assertFalse(results[0]["live_promotion_allowed"])

    def test_write_outputs_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out_dir = base / "runtime_outputs" / "learning_to_profit"
            report_md = base / "TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md"
            with mock.patch("tae_paper_experiment_runner.OUTPUT_DIR", out_dir), mock.patch(
                "tae_paper_experiment_runner.RESULTS_JSON", out_dir / "experiment_results.json"
            ), mock.patch(
                "tae_paper_experiment_runner.RESULTS_JSONL", out_dir / "experiment_results.jsonl"
            ), mock.patch("tae_paper_experiment_runner.REPORT_MD", report_md):
                from tae_paper_experiment_runner import write_outputs

                report = build_report_payload(
                    [{"hypothesis_id": "H1"}],
                    [
                        {
                            "experiment_id": "EXP-H1",
                            "hypothesis_id": "H1",
                            "hypothesis_type": "WINNER_LIFECYCLE",
                            "verdict": "CONTINUE_TESTING",
                            "rank": 1,
                            "deltas": {
                                "expected_profit_delta_usd": 1.0,
                                "risk_delta": 0.0,
                                "capital_efficiency_delta": 0.5,
                            },
                            "confidence": 0.5,
                            "live_promotion_allowed": False,
                        }
                    ],
                    {"sources_present": {}},
                )
                paths = write_outputs(report)
                self.assertTrue(paths[0].is_file())
                data = json.loads(paths[0].read_text(encoding="utf-8"))
                self.assertEqual(data["experiments_run"], 1)


if __name__ == "__main__":
    unittest.main()
