#!/usr/bin/env python3
"""Tests for tae_profit_pipeline.py — read-only consolidation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_profit_pipeline as pp


class ProfitPipelineTest(unittest.TestCase):
    def test_build_pipeline_no_duplicate_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._write_minimal_fixtures(base)
            with self._patch_paths(base):
                payload = pp.build_profit_pipeline(write_outputs=False)
        timelines = payload.get("timelines") or []
        ids = [t["decision_id"] for t in timelines]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(payload["data_quality"]["duplicate_timeline_rows"], 0)

    def test_pnl_matches_portfolio_ssot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._write_minimal_fixtures(base)
            with self._patch_paths(base):
                payload = pp.build_profit_pipeline(write_outputs=False)
        summary = payload["summary"]
        self.assertAlmostEqual(summary["realized_pnl"], -10.0, places=2)
        self.assertAlmostEqual(summary["unrealized_pnl"], 5.0, places=2)
        self.assertAlmostEqual(summary["total_value"], 29995.0, places=2)

    def test_block_reasons_from_orders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._write_minimal_fixtures(base)
            with self._patch_paths(base):
                payload = pp.build_profit_pipeline(write_outputs=False)
        blocks = payload.get("block_reason_rollup") or {}
        self.assertGreaterEqual(blocks.get("no_mark_price", 0), 1)
        self.assertGreaterEqual(blocks.get("executed", 0), 1)

    def test_join_coverage_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._write_minimal_fixtures(base)
            with self._patch_paths(base):
                payload = pp.build_profit_pipeline(write_outputs=False)
        jc = payload["data_quality"]["join_coverage"]
        self.assertEqual(jc["total_decisions"], 2)
        self.assertGreaterEqual(jc["decision_id"], 1)

    def test_write_outputs_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._write_minimal_fixtures(base)
            orders_path = base / "runtime_outputs/paper_execution/paper_orders.jsonl"
            before = orders_path.read_text()
            with self._patch_paths(base):
                pp.REPORT_MD = base / "TAE_PROFIT_PIPELINE_REPORT.md"
                pp.REPORT_JSON = base / "tae_profit_pipeline.json"
                pp.build_profit_pipeline(write_outputs=True)
            self.assertEqual(orders_path.read_text(), before)
            self.assertTrue((base / "tae_profit_pipeline.json").is_file())

    def _patch_paths(self, base: Path):
        return mock.patch.multiple(
            pp,
            ROOT=base,
            SIGNALS_CSV=base / "live_signals.csv",
            GII_JSON=base / "tae_growth_intelligence.json",
            LEDGER_JSON=base / "tae_opportunity_cost_ledger.json",
            DECISIONS_JSON=base / "runtime_outputs/paper_decisions/paper_decisions.json",
            DECISION_STATE_JSON=base / "runtime_outputs/decision_state/active_decisions.json",
            CONFLICTS_JSON=base / "runtime_outputs/conflict_resolution/conflicts.json",
            ORDERS_JSONL=base / "runtime_outputs/paper_execution/paper_orders.jsonl",
            TRADES_JSONL=base / "runtime_outputs/paper_execution/paper_trades.jsonl",
            PORTFOLIO_JSON=base / "runtime_outputs/paper_execution/paper_portfolio.json",
            VALIDATION_JSON=base / "runtime_outputs/paper_decisions/decision_validation_results.json",
            MEMORY_JSONL=base / "runtime_outputs/longitudinal_memory/decisions.jsonl",
            ATTRIBUTION_JSON=base / "runtime_outputs/paper_execution/rule_outcome_attribution.json",
            ATTRIBUTION_JSON_ALT=base / "runtime_outputs/rule_outcome_attribution.json",
            INTEGRITY_JSON=base / "tae_paper_profit_integrity_guard_report.json",
        )

    def _write_minimal_fixtures(self, base: Path) -> None:
        (base / "live_signals.csv").write_text(
            "Time,Ticker,Price,SMA50,RSI,Score,Signal\n"
            "2026-07-14 01:00:00,AAA,10,9,50,100,STRONG BUY\n"
            "2026-07-14 01:00:00,BBB,20,19,50,80,BUY\n",
            encoding="utf-8",
        )
        (base / "tae_growth_intelligence.json").write_text(
            json.dumps(
                {
                    "tickers": [
                        {"ticker": "AAA", "missed_usd": 12, "growth_score": 40},
                        {"ticker": "BBB", "missed_usd": 0, "growth_score": 30},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (base / "tae_opportunity_cost_ledger.json").write_text(
            json.dumps({"ledger": [{"ticker": "AAA", "missed_usd": 12}]}),
            encoding="utf-8",
        )
        dec_dir = base / "runtime_outputs/paper_decisions"
        dec_dir.mkdir(parents=True)
        (dec_dir / "paper_decisions.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-07-14T01:00:00+00:00",
                    "decisions": [
                        {
                            "decision_id": "PDEC-AAA-0001",
                            "ticker": "AAA",
                            "action": "BUY_PAPER",
                            "confidence": 0.8,
                            "expected_profit_delta": 5,
                            "decision_switch_authorized": True,
                            "created_at": "2026-07-14T01:00:00+00:00",
                            "evidence": "signal=STRONG BUY",
                        },
                        {
                            "decision_id": "PDEC-BBB-0002",
                            "ticker": "BBB",
                            "action": "BUY_PAPER",
                            "confidence": 0.5,
                            "expected_profit_delta": 2,
                            "decision_switch_authorized": True,
                            "created_at": "2026-07-14T01:00:00+00:00",
                            "evidence": "signal=BUY",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (dec_dir / "decision_validation_results.json").write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "decision_id": "PDEC-AAA-0001",
                            "verdict": "PROMISING",
                            "profit_delta": 5,
                        },
                        {
                            "decision_id": "PDEC-BBB-0002",
                            "verdict": "NEEDS_MORE_DATA",
                            "profit_delta": 2,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        state_dir = base / "runtime_outputs/decision_state"
        state_dir.mkdir(parents=True)
        (state_dir / "active_decisions.json").write_text(
            json.dumps({"tickers": {"AAA": {"last_action": "BUY_PAPER"}}}),
            encoding="utf-8",
        )
        conf_dir = base / "runtime_outputs/conflict_resolution"
        conf_dir.mkdir(parents=True)
        (conf_dir / "conflicts.json").write_text(
            json.dumps({"tickers": [{"ticker": "AAA", "winner_action": "BUY_PAPER"}]}),
            encoding="utf-8",
        )
        exe = base / "runtime_outputs/paper_execution"
        exe.mkdir(parents=True)
        (exe / "paper_orders.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-07-14T01:00:01+00:00",
                            "decision_id": "PDEC-AAA-0001",
                            "ticker": "AAA",
                            "action": "BUY_PAPER",
                            "status": "EXECUTED",
                            "executed": True,
                            "realized_pnl": 0,
                            "fill_price": 10,
                            "rule_sources": ["RULE-A"],
                            "reason": "signal=STRONG BUY",
                        }
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-07-14T01:00:01+00:00",
                            "decision_id": "PDEC-BBB-0002",
                            "ticker": "BBB",
                            "action": "BUY_PAPER",
                            "status": "SKIPPED_NO_MARK_PRICE",
                            "executed": False,
                            "realized_pnl": 0,
                            "fill_price": 0,
                            "reason": "no mark price",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (exe / "paper_trades.jsonl").write_text(
            json.dumps(
                {
                    "timestamp": "2026-07-14T01:00:01+00:00",
                    "decision_id": "PDEC-AAA-0001",
                    "ticker": "AAA",
                    "realized_pnl": 0,
                    "fill_shares": 1,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (exe / "paper_portfolio.json").write_text(
            json.dumps(
                {
                    "realized_pnl": -10,
                    "unrealized_pnl": 5,
                    "total_value": 29995,
                    "validation_capital_base": 30000,
                    "positions": {
                        "AAA": {"pnl": 5, "mark_source": "test", "mark_status": "DATA_OK"},
                    },
                }
            ),
            encoding="utf-8",
        )
        (exe / "rule_outcome_attribution.json").write_text(
            json.dumps({"rules": {"RULE-A": {"rule_id": "RULE-A", "net_pnl_impact": 5}}}),
            encoding="utf-8",
        )
        (base / "tae_paper_profit_integrity_guard_report.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "verdict": "PAPER_PROFIT_INTEGRITY_CLOSED",
                    "reconciliation": {"ok": True},
                    "checks": [{"name": "portfolio_reconciliation", "pass": True}],
                }
            ),
            encoding="utf-8",
        )
        mem = base / "runtime_outputs/longitudinal_memory"
        mem.mkdir(parents=True)
        (mem / "decisions.jsonl").write_text("", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
