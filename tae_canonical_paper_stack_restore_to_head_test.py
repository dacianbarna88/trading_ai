#!/usr/bin/env python3
"""TAE_CANONICAL_PAPER_STACK_RESTORE_TO_HEAD — ownership + stack integrity tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_paper_execution as pe


class CanonicalPaperStackRestoreTest(unittest.TestCase):
    def test_paper_execution_owner_present(self) -> None:
        self.assertTrue(Path("tae_paper_execution.py").is_file())
        self.assertTrue(callable(pe.run_paper_execution))
        self.assertTrue(callable(pe.run_paper_mark_to_market))
        self.assertTrue(callable(pe.append_paper_daily_equity_observation))

    def test_full_paper_cycle_owner_present(self) -> None:
        self.assertTrue(Path("tae_full_paper_cycle.py").is_file())
        self.assertTrue(Path("tae_structural_governance.py").is_file())
        self.assertTrue(Path("tae.py").is_file())
        from tae_cli.dispatcher import COMMANDS

        self.assertIn("full-paper-cycle", COMMANDS)
        self.assertIn("paper-mark-to-market", COMMANDS)
        self.assertIn("paper-execution", COMMANDS)

    def test_forbidden_components_absent(self) -> None:
        forbidden = [
            "tae_canonical_learning_daemon.py",
            "tae_parallel_paper_daemon.py",
            "tae_startup_launcher.py",
            "tae_launchd_market_open_safe.py",
            "tae_launchd_market_close_safe.py",
            "tae_e3_forward_paper.py",
            "tae_learning_economic_attribution_engine.py",
        ]
        for name in forbidden:
            self.assertFalse(Path(name).exists(), f"forbidden restored: {name}")

    def test_daily_equity_idempotent(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "open_positions_value": 500.0,
            "total_value": 1500.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 10.0,
            "starting_value": 1500.0,
            "validation_capital_base": 30000.0,
            "canonical_state_version": "test-v1",
            "positions": {},
        }
        pe.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = pe.OUTPUT_DIR / "paper_daily_equity_restore_test_only.jsonl"
        if path.exists():
            path.unlink()
        try:
            first = pe.append_paper_daily_equity_observation(portfolio, path=path)
            second = pe.append_paper_daily_equity_observation(portfolio, path=path)
            self.assertTrue(first.get("ok"))
            self.assertTrue(first.get("appended"))
            self.assertTrue(second.get("ok"))
            self.assertFalse(second.get("appended"))
            self.assertTrue(second.get("idempotent"))
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            daily = [r for r in rows if r.get("record_type") == "DAILY_EQUITY"]
            self.assertEqual(len(daily), 1)
        finally:
            if path.exists():
                path.unlink()

    def test_reconciliation_formulas(self) -> None:
        portfolio = {
            "cash": 100.0,
            "open_positions_value": 50.0,
            "total_value": 150.0,
            "realized_pnl": 5.0,
            "unrealized_pnl": 5.0,
            "total_pnl": 10.0,
            "starting_value": 140.0,
            "positions": {
                "AAA": {"current_value": 50.0, "pnl": 5.0},
            },
        }
        rec = pe.validate_portfolio_reconciliation(portfolio)
        self.assertTrue(rec.get("ok"))

    def test_hard_risk_limits_unchanged(self) -> None:
        import hard_risk_guardian as hr

        self.assertEqual(hr.STOP_LIMIT, -3.0)
        self.assertEqual(hr.CRITICAL_LIMIT, -5.0)
        breach = hr.evaluate_position_risk("X", avg_price=100.0, current_price=96.5, shares=1.0)
        self.assertEqual(breach["status"], "STOP_LOSS_BREACHED")

    def test_learning_handoff_owner(self) -> None:
        from tae_canonical_learning_runtime import run_canonical_learning_cycle

        self.assertTrue(callable(run_canonical_learning_cycle))

    def test_mtm_handles_empty_portfolio_file(self) -> None:
        with mock.patch.object(pe, "load_json", return_value={}):
            result = pe.run_paper_mark_to_market(write_report_flag=False)
            self.assertFalse(result.get("ok"))
            self.assertIn("missing", str(result.get("error", "")).lower() + "missing")


if __name__ == "__main__":
    unittest.main()
