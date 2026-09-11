#!/usr/bin/env python3
"""
Regression coverage for the V1/V2 -> V3 cross-arm training bridge
(2026-09-09). Built because V3's exit-side learning (SELL_PAPER/
PROTECT_PAPER) was stuck at n=11 samples system-wide, never crossing the
15-sample fit threshold, while V1 (52 closed SELLs) and V2 (68 closed
CLOSEs) sat completely unused with real realized PnL. All fixtures here
are synthetic, written to a temp directory -- never touches the real
runtime_outputs/ journals.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tae_v3_cross_arm_training_bridge as bridge


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class V1PnlReconstructionTest(unittest.TestCase):
    """V1's SELL records carry no realized_pnl field -- must be
    reconstructed via weighted-average cost basis."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._orig_roots = dict(bridge.ARM_JOURNAL_ROOTS)
        bridge.ARM_JOURNAL_ROOTS["v1"] = self.root / "v1"
        self.addCleanup(lambda: bridge.ARM_JOURNAL_ROOTS.update(self._orig_roots))

    def test_single_buy_then_sell_at_profit(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v1"] / "trades.jsonl",
            [
                {"action": "BUY", "ticker": "ZZZ", "shares": 10.0, "price": 100.0},
                {"action": "SELL", "ticker": "ZZZ", "shares": 10.0, "price": 110.0, "decision_id": "D1"},
            ],
        )
        rows = list(bridge.bridged_training_records("v1"))
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["expected_profit_delta"], 100.0, places=4)
        self.assertEqual(rows[0]["action"], "SELL_PAPER")

    def test_partial_sell_uses_average_cost_of_remaining(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v1"] / "trades.jsonl",
            [
                {"action": "BUY", "ticker": "ZZZ", "shares": 5.0, "price": 100.0},
                {"action": "BUY", "ticker": "ZZZ", "shares": 5.0, "price": 120.0},
                # avg cost = 110.0
                {"action": "SELL", "ticker": "ZZZ", "shares": 4.0, "price": 130.0},
            ],
        )
        rows = list(bridge.bridged_training_records("v1"))
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["expected_profit_delta"], (130.0 - 110.0) * 4.0, places=4)

    def test_sell_at_loss_yields_negative_delta(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v1"] / "trades.jsonl",
            [
                {"action": "BUY", "ticker": "ZZZ", "shares": 10.0, "price": 100.0},
                {"action": "SELL", "ticker": "ZZZ", "shares": 10.0, "price": 90.0},
            ],
        )
        rows = list(bridge.bridged_training_records("v1"))
        self.assertLess(rows[0]["expected_profit_delta"], 0.0)

    def test_score_pulled_from_matching_decision_id(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v1"] / "trades.jsonl",
            [
                {"action": "BUY", "ticker": "ZZZ", "shares": 10.0, "price": 100.0},
                {"action": "SELL", "ticker": "ZZZ", "shares": 10.0, "price": 110.0, "decision_id": "D1"},
            ],
        )
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v1"] / "decisions.jsonl",
            [{"decision_id": "D1", "score": 82.5}],
        )
        rows = list(bridge.bridged_training_records("v1"))
        self.assertEqual(rows[0]["growth_score"], 82.5)

    def test_missing_score_falls_back_to_default_not_zero(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v1"] / "trades.jsonl",
            [
                {"action": "BUY", "ticker": "ZZZ", "shares": 10.0, "price": 100.0},
                {"action": "SELL", "ticker": "ZZZ", "shares": 10.0, "price": 110.0, "decision_id": "MISSING"},
            ],
        )
        rows = list(bridge.bridged_training_records("v1"))
        self.assertEqual(rows[0]["growth_score"], bridge.DEFAULT_GROWTH_SCORE)

    def test_no_journal_files_yields_nothing(self) -> None:
        rows = list(bridge.bridged_training_records("v1"))
        self.assertEqual(rows, [])

    def test_malformed_line_is_skipped_not_fatal(self) -> None:
        path = bridge.ARM_JOURNAL_ROOTS["v1"] / "trades.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"action": "BUY", "ticker": "ZZZ", "shares": 10.0, "price": 100.0}\nNOT JSON\n', encoding="utf-8")
        rows = list(bridge.bridged_training_records("v1"))
        self.assertEqual(rows, [])  # BUY alone produces no SELL row; no crash on the bad line


