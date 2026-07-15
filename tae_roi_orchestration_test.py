#!/usr/bin/env python3
"""Tests for ROI economic orchestration (reuse-only closure)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_roi001_challenger as roi


class ROIOrchestrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.queue_path = self.root / "tae_roi_queue.json"
        self.report_path = self.root / "tae_roi001_challenger_report.json"
        self.next_path = self.root / "tae_next_dollar.json"
        self.orders_path = self.root / "paper_orders.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _patch_paths(self) -> None:
        roi.ROI_QUEUE_JSON = self.queue_path
        roi.NEXT_DOLLAR_JSON = self.next_path
        roi.REPORT_JSON = self.report_path
        roi.CLOSURE_AUDIT_JSON = self.root / "closure.json"

    def _write_queue(self, items: list[dict]) -> None:
        doc = {
            "schema": "tae_roi_queue",
            "version": "2.0",
            "queue": items,
        }
        self.queue_path.write_text(json.dumps(doc), encoding="utf-8")

    def test_only_one_roi_can_be_active(self) -> None:
        self._patch_paths()
        self._write_queue(
            [
                {"roi_id": "ROI-001", "rank": 1, "active": True, "status": "ACTIVE_CHALLENGER", "challenger_runner": "run_roi001_challenger"},
                {"roi_id": "ROI-002", "rank": 2, "active": True, "status": "WAITING", "depends_on": "ROI-001"},
            ]
        )
        doc = roi.ensure_single_active_roi(roi.load_roi_queue_ssot())
        active = [i for i in doc["queue"] if i.get("active")]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["roi_id"], "ROI-001")

    def test_economically_positive_does_not_enable_production(self) -> None:
        entry = {"status": "ACTIVE_CHALLENGER", "active": True}
        report = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "sample": {"reduce_executions": 4, "min_required_executions": 10, "min_required_tickers": 3},
            "delta": {"realized_pnl": 5.0, "drawdown_pct": -0.1, "expectancy": 1.0, "profit_factor": 1.1},
            "promotion_checks": {
                "higher_realized_profit": True,
                "drawdown_le_baseline": True,
                "profit_factor_ge_baseline": True,
                "expectancy_ge_baseline": True,
                "min_reduce_executions": False,
                "min_tickers": True,
                "profit_integrity_pass": True,
                "reconciliation_pass": True,
            },
        }
        out = roi.sync_queue_entry_from_report(entry, report)
        self.assertEqual(out["status"], "ECONOMICALLY_POSITIVE")
        self.assertFalse(out["production_enabled"])

    def test_all_gates_pass_promotes_paper(self) -> None:
        entry = {"status": "ECONOMICALLY_POSITIVE", "active": True, "production_flag": "roi001_challenger"}
        report = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "sample": {"reduce_executions": 10, "min_required_executions": 10, "min_required_tickers": 3},
            "delta": {"realized_pnl": 12.0, "drawdown_pct": -0.2, "expectancy": 2.0, "profit_factor": 2.0},
            "promotion_checks": {
                "higher_realized_profit": True,
                "drawdown_le_baseline": True,
                "profit_factor_ge_baseline": True,
                "expectancy_ge_baseline": True,
                "min_reduce_executions": True,
                "min_tickers": True,
                "profit_integrity_pass": True,
                "reconciliation_pass": True,
            },
        }
        out = roi.sync_queue_entry_from_report(entry, report)
        self.assertEqual(out["status"], "PROMOTED_PAPER")
        self.assertTrue(out["production_enabled"])
        self.assertFalse(out["active"])

    def test_promoted_enables_production_flag_reader(self) -> None:
        self._patch_paths()
        self._write_queue(
            [
                {
                    "roi_id": "ROI-001",
                    "rank": 1,
                    "status": "PROMOTED_PAPER",
                    "active": False,
                    "production_flag": "roi001_challenger",
                    "production_enabled": True,
                }
            ]
        )
        flags = roi.resolve_roi_production_flags()
        self.assertTrue(flags["roi001_challenger"])

    def test_post_promotion_regression_retires(self) -> None:
        entry = {
            "status": "PROMOTED_PAPER",
            "active": False,
            "production_enabled": True,
            "promotion_metrics_snapshot": {
                "realized_profit_delta": 10.0,
                "drawdown_delta": -0.1,
                "expectancy_delta": 2.0,
                "profit_factor_delta": 1.5,
            },
        }
        report = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "sample": {"reduce_executions": 10, "min_required_executions": 10, "min_required_tickers": 3},
            "delta": {"realized_pnl": 0.0, "drawdown_pct": 0.5, "expectancy": 1.0, "profit_factor": 1.0},
            "promotion_checks": {
                "higher_realized_profit": False,
                "drawdown_le_baseline": False,
                "profit_factor_ge_baseline": False,
                "expectancy_ge_baseline": False,
                "min_reduce_executions": True,
                "min_tickers": True,
                "profit_integrity_pass": True,
                "reconciliation_pass": True,
            },
        }
        out = roi.sync_queue_entry_from_report(entry, report)
        self.assertEqual(out["status"], "RETIRED")
        self.assertFalse(out["production_enabled"])

    def test_queue_advances_after_roi001_completion(self) -> None:
        self._patch_paths()
        self._write_queue(
            [
                {"roi_id": "ROI-001", "rank": 1, "status": "PROMOTED_PAPER", "active": False, "challenger_runner": "run_roi001_challenger"},
                {"roi_id": "ROI-002", "rank": 2, "status": "WAITING", "active": False, "depends_on": "ROI-001"},
            ]
        )
        doc = roi.advance_roi_queue(roi.load_roi_queue_ssot())
        active = next(i for i in doc["queue"] if i.get("active"))
        self.assertEqual(active["roi_id"], "ROI-002")
        self.assertEqual(active["status"], "WAITING_IMPLEMENTATION_MAPPING")

    def test_roi002_not_active_before_roi001_complete(self) -> None:
        self._patch_paths()
        self._write_queue(
            [
                {"roi_id": "ROI-001", "rank": 1, "status": "ECONOMICALLY_POSITIVE", "active": True, "challenger_runner": "run_roi001_challenger"},
                {"roi_id": "ROI-002", "rank": 2, "status": "WAITING", "active": False, "depends_on": "ROI-001"},
            ]
        )
        doc = roi.ensure_single_active_roi(roi.load_roi_queue_ssot())
        roi002 = next(i for i in doc["queue"] if i["roi_id"] == "ROI-002")
        self.assertFalse(roi002.get("active"))

    def test_collect_reduce_sample_grows_with_new_order(self) -> None:
        self.orders_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "action": "REDUCE_PAPER",
                            "status": "EXECUTED",
                            "is_trade": True,
                            "ticker": "PG",
                            "confidence": 0.8,
                            "fill_price": 100.0,
                            "realized_pnl": 1.0,
                            "fill_shares": 1.0,
                            "before_position": {"shares": 5, "avg_price": 90, "pnl": 2},
                        }
                    ),
                    json.dumps(
                        {
                            "action": "REDUCE_PAPER",
                            "status": "EXECUTED",
                            "is_trade": True,
                            "ticker": "AAPL",
                            "confidence": 0.8,
                            "fill_price": 200.0,
                            "realized_pnl": 2.0,
                            "fill_shares": 1.0,
                            "before_position": {"shares": 5, "avg_price": 180, "pnl": 3},
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        with mock.patch.object(roi, "ORDERS_JSONL", self.orders_path):
            rows = roi.collect_reduce_opportunities()
        self.assertEqual(len(rows), 2)
        self.orders_path.write_text(
            self.orders_path.read_text()
            + json.dumps(
                {
                    "action": "REDUCE_PAPER",
                    "status": "EXECUTED",
                    "is_trade": True,
                    "ticker": "GE",
                    "confidence": 0.5,
                    "fill_price": 50.0,
                    "realized_pnl": -0.1,
                    "fill_shares": 1.0,
                    "before_position": {"shares": 4, "avg_price": 51, "pnl": -1},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with mock.patch.object(roi, "ORDERS_JSONL", self.orders_path):
            rows2 = roi.collect_reduce_opportunities()
        self.assertEqual(len(rows2), 3)

    def test_structural_governance_calls_orchestration(self) -> None:
        src = Path("tae_structural_governance.py").read_text(encoding="utf-8")
        self.assertIn("run_roi_economic_orchestration", src)
        self.assertIn("[START] roi_economic_orchestration", src)

    def test_terminology_ownership_isolated(self) -> None:
        self.assertIn("capital_challengers_promotion_hint", roi.TERMINOLOGY_OWNERSHIP)
        self.assertIn("watchlist_promotion_queue", roi.TERMINOLOGY_OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
