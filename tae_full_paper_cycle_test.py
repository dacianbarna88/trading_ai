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
    collect_summary,
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

    def test_forbidden_unchanged(self) -> None:
        self.assertTrue(forbidden_files_unchanged({"a": 1.0}, {"a": 1.0}))
        self.assertFalse(forbidden_files_unchanged({"a": 1.0}, {"a": 2.0}))

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