class V2RealizedPnlPassthroughTest(unittest.TestCase):
    """V2's CLOSE records already carry a real realized_pnl field --
    must be used as-is, no reconstruction."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._orig_roots = dict(bridge.ARM_JOURNAL_ROOTS)
        bridge.ARM_JOURNAL_ROOTS["v2"] = self.root / "v2"
        self.addCleanup(lambda: bridge.ARM_JOURNAL_ROOTS.update(self._orig_roots))

    def test_close_record_realized_pnl_used_directly(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v2"] / "trades.jsonl",
            [{"action": "CLOSE", "ticker": "ZZZ", "realized_pnl": -42.5, "decision_id": "D2"}],
        )
        rows = list(bridge.bridged_training_records("v2"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["expected_profit_delta"], -42.5)

    def test_non_close_actions_ignored(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v2"] / "trades.jsonl",
            [
                {"action": "BUY", "ticker": "ZZZ", "realized_pnl": 999.0},
                {"action": "ADD", "ticker": "ZZZ", "realized_pnl": 999.0},
            ],
        )
        rows = list(bridge.bridged_training_records("v2"))
        self.assertEqual(rows, [])

    def test_close_without_realized_pnl_field_skipped(self) -> None:
        _write_jsonl(
            bridge.ARM_JOURNAL_ROOTS["v2"] / "trades.jsonl",
            [{"action": "CLOSE", "ticker": "ZZZ"}],
        )
        rows = list(bridge.bridged_training_records("v2"))
        self.assertEqual(rows, [])


class V3OwnExitsTest(unittest.TestCase):
    """V3 learning from its own realized exits (2026-09-09): learning_events.
    jsonl always had a holding_duration_sec field but no caller ever
    populated it -- this covers the bridge's read side once real values
    start showing up (the write side is fixed in tae_parallel_paper_runtime.py)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._orig_root = bridge.V3_JOURNAL_ROOT
        bridge.V3_JOURNAL_ROOT = Path(self._tmp.name) / "v3"
        self.addCleanup(lambda: setattr(bridge, "V3_JOURNAL_ROOT", self._orig_root))

    def test_execution_outcome_sell_with_duration_is_converted_to_hours(self) -> None:
        _write_jsonl(
            bridge.V3_JOURNAL_ROOT / "learning_events.jsonl",
            [{
                "event_type": "EXECUTION_OUTCOME", "action": "SELL",
                "realized_pnl": -42.0, "holding_duration_sec": 7200.0,
            }],
        )
        rows = list(bridge.v3_own_training_records())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["expected_profit_delta"], -42.0)
        self.assertEqual(rows[0]["holding_duration_hours"], 2.0)
        self.assertEqual(rows[0]["action"], "SELL_PAPER")

    def test_missing_duration_omits_the_field_not_zero(self) -> None:
        _write_jsonl(
            bridge.V3_JOURNAL_ROOT / "learning_events.jsonl",
            [{"event_type": "EXECUTION_OUTCOME", "action": "SELL", "realized_pnl": 10.0}],
        )
        rows = list(bridge.v3_own_training_records())
        self.assertNotIn("holding_duration_hours", rows[0])

    def test_non_sell_execution_outcomes_are_ignored(self) -> None:
        _write_jsonl(
            bridge.V3_JOURNAL_ROOT / "learning_events.jsonl",
            [{"event_type": "EXECUTION_OUTCOME", "action": "BUY", "realized_pnl": 10.0}],
        )
        self.assertEqual(list(bridge.v3_own_training_records()), [])

    def test_missing_realized_pnl_skipped(self) -> None:
        _write_jsonl(
            bridge.V3_JOURNAL_ROOT / "learning_events.jsonl",
            [{"event_type": "EXECUTION_OUTCOME", "action": "SELL"}],
        )
        self.assertEqual(list(bridge.v3_own_training_records()), [])


class AggregationTest(unittest.TestCase):
    def test_unknown_arm_yields_nothing(self) -> None:
        self.assertEqual(list(bridge.bridged_training_records("v99")), [])

    def test_all_bridged_records_includes_v3_own_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orig = bridge.V3_JOURNAL_ROOT
            bridge.V3_JOURNAL_ROOT = Path(tmp) / "v3"
            try:
                _write_jsonl(
                    bridge.V3_JOURNAL_ROOT / "learning_events.jsonl",
                    [{"event_type": "EXECUTION_OUTCOME", "action": "SELL", "realized_pnl": 5.0}],
                )
                sources = {r["_bridge_source"] for r in bridge.all_bridged_training_records()}
                self.assertIn("v3_own_exits", sources)
            finally:
                bridge.V3_JOURNAL_ROOT = orig

    def test_all_bridged_records_uses_real_configured_arms_only(self) -> None:
        self.assertEqual(set(bridge.ARM_JOURNAL_ROOTS.keys()), {"v1", "v2"})


if __name__ == "__main__":
    unittest.main()
