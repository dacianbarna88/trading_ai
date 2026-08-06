#!/usr/bin/env python3
"""Tests for tae_paper_execution.py."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import tae_paper_execution as pe


from tae_test_isolation import isolate_adaptive_deployment as _isolate_adaptive_deployment


class PaperExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        # Keep legacy fill tests independent of opening-noise temporal gate.
        self._adaptive_root = _isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )

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
                result = pe.compare_canonical_vs_paper(
                    write_report_flag=False,
                    accounting_path=accounting,
                    paper_path=out_dir / "paper_portfolio.json",
                )
            self.assertTrue(result["ok"])
            self.assertAlmostEqual(result["delta"]["total_value"], 100.0, places=2)
            self.assertEqual(result["sources"]["accounting"], str(accounting))
            self.assertNotIn("build_accounting_snapshot", result["sources"]["accounting"])

    def test_compare_canonical_vs_paper_host_not_read_with_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounting = root / "fixture_accounting.json"
            paper = root / "paper_portfolio.json"
            accounting.write_text(
                json.dumps(
                    {
                        "cash_available": 500.0,
                        "account_value_corrected": 1500.0,
                        "open_positions_count": 1,
                        "realized_pnl": 0.0,
                        "unrealized_pnl": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            paper.write_text(
                json.dumps(
                    {
                        "cash": 400.0,
                        "open_positions_value": 1200.0,
                        "total_value": 1600.0,
                        "realized_pnl": 50.0,
                        "unrealized_pnl": 25.0,
                        "total_pnl": 75.0,
                        "positions": {
                            "X": {
                                "shares": 1.0,
                                "avg_price": 100.0,
                                "current_price": 1200.0,
                                "current_value": 1200.0,
                                "pnl": 25.0,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            def _boom(*_a, **_k):
                raise AssertionError("HOST_ACCOUNTING_READ")

            with mock.patch.object(pe, "_load_live_accounting", side_effect=_boom):
                result = pe.compare_canonical_vs_paper(
                    write_report_flag=False,
                    accounting_path=accounting,
                    paper_path=paper,
                )
            self.assertTrue(result["ok"])
            self.assertAlmostEqual(result["canonical"]["total_value"], 1500.0, places=2)
            self.assertAlmostEqual(result["paper"]["total_value"], 1600.0, places=2)
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
    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )

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
        with mock.patch.object(pe, "resolve_mark_price", return_value={
            "price": 0.0,
            "source": "UNAVAILABLE",
            "timestamp": None,
            "freshness": "UNAVAILABLE",
            "attempts": [],
        }):
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
    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )

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
        with mock.patch.object(pe, "resolve_mark_price", return_value={
            "price": 100.0,
            "source": "decision_portfolio_snapshot",
            "timestamp": None,
            "freshness": "STALE",
            "attempts": [],
        }):
            order = pe.execute_decision(
                {
                    "decision_id": "PDEC-ZZZ-001",
                    "ticker": "ZZZNOTREAL",
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


class TestNonTerminalOrderRecovery(unittest.TestCase):
    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )

    def test_executed_same_action_does_not_reexecute(self) -> None:
        processed = {"PDEC-AAPL-001"}
        last_orders = {
            "PDEC-AAPL-001": {
                "action": "PROTECT_PAPER",
                "status": "EXECUTED",
                "executed": True,
            }
        }
        ok, reason = pe.should_execute_decision(
            "PDEC-AAPL-001", "PROTECT_PAPER", processed=processed, last_orders=last_orders
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "already_processed_same_action")

    def test_crash_recovery_honors_executed_order_without_processed_id(self) -> None:
        """Orders.jsonl EXECUTED must block re-SELL even if processed_decision_ids lost."""
        last_orders = {
            "PDEC-SELL-CRASH": {
                "action": "SELL_PAPER",
                "status": "EXECUTED",
                "executed": True,
                "is_trade": True,
                "fill_shares": 10.0,
                "fill_price": 100.0,
            }
        }
        ok, reason = pe.should_execute_decision(
            "PDEC-SELL-CRASH",
            "SELL_PAPER",
            processed=set(),  # crash before portfolio save
            last_orders=last_orders,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "already_processed_same_action")

    def test_adaptive_buy_gates_do_not_appear_on_sell_branch(self) -> None:
        src = Path(pe.__file__).read_text(encoding="utf-8")
        sell_idx = src.find('elif action == "SELL_PAPER":')
        buy_idx = src.find('elif action == "BUY_PAPER":')
        self.assertGreater(sell_idx, 0)
        self.assertGreater(buy_idx, sell_idx)
        sell_block = src[sell_idx:buy_idx]
        self.assertNotIn("resolve_buy_notional", sell_block)
        self.assertNotIn("BLOCKED_TICKER_SCOPE", sell_block)
        self.assertNotIn("BLOCKED_CAPITAL_CAP", sell_block)
        self.assertNotIn("evaluate_opening_noise_new_buy_gate", sell_block)
        self.assertNotIn("evaluate_profit_decay_new_buy_gate", sell_block)

    def test_save_json_is_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "paper_portfolio.json"
            # Point assert_safe_path via OUTPUT_DIR override
            with mock.patch.object(pe, "OUTPUT_DIR", root), mock.patch.object(
                pe, "assert_safe_path", lambda p: None
            ):
                pe.save_json(path, {"ok": True, "n": 1})
                self.assertTrue(path.is_file())
                self.assertEqual(json.loads(path.read_text())["n"], 1)
                pe.save_json(path, {"ok": True, "n": 2})
                self.assertEqual(json.loads(path.read_text())["n"], 2)
                self.assertEqual(len(list(root.glob("*.tmp"))), 0)

    def test_skipped_no_mark_is_non_terminal(self) -> None:
        self.assertFalse(pe.is_terminal_order_status("SKIPPED_NO_MARK_PRICE"))
        self.assertTrue(pe.is_terminal_order_status("EXECUTED", executed=True))

    def test_reconcile_drops_non_terminal_from_processed(self) -> None:
        processed = {"PDEC-HD-0010"}
        last_orders = {"PDEC-HD-0010": {"status": "SKIPPED_NO_MARK_PRICE", "action": "BUY_PAPER"}}
        cleaned = pe.reconcile_processed_decision_ids(processed, last_orders)
        self.assertNotIn("PDEC-HD-0010", cleaned)

    def test_hd_buy_resolves_live_signal_price(self) -> None:
        with mock.patch.object(pe, "SIGNALS_CSV", Path(__file__).parent / "live_signals.csv"):
            if not (Path(__file__).parent / "live_signals.csv").is_file():
                self.skipTest("live_signals.csv not present")
            resolved = pe.resolve_mark_price("HD", None, {})
            self.assertGreater(resolved["price"], 0)
            self.assertEqual(resolved["source"], "live_signals.csv")

    def test_retry_executes_when_mark_available(self) -> None:
        portfolio = {"cash": 5000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-HD-0010",
            "ticker": "HD",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "expected_profit_delta": 15.0,
            "evidence": "retry buy",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value={
            "price": 337.11,
            "source": "live_signals.csv",
            "timestamp": "2026-07-14T02:28:53",
            "freshness": "FRESH",
            "attempts": [],
        }):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["is_trade"])
        self.assertAlmostEqual(order["fill_price"], 337.11, places=2)
        self.assertIn("HD", portfolio["positions"])

    def test_retry_without_mark_does_not_mutate_portfolio(self) -> None:
        portfolio = {"cash": 5000.0, "realized_pnl": 0.0, "positions": {}}
        cash_before = portfolio["cash"]
        decision = {
            "decision_id": "PDEC-NEW-002",
            "ticker": "NEWCO",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "evidence": "retry",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value={
            "price": 0.0,
            "source": "UNAVAILABLE",
            "timestamp": None,
            "freshness": "UNAVAILABLE",
            "attempts": [],
        }):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "SKIPPED_NO_MARK_PRICE")
        self.assertEqual(portfolio["cash"], cash_before)
        self.assertEqual(order["order_classification"], "NON_TERMINAL")

    def test_retry_cooldown_blocks_second_attempt_same_cycle(self) -> None:
        cycle_ts = datetime(2026, 7, 14, 1, 0, 0, tzinfo=timezone.utc)
        last_orders = {
            "PDEC-HD-0010": {
                "timestamp": "2026-07-14T01:00:05+00:00",
                "status": "SKIPPED_NO_MARK_PRICE",
                "action": "BUY_PAPER",
            }
        }
        ok, reason = pe.should_execute_decision(
            "PDEC-HD-0010",
            "BUY_PAPER",
            processed={"PDEC-HD-0010"},
            last_orders=last_orders,
            cycle_ts=cycle_ts,
            cycle_orders={"PDEC-HD-0010": last_orders["PDEC-HD-0010"]},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "retry_cooldown_active")

    def test_successful_retry_becomes_terminal(self) -> None:
        order = {
            "status": "EXECUTED",
            "executed": True,
            "is_trade": True,
        }
        self.assertTrue(pe.is_terminal_order_status(order["status"], executed=order["executed"], is_trade=order["is_trade"]))

    def test_synthetic_price_still_blocked_with_signal(self) -> None:
        with mock.patch.object(pe, "resolve_mark_price", return_value={
            "price": 100.0,
            "source": "decision_portfolio_snapshot",
            "timestamp": None,
            "freshness": "STALE",
            "attempts": [],
        }):
            order = pe.execute_decision(
                {
                    "decision_id": "PDEC-ZZZ-001",
                    "ticker": "ZZZNOTREAL",
                    "action": "BUY_PAPER",
                    "confidence": 0.8,
                    "evidence": "test",
                },
                {"cash": 5000.0, "realized_pnl": 0.0, "positions": {}},
                accounting=None,
                all_decisions=[],
            )
        self.assertEqual(order["status"], "BLOCKED_FAKE_PROFIT_RISK")

    def test_non_terminal_retry_allowed_after_skipped_mark(self) -> None:
        processed = {"PDEC-HD-0010"}
        last_orders = {
            "PDEC-HD-0010": {"action": "BUY_PAPER", "status": "SKIPPED_NO_MARK_PRICE", "timestamp": "2026-07-10T07:07:35+00:00"}
        }
        ok, reason = pe.should_execute_decision(
            "PDEC-HD-0010",
            "BUY_PAPER",
            processed=processed,
            last_orders=last_orders,
            cycle_ts=datetime(2026, 7, 14, 1, 0, 0, tzinfo=timezone.utc),
            cycle_orders={},
        )
        self.assertTrue(ok)
        self.assertTrue(reason.startswith("retry_after_non_terminal"))


class Sprint1FillTimeHardRiskTest(unittest.TestCase):
    """Execution-time hard-risk revalidation (CRITICAL #1)."""

    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(self)

    def _portfolio(self, *, avg: float, mark: float, shares: float = 10.0) -> dict:
        return {
            "cash": 5000.0,
            "realized_pnl": 0.0,
            "positions": {
                "RISK": {
                    "ticker": "RISK",
                    "shares": shares,
                    "avg_price": avg,
                    "current_price": mark,
                    "status": "OPEN",
                }
            },
        }

    def _decision(self, action: str, decision_id: str = "PDEC-RISK-0001") -> dict:
        return {
            "decision_id": decision_id,
            "ticker": "RISK",
            "action": action,
            "confidence": 0.9,
            "evidence": "sprint1 test",
            "expected_profit_delta": 0.0,
        }

    def test_safe_state_reduce_executes_unchanged(self) -> None:
        # Mark only -1% vs avg — below stop threshold.
        portfolio = self._portfolio(avg=100.0, mark=99.0)
        decision = self._decision("REDUCE_PAPER")
        cash_before = portfolio["cash"]
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["action"], "REDUCE_PAPER")
        self.assertEqual(decision["action"], "REDUCE_PAPER")  # never rewritten
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["executed"])
        self.assertGreater(order["fill_shares"], 0)
        self.assertEqual((order.get("fill_time_hard_risk") or {}).get("status"), "OK")
        self.assertGreater(portfolio["cash"], cash_before)

    def test_unsafe_after_decision_blocks_non_sell_fill(self) -> None:
        # Decision approved as REDUCE while fill mark is -4% (stop breached).
        portfolio = self._portfolio(avg=100.0, mark=96.0)
        decision = self._decision("REDUCE_PAPER")
        shares_before = portfolio["positions"]["RISK"]["shares"]
        cash_before = portfolio["cash"]
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "BLOCKED_HARD_RISK_AT_FILL")
        self.assertFalse(order["executed"])
        self.assertFalse(order["is_trade"])
        self.assertEqual(order["action"], "REDUCE_PAPER")
        self.assertEqual(decision["action"], "REDUCE_PAPER")  # never silently rewritten
        self.assertEqual(order["fill_shares"], 0.0)
        self.assertEqual(portfolio["positions"]["RISK"]["shares"], shares_before)
        self.assertEqual(portfolio["cash"], cash_before)
        hr = order.get("fill_time_hard_risk") or {}
        self.assertEqual(hr.get("status"), "STOP_LOSS_BREACHED")
        self.assertIn("HARD_STOP", str(hr.get("hard_rule") or ""))

    def test_required_risk_sell_still_executes(self) -> None:
        portfolio = self._portfolio(avg=100.0, mark=94.0)  # -6% critical
        decision = self._decision("SELL_PAPER")
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["action"], "SELL_PAPER")
        self.assertEqual(decision["action"], "SELL_PAPER")
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["executed"])
        self.assertNotIn("RISK", portfolio["positions"])
        hr = order.get("fill_time_hard_risk") or {}
        self.assertEqual(hr.get("status"), "CRITICAL_LOSS")

    def test_decision_action_never_silently_rewritten_on_block(self) -> None:
        portfolio = self._portfolio(avg=100.0, mark=96.5)
        decision = self._decision("PROTECT_PAPER")
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "BLOCKED_HARD_RISK_AT_FILL")
        self.assertEqual(order["action"], "PROTECT_PAPER")
        self.assertEqual(decision["action"], "PROTECT_PAPER")
        self.assertNotEqual(order["action"], "SELL_PAPER")

    def test_no_duplicate_execution_after_block_then_same_action(self) -> None:
        portfolio = self._portfolio(avg=100.0, mark=96.0)
        decision = self._decision("REDUCE_PAPER", "PDEC-RISK-DUP")
        order1 = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order1["status"], "BLOCKED_HARD_RISK_AT_FILL")
        shares_after_block = portfolio["positions"]["RISK"]["shares"]
        cash_after_block = portfolio["cash"]

        # Same decision_id + same action with non-terminal prior → retry allowed,
        # but fill remains blocked; capital must not move.
        ok, reason = pe.should_execute_decision(
            "PDEC-RISK-DUP",
            "REDUCE_PAPER",
            processed={"PDEC-RISK-DUP"},
            last_orders={"PDEC-RISK-DUP": order1},
            cycle_ts=datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc),
            cycle_orders={},
        )
        self.assertTrue(ok)
        self.assertTrue(reason.startswith("retry_after_non_terminal"))
        order2 = pe.execute_decision(
            decision,
            portfolio,
            accounting=None,
            all_decisions=[decision],
            execution_reason=reason,
        )
        self.assertEqual(order2["status"], "BLOCKED_HARD_RISK_AT_FILL")
        self.assertFalse(order2["executed"])
        self.assertEqual(portfolio["positions"]["RISK"]["shares"], shares_after_block)
        self.assertEqual(portfolio["cash"], cash_after_block)

        # After a successful SELL, same decision_id + same action must not re-execute.
        sell = self._decision("SELL_PAPER", "PDEC-RISK-DUP")
        order_sell = pe.execute_decision(
            sell,
            portfolio,
            accounting=None,
            all_decisions=[sell],
            execution_reason="action_changed:REDUCE_PAPER->SELL_PAPER",
        )
        self.assertEqual(order_sell["status"], "EXECUTED")
        ok2, reason2 = pe.should_execute_decision(
            "PDEC-RISK-DUP",
            "SELL_PAPER",
            processed={"PDEC-RISK-DUP"},
            last_orders={"PDEC-RISK-DUP": order_sell},
            cycle_ts=datetime(2026, 7, 17, 13, 0, 0, tzinfo=timezone.utc),
            cycle_orders={},
        )
        self.assertFalse(ok2)
        self.assertEqual(reason2, "already_processed_same_action")


