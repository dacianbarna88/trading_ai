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


class PaperDecisionValidationInfraTest(unittest.TestCase):
    def _write_fixture(self, base: Path) -> Path:
        pd_dir = base / "runtime_outputs" / "paper_decisions"
        pd_dir.mkdir(parents=True)
        dec_path = pd_dir / "paper_decisions.jsonl"
        decision = {
            "decision_id": "PDEC-TEST-001",
            "ticker": "MRK",
            "action": "HOLD_PAPER",
            "confidence": 0.7,
            "expected_profit_delta": 2.0,
            "expected_risk_delta": 0.02,
            "capital_efficiency_delta": 0.0,
            "evidence": "healthy winner; GII growth strong",
            "hypothesis_rules_applied": [{"hypothesis_id": "LTB-MRK-001"}],
        }
        dec_path.write_text(json.dumps(decision) + "\n", encoding="utf-8")
        gii_path = base / "tae_growth_intelligence.json"
        gii_path.write_text(
            json.dumps(
                {
                    "tickers": [
                        {
                            "ticker": "MRK",
                            "missed_usd": 12.0,
                            "capital_efficiency": 90.0,
                            "growth_score": 90.0,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return pd_dir, dec_path, gii_path

    def test_run_paper_decision_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pd_dir, dec_path, gii_path = self._write_fixture(base)
            with mock.patch("tae_dpe_paper_executor_infra.PAPER_DECISIONS_JSONL", dec_path), mock.patch(
                "tae_dpe_paper_executor_infra.PAPER_DECISION_VALIDATION_DIR", pd_dir
            ), mock.patch("tae_dpe_paper_executor_infra.GII_JSON", gii_path), mock.patch(
                "tae_dpe_paper_executor_infra.SHADOW_JSON", base / "x.json"
            ), mock.patch("tae_dpe_paper_executor_infra.PROTECTION_VALIDATION_JSON", base / "y.json"), mock.patch(
                "tae_dpe_paper_executor_infra.DECISION_VALIDATION_REPORT_MD", base / "TAE_PAPER_DECISION_VALIDATION_REPORT.md"
            ), mock.patch("tae_dpe_paper_executor_infra.EXPERIMENT_RUNNER_REPORT_MD", base / "TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md"):
                from tae_dpe_paper_executor_infra import run_paper_decision_validation

                report, code = run_paper_decision_validation()
                self.assertEqual(code, 0)
                self.assertEqual(report["decisions_unique"], 1)
                row = report["results"][0]
                self.assertTrue(row["paper_decision_consumed"])
                self.assertIsNotNone(row["profit_delta"])
                self.assertIsNotNone(row["reason"])
                self.assertEqual(row["source_decision_id"], "PDEC-TEST-001")
                self.assertEqual(row["source_hypothesis_id"], "LTB-MRK-001")
                self.assertEqual(row["mode"], "PAPER_ONLY")
                self.assertFalse(row["live_promotion_allowed"])
                self.assertTrue(row["evidence_summary"])

    def test_dedupe_json_and_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pd_dir, dec_path, gii_path = self._write_fixture(base)
            decision = json.loads(dec_path.read_text(encoding="utf-8").strip())
            (pd_dir / "paper_decisions.json").write_text(
                json.dumps({"decisions": [decision, decision]}),
                encoding="utf-8",
            )
            with mock.patch("tae_dpe_paper_executor_infra.PAPER_DECISIONS_JSONL", dec_path), mock.patch(
                "tae_dpe_paper_executor_infra.PAPER_DECISION_VALIDATION_DIR", pd_dir
            ), mock.patch("tae_dpe_paper_executor_infra.GII_JSON", gii_path), mock.patch(
                "tae_dpe_paper_executor_infra.SHADOW_JSON", base / "x.json"
            ), mock.patch("tae_dpe_paper_executor_infra.PROTECTION_VALIDATION_JSON", base / "y.json"), mock.patch(
                "tae_dpe_paper_executor_infra.DECISION_VALIDATION_REPORT_MD", base / "TAE_PAPER_DECISION_VALIDATION_REPORT.md"
            ), mock.patch("tae_dpe_paper_executor_infra.EXPERIMENT_RUNNER_REPORT_MD", base / "TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md"):
                from tae_dpe_paper_executor_infra import run_paper_decision_validation

                report, code = run_paper_decision_validation()
                self.assertEqual(code, 0)
                self.assertEqual(report["decisions_unique"], 1)
                self.assertGreater(report["decisions_consumed_raw"], 1)

    def test_ranking_and_reasons_for_verdicts(self) -> None:
        from tae_dpe_paper_executor_infra import (
            build_validation_reason,
            rank_validation_results,
            score_paper_decision,
        )

        gii_by = {"MRK": {"missed_usd": 20.0, "growth_score": 85.0, "capital_efficiency": 80.0}}
        promising = score_paper_decision(
            {
                "decision_id": "PDEC-A",
                "ticker": "MRK",
                "action": "PROTECT_PAPER",
                "confidence": 0.8,
                "expected_profit_delta": 15.0,
            },
            gii_by=gii_by,
            shadow_by={},
            validation={"gates": {"gates_passed": True}},
        )
        continue_row = score_paper_decision(
            {
                "decision_id": "PDEC-B",
                "ticker": "LLY",
                "action": "HOLD_PAPER",
                "confidence": 0.5,
                "expected_profit_delta": 5.0,
            },
            gii_by={"LLY": {"missed_usd": 8.0, "growth_score": 70.0, "capital_efficiency": 75.0}},
            shadow_by={},
            validation=None,
        )
        self.assertIsNotNone(promising["profit_delta"])
        self.assertIsNotNone(promising["reason"])
        self.assertIsNotNone(continue_row["profit_delta"])
        self.assertIsNotNone(continue_row["reason"])
        ranked = rank_validation_results([continue_row, promising])
        self.assertEqual(ranked[0]["decision_id"], promising["decision_id"])
        self.assertEqual(ranked[0]["rank"], 1)

        reject_reason = build_validation_reason(
            "REJECT",
            action="BUY_PAPER",
            ticker="BAD",
            deltas={"expected_profit_delta_usd": -2.0, "expected_risk_delta": 0.05, "capital_efficiency_delta": -1.0},
            confidence=0.3,
            decision={"rejection_rule": "fail fast"},
            validation=None,
            gii_row=None,
        )
        self.assertIn("REJECT", reject_reason)

        needs_reason = build_validation_reason(
            "NEEDS_MORE_DATA",
            action="SKIP_PAPER",
            ticker="X",
            deltas={"expected_profit_delta_usd": 0.0, "expected_risk_delta": 0.0, "capital_efficiency_delta": 0.0},
            confidence=0.2,
            decision={},
            validation=None,
            gii_row=None,
        )
        self.assertIn("NEEDS_MORE_DATA", needs_reason)
        self.assertIn("missing", needs_reason.lower())


if __name__ == "__main__":
    unittest.main()
