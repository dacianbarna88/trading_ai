#!/usr/bin/env python3
"""
Regression coverage for the orphaned-cycle recovery mechanism (2026-09-09).

Found while debugging why the new V2 relative-weakness trim never fired
on CDNS/INTU/BLK despite the standalone function correctly flagging them:
17 of V2's 50 positions (34%) have real shares in portfolio.json but no
live cycle record in cycle_state.json (their only cycle record is marked
CLOSED, most likely from a close attempt whose portfolio-level rollback
was not mirrored at the cycle-store level). Every V2 exit mechanism —
trailing stop, stop-loss, ATR profit target, concentration trim,
relative-weakness trim — gates on `cycle` being truthy in
tae_parallel_paper_runtime._run_v2_arm, so these positions were receiving
NO exit management at all. recover_orphaned_cycle() synthesizes and
persists a fresh OPEN cycle matching the position's real current state,
restoring exit eligibility without inventing entry/add capacity.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tae_strategy_v2_foundation as v2f


class RecoverOrphanedCycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cycle_path = Path(self._tmp.name) / "cycle_state.json"

    def test_no_position_returns_none(self) -> None:
        store = v2f.empty_cycle_store()
        portfolio = {"positions": {}}
        result = v2f.recover_orphaned_cycle(store, portfolio=portfolio, ticker="ZZZ")
        self.assertIsNone(result)

    def test_zero_shares_returns_none(self) -> None:
        store = v2f.empty_cycle_store()
        portfolio = {"positions": {"ZZZ": {"shares": 0.0, "avg_price": 100.0}}}
        result = v2f.recover_orphaned_cycle(store, portfolio=portfolio, ticker="ZZZ")
        self.assertIsNone(result)

    def test_synthesizes_a_cycle_matching_real_position_state(self) -> None:
        store = v2f.empty_cycle_store()
        portfolio = {"positions": {"ZZZ": {"shares": 5.0, "avg_price": 200.0}}}
        cycle = v2f.recover_orphaned_cycle(store, portfolio=portfolio, ticker="ZZZ")
        self.assertIsNotNone(cycle)
        self.assertEqual(cycle["ticker"], "ZZZ")
        self.assertEqual(cycle["status"], "OPEN")
        self.assertEqual(cycle["total_quantity"], 5.0)
        self.assertEqual(cycle["average_cost"], 200.0)
        self.assertTrue(cycle["recovered"])

    def test_never_authorizes_further_adds(self) -> None:
        """Conservative by design: a recovered cycle must not silently
        grant new tranche budget it never independently earned."""
        store = v2f.empty_cycle_store()
        portfolio = {"positions": {"ZZZ": {"shares": 5.0, "avg_price": 200.0}}}
        cycle = v2f.recover_orphaned_cycle(store, portfolio=portfolio, ticker="ZZZ")
        self.assertEqual(cycle["budget_remaining"], 0.0)

    def test_existing_open_cycle_is_returned_unchanged_not_replaced(self) -> None:
        store = v2f.empty_cycle_store()
        real_cycle = v2f.build_cycle(
            ticker="ZZZ", currency="USD", company_budget=1000.0, max_tranches=5, status="OPEN"
        )
        store["cycles"][real_cycle["cycle_id"]] = real_cycle
        portfolio = {"positions": {"ZZZ": {"shares": 5.0, "avg_price": 200.0}}}
        result = v2f.recover_orphaned_cycle(store, portfolio=portfolio, ticker="ZZZ")
        self.assertEqual(result["cycle_id"], real_cycle["cycle_id"])
        self.assertNotIn("recovered", result)

    def test_persists_to_disk_when_path_given(self) -> None:
        store = v2f.empty_cycle_store()
        portfolio = {"positions": {"ZZZ": {"shares": 5.0, "avg_price": 200.0}}}
        v2f.recover_orphaned_cycle(
            store, portfolio=portfolio, ticker="ZZZ", persist_path=self.cycle_path
        )
        self.assertTrue(self.cycle_path.is_file())
        reloaded = v2f.load_cycle_store(self.cycle_path)
        found = v2f.find_open_cycle_for_ticker(reloaded, "ZZZ")
        self.assertIsNotNone(found)

    def test_second_call_after_persist_finds_the_same_cycle_not_a_new_one(self) -> None:
        store = v2f.empty_cycle_store()
        portfolio = {"positions": {"ZZZ": {"shares": 5.0, "avg_price": 200.0}}}
        first = v2f.recover_orphaned_cycle(
            store, portfolio=portfolio, ticker="ZZZ", persist_path=self.cycle_path
        )
        reloaded_store = v2f.load_cycle_store(self.cycle_path)
        second = v2f.recover_orphaned_cycle(
            reloaded_store, portfolio=portfolio, ticker="ZZZ", persist_path=self.cycle_path
        )
        self.assertEqual(first["cycle_id"], second["cycle_id"])


class RuntimeWiringSmokeTest(unittest.TestCase):
    def test_run_v2_arm_calls_recovery_when_cycle_missing(self) -> None:
        import inspect

        import tae_parallel_paper_runtime as ppr

        source = inspect.getsource(ppr._run_v2_arm)
        self.assertIn("recover_orphaned_cycle", source)


if __name__ == "__main__":
    unittest.main()