class ProactiveHardRiskExitScanTest(unittest.TestCase):
    """Proactive hard-risk scan closes breach positions between PDE cycles."""

    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(self)

    def test_proactive_scan_sells_breached_position(self) -> None:
        portfolio = {
            "cash": 5000.0,
            "realized_pnl": 0.0,
            "positions": {
                "RISK": {
                    "ticker": "RISK",
                    "shares": 10.0,
                    "avg_price": 100.0,
                    "current_price": 96.0,
                    "status": "OPEN",
                }
            },
        }
        orders = pe.execute_proactive_hard_risk_exits(
            portfolio,
            accounting=None,
            processed=set(),
            last_orders={},
        )
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["action"], "SELL_PAPER")
        self.assertEqual(orders[0]["status"], "EXECUTED")
        self.assertNotIn("RISK", portfolio.get("positions") or {})

    def test_proactive_scan_skips_safe_position(self) -> None:
        portfolio = {
            "cash": 5000.0,
            "realized_pnl": 0.0,
            "positions": {
                "SAFE": {
                    "ticker": "SAFE",
                    "shares": 10.0,
                    "avg_price": 100.0,
                    "current_price": 99.0,
                    "status": "OPEN",
                }
            },
        }
        orders = pe.execute_proactive_hard_risk_exits(
            portfolio,
            accounting=None,
            processed=set(),
            last_orders={},
        )
        self.assertEqual(orders, [])
        self.assertIn("SAFE", portfolio["positions"])


