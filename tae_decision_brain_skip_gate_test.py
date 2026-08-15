#!/usr/bin/env python3
"""Tests for binding Decision Brain SKIP PAPER entry gate."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from unittest import mock

import tae_paper_execution as pe
import tae_strategy_v2_buy_policy as pol
from tae_test_isolation import isolate_adaptive_deployment as _isolate_adaptive_deployment


class DecisionBrainSkipGateUnitTest(unittest.TestCase):
    def test_flag_default_on(self) -> None:
        with mock.patch.dict("os.environ", {"DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED": "true"}):
            self.assertTrue(pe.decision_brain_skip_paper_gate_enabled())
        # Absent key → default true
        import os

        prev = os.environ.pop("DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED", None)
        try:
            self.assertTrue(pe.decision_brain_skip_paper_gate_enabled())
        finally:
            if prev is not None:
                os.environ["DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED"] = prev

    def test_flag_off(self) -> None:
        with mock.patch.dict("os.environ", {"DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED": "false"}):
            self.assertFalse(pe.decision_brain_skip_paper_gate_enabled())

    def test_normalize_skip_synonyms(self) -> None:
        self.assertEqual(pe.normalize_decision_brain_action("SKIP"), "SKIP_PAPER")
        self.assertEqual(pe.normalize_decision_brain_action("SKIP_PAPER"), "SKIP_PAPER")
        self.assertTrue(pe.is_decision_brain_skip("SKIP"))

    def test_resolve_explicit_verdict(self) -> None:
        resolved = pe.resolve_decision_brain_verdict(
            ticker="AAPL",
            decision={"decision_id": "X", "decision_brain_verdict": "SKIP_PAPER"},
        )
        self.assertEqual(resolved["verdict"], "SKIP_PAPER")
        self.assertEqual(resolved["source"], "decision.decision_brain_verdict")

    def test_resolve_action_changed(self) -> None:
        resolved = pe.resolve_decision_brain_verdict(
            ticker="NVDA",
            decision={"decision_id": "Y", "action": "BUY_PAPER"},
            execution_reason="action_changed:SKIP_PAPER->BUY_PAPER",
        )
        self.assertEqual(resolved["verdict"], "SKIP_PAPER")
        self.assertEqual(resolved["source"], "execution_reason.action_changed")

    def test_add_entry_kind_not_in_scope(self) -> None:
        gate = pe.evaluate_decision_brain_skip_new_entry_gate(
            action="BUY_PAPER",
            is_new_position=False,
            ticker="AAPL",
            explicit_verdict="SKIP_PAPER",
            entry_kind="ADD",
            strategy_id="V2",
        )
        self.assertFalse(gate["blocked"])
        self.assertEqual(gate["diagnostic"], "V2_ADD_NOT_IN_SCOPE")

    def test_live_money_not_in_scope(self) -> None:
        gate = pe.evaluate_decision_brain_skip_new_entry_gate(
            action="BUY_PAPER",
            is_new_position=True,
            ticker="AAPL",
            explicit_verdict="SKIP_PAPER",
            live_money=True,
        )
        self.assertFalse(gate["blocked"])
        self.assertEqual(gate["diagnostic"], "LIVE_OR_BROKER_NOT_IN_SCOPE")


class V1BindingSkipGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(
            self,
            extra_env={
                "DEFER_NEW_BUY_DURING_OPENING_NOISE": "false",
                "BLOCK_NEW_BUY_DURING_PROFIT_DECAY": "false",
                "DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED": "true",
            },
        )

    def _mark(self, price: float = 100.0) -> dict:
        return {
            "price": price,
            "source": "test",
            "timestamp": "2026-08-03T12:00:00Z",
            "freshness": "FRESH",
            "attempts": [],
        }

    def test_01_v1_buy_skip_blocked(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}, "strategy_id": "V1"}
        cash_before = portfolio["cash"]
        decision = {
            "decision_id": "PDEC-DBSKIP-001",
            "ticker": "AMAT",
            "action": "BUY_PAPER",
            "confidence": 0.9,
            "score": 100,
            "strategy_id": "V1",
            "decision_brain_verdict": "SKIP_PAPER",
            "short_term_trend_7d": "NEGATIVE",
            "evidence": "strong buy despite skip",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ) as append_evt:
            order = pe.execute_decision(
                decision,
                portfolio,
                accounting=None,
                all_decisions=[decision],
                execution_reason="action_changed:SKIP_PAPER->BUY_PAPER",
            )
        self.assertEqual(order["status"], pe.BLOCK_REASON_DECISION_BRAIN_SKIP)
        self.assertEqual(order["block_reason"], pe.BLOCK_REASON_DECISION_BRAIN_SKIP)
        self.assertEqual(order["authorized_action"], "SKIP_PAPER")
        self.assertEqual(order["economic_class"], pe.ECONOMIC_CLASS_DECISION_BRAIN_SKIP)
        self.assertEqual(order["strategy_id"], "V1")
        self.assertFalse(order["executed"])
        self.assertFalse(order["is_trade"])
        self.assertEqual(order["fill_shares"], 0.0)
        self.assertEqual(portfolio["cash"], cash_before)
        self.assertNotIn("AMAT", portfolio.get("positions") or {})
        append_evt.assert_called_once()
        payload = append_evt.call_args[0][0]
        self.assertEqual(payload["gate_name"], "DECISION_BRAIN_SKIP_PAPER_GATE")
        self.assertEqual(payload["final_action"], "BLOCKED_DECISION_BRAIN_SKIP")
        self.assertEqual(payload["strategy_id"], "V1")

    def test_02_v1_buy_without_skip_allowed(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}, "strategy_id": "V1"}
        decision = {
            "decision_id": "PDEC-DBSKIP-002",
            "ticker": "GROW",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "decision_brain_verdict": "BUY_PAPER",
            "evidence": "buy ok",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ) as append_evt, mock.patch.object(
            pe, "_latest_paper_decision_for_ticker", return_value=None
        ), mock.patch.object(
            pe, "_latest_longitudinal_action_for_ticker", return_value=(None, None)
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["executed"])
        self.assertIn("GROW", portfolio["positions"])
        self.assertLess(portfolio["cash"], 10000.0)
        append_evt.assert_not_called()

    def test_03_v1_hold_verdict_allows_buy(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-DBSKIP-003",
            "ticker": "HOLDY",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "decision_brain_verdict": "HOLD_PAPER",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(40.0)), mock.patch.object(
            pe, "_latest_paper_decision_for_ticker", return_value=None
        ), mock.patch.object(
            pe, "_latest_longitudinal_action_for_ticker", return_value=(None, None)
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")

    def test_04_sell_unchanged(self) -> None:
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
            "decision_id": "PDEC-DBSKIP-SELL",
            "ticker": "AAPL",
            "action": "SELL_PAPER",
            "confidence": 0.9,
            "decision_brain_verdict": "SKIP_PAPER",
            "evidence": "sell still allowed",
        }
        order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")
        self.assertTrue(order["is_trade"])

    def test_05_existing_position_add_on_not_blocked_by_this_gate(self) -> None:
        """Scale-in on existing V1 position is outside NEW-entry scope of this gate."""
        portfolio = {
            "cash": 10000.0,
            "realized_pnl": 0.0,
            "positions": {
                "AAPL": {
                    "ticker": "AAPL",
                    "shares": 5.0,
                    "avg_price": 100.0,
                    "current_price": 100.0,
                    "status": "OPEN",
                }
            },
        }
        decision = {
            "decision_id": "PDEC-DBSKIP-ADDON",
            "ticker": "AAPL",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "decision_brain_verdict": "SKIP_PAPER",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(100.0)), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ) as append_evt:
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        # Gate diagnostic path: existing position → not blocked by Decision Brain SKIP gate.
        self.assertNotEqual(order["status"], pe.BLOCK_REASON_DECISION_BRAIN_SKIP)
        append_evt.assert_not_called()

    def test_06_cash_unchanged_and_idempotent_terminal(self) -> None:
        portfolio = {"cash": 7777.0, "realized_pnl": 0.0, "positions": {}}
        snap = json.dumps(portfolio, sort_keys=True)
        decision = {
            "decision_id": "PDEC-DBSKIP-IDEMP",
            "ticker": "MSFT",
            "action": "BUY_PAPER",
            "confidence": 0.9,
            "decision_brain_verdict": "SKIP_PAPER",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark()), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], pe.BLOCK_REASON_DECISION_BRAIN_SKIP)
        self.assertEqual(json.dumps(portfolio, sort_keys=True), snap)
        self.assertTrue(
            pe.is_terminal_order_status(pe.BLOCK_REASON_DECISION_BRAIN_SKIP, executed=False, is_trade=False)
        )
        ok, reason = pe.should_execute_decision(
            "PDEC-DBSKIP-IDEMP",
            "BUY_PAPER",
            processed={"PDEC-DBSKIP-IDEMP"},
            last_orders={
                "PDEC-DBSKIP-IDEMP": {
                    "action": "BUY_PAPER",
                    "status": pe.BLOCK_REASON_DECISION_BRAIN_SKIP,
                    "executed": False,
                    "is_trade": False,
                }
            },
            cycle_ts=None,
            cycle_orders={},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "already_processed_same_action")

    def test_07_feature_flag_off_allows_buy(self) -> None:
        portfolio = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}}
        decision = {
            "decision_id": "PDEC-DBSKIP-OFF",
            "ticker": "AMAT",
            "action": "BUY_PAPER",
            "confidence": 0.8,
            "decision_brain_verdict": "SKIP_PAPER",
        }
        with mock.patch.dict("os.environ", {"DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED": "false"}), mock.patch.object(
            pe, "resolve_mark_price", return_value=self._mark(50.0)
        ), mock.patch.object(
            pe, "_latest_paper_decision_for_ticker", return_value=None
        ), mock.patch.object(
            pe, "_latest_longitudinal_action_for_ticker", return_value=(None, None)
        ):
            order = pe.execute_decision(decision, portfolio, accounting=None, all_decisions=[decision])
        self.assertEqual(order["status"], "EXECUTED")

    def test_08_v1_v2_isolation_same_ticker(self) -> None:
        """V1 block does not mutate a separate V2 portfolio object."""
        v1 = {"cash": 10000.0, "realized_pnl": 0.0, "positions": {}, "strategy_id": "V1"}
        v2 = {"cash": 30000.0, "realized_pnl": 0.0, "positions": {"AMAT": {"shares": 1.0}}, "strategy_id": "V2"}
        v2_snap = json.dumps(v2, sort_keys=True)
        decision = {
            "decision_id": "PDEC-DBSKIP-ISO",
            "ticker": "AMAT",
            "action": "BUY_PAPER",
            "confidence": 0.9,
            "strategy_id": "V1",
            "decision_brain_verdict": "SKIP_PAPER",
        }
        with mock.patch.object(pe, "resolve_mark_price", return_value=self._mark(50.0)), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ):
            pe.execute_decision(decision, v1, accounting=None, all_decisions=[decision])
        self.assertEqual(json.dumps(v2, sort_keys=True), v2_snap)
        self.assertEqual(v1["cash"], 10000.0)


class V2BindingSkipGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._adaptive_root = _isolate_adaptive_deployment(
            self,
            extra_env={"DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED": "true"},
        )
        from tae_strategy_v2_config import load_strategy_v2_config

        self.cfg = dict(load_strategy_v2_config())
        self.cfg["tranche_fraction"] = 0.20
        self.cfg["max_tranches"] = 5
        self.cfg["add_tranche_drop_pct"] = 0.03
        self.cfg["MIN_CASH_RESERVE_USD"] = 100.0
        self.cfg["thesis_unknown_blocks_entry"] = True


    def _open_inp(self, *, pde_action: str, score: float = 100.0) -> pol.BuyPolicyInput:
        return pol.BuyPolicyInput(
            ticker="MSFT",
            timestamp="2026-08-03T12:00:00Z",
            mark_price=400.0,
            mark_freshness="FRESH",
            mark_age_seconds=1.0,
            score=score,
            confidence=0.9,
            pde_action=pde_action,
            hard_risk_active=False,
            hard_risk_status="OK",
            session_valid=True,
            data_fresh=True,
            candidate_eligible=True,
            held=False,
            cash=30000.0,
            decision_id="V2-OPEN-DBSKIP-001",
        )

    def test_01_v2_open_skip_blocked(self) -> None:
        with mock.patch.object(pol, "is_strategy_v2_enabled", return_value=True), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ) as append_evt:
            out = pol.evaluate_buy_policy(self._open_inp(pde_action="SKIP_PAPER"), cfg=self.cfg, enabled=True)
        self.assertEqual(out["action"], "SKIP")
        self.assertEqual(out["reason_code"], pol.REASON_BLOCK_DECISION_BRAIN_SKIP)
        self.assertFalse(out.get("capital_mutating"))
        self.assertEqual(out.get("block_reason"), pe.BLOCK_REASON_DECISION_BRAIN_SKIP)
        append_evt.assert_called_once()
        self.assertEqual(append_evt.call_args[0][0]["strategy_id"], "V2")

    def test_02_v2_open_buy_unchanged(self) -> None:
        with mock.patch.object(pol, "is_strategy_v2_enabled", return_value=True), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ) as append_evt:
            out = pol.evaluate_buy_policy(self._open_inp(pde_action="BUY_PAPER"), cfg=self.cfg, enabled=True)
        self.assertEqual(out["action"], "OPEN_CYCLE")
        self.assertEqual(out["reason_code"], pol.REASON_OPEN)
        append_evt.assert_not_called()

    def test_03_v2_add_with_skip_not_affected(self) -> None:
        cycle = {
            "cycle_id": "CYC-1",
            "ticker": "MSFT",
            "status": "OPEN",
            "thesis_state": "VALID",
            "company_budget": 5000.0,
            "budget_used": 1000.0,
            "budget_remaining": 4000.0,
            "tranche_count": 1,
            "max_tranches": 5,
            "last_tranche_price": 420.0,
            "currency": "USD",
        }
        inp = pol.BuyPolicyInput(
            ticker="MSFT",
            timestamp="2026-08-03T12:00:00Z",
            mark_price=400.0,  # ~4.76% below last → drop reached at 3%
            mark_freshness="FRESH",
            mark_age_seconds=1.0,
            score=100.0,
            pde_action="SKIP_PAPER",
            hard_risk_active=False,
            hard_risk_status="OK",
            session_valid=True,
            data_fresh=True,
            candidate_eligible=True,
            held=True,
            quantity=2.0,
            average_cost=420.0,
            cash=30000.0,
            cycle=cycle,
            decision_id="V2-ADD-DBSKIP-001",
            hard_risk_class="SAFE",
            allow_position_growth=True,
            decline_class="CONTROLLED_PULLBACK",
            context_verdict="ALLOW",
            relative_strength_state="OK",
            market_regime="RISK_ON",
        )
        with mock.patch.object(pol, "is_strategy_v2_enabled", return_value=True), mock.patch.object(
            pe, "append_decision_brain_skip_block_event"
        ) as append_evt:
            out = pol.evaluate_buy_policy(inp, cfg=self.cfg, enabled=True)
        self.assertNotEqual(out.get("reason_code"), pol.REASON_BLOCK_DECISION_BRAIN_SKIP)
        append_evt.assert_not_called()
        # ADD may HOLD on profit-context or fire ADD — either is fine as long as SKIP gate did not fire.
        self.assertIn(out["action"], {"ADD_TRANCHE", "HOLD", "STOP_ACCUMULATION", "SKIP"})


class SemanticsUnchangedSmokeTest(unittest.TestCase):
    """Hard Risk / trailing / SELL semantics must remain untouched by this sprint."""

    def test_hard_risk_constant_unchanged(self) -> None:
        self.assertIn("BLOCKED_HARD_RISK_AT_FILL", pe.NON_TERMINAL_ORDER_STATUSES)
        self.assertIn("STOP_LOSS_BREACHED", pe.HARD_RISK_BREACH_STATUSES)

    def test_block_reason_deterministic(self) -> None:
        self.assertEqual(pe.BLOCK_REASON_DECISION_BRAIN_SKIP, "BLOCKED_DECISION_BRAIN_SKIP")
        self.assertEqual(pe.ECONOMIC_CLASS_DECISION_BRAIN_SKIP, "ENTRY_BLOCKED_BY_DECISION_BRAIN_SKIP")


if __name__ == "__main__":
    unittest.main()
