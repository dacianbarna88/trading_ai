#!/usr/bin/env python3
"""Tests for tae_structural_governance.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hard_risk_guardian import STOP_LIMIT, evaluate_position_risk, run_paper_hard_risk
from tae_structural_governance import (
    EXECUTION_HIERARCHY,
    compute_final_verdict,
    gate_accounting_reconciliation,
    gate_capital_safety,
    gate_data_validity,
    check_forbidden_file_safety,
    StepRecord,
)


class HardRiskGuardianTest(unittest.TestCase):
    def test_stop_loss_at_minus_3(self) -> None:
        row = evaluate_position_risk("TEST", avg_price=100.0, current_price=96.9, shares=10)
        self.assertEqual(row["status"], "STOP_LOSS_BREACHED")
        self.assertEqual(row["hard_rule"], "HARD_STOP_LOSS_-3")

    def test_critical_at_minus_5(self) -> None:
        row = evaluate_position_risk("TEST", avg_price=100.0, current_price=94.0, shares=10)
        self.assertEqual(row["status"], "CRITICAL_LOSS")
        self.assertEqual(row["required_action"], "FORCE_SELL_REQUIRED")

    def test_stop_limit_constant(self) -> None:
        self.assertEqual(STOP_LIMIT, -3.0)


class StructuralGovernanceTest(unittest.TestCase):
    def test_execution_hierarchy_has_19_steps(self) -> None:
        self.assertEqual(len(EXECUTION_HIERARCHY), 19)
        ranks = [s["rank"] for s in EXECUTION_HIERARCHY]
        self.assertEqual(ranks, list(range(1, 20)))

    def test_forbidden_diff_clean_when_git_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch("tae_structural_governance.subprocess.run") as run:
                run.side_effect = [
                    mock.Mock(returncode=0, stdout="", stderr=""),
                    mock.Mock(returncode=0, stdout="", stderr=""),
                ]
                result = check_forbidden_file_safety(root)
        self.assertTrue(result["forbidden_content_diff_clean"])
        self.assertEqual(result["safety_status"], "PASS")

    def test_final_verdict_blocks_reconciliation_fail(self) -> None:
        steps = [
            StepRecord(2, "accounting_reconciliation", "ACCOUNTING", "HARD", False, "FAIL", "cash mismatch"),
        ]
        verdict, reasons = compute_final_verdict(
            steps,
            safety={"forbidden_content_diff_clean": True},
            paper_reconciliation={"ok": False, "errors": ["cash mismatch"]},
            hard_risk={"status": "PASS"},
            mtm_status="LIVE",
            paper_positions=1,
        )
        self.assertEqual(verdict, "BLOCKED_WITH_REASONS")
        self.assertTrue(any("reconciliation" in r for r in reasons))

    def test_final_verdict_ready_for_paper_day(self) -> None:
        steps = [
            StepRecord(19, "final_verdict", "FINAL", "HARD", True, "PASS", None),
        ]
        verdict, reasons = compute_final_verdict(
            steps,
            safety={"forbidden_content_diff_clean": True},
            paper_reconciliation={"ok": True, "errors": []},
            hard_risk={"status": "PASS", "breach_count": 0},
            mtm_status="LIVE",
            paper_positions=2,
        )
        self.assertEqual(verdict, "READY_FOR_PAPER_DAY")
        self.assertEqual(reasons, [])

    def test_gate_capital_safety_blocks_broker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            portfolio_path = Path(tmp) / "paper_portfolio.json"
            portfolio_path.write_text(
                json.dumps({"broker_executed": True, "live_money": False, "cash": 1000}),
                encoding="utf-8",
            )
            with mock.patch("tae_structural_governance.PAPER_PORTFOLIO_JSON", portfolio_path):
                step = gate_capital_safety()
        self.assertFalse(step.ok)
        self.assertIn("broker_executed", step.reason or "")

    def test_pde_hard_risk_override(self) -> None:
        from tae_paper_decision_engine import enforce_hard_risk_discipline

        scores = {a: 50.0 for a in ("BUY_PAPER", "SELL_PAPER", "PROTECT_PAPER", "HOLD_PAPER", "SKIP_PAPER", "REDUCE_PAPER", "ROTATE_PAPER")}
        evidence: list[str] = []
        ctx = {
            "paper_positions": {"LOSS": {"shares": 10}},
            "hard_risk_by": {
                "LOSS": {
                    "status": "STOP_LOSS_BREACHED",
                    "hard_rule": "HARD_STOP_LOSS_-3",
                    "pnl_pct": -3.5,
                    "required_action": "SELL_REQUIRED",
                }
            },
        }
        detail = enforce_hard_risk_discipline("LOSS", scores, evidence, ctx)
        self.assertTrue(detail["override"])
        self.assertEqual(scores["SELL_PAPER"], 100.0)
        self.assertEqual(scores["PROTECT_PAPER"], 0.0)


if __name__ == "__main__":
    unittest.main()