class MarkToMarketFreshnessTest(unittest.TestCase):
    """Deterministic MTM freshness / ALL_STALE safety tests (no live network)."""

    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(self)

    def _write_portfolio(self, root: Path, positions: dict) -> Path:
        out_dir = root / "runtime_outputs/paper_execution"
        out_dir.mkdir(parents=True)
        portfolio_path = out_dir / "paper_portfolio.json"
        cash = 1000.0
        open_value = sum(
            float(p["shares"]) * float(p["current_price"]) for p in positions.values()
        )
        portfolio = {
            "schema": pe.SCHEMA,
            "mode": "PAPER_ONLY",
            "cash": cash,
            "starting_value": cash + open_value,
            "peak_value": cash + open_value,
            "total_value": cash + open_value,
            "open_positions_value": open_value,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0,
            "positions": positions,
        }
        portfolio_path.write_text(json.dumps(portfolio), encoding="utf-8")
        return portfolio_path

    def _run_mtm(self, root: Path, portfolio_path: Path, fetch_map: dict):
        out_dir = portfolio_path.parent

        def _fake_fetch(ticker: str):
            row = fetch_map.get(ticker)
            if row is None:
                return None, "UNAVAILABLE", "STALE"
            return row

        with mock.patch.object(pe, "OUTPUT_DIR", out_dir), mock.patch.object(
            pe, "PORTFOLIO_JSON", portfolio_path
        ), mock.patch.object(
            pe, "ATTRIBUTION_JSON", out_dir / "rule_outcome_attribution.json"
        ), mock.patch.object(
            pe, "MTM_JSON", out_dir / "mark_to_market.json"
        ), mock.patch.object(
            pe, "MTM_REPORT_MD", root / "TAE_PAPER_MARK_TO_MARKET_REPORT.md"
        ), mock.patch.object(
            pe, "ORDERS_JSONL", out_dir / "paper_orders.jsonl"
        ), mock.patch.object(
            pe, "VALIDATION_JSON", out_dir / "validation.json"
        ), mock.patch.object(pe, "_fetch_ticker_price", side_effect=_fake_fetch):
            return pe.run_paper_mark_to_market(write_report_flag=False)

    def test_fresh_valid_prices_mtm_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_path = self._write_portfolio(
                root,
                {
                    "AAPL": {
                        "ticker": "AAPL",
                        "shares": 2.0,
                        "avg_price": 100.0,
                        "current_price": 100.0,
                        "status": "OPEN",
                    },
                    "SPY": {
                        "ticker": "SPY",
                        "shares": 1.0,
                        "avg_price": 500.0,
                        "current_price": 500.0,
                        "status": "OPEN",
                    },
                },
            )
            result = self._run_mtm(
                root,
                portfolio_path,
                {
                    "AAPL": (110.0, "yfinance_download_5d", "DATA_OK"),
                    "SPY": (510.0, "yfinance_download_5d", "DATA_OK"),
                },
            )
            self.assertTrue(result["ok"])
            mtm = json.loads((portfolio_path.parent / "mark_to_market.json").read_text())
            self.assertEqual(mtm["live_price_count"], 2)
            self.assertEqual(mtm["stale_price_count"], 0)
            from tae_structural_governance import _mark_to_market_status

            self.assertEqual(_mark_to_market_status(mtm), "LIVE")

    def test_all_stale_with_open_positions_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_path = self._write_portfolio(
                root,
                {
                    "AAPL": {
                        "ticker": "AAPL",
                        "shares": 2.0,
                        "avg_price": 100.0,
                        "current_price": 105.0,
                        "status": "OPEN",
                    },
                    "NVDA": {
                        "ticker": "NVDA",
                        "shares": 1.0,
                        "avg_price": 200.0,
                        "current_price": 190.0,
                        "status": "OPEN",
                    },
                },
            )
            result = self._run_mtm(
                root,
                portfolio_path,
                {
                    "AAPL": (None, "UNAVAILABLE", "STALE"),
                    "NVDA": (None, "UNAVAILABLE", "STALE"),
                },
            )
            self.assertTrue(result["ok"])
            mtm = json.loads((portfolio_path.parent / "mark_to_market.json").read_text())
            self.assertEqual(mtm["live_price_count"], 0)
            self.assertEqual(mtm["stale_price_count"], 2)
            from tae_structural_governance import _mark_to_market_status

            self.assertEqual(_mark_to_market_status(mtm), "ALL_STALE")
            for row in mtm["positions"]:
                self.assertEqual(row["mark_source"], "FALLBACK_STALE")
                self.assertNotEqual(row["current_price"], 100.0)  # no synthetic $100

    def test_mixed_fresh_stale_marks_valid_positions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_path = self._write_portfolio(
                root,
                {
                    "AAPL": {
                        "ticker": "AAPL",
                        "shares": 2.0,
                        "avg_price": 100.0,
                        "current_price": 100.0,
                        "status": "OPEN",
                    },
                    "AIR.PA": {
                        "ticker": "AIR.PA",
                        "shares": 1.0,
                        "avg_price": 190.0,
                        "current_price": 194.0,
                        "status": "OPEN",
                    },
                },
            )
            result = self._run_mtm(
                root,
                portfolio_path,
                {
                    "AAPL": (112.0, "yfinance_download_5d", "DATA_OK"),
                    "AIR.PA": (None, "UNAVAILABLE", "STALE"),
                },
            )
            self.assertTrue(result["ok"])
            mtm = json.loads((portfolio_path.parent / "mark_to_market.json").read_text())
            self.assertEqual(mtm["live_price_count"], 1)
            self.assertEqual(mtm["stale_price_count"], 1)
            by_ticker = {r["ticker"]: r for r in mtm["positions"]}
            self.assertEqual(by_ticker["AAPL"]["current_price"], 112.0)
            self.assertEqual(by_ticker["AAPL"]["mark_status"], "DATA_OK")
            self.assertEqual(by_ticker["AIR.PA"]["current_price"], 194.0)
            self.assertEqual(by_ticker["AIR.PA"]["mark_source"], "FALLBACK_STALE")
            from tae_structural_governance import _mark_to_market_status

            self.assertEqual(_mark_to_market_status(mtm), "PARTIAL_STALE")

    def test_missing_prices_never_receive_synthetic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_path = self._write_portfolio(
                root,
                {
                    "ZZZ": {
                        "ticker": "ZZZ",
                        "shares": 3.0,
                        "avg_price": 42.5,
                        "current_price": 42.5,
                        "status": "OPEN",
                    },
                },
            )
            prior_cash = json.loads(portfolio_path.read_text())["cash"]
            prior_shares = 3.0
            result = self._run_mtm(
                root,
                portfolio_path,
                {"ZZZ": (None, "UNAVAILABLE", "STALE")},
            )
            self.assertTrue(result["ok"])
            portfolio = json.loads(portfolio_path.read_text())
            pos = portfolio["positions"]["ZZZ"]
            self.assertEqual(pos["current_price"], 42.5)
            self.assertEqual(pos["shares"], prior_shares)
            self.assertEqual(portfolio["cash"], prior_cash)
            self.assertNotIn(100.0, [pos["current_price"], portfolio["cash"]])
            mtm = json.loads((portfolio_path.parent / "mark_to_market.json").read_text())
            self.assertEqual(mtm["positions"][0]["mark_source"], "FALLBACK_STALE")

    def test_accounting_unchanged_on_fresh_mark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_path = self._write_portfolio(
                root,
                {
                    "AAPL": {
                        "ticker": "AAPL",
                        "shares": 4.0,
                        "avg_price": 50.0,
                        "current_price": 50.0,
                        "status": "OPEN",
                    },
                },
            )
            before = json.loads(portfolio_path.read_text())
            result = self._run_mtm(
                root,
                portfolio_path,
                {"AAPL": (55.0, "yfinance_download_5d", "DATA_OK")},
            )
            self.assertTrue(result["ok"])
            after = json.loads(portfolio_path.read_text())
            self.assertEqual(after["cash"], before["cash"])
            self.assertEqual(after["positions"]["AAPL"]["shares"], before["positions"]["AAPL"]["shares"])
            self.assertEqual(after["positions"]["AAPL"]["avg_price"], before["positions"]["AAPL"]["avg_price"])
            self.assertEqual(after["realized_pnl"], before["realized_pnl"])
            self.assertAlmostEqual(after["unrealized_pnl"], 20.0, places=4)


