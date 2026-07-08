#!/usr/bin/env python3
"""Tests for tae_paper_execution.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_paper_execution as pe


class PaperExecutionTest(unittest.TestCase):
    def test_extract_rule_sources(self) -> None:
        decision = {
            "hypothesis_rules_applied": [{"hypothesis_id": "LTB-PROT-HSBA.L"}],
            "knowledge_evidence": {
                "rules_applied": ["MISSED_PROFIT_PROTECTION"],
                "named_confidence_rules": ["DO_NOT_PROMOTE_TO_LIVE"],
            },
        }
        rules = pe.extract_rule_sources(decision)
        self.assertIn("LTB-PROT-HSBA.L", rules)
        self.assertIn("MISSED_PROFIT_PROTECTION", rules)

    def test_bootstrap_from_accounting(self) -> None:
        accounting = {
            "cash_available": 1000.0,
            "account_value_corrected": 10000.0,
            "open_positions": [
                {"ticker": "AAPL", "shares": 10, "current_price": 100.0, "pnl": 50.0},
            ],
        }
        portfolio = pe.bootstrap_portfolio(accounting, None)
        self.assertEqual(portfolio["schema"], pe.SCHEMA)
        self.assertIn("AAPL", portfolio["positions"])
        self.assertGreater(portfolio["total_value"], 0)

    def test_execute_sell_paper(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "AAPL": {
                    "ticker": "AAPL",
                    "shares": 10.0,
                    "avg_price": 90.0,
                    "current_price": 100.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-AAPL-001",
            "ticker": "AAPL",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "expected_profit_delta": 100.0,
            "evidence": "test sell",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["action"], "SELL_PAPER")
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["executed"])
        self.assertTrue(order["is_trade"])
        self.assertGreater(order["fill_shares"], 0)
        self.assertFalse(order["broker_executed"])
        self.assertFalse(order["live_money"])
        self.assertEqual(order["mode"], "PAPER_ONLY")
        self.assertNotIn("AAPL", portfolio["positions"])
        self.assertGreater(order["simulated_pnl_impact"], 0)

    def test_sell_paper_skipped_without_position(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {},
        }
        cash_before = portfolio["cash"]
        decision = {
            "decision_id": "PDEC-AZN-001",
            "ticker": "AZN.L",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "evidence": "test sell no position",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "SKIPPED_NO_POSITION")
        self.assertFalse(order["executed"])
        self.assertFalse(order["is_trade"])
        self.assertEqual(order["fill_shares"], 0.0)
        self.assertEqual(portfolio["cash"], cash_before)

    def test_validate_execution_run_counts(self) -> None:
        orders = [
            {
                "decision_id": "1",
                "action": "SELL_PAPER",
                "status": "EXECUTED",
                "executed": True,
                "is_trade": True,
                "fill_shares": 5.0,
                "before_position": {"shares": 5.0},
            },
            {
                "decision_id": "2",
                "action": "SELL_PAPER",
                "status": "SKIPPED_NO_POSITION",
                "executed": False,
                "is_trade": False,
                "fill_shares": 0.0,
                "before_position": {"shares": 0.0},
            },
        ]
        portfolio = {"positions": {"AAPL": {"shares": 1.0}}}
        validation = pe.validate_execution_run(
            orders,
            trades_written=1,
            trades_file_lines=1,
            portfolio=portfolio,
            before_snapshot={"positions_count": 2, "cash": 100.0, "realized_pnl": 0.0},
            after_snapshot={"positions_count": 1, "cash": 200.0, "realized_pnl": 10.0},
        )
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["orders_created"], 2)
        self.assertEqual(validation["orders_executed"], 1)
        self.assertEqual(validation["orders_skipped"], 1)
        self.assertEqual(validation["trades_written"], 1)

    def test_rule_attribution_positive_negative(self) -> None:
        orders = [
            {
                "rule_sources": ["RULE-A"],
                "simulated_pnl_impact": 10.0,
                "expected_profit_delta": 10.0,
                "action": "SELL_PAPER",
                "ticker": "X",
                "executed": True,
            },
            {
                "rule_sources": ["RULE-B"],
                "simulated_pnl_impact": -5.0,
                "expected_profit_delta": -5.0,
                "action": "BUY_PAPER",
                "ticker": "Y",
                "executed": True,
            },
        ]
        attr = pe.build_rule_attribution(orders, None)
        self.assertEqual(attr["rules"]["RULE-A"]["positive_outcomes"], 1)
        self.assertEqual(attr["rules"]["RULE-B"]["negative_outcomes"], 1)

    def test_run_paper_execution_integration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decisions_path = root / "runtime_outputs/paper_decisions/paper_decisions.json"
            accounting_path = root / "tae_accounting_snapshot.json"
            out_dir = root / "runtime_outputs/paper_execution"
            decisions_path.parent.mkdir(parents=True)
            out_dir.mkdir(parents=True)
            decisions_path.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "decision_id": "PDEC-TEST-001",
                                "ticker": "AAPL",
                                "action": "HOLD_PAPER",
                                "confidence": 0.5,
                                "evidence": "hold",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            accounting_path.write_text(
                json.dumps(
                    {
                        "cash_available": 5000,
                        "account_value_corrected": 10000,
                        "open_positions": [
                            {"ticker": "AAPL", "shares": 5, "current_price": 100, "pnl": 0},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(pe, "DECISIONS_JSON", decisions_path), mock.patch.object(
                pe, "ACCOUNTING_JSON", accounting_path
            ), mock.patch.object(pe, "OUTPUT_DIR", out_dir), mock.patch.object(
                pe, "PORTFOLIO_JSON", out_dir / "paper_portfolio.json"
            ), mock.patch.object(
                pe, "ORDERS_JSONL", out_dir / "paper_orders.jsonl"
            ), mock.patch.object(
                pe, "TRADES_JSONL", out_dir / "paper_trades.jsonl"
            ), mock.patch.object(
                pe, "ATTRIBUTION_JSON", out_dir / "rule_outcome_attribution.json"
            ), mock.patch.object(pe, "REPORT_MD", root / "TAE_PAPER_EXECUTION_REPORT.md"):
                result = pe.run_paper_execution(write_report_flag=False)
                self.assertTrue(result["ok"])
                stats = result.get("stats") or {}
                self.assertEqual(stats.get("orders_created"), 1)
                self.assertEqual(stats.get("trades_written"), 0)
                self.assertTrue((out_dir / "paper_portfolio.json").is_file())
                trades_path = out_dir / "paper_trades.jsonl"
                if trades_path.is_file():
                    for line in trades_path.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        self.assertGreater(pe._f(row.get("fill_shares") or row.get("shares")), 0)


    def test_sanitize_trades_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper_trades.jsonl"
            rows = [
                {
                    "decision_id": "bad",
                    "action": "SELL_PAPER",
                    "before_position": {"shares": 0},
                    "fill_shares": 0,
                    "record_type": "paper_trade",
                },
                {
                    "decision_id": "good",
                    "action": "SELL_PAPER",
                    "before_position": {"shares": 5.0},
                    "fill_shares": 5.0,
                    "record_type": "paper_trade",
                },
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            with mock.patch.object(pe, "OUTPUT_DIR", Path(tmp)):
                removed = pe.sanitize_trades_file(path)
            self.assertEqual(removed, 1)
            remaining = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["decision_id"], "good")


if __name__ == "__main__":
    unittest.main()
