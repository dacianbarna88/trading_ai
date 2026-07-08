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
        self.assertGreater(order["realized_pnl"], 0)
        self.assertGreater(order["gross_value"], 0)
        self.assertGreater(order["cost_basis"], 0)
        self.assertAlmostEqual(order["cash_after"], 2000.0, places=2)

    def test_sell_realized_pnl_at_market_price(self) -> None:
        portfolio = {
            "cash": 5000.0,
            "realized_pnl": 0.0,
            "starting_value": 10000.0,
            "positions": {
                "MU": {
                    "ticker": "MU",
                    "shares": 2.0,
                    "avg_price": 100.0,
                    "current_price": 90.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-MU-001",
            "ticker": "MU",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "evidence": "sell at market",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertAlmostEqual(order["realized_pnl"], -20.0, places=2)
        self.assertAlmostEqual(order["gross_value"], 180.0, places=2)
        self.assertAlmostEqual(order["cost_basis"], 200.0, places=2)
        self.assertAlmostEqual(portfolio["realized_pnl"], -20.0, places=2)
        self.assertAlmostEqual(portfolio["cash"], 5180.0, places=2)

    def test_reduce_realized_pnl(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "AAPL": {
                    "ticker": "AAPL",
                    "shares": 10.0,
                    "avg_price": 100.0,
                    "current_price": 110.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-AAPL-RED",
            "ticker": "AAPL",
            "action": "REDUCE_PAPER",
            "confidence": 0.8,
            "evidence": "reduce",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertAlmostEqual(order["fill_shares"], 2.0, places=2)
        self.assertAlmostEqual(order["realized_pnl"], 20.0, places=2)
        self.assertAlmostEqual(portfolio["positions"]["AAPL"]["shares"], 8.0, places=2)

    def test_rotate_realized_pnl(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "OLD": {
                    "ticker": "OLD",
                    "shares": 5.0,
                    "avg_price": 50.0,
                    "current_price": 60.0,
                    "status": "OPEN",
                }
            },
        }
        decisions = [
            {
                "decision_id": "PDEC-ROT-1",
                "ticker": "OLD",
                "action": "ROTATE_PAPER",
                "confidence": 0.7,
                "evidence": "rotate out",
            },
            {
                "decision_id": "PDEC-BUY-NEW",
                "ticker": "NEW",
                "action": "BUY_PAPER",
                "confidence": 0.9,
                "expected_profit_delta": 50.0,
                "evidence": "rotate in",
            },
        ]
        order = pe.execute_decision(decisions[0], portfolio, accounting=None, all_decisions=decisions)
        self.assertTrue(order["is_trade"])
        self.assertAlmostEqual(order["realized_pnl"], 50.0, places=2)
        self.assertNotIn("OLD", portfolio["positions"])

    def test_portfolio_reconciliation(self) -> None:
        portfolio = {
            "cash": 5000.0,
            "realized_pnl": 0.0,
            "positions": {
                "AAPL": {
                    "ticker": "AAPL",
                    "shares": 10.0,
                    "avg_price": 100.0,
                    "current_price": 110.0,
                }
            },
        }
        pe.recalc_portfolio(portfolio)
        portfolio["starting_value"] = portfolio["total_value"]
        portfolio["baseline_unrealized_pnl"] = portfolio["unrealized_pnl"]
        recon = pe.validate_portfolio_reconciliation(portfolio)
        self.assertTrue(recon["ok"])
        self.assertEqual(recon["status"], "PASS")

    def test_backfill_legacy_trades(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper_trades.jsonl"
            legacy = {
                "decision_id": "PDEC-MU-0016",
                "action": "SELL_PAPER",
                "is_trade": True,
                "record_type": "paper_trade",
                "fill_shares": 2.0,
                "price": 100.0,
                "before_position": {"shares": 2.0, "avg_price": 100.0, "current_price": 90.0},
                "simulated_pnl_impact": 0.0,
            }
            path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
            portfolio = {"cash": 1200.0, "realized_pnl": 0.0, "positions": {}}
            changed = pe.backfill_portfolio_realized_from_trades(portfolio, path)
            self.assertTrue(changed)
            self.assertAlmostEqual(portfolio["realized_pnl"], -20.0, places=2)
            self.assertAlmostEqual(portfolio["cash"], 1180.0, places=2)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertAlmostEqual(rows[0]["realized_pnl"], -20.0, places=2)

    def test_trade_jsonl_counts_match_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "runtime_outputs/paper_execution"
            out_dir.mkdir(parents=True)
            trades_path = out_dir / "paper_trades.jsonl"
            trades_path.write_text(
                json.dumps(
                    {
                        "decision_id": "t1",
                        "action": "SELL_PAPER",
                        "is_trade": True,
                        "record_type": "paper_trade",
                        "fill_shares": 1.0,
                        "fill_price": 110.0,
                        "gross_value": 110.0,
                        "cost_basis": 100.0,
                        "realized_pnl": 10.0,
                        "before_position": {"shares": 1.0, "avg_price": 100.0},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            errors = pe.validate_trades_file(trades_path)
            self.assertEqual(errors, [])
            self.assertEqual(pe._count_jsonl_lines(trades_path), 1)

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
                "realized_pnl": 10.0,
                "gross_value": 50.0,
                "before_position": {"shares": 5.0, "avg_price": 8.0},
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
        portfolio = {"positions": {"AAPL": {"shares": 1.0, "avg_price": 100.0, "current_price": 100.0}}}
        pe.recalc_portfolio(portfolio)
        validation = pe.validate_execution_run(
            orders,
            trades_written=1,
            trades_file_lines=1,
            portfolio=portfolio,
            before_snapshot={"positions_count": 2, "cash": 100.0, "realized_pnl": 0.0, "unrealized_pnl": 0.0, "total_pnl": 0.0, "total_value": 200.0, "open_positions_value": 100.0},
            after_snapshot={"positions_count": 1, "cash": 200.0, "realized_pnl": 10.0, "unrealized_pnl": 0.0, "total_pnl": 10.0, "total_value": 300.0, "open_positions_value": 100.0},
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
                        "effective_contributed_capital": 30000.0,
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
            ), mock.patch.object(pe, "REPORT_MD", root / "TAE_PAPER_EXECUTION_REPORT.md"), mock.patch.object(
                pe, "INTEGRITY_REPORT_JSON", out_dir / "integrity.json"
            ), mock.patch.object(pe, "INTEGRITY_REPORT_MD", out_dir / "integrity.md"), mock.patch.object(
                pe, "VALIDATION_PROFIT_JSON", out_dir / "validation.json"
            ):
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


    def test_mtm_uses_live_price_not_avg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "runtime_outputs/paper_execution"
            out_dir.mkdir(parents=True)
            portfolio_path = out_dir / "paper_portfolio.json"
            portfolio_path.write_text(
                json.dumps(
                    {
                        "cash": 1000.0,
                        "realized_pnl": 0.0,
                        "starting_value": 2000.0,
                        "positions": {
                            "AAPL": {
                                "ticker": "AAPL",
                                "shares": 10.0,
                                "avg_price": 100.0,
                                "current_price": 100.0,
                                "status": "OPEN",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(pe, "OUTPUT_DIR", out_dir), mock.patch.object(
                pe, "PORTFOLIO_JSON", portfolio_path
            ), mock.patch.object(pe, "ATTRIBUTION_JSON", out_dir / "rule_outcome_attribution.json"            ), mock.patch.object(
                pe, "MTM_JSON", out_dir / "mark_to_market.json"
            ), mock.patch.object(pe, "MTM_REPORT_MD", Path(tmp) / "TAE_PAPER_MARK_TO_MARKET_REPORT.md"), mock.patch.object(
                pe, "ORDERS_JSONL", out_dir / "paper_orders.jsonl"
            ), mock.patch.object(pe, "VALIDATION_JSON", out_dir / "validation.json"), mock.patch.object(
                pe, "_fetch_ticker_price", return_value=(110.0, "yfinance", "LIVE")
            ):
                result = pe.run_paper_mark_to_market(write_report_flag=False)
            self.assertTrue(result["ok"])
            portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
            pos = portfolio["positions"]["AAPL"]
            self.assertEqual(pos["current_price"], 110.0)
            self.assertEqual(pos["mark_status"], "LIVE")
            self.assertAlmostEqual(portfolio["unrealized_pnl"], 100.0, places=2)

    def test_compare_canonical_vs_paper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounting = root / "tae_accounting_snapshot.json"
            out_dir = root / "runtime_outputs/paper_execution"
            out_dir.mkdir(parents=True)
            accounting.write_text(
                json.dumps({"cash_available": 500.0, "account_value_corrected": 1500.0, "open_positions_count": 1}),
                encoding="utf-8",
            )
            (out_dir / "paper_portfolio.json").write_text(
                json.dumps(
                    {
                        "cash": 400.0,
                        "open_positions_value": 1200.0,
                        "total_value": 1600.0,
                        "realized_pnl": 50.0,
                        "unrealized_pnl": 25.0,
                        "total_pnl": 75.0,
                        "positions": {"X": {"shares": 1.0, "avg_price": 100.0, "current_price": 1200.0, "current_value": 1200.0, "pnl": 25.0}},
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(pe, "ACCOUNTING_JSON", accounting), mock.patch.object(
                pe, "PORTFOLIO_JSON", out_dir / "paper_portfolio.json"
            ), mock.patch.object(pe, "CANONICAL_VS_PAPER_MD", root / "TAE_CANONICAL_VS_PAPER_REPORT.md"):
                result = pe.compare_canonical_vs_paper(write_report_flag=False)
            self.assertTrue(result["ok"])
            self.assertAlmostEqual(result["delta"]["total_value"], 100.0, places=2)

    def test_order_counts_legacy_without_executed_flag(self) -> None:
        legacy = {
            "decision_id": "PDEC-LEG-1",
            "ticker": "AAPL",
            "action": "HOLD_PAPER",
            "before_position": {"shares": 5.0},
            "after_position": {"shares": 5.0},
        }
        skipped = {
            "decision_id": "PDEC-LEG-2",
            "ticker": "AZN.L",
            "action": "SELL_PAPER",
            "before_position": {"shares": 0.0},
        }
        self.assertTrue(pe._order_counts_for_attribution(legacy))
        self.assertFalse(pe._order_counts_for_attribution(skipped))

    def test_refresh_rule_attribution_from_actual(self) -> None:
        portfolio = {
            "positions": {
                "AAPL": {"shares": 5.0, "pnl": 20.0, "drawdown_pct": 1.0},
            }
        }
        orders = [
            {
                "executed": True,
                "decision_id": "D1",
                "ticker": "AAPL",
                "action": "BUY_PAPER",
                "expected_profit_delta": 10.0,
                "rule_sources": ["RULE-WIN"],
            }
        ]
        attr = pe.refresh_rule_attribution_from_actual(portfolio, orders=orders)
        rule = attr["rules"]["RULE-WIN"]
        self.assertEqual(rule["wins"], 1)
        self.assertAlmostEqual(rule["avg_actual_pnl"], 20.0, places=2)
        self.assertGreater(rule["recommended_influence_delta"], 0)

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

    def test_reexecute_when_action_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "runtime_outputs/paper_execution"
            out_dir.mkdir(parents=True)
            decisions_path = Path(tmp) / "runtime_outputs/paper_decisions/paper_decisions.json"
            decisions_path.parent.mkdir(parents=True, exist_ok=True)
            portfolio_path = out_dir / "paper_portfolio.json"
            portfolio_path.write_text(
                json.dumps(
                    {
                        "schema": pe.SCHEMA,
                        "mode": pe.MODE,
                        "cash": 1000.0,
                        "realized_pnl": 0.0,
                        "processed_decision_ids": ["PDEC-AAPL-001"],
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
                ),
                encoding="utf-8",
            )
            orders_path = out_dir / "paper_orders.jsonl"
            orders_path.write_text(
                json.dumps(
                    {
                        "decision_id": "PDEC-AAPL-001",
                        "ticker": "AAPL",
                        "action": "PROTECT_PAPER",
                        "executed": True,
                        "is_trade": False,
                        "fill_shares": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            decisions_path.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "decision_id": "PDEC-AAPL-001",
                                "ticker": "AAPL",
                                "action": "SELL_PAPER",
                                "confidence": 0.9,
                                "expected_profit_delta": 100.0,
                                "evidence": "sell after protect",
                                "decision_switch_authorized": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(pe, "DECISIONS_JSON", decisions_path), mock.patch.object(
                pe, "OUTPUT_DIR", out_dir
            ), mock.patch.object(pe, "PORTFOLIO_JSON", portfolio_path), mock.patch.object(
                pe, "ORDERS_JSONL", orders_path
            ), mock.patch.object(pe, "TRADES_JSONL", out_dir / "paper_trades.jsonl"), mock.patch.object(
                pe, "ATTRIBUTION_JSON", out_dir / "rule_outcome_attribution.json"
            ), mock.patch.object(pe, "ACCOUNTING_JSON", out_dir / "acct.json"), mock.patch.object(
                pe, "REPORT_MD", Path(tmp) / "report.md"
            ):
                result = pe.run_paper_execution(write_report_flag=False)
            self.assertTrue(result["ok"])
            self.assertEqual(result["stats"]["reexecuted_on_action_change"], 1)
            self.assertEqual(result["stats"]["trades_written"], 1)
            portfolio = json.loads(portfolio_path.read_text())
            self.assertNotIn("AAPL", portfolio.get("positions") or {})


class TestCapitalBaseDefectFix(unittest.TestCase):
    def test_fill_price_no_synthetic_default(self) -> None:
        decision = {"portfolio_snapshot": {}}
        self.assertEqual(pe.fill_price_for_position(None, "NEWCO", None, decision), 0.0)
        self.assertEqual(pe.price_for_ticker("NEWCO", None, decision), 0.0)

    def test_buy_skipped_without_mark_price(self) -> None:
        portfolio = {"cash": 5000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-NEW-001",
            "ticker": "NEWCO",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "expected_profit_delta": 10.0,
            "evidence": "test",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "SKIPPED_NO_MARK_PRICE")
        self.assertFalse(order["is_trade"])
        self.assertEqual(portfolio["cash"], 5000.0)

    def test_reset_portfolio_from_accounting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "paper_execution"
            out_dir.mkdir(parents=True)
            acct_path = Path(tmp) / "acct.json"
            acct = {
                "effective_contributed_capital": 30000.0,
                "account_value_corrected": 30340.91,
                "cash_available": 2335.28,
                "open_positions_value": 28005.63,
                "open_positions": [
                    {"ticker": "AAPL", "shares": 10.0, "current_price": 312.96, "pnl": 35.0},
                ],
            }
            acct_path.write_text(json.dumps(acct), encoding="utf-8")
            corrupt = {
                "schema": pe.SCHEMA,
                "total_value": 51442.97,
                "cash": 24583.88,
                "realized_pnl": 14870.56,
                "positions": {"DIA": {"shares": 8.0, "avg_price": 100.0, "current_price": 522.0}},
            }
            portfolio_path = out_dir / "paper_portfolio.json"
            trades_path = out_dir / "paper_trades.jsonl"
            portfolio_path.write_text(json.dumps(corrupt), encoding="utf-8")
            trades_path.write_text(
                json.dumps(
                    {
                        "action": "BUY_PAPER",
                        "fill_price": 100.0,
                        "is_trade": True,
                        "record_type": "paper_trade",
                        "fill_shares": 1.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(pe, "OUTPUT_DIR", out_dir), mock.patch.object(
                pe, "PORTFOLIO_JSON", portfolio_path
            ), mock.patch.object(pe, "ORDERS_JSONL", out_dir / "paper_orders.jsonl"), mock.patch.object(
                pe, "TRADES_JSONL", trades_path
            ), mock.patch.object(pe, "ACCOUNTING_JSON", acct_path):
                self.assertTrue(pe.paper_portfolio_has_synthetic_fill_corruption(corrupt, acct))
                reset = pe.reset_paper_portfolio_from_accounting(acct, archive_ledger=True)
            self.assertAlmostEqual(reset["validation_capital_base"], 30000.0, places=2)
            self.assertAlmostEqual(reset["realized_pnl"], 0.0, places=2)
            self.assertIn("AAPL", reset["positions"])
            self.assertNotIn("DIA", reset["positions"])
            self.assertAlmostEqual(reset["total_value"], 5464.88, places=0)


class TestProfitIntegrityGuard(unittest.TestCase):
    def test_sell_skipped_without_mark_price_no_mutation(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "NEWCO": {
                    "ticker": "NEWCO",
                    "shares": 5.0,
                    "avg_price": 200.0,
                    "current_price": 0.0,
                    "status": "OPEN",
                }
            },
        }
        before_cash = portfolio["cash"]
        decision = {
            "decision_id": "PDEC-NEW-002",
            "ticker": "NEWCO",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "evidence": "sell",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "SKIPPED_NO_MARK_PRICE")
        self.assertFalse(order["is_trade"])
        self.assertEqual(portfolio["cash"], before_cash)
        self.assertIn("NEWCO", portfolio["positions"])

    def test_synthetic_buy_blocked_from_ledger(self) -> None:
        self.assertTrue(
            pe.is_suspicious_synthetic_fill_price(100.0, "DIA", pos=None, decision={}, accounting=None)
        )
        order = pe.execute_decision(
            {
                "decision_id": "PDEC-DIA-X",
                "ticker": "DIA",
                "action": "BUY_PAPER",
                "confidence": 0.8,
                "portfolio_snapshot": {"current_price": 100.0},
                "evidence": "test",
            },
            {"cash": 5000.0, "realized_pnl": 0.0, "positions": {}},
            accounting=None,
            all_decisions=[],
        )
        self.assertEqual(order["status"], "BLOCKED_FAKE_PROFIT_RISK")

    def test_corrupt_avg_price_detected_before_validation(self) -> None:
        corrupt = {
            "validation_capital_base": 30000.0,
            "total_value": 51442.97,
            "cash": 24583.88,
            "positions": {"DIA": {"shares": 8.0, "avg_price": 100.0, "current_price": 522.0}},
        }
        findings = pe.collect_fake_profit_contamination(corrupt, {"account_value_corrected": 30340.91})
        codes = {f["code"] for f in findings}
        self.assertIn("SUSPICIOUS_AVG_PRICE", codes)
        self.assertIn("PAPER_CANONICAL_VALUE_GAP", codes)

    def test_validation_blocked_when_capital_base_not_30000(self) -> None:
        portfolio = {
            "validation_capital_base": 25000.0,
            "cash": 1000.0,
            "open_positions_value": 9000.0,
            "total_value": 10000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0,
            "starting_value": 10000.0,
            "baseline_unrealized_pnl": 0.0,
            "realized_pnl_at_baseline": 0.0,
            "positions": {},
        }
        with mock.patch.object(pe, "VALIDATION_PROFIT_JSON", Path("/dev/null/nonexistent.json")):
            result = pe.check_paper_profit_integrity(
                portfolio=portfolio,
                accounting={"effective_contributed_capital": 30000.0},
                write_report_flag=False,
                update_validation_json=False,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], "BLOCKED_BY_UNRESOLVED_CAPITAL_DEFECT")

    def test_integrity_pass_on_clean_portfolio(self) -> None:
        portfolio = {
            "validation_capital_base": 30000.0,
            "cash": 2335.28,
            "open_positions_value": 2504.0,
            "total_value": 4839.28,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.32,
            "total_pnl": 0.32,
            "starting_value": 4839.28,
            "baseline_unrealized_pnl": 0.0,
            "realized_pnl_at_baseline": 0.0,
            "value_delta": 0.32,
            "positions": {
                "AAPL": {
                    "shares": 8.0,
                    "avg_price": 312.96,
                    "current_price": 313.0,
                    "current_value": 2504.0,
                    "pnl": 0.32,
                }
            },
        }
        with mock.patch.object(pe, "VALIDATION_PROFIT_JSON", Path("/dev/null/nonexistent.json")):
            result = pe.check_paper_profit_integrity(
                portfolio=portfolio,
                accounting={"effective_contributed_capital": 30000.0, "account_value_corrected": 30340.91},
                trades=[],
                orders=[],
                write_report_flag=False,
                update_validation_json=False,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["verdict"], "PAPER_PROFIT_INTEGRITY_CLOSED")
        self.assertAlmostEqual(result["metrics"]["profit_vs_capital_base"], -25160.72, places=1)


if __name__ == "__main__":
    unittest.main()