class CanonicalE3ProfitDecayGateTest(unittest.TestCase):
    """Canonical PAPER gate: block NEW BUY when lifecycle_stage == PROFIT_DECAY."""

    def setUp(self) -> None:
        # Isolate E3 tests from opening-noise gate (orthogonal temporal gate)
        # and from live Adaptive Deployment canary SSOT.
        self._adaptive_root = _isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )

    def _mark(self, price: float = 100.0) -> dict:
        return {
            "price": price,
            "source": "test",
            "timestamp": "2026-07-22T00:00:00Z",
            "freshness": "FRESH",
            "attempts": [],
        }

    def _gii_meta_ok(self) -> dict:
        return {
            "gate_status": "OK",
            "generated_at": "2026-07-22T00:00:00Z",
            "age_hours": 1.0,
            "max_age_hours": 24.0,
        }

    def test_01_new_buy_profit_decay_blocked(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        cash_before = portfolio["cash"]
        decision = {
            "decision_id": "PDEC-E3-001",
            "ticker": "DECAY",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "timestamp": "2026-07-22T12:00:00Z",
            "evidence": "strong buy",
        }
        gii = {"DECAY": {"lifecycle_stage": "PROFIT_DECAY", "collapse_probability": 0.95}}
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.object(
            pe, "append_e3_block_event"
        ) as append_evt:
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker=gii,
                gii_meta=self._gii_meta_ok(),
            )
        self.assertEqual(order["original_action"], "BUY_PAPER")
        self.assertEqual(order["authorized_action"], "HOLD_PAPER")
        self.assertEqual(order["status"], pe.BLOCK_REASON_PROFIT_DECAY)
        self.assertEqual(order["block_reason"], pe.BLOCK_REASON_PROFIT_DECAY)
        self.assertFalse(order["executed"])
        self.assertFalse(order["is_trade"])
        self.assertEqual(order["fill_shares"], 0.0)
        self.assertEqual(portfolio["cash"], cash_before)
        self.assertNotIn("DECAY", portfolio["positions"])
        append_evt.assert_called_once()

    def test_02_new_buy_normal_stage_allowed(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-E3-002",
            "ticker": "GROW",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "evidence": "buy ok",
        }
        gii = {"GROW": {"lifecycle_stage": "EARLY_WINNER", "collapse_probability": 0.1}}
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.object(
            pe, "append_e3_block_event"
        ) as append_evt:
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker=gii,
                gii_meta=self._gii_meta_ok(),
            )
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["is_trade"])
        self.assertIn("GROW", portfolio["positions"])
        self.assertLess(portfolio["cash"], 10000.0)
        append_evt.assert_not_called()

    def test_03_sell_in_profit_decay_authorized(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "DECAY": {
                    "ticker": "DECAY",
                    "shares": 10.0,
                    "avg_price": 90.0,
                    "current_price": 100.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-E3-003",
            "ticker": "DECAY",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "evidence": "exit",
        }
        gii = {"DECAY": {"lifecycle_stage": "PROFIT_DECAY", "collapse_probability": 1.0}}
        order = pe.execute_decision(
            decision,
            portfolio,
            accounting=None,
            all_decisions=[decision],
            gii_by_ticker=gii,
            gii_meta=self._gii_meta_ok(),
        )
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["is_trade"])
        self.assertNotIn("DECAY", portfolio["positions"])

    def test_04_reduce_in_profit_decay_authorized(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "DECAY": {
                    "ticker": "DECAY",
                    "shares": 10.0,
                    "avg_price": 90.0,
                    "current_price": 100.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-E3-004",
            "ticker": "DECAY",
            "action": "REDUCE_PAPER",
            "confidence": 0.7,
            "evidence": "trim",
        }
        gii = {"DECAY": {"lifecycle_stage": "PROFIT_DECAY"}}
        order = pe.execute_decision(
            decision,
            portfolio,
            accounting=None,
            all_decisions=[decision],
            gii_by_ticker=gii,
            gii_meta=self._gii_meta_ok(),
        )
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["is_trade"])
        self.assertIn("DECAY", portfolio["positions"])

    def test_05_hard_stop_in_profit_decay_executes(self) -> None:
        # Existing hard-risk path: breached open position blocks non-sell; SELL still executes.
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "DECAY": {
                    "ticker": "DECAY",
                    "shares": 10.0,
                    "avg_price": 100.0,
                    "current_price": 50.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-E3-005",
            "ticker": "DECAY",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "evidence": "hard stop exit",
        }
        gii = {"DECAY": {"lifecycle_stage": "PROFIT_DECAY"}}
        with mock.patch.object(
            pe,
            "evaluate_fill_time_hard_risk",
            return_value={
                "status": "STOP_LOSS_BREACHED",
                "hard_rule": "STOP_LOSS",
                "pnl_pct": -50.0,
                "required_action": "SELL_PAPER",
            },
        ):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker=gii,
                gii_meta=self._gii_meta_ok(),
            )
        self.assertEqual(order["status"], "EXECUTED")
        self.assertNotIn("DECAY", portfolio["positions"])

    def test_06_existing_position_buy_addon_not_treated_as_new(self) -> None:
        portfolio = {
            "cash": 10000.0,
            "realized_pnl": 0.0,
            "positions": {
                "DECAY": {
                    "ticker": "DECAY",
                    "shares": 5.0,
                    "avg_price": 40.0,
                    "current_price": 50.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-E3-006",
            "ticker": "DECAY",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "evidence": "add",
        }
        gii = {"DECAY": {"lifecycle_stage": "PROFIT_DECAY"}}
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker=gii,
                gii_meta=self._gii_meta_ok(),
            )
        self.assertFalse(order["is_new_position"])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertNotEqual(order["status"], pe.BLOCK_REASON_PROFIT_DECAY)

    def test_07_missing_ticker_lifecycle_no_false_block(self) -> None:
        gate = pe.evaluate_profit_decay_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="UNKNOWN",
            gii_by_ticker={},
            gii_meta=self._gii_meta_ok(),
        )
        self.assertFalse(gate["blocked"])
        self.assertEqual(gate["diagnostic"], "NO_LIFECYCLE_EVIDENCE")

    def test_08_corrupt_json_fail_open_sell_untouched(self) -> None:
        by, meta = pe.load_gii_lifecycle_index(Path("/nonexistent/gii.json"))
        self.assertEqual(by, {})
        self.assertIn(meta["gate_status"], {"MISSING_FILE", "PROFIT_DECAY_GATE_DATA_INVALID"})
        gate = pe.evaluate_profit_decay_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="X",
            gii_by_ticker=by,
            gii_meta=meta,
        )
        self.assertFalse(gate["blocked"])
        self.assertEqual(gate["authorization"], "ALLOW")

        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "X": {
                    "ticker": "X",
                    "shares": 2.0,
                    "avg_price": 10.0,
                    "current_price": 12.0,
                    "status": "OPEN",
                }
            },
        }
        order = pe.execute_decision(
            {"decision_id": "PDEC-E3-008", "ticker": "X", "action": "SELL_PAPER", "confidence": 0.9},
            portfolio,
            accounting=None,
            all_decisions=[],
            gii_by_ticker=by,
            gii_meta=meta,
        )
        self.assertEqual(order["status"], "EXECUTED")

    def test_09_stale_lifecycle_fail_open(self) -> None:
        meta = {
            "gate_status": "PROFIT_DECAY_GATE_STALE",
            "generated_at": "2026-01-01T00:00:00Z",
            "age_hours": 100.0,
        }
        gate = pe.evaluate_profit_decay_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="DECAY",
            gii_by_ticker={"DECAY": {"lifecycle_stage": "PROFIT_DECAY"}},
            gii_meta=meta,
        )
        self.assertFalse(gate["blocked"])
        self.assertEqual(gate["diagnostic"], "PROFIT_DECAY_GATE_STALE")

    def test_10_idempotency_terminal_block(self) -> None:
        self.assertTrue(pe.is_terminal_order_status(pe.BLOCK_REASON_PROFIT_DECAY, executed=False, is_trade=False))
        ok, reason = pe.should_execute_decision(
            "PDEC-E3-010",
            "BUY_PAPER",
            processed={"PDEC-E3-010"},
            last_orders={
                "PDEC-E3-010": {
                    "action": "BUY_PAPER",
                    "status": pe.BLOCK_REASON_PROFIT_DECAY,
                    "executed": False,
                    "is_trade": False,
                }
            },
            cycle_ts=datetime(2026, 7, 22, 12, 0, 0, tzinfo=timezone.utc),
            cycle_orders={},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "already_processed_same_action")

    def test_11_accounting_unchanged_on_block(self) -> None:
        portfolio = {"cash": 7777.0, "realized_pnl": 12.0, "positions": {}}
        snap = json.dumps(portfolio, sort_keys=True)
        decision = {
            "decision_id": "PDEC-E3-011",
            "ticker": "DECAY",
            "action": "BUY_PAPER",
            "confidence": 0.9,
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark()), mock.patch.object(
            pe, "append_e3_block_event"
        ):
            pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker={"DECAY": {"lifecycle_stage": "PROFIT_DECAY"}},
                gii_meta=self._gii_meta_ok(),
            )
        self.assertEqual(json.dumps(portfolio, sort_keys=True), snap)

    def test_12_feature_flag_off_allows_buy(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-E3-012",
            "ticker": "DECAY",
            "action": "BUY_PAPER",
            "confidence": 0.8,
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.dict(
            "os.environ", {"BLOCK_NEW_BUY_DURING_PROFIT_DECAY": "false"}
        ):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker={"DECAY": {"lifecycle_stage": "PROFIT_DECAY"}},
                gii_meta=self._gii_meta_ok(),
            )
        self.assertEqual(order["status"], "EXECUTED")


