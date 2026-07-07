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
        self.assertFalse(order["broker_executed"])
        self.assertFalse(order["live_money"])
        self.assertEqual(order["mode"], "PAPER_ONLY")
        self.assertNotIn("AAPL", portfolio["positions"])
        self.assertGreater(order["simulated_pnl_impact"], 0)

    def test_rule_attribution_positive_negative(self) -> None:
        orders = [
            {
                "rule_sources": ["RULE-A"],
                "simulated_pnl_impact": 10.0,
                "expected_profit_delta": 10.0,
                "action": "SELL_PAPER",
                "ticker": "X",
            },
            {
                "rule_sources": ["RULE-B"],
                "simulated_pnl_impact": -5.0,
                "expected_profit_delta": -5.0,
                "action": "BUY_PAPER",
                "ticker": "Y",
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
                self.assertEqual(result["orders_executed"], 1)
                self.assertTrue((out_dir / "paper_portfolio.json").is_file())


if __name__ == "__main__":
    unittest.main()
