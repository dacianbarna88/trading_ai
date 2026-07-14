#!/usr/bin/env python3
"""Tests for tae_full_paper_cycle.py and tae_full_implementation_audit.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_full_implementation_audit import build_gap_backlog, build_inventory, build_logic_map
from tae_full_paper_cycle import (
    build_promotion_gate,
    check_forbidden_file_safety,
    collect_summary,
    compare_constitutional_evolution,
    feedback_artifacts_exist,
    forbidden_files_unchanged,
    map_validation_verdict,
)


class FullImplementationAuditTest(unittest.TestCase):
    def test_build_inventory(self) -> None:
        inv = build_inventory()
        self.assertIn("components", inv)
        self.assertGreater(inv["summary"]["components_total"], 10)

    def test_build_logic_map(self) -> None:
        logic = build_logic_map()
        self.assertGreater(logic["active_edge_count"], 5)
        self.assertIn("multi_horizon_context", logic["stages"])

    def test_build_gap_backlog(self) -> None:
        inv = build_inventory()
        logic = build_logic_map()
        gaps = build_gap_backlog(inv, logic)
        self.assertIn("gaps", gaps)
        self.assertGreaterEqual(gaps["summary"]["closed_fixes"], 1)


class FullPaperCycleTest(unittest.TestCase):
    def test_promotion_gate_live_blocked(self) -> None:
        gate = build_promotion_gate(
            {
                "results": [
                    {"ticker": "MRK", "action": "HOLD_PAPER", "verdict": "PROMISING", "reason": "test"},
                ]
            }
        )
        self.assertFalse(gate["live_promotion_allowed"])
        self.assertEqual(gate["recommendations"][0]["promotion_recommendation"], "PROMOTE_TO_LIVE_CANDIDATE")
        self.assertTrue(gate["recommendations"][0]["operator_approval_required"])

    def test_map_validation_verdict(self) -> None:
        self.assertEqual(map_validation_verdict("PROMISING"), "PROMOTE_TO_LIVE_CANDIDATE")
        self.assertEqual(map_validation_verdict("CONTINUE_TESTING"), "CONTINUE_PAPER")

    def test_feedback_artifacts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(feedback_artifacts_exist(root))
            (root / "runtime_outputs/paper_execution/rule_outcome_attribution.json").parent.mkdir(
                parents=True, exist_ok=True
            )
            (root / "runtime_outputs/paper_execution/rule_outcome_attribution.json").write_text("{}")
            self.assertTrue(feedback_artifacts_exist(root))

    def test_compare_constitutional_evolution_detects_weight_change(self) -> None:
        before_w = {"weights": {"BUY_PAPER": {"new_weight": 1.0}}}
        after_w = {"weights": {"BUY_PAPER": {"new_weight": 1.02}}}
        before_d = {"decisions": [{"ticker": "HD", "action": "BUY_PAPER", "confidence": 0.7}]}
        after_d = {"decisions": [{"ticker": "HD", "action": "BUY_PAPER", "confidence": 0.72}]}
        result = compare_constitutional_evolution(before_d, after_d, before_w, after_w)
        self.assertTrue(result["loop_closed"])
        self.assertGreaterEqual(result["weight_change_count"], 1)
        self.assertFalse(result["human_intervention_required"])

    def test_forbidden_unchanged(self) -> None:
        self.assertTrue(forbidden_files_unchanged({"a": 1.0}, {"a": 1.0}))
        self.assertFalse(forbidden_files_unchanged({"a": 1.0}, {"a": 2.0}))

    def test_check_forbidden_file_safety_clean(self) -> None:
        with mock.patch("tae_full_paper_cycle.subprocess.run") as run:
            run.side_effect = [
                mock.Mock(returncode=0, stdout="", stderr=""),
                mock.Mock(returncode=0, stdout="", stderr=""),
            ]
            safety = check_forbidden_file_safety(Path("."), before_mtimes={"live_bot.py": 1.0})
            self.assertTrue(safety["forbidden_content_diff_clean"])
            self.assertEqual(safety["safety_status"], "PASS")
            self.assertIsNone(safety["safety_block_reason"])

    def test_check_forbidden_file_safety_mtime_drift_only(self) -> None:
        with mock.patch("tae_full_paper_cycle.subprocess.run") as run, mock.patch(
            "tae_full_paper_cycle._file_mtime", side_effect=[1.0, 2.0, None, None, None, None]
        ):
            run.side_effect = [
                mock.Mock(returncode=0, stdout="", stderr=""),
                mock.Mock(returncode=0, stdout="", stderr=""),
            ]
            safety = check_forbidden_file_safety(Path("."), before_mtimes={"live_bot.py": 1.0})
            self.assertTrue(safety["forbidden_content_diff_clean"])
            self.assertTrue(safety["forbidden_mtime_drift_detected"])
            self.assertIn("mtime drift ignored", safety.get("note") or "")

    def test_check_forbidden_file_safety_content_diff(self) -> None:
        with mock.patch("tae_full_paper_cycle.subprocess.run") as run:
            run.side_effect = [
                mock.Mock(returncode=0, stdout="--- a/live_bot.py\n+++ b/live_bot.py", stderr=""),
                mock.Mock(returncode=0, stdout="live_bot.py\n", stderr=""),
            ]
            safety = check_forbidden_file_safety(Path("."))
            self.assertFalse(safety["forbidden_content_diff_clean"])
            self.assertEqual(safety["safety_status"], "BLOCKED")
            self.assertIn("live_bot.py", safety["changed_files"])

    def test_collect_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            acct = {
                "cash_available": 1000.0,
                "open_positions_count": 2,
                "account_value_corrected": 5000.0,
                "total_pnl": 100.0,
            }
            (base / "tae_accounting_snapshot.json").write_text(json.dumps(acct), encoding="utf-8")
            val_dir = base / "runtime_outputs" / "paper_decisions"
            val_dir.mkdir(parents=True)
            (val_dir / "decision_validation_results.json").write_text(
                json.dumps({"verdict_summary": {"PROMISING": 1}, "results": []}),
                encoding="utf-8",
            )
            with mock.patch("tae_full_paper_cycle.ACCOUNTING_JSON", base / "tae_accounting_snapshot.json"), mock.patch(
                "tae_full_paper_cycle.VALIDATION_JSON", val_dir / "decision_validation_results.json"
            ), mock.patch("tae_full_paper_cycle.PROMOTION_JSON", base / "promotion_gate.json"):
                summary = collect_summary([{"step": "health", "ok": True}], forbidden_ok=True)
                self.assertIn(summary["final_verdict"], {"READY_FOR_PAPER_DAY", "READY_WITH_WARNINGS", "BLOCKED_WITH_REASONS"})
                self.assertFalse(summary["live_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