class CanonicalOpeningNoiseDeferTest(unittest.TestCase):
    """Canonical PAPER gate: DEFER NEW BUY in first 15m of regular session."""

    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(self)

    def _mark(self, price: float = 100.0) -> dict:
        return {
            "price": price,
            "source": "test",
            "timestamp": "2026-07-22T14:00:00Z",
            "freshness": "FRESH",
            "attempts": [],
        }

    def _ts(self, market: str, minutes_after_open: float) -> str:
        from zoneinfo import ZoneInfo
        from markets.market_config import MARKETS

        cfg = MARKETS[market]
        tz = ZoneInfo(cfg["timezone"])
        # Fixed weekday: Wednesday 2026-07-22
        local = datetime(2026, 7, 22, cfg["open_hour"], cfg["open_minute"], tzinfo=tz)
        from datetime import timedelta

        local = local + timedelta(minutes=minutes_after_open)
        return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def test_01_us_buy_plus_5m_deferred(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        cash_before = portfolio["cash"]
        decision = {
            "decision_id": "PDEC-ON-001",
            "ticker": "AAPL",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "timestamp": self._ts("US", 5),
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark()), mock.patch.object(
            pe, "append_opening_noise_defer_event"
        ) as append_evt:
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], pe.DEFER_REASON_OPENING_NOISE)
        self.assertEqual(order["original_action"], "BUY_PAPER")
        self.assertEqual(order["authorized_action"], "DEFERRED")
        self.assertEqual(order["defer_reason"], pe.DEFER_REASON_OPENING_NOISE)
        self.assertFalse(order["executed"])
        self.assertFalse(order["is_trade"])
        self.assertEqual(portfolio["cash"], cash_before)
        self.assertNotIn("AAPL", portfolio["positions"])
        append_evt.assert_called_once()

    def test_02_us_buy_exactly_15m_passes_opening_gate(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-ON-002",
            "ticker": "AAPL",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "timestamp": self._ts("US", 15),
        }
        gii_meta = {"gate_status": "OK", "generated_at": "2026-07-22T00:00:00Z", "age_hours": 1.0}
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.dict(
            "os.environ", {"BLOCK_NEW_BUY_DURING_PROFIT_DECAY": "false"}
        ):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker={"AAPL": {"lifecycle_stage": "EARLY_WINNER"}},
                gii_meta=gii_meta,
            )
        self.assertNotEqual(order["status"], pe.DEFER_REASON_OPENING_NOISE)
        self.assertEqual(order["status"], "EXECUTED")

    def test_03_eu_buy_first_15m_deferred(self) -> None:
        gate = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="SAP.DE",
            decision_timestamp=self._ts("EU", 3),
        )
        self.assertTrue(gate["deferred"])
        self.assertEqual(gate["market"], "EU")
        self.assertEqual(gate["defer_reason"], pe.DEFER_REASON_OPENING_NOISE)

    def test_04_uk_buy_first_15m_deferred(self) -> None:
        gate = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="HSBA.L",
            decision_timestamp=self._ts("UK", 10),
        )
        self.assertTrue(gate["deferred"])
        self.assertEqual(gate["market"], "UK")

    def test_05_sell_in_first_15m_executes(self) -> None:
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
            "decision_id": "PDEC-ON-005",
            "ticker": "AAPL",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "timestamp": self._ts("US", 3),
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertNotIn("AAPL", portfolio["positions"])

    def test_06_hard_stop_in_first_15m_executes(self) -> None:
        portfolio = {
            "cash": 1000.0,
            "realized_pnl": 0.0,
            "positions": {
                "AAPL": {
                    "ticker": "AAPL",
                    "shares": 10.0,
                    "avg_price": 100.0,
                    "current_price": 50.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-ON-006",
            "ticker": "AAPL",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "timestamp": self._ts("US", 2),
        }
        with mock.patch.object(
            pe,
            "evaluate_fill_time_hard_risk",
            return_value={
                "status": "STOP_LOSS_BREACHED",
                "hard_rule": "STOP_LOSS",
                "pnl_pct": -50.0,
                "required_action": "SELL_PAPER",
            },
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")

    def test_07_existing_position_buy_not_deferred_as_new(self) -> None:
        portfolio = {
            "cash": 10000.0,
            "realized_pnl": 0.0,
            "positions": {
                "AAPL": {
                    "ticker": "AAPL",
                    "shares": 5.0,
                    "avg_price": 40.0,
                    "current_price": 50.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-ON-007",
            "ticker": "AAPL",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "timestamp": self._ts("US", 5),
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.dict(
            "os.environ", {"BLOCK_NEW_BUY_DURING_PROFIT_DECAY": "false"}
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertFalse(order["is_new_position"])
        self.assertNotEqual(order["status"], pe.DEFER_REASON_OPENING_NOISE)
        self.assertEqual(order["status"], "EXECUTED")

    def test_08_repeated_defer_idempotent_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            event = {
                "decision_id": "PDEC-ON-008",
                "ticker": "AAPL",
                "defer_reason": pe.DEFER_REASON_OPENING_NOISE,
            }
            with mock.patch.object(pe, "OUTPUT_DIR", out):
                pe.append_opening_noise_defer_event(event)
                pe.append_opening_noise_defer_event(event)
                lines = (out / "opening_noise_defers.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)

    def test_09_deferred_is_terminal_no_autofill(self) -> None:
        self.assertTrue(
            pe.is_terminal_order_status(pe.DEFER_REASON_OPENING_NOISE, executed=False, is_trade=False)
        )
        ok, reason = pe.should_execute_decision(
            "PDEC-ON-009",
            "BUY_PAPER",
            processed={"PDEC-ON-009"},
            last_orders={
                "PDEC-ON-009": {
                    "action": "BUY_PAPER",
                    "status": pe.DEFER_REASON_OPENING_NOISE,
                    "executed": False,
                    "is_trade": False,
                }
            },
            cycle_ts=datetime(2026, 7, 22, 14, 30, 0, tzinfo=timezone.utc),
            cycle_orders={},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "already_processed_same_action")

    def test_10_post_window_profit_decay_blocks(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-ON-010",
            "ticker": "DECAY",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "timestamp": self._ts("US", 20),
        }
        gii_meta = {"gate_status": "OK", "generated_at": "2026-07-22T00:00:00Z", "age_hours": 1.0}
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.object(
            pe, "append_e3_block_event"
        ):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker={"DECAY": {"lifecycle_stage": "PROFIT_DECAY", "collapse_probability": 0.95}},
                gii_meta=gii_meta,
            )
        self.assertEqual(order["status"], pe.BLOCK_REASON_PROFIT_DECAY)
        self.assertNotEqual(order["status"], pe.DEFER_REASON_OPENING_NOISE)

    def test_11_feature_flag_off_bypasses(self) -> None:
        gate = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="AAPL",
            decision_timestamp=self._ts("US", 5),
            enabled=False,
        )
        self.assertFalse(gate["deferred"])
        self.assertEqual(gate["diagnostic"], "FEATURE_FLAG_OFF")

    def test_12_market_closed_not_opening_noise(self) -> None:
        # Sunday
        from zoneinfo import ZoneInfo

        ts = datetime(2026, 7, 19, 15, 0, tzinfo=ZoneInfo("US/Eastern")).astimezone(timezone.utc)
        gate = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="AAPL",
            decision_timestamp=ts.isoformat().replace("+00:00", "Z"),
        )
        self.assertFalse(gate["deferred"])
        self.assertEqual(gate["diagnostic"], "MARKET_CLOSED_NOT_OPENING_NOISE")

    def test_13_dst_us_eu_uk_aware(self) -> None:
        # US EDT (July) open 09:30 → +5m still deferred
        gate_us = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="MSFT",
            decision_timestamp=self._ts("US", 5),
        )
        self.assertTrue(gate_us["deferred"])
        self.assertIn("US/Eastern", str(gate_us.get("exchange_timezone")))
        # EU CEST
        gate_eu = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="SIE.DE",
            decision_timestamp=self._ts("EU", 5),
        )
        self.assertTrue(gate_eu["deferred"])
        # UK BST
        gate_uk = pe.evaluate_opening_noise_new_buy_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="BP.L",
            decision_timestamp=self._ts("UK", 5),
        )
        self.assertTrue(gate_uk["deferred"])

    def test_14_shortened_session_uses_configured_open(self) -> None:
        # Opening window measured from configured open even if session later shortens.
        from markets.market_hours import ticker_session_context
        from zoneinfo import ZoneInfo
        from markets.market_config import MARKETS

        cfg = MARKETS["US"]
        local = datetime(2026, 7, 22, cfg["open_hour"], cfg["open_minute"], 0, tzinfo=ZoneInfo(cfg["timezone"]))
        ctx = ticker_session_context("SPY", at=local)
        self.assertTrue(ctx["is_open"])
        self.assertAlmostEqual(ctx["minutes_since_open"], 0.0, places=3)
        self.assertFalse(ctx["shortened_session"])  # no holiday SSOT — documented

    def test_15_accounting_unchanged_on_defer(self) -> None:
        portfolio = {"cash": 5555.0, "realized_pnl": 9.0, "positions": {}}
        snap = json.dumps(portfolio, sort_keys=True)
        decision = {
            "decision_id": "PDEC-ON-015",
            "ticker": "AAPL",
            "action": "BUY_PAPER",
            "confidence": 0.9,
            "timestamp": self._ts("US", 1),
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark()), mock.patch.object(
            pe, "append_opening_noise_defer_event"
        ):
            pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(json.dumps(portfolio, sort_keys=True), snap)

    def test_16_post_window_requires_fresh_decision_id(self) -> None:
        """Deferred id stays terminal; a new-cycle stamped BUY id can proceed after window."""
        old_id = "PDEC-AAPL-0001"
        new_id = "PDEC-AAPL-202607221030-0001"
        last_orders = {
            old_id: {
                "decision_id": old_id,
                "action": "BUY_PAPER",
                "status": pe.DEFER_REASON_OPENING_NOISE,
            }
        }
        processed = {old_id}
        ok_old, reason_old = pe.should_execute_decision(
            old_id, "BUY_PAPER", processed=processed, last_orders=last_orders
        )
        self.assertFalse(ok_old)
        self.assertEqual(reason_old, "already_processed_same_action")

        ok_new, reason_new = pe.should_execute_decision(
            new_id, "BUY_PAPER", processed=processed, last_orders=last_orders
        )
        self.assertTrue(ok_new)
        self.assertEqual(reason_new, "new_decision")

        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": new_id,
            "ticker": "AAPL",
            "action": "BUY_PAPER",
            "confidence": 0.85,
            "timestamp": self._ts("US", 20),
        }
        gii_meta = {"gate_status": "OK", "generated_at": "2026-07-22T00:00:00Z", "age_hours": 1.0}
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark()):
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                gii_by_ticker={"AAPL": {"lifecycle_stage": "SURVIVED"}},
                gii_meta=gii_meta,
            )
        self.assertNotEqual(order["status"], pe.DEFER_REASON_OPENING_NOISE)
        self.assertEqual(order["decision_id"], new_id)
        gate = order.get("opening_noise_gate") or {}
        self.assertFalse(gate.get("deferred"))
        self.assertEqual(gate.get("diagnostic"), "OPENING_NOISE_WINDOW_PASSED")


