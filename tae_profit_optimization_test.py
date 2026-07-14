#!/usr/bin/env python3
"""Unit tests for tae_profit_optimization."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tae_profit_optimization import (
    build_evidence_set,
    define_challengers,
    replay_challengers,
    run_profit_optimization,
    select_calibration,
)


class ProfitOptimizationTest(unittest.TestCase):
    def test_evidence_set_excludes_synthetic_fills(self) -> None:
        evidence = build_evidence_set()
        self.assertIn("exclusion_counts", evidence)
        self.assertGreaterEqual(evidence["usable_orders"], 1)
        self.assertTrue(evidence["integrity_ok"])

    def test_challengers_defined(self) -> None:
        challengers = define_challengers()
        self.assertEqual(len(challengers), 5)
        ids = {c["id"] for c in challengers}
        self.assertIn("C2", ids)

    def test_replay_rejects_all_on_small_sample(self) -> None:
        evidence = build_evidence_set()
        replay = replay_challengers(evidence, define_challengers())
        self.assertIn("baseline", replay)
        passed = [c for c in replay["challengers"] if c["passed"]]
        self.assertEqual(len(passed), 0)

    def test_selection_retains_brain(self) -> None:
        evidence = build_evidence_set()
        replay = replay_challengers(evidence, define_challengers())
        sel = select_calibration(replay, evidence)
        self.assertEqual(sel["verdict"], "CURRENT_BRAIN_RETAINED_INSUFFICIENT_EVIDENCE")

    def test_run_writes_deliverables(self) -> None:
        with patch("tae_profit_optimization._integrity_check") as mock_int:
            mock_int.return_value = {
                "ok": True,
                "verdict": "PAPER_PROFIT_INTEGRITY_CLOSED",
                "reconciliation": {"status": "PASS"},
            }
            summary = run_profit_optimization(write_outputs=True)
        self.assertIn(summary["verdict"], {
            "CURRENT_BRAIN_RETAINED_INSUFFICIENT_EVIDENCE",
            "PROFIT_CALIBRATION_PROMOTED",
        })
        self.assertTrue(Path("TAE_PROFIT_OPTIMIZATION_AUDIT.md").is_file())
        self.assertTrue(Path("tae_baseline_vs_challengers.json").is_file())


if __name__ == "__main__":
    unittest.main()