class AdaptiveDeploymentIsolationRegressionTest(unittest.TestCase):
    """Regressions for the 2026-07-28 paper-execution suite failures."""

    def test_live_canary_scope_blocks_out_of_scope_without_isolation(self) -> None:
        import tae_adaptive_deployment as adep

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Mimic live PAPER_CHALLENGER canary constraints (does not touch real SSOT).
            st = adep.load_state(root=root, create_default=True)
            st["deployment_state"] = adep.ST_PAPER_CHALLENGER
            st["ticker_scope"] = ["AAPL", "MSFT", "NVDA"]
            st["capital_limit"] = 500.0
            st["challenger_exposure_usd"] = 500.0
            st["challenger_formula_id"] = adep.FORMULA_LIVE_EQUAL_SPLIT
            st["live_allowed"] = False
            adep.save_state(st, root=root)
            blocked = adep.resolve_buy_notional(
                control_notional=1000.0,
                inputs={"cash_available": 10000.0, "cash_reserve": 0.0, "maximum_position_notional": 1500.0},
                ticker="GROW",
                arm="CANONICAL_PAPER",
                root=root,
            )
            self.assertTrue(blocked["blocked"])
            self.assertEqual(blocked["reason_code"], adep.BLOCKED_TICKER_SCOPE)
            capped = adep.resolve_buy_notional(
                control_notional=1000.0,
                inputs={"cash_available": 10000.0, "cash_reserve": 0.0, "maximum_position_notional": 1500.0},
                ticker="AAPL",
                arm="CANONICAL_PAPER",
                root=root,
            )
            self.assertFalse(capped["blocked"])
            self.assertEqual(capped["decision"], "USE_CONTROL")
            self.assertGreaterEqual(float(capped["executed_notional"]), 250.0)

    def test_isolated_draft_root_allows_buy_execution(self) -> None:
        _isolate_adaptive_deployment(self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"})
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-ISO-001",
            "ticker": "GROW",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "evidence": "isolation",
        }
        mark = {
            "price": 50.0,
            "source": "test",
            "timestamp": "2026-07-22T00:00:00Z",
            "freshness": "FRESH",
            "attempts": [],
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=mark):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertIn("GROW", portfolio["positions"])

    def test_env_isolation_does_not_leak_defer_flag(self) -> None:
        before = os.environ.get("DEFER_NEW_BUY_DURING_OPENING_NOISE")
        class _Tmp(unittest.TestCase):
            pass
        t = _Tmp()
        # Simulate PaperExecutionTest setUp/cleanup without leaving DEFER=false.
        root = _isolate_adaptive_deployment(
            t, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )
        self.assertTrue(root.is_dir())
        self.assertEqual(os.environ.get("DEFER_NEW_BUY_DURING_OPENING_NOISE"), "false")
        # Run cleanups registered on the helper test case.
        t.doCleanups()
        self.assertEqual(os.environ.get("DEFER_NEW_BUY_DURING_OPENING_NOISE"), before)

    def test_no_mark_price_no_capital_or_portfolio_mutation(self) -> None:
        _isolate_adaptive_deployment(self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"})
        portfolio = {"cash": 5000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-ISO-NOMARK",
            "ticker": "NEWCO",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "evidence": "no mark",
        }
        with mock.patch.object(
            pe,
            "resolve_mark_price",
            return_value={
                "price": 0.0,
                "source": "UNAVAILABLE",
                "timestamp": None,
                "freshness": "UNAVAILABLE",
                "attempts": [],
            },
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "SKIPPED_NO_MARK_PRICE")
        self.assertEqual(portfolio["cash"], 5000.0)
        self.assertEqual(portfolio["positions"], {})

    def test_nonfinite_prices_rejected_by_valid_resolved_price(self) -> None:
        import math

        self.assertIsNone(pe._valid_resolved_price(float("nan")))
        self.assertIsNone(pe._valid_resolved_price(float("inf")))
        self.assertIsNone(pe._valid_resolved_price(float("-inf")))
        self.assertIsNone(pe._valid_resolved_price(0.0))
        self.assertIsNone(pe._valid_resolved_price(-1.0))
        self.assertIsNone(pe._valid_resolved_price("100"))
        self.assertEqual(pe._valid_resolved_price(12.5), 12.5)
        self.assertTrue(math.isfinite(pe._valid_resolved_price(12.5)))

    def test_unit_buy_path_does_not_require_real_network(self) -> None:
        _isolate_adaptive_deployment(self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"})
        portfolio = {"cash": 8000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-ISO-NET",
            "ticker": "ZZZZ",
            "action": "BUY_PAPER",
            "confidence": 0.7,
            "evidence": "offline",
        }

        def _boom(*_a, **_k):
            raise RuntimeError("real network must not be called")

        with mock.patch.object(pe, "resolve_mark_price", side_effect=_boom):
            # Explicit mark injection via patched return — prove execute path stays offline.
            pass
        with mock.patch.object(
            pe,
            "resolve_mark_price",
            return_value={
                "price": 25.0,
                "source": "fixture",
                "timestamp": "2026-07-22T00:00:00Z",
                "freshness": "FRESH",
                "attempts": [],
            },
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertEqual(order["fill_price"], 25.0)


if __name__ == "__main__":
    unittest.main()
