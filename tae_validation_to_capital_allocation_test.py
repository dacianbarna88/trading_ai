#!/usr/bin/env python3
"""Tests for Validation → Capital Allocation closure (existing PDE/weights only)."""

from __future__ import annotations

import unittest
from unittest import mock

from tae_adaptive_paper_weights import (
    aggregate_experiments_by_action,
    clamp_delta,
    clamp_weight,
    compute_action_weight,
)
from tae_paper_decision_engine import (
    apply_experiment_capital_evidence,
    classify_experiment_capital_eligibility,
    map_paper_experiment_action,
    update_capital_challenger_registry,
)


def _base_ctx(*, held: bool = True, shares: float = 10.0, price: float = 100.0) -> dict:
    ticker_pos = {
        "AAPL": {
            "shares": shares if held else 0.0,
            "avg_price": price,
            "current_price": price,
            "current_value": shares * price if held else 0.0,
            "status": "OPEN" if held else "FLAT",
        }
    }
    return {
        "paper_positions": ticker_pos if held else {},
        "paper_portfolio": {"cash": 5000.0},
        "accounting": {"cash_available": 5000.0},
        "signals": {"AAPL": {"signal": "STRONG BUY", "score": 92.0}},
        "rule_lifecycle": {"rules": {}},
        "preferred_philosophy": "COLLABORATIVE",
        "exp_by_ticker": {},
        "hard_risk_by": {},
        "gii_by": {},
        "recent_hard_stops_by_ticker": {},
    }


class CapitalAllocationClosureTest(unittest.TestCase):
    def test_promising_alone_does_not_authorize_capital(self) -> None:
        exp = {
            "hypothesis_id": "LTB-X",
            "verdict": "PROMISING",
            "paper_experiment_action": "PAPER_REALLOCATION",
            "hypothesis_type": "OPPORTUNITY_COST",
            "deltas": {"expected_profit_delta_usd": 50.0, "risk_delta": -0.05, "capital_efficiency_delta": 1.0},
            "confidence": 0.9,
            "scoring_method": "read_only_ssot_simulation",
            "affected_tickers": ["MU"],
        }
        ctx = _base_ctx(held=False)
        with mock.patch(
            "tae_paper_decision_engine.evaluate_pre_entry_hard_risk_compatibility",
            return_value={"compatible": False, "hard_block": True, "risk_level": "CRITICAL", "reasons": ["blocked"]},
        ):
            row = classify_experiment_capital_eligibility(exp, ticker="MU", ctx=ctx)
        self.assertFalse(row["allocation_authorized"])
        self.assertNotEqual(row["capital_candidate_status"], "ACTIONABLE_CAPITAL_CANDIDATE")

    def test_eligible_maps_to_existing_action(self) -> None:
        self.assertEqual(map_paper_experiment_action("PAPER_TRAILING_PROTECT_TRIM"), "REDUCE_PAPER")
        self.assertEqual(map_paper_experiment_action("PAPER_REALLOCATION"), "ROTATE_PAPER")
        self.assertIsNone(map_paper_experiment_action("PAPER_DPE_PHILOSOPHY_WEIGHT"))

    def test_ineligible_remains_report_only(self) -> None:
        exp = {
            "hypothesis_id": "LTB-DPE-PHIL-001",
            "verdict": "PROMISING",
            "paper_experiment_action": "PAPER_DPE_PHILOSOPHY_WEIGHT",
            "hypothesis_type": "DPE_PHILOSOPHY",
            "deltas": {"expected_profit_delta_usd": 100.0, "risk_delta": -0.05, "capital_efficiency_delta": 0.5},
            "confidence": 0.9,
            "scoring_method": "read_only_ssot_simulation",
            "affected_tickers": [],
        }
        row = classify_experiment_capital_eligibility(exp, ticker="_PORTFOLIO", ctx=_base_ctx())
        self.assertEqual(row["capital_candidate_status"], "PORTFOLIO_POLICY_CANDIDATE")
        self.assertFalse(row["allocation_authorized"])

    def test_hard_risk_blocks_amat_mu(self) -> None:
        exp = {
            "hypothesis_id": "LTB-OPP-AMAT-03",
            "verdict": "PROMISING",
            "paper_experiment_action": "PAPER_REALLOCATION",
            "hypothesis_type": "OPPORTUNITY_COST",
            "deltas": {"expected_profit_delta_usd": 35.0, "risk_delta": -0.06, "capital_efficiency_delta": 2.0},
            "confidence": 0.88,
            "scoring_method": "read_only_ssot_simulation",
            "affected_tickers": ["AMAT"],
        }
        ctx = _base_ctx(held=False)
        with mock.patch(
            "tae_paper_decision_engine.evaluate_pre_entry_hard_risk_compatibility",
            return_value={
                "compatible": False,
                "hard_block": True,
                "risk_level": "CRITICAL",
                "reasons": ["persistent_critical_risk_after_hard_stop"],
            },
        ):
            row = classify_experiment_capital_eligibility(exp, ticker="AMAT", ctx=ctx)
        self.assertEqual(row["capital_candidate_status"], "NOT_EXECUTABLE")
        self.assertIn("hard_risk", (row.get("allocation_block_reason") or "").lower())

    def test_held_protection_creates_bounded_trim(self) -> None:
        exp = {
            "hypothesis_id": "LTB-PROT-AAPL",
            "verdict": "PROMISING",
            "paper_experiment_action": "PAPER_TRAILING_PROTECT_TRIM",
            "hypothesis_type": "PROFIT_PROTECTION",
            "deltas": {"expected_profit_delta_usd": 8.0, "risk_delta": -0.05, "capital_efficiency_delta": -0.5},
            "confidence": 0.7,
            "scoring_method": "read_only_ssot_simulation",
            "affected_tickers": ["AAPL"],
        }
        ctx = _base_ctx(held=True, shares=8.0, price=100.0)
        with mock.patch(
            "tae_paper_decision_engine.evaluate_pre_entry_hard_risk_compatibility",
            return_value={"compatible": True, "hard_block": False, "risk_level": "LOW", "reasons": []},
        ):
            row = classify_experiment_capital_eligibility(exp, ticker="AAPL", ctx=ctx)
        self.assertEqual(row["capital_candidate_status"], "ACTIONABLE_CAPITAL_CANDIDATE")
        self.assertEqual(row["experiment_action_mapping"], "REDUCE_PAPER")
        self.assertTrue(row["allocation_authorized"])
        self.assertGreater(row["proposed_allocation_usd"], 0.0)
        self.assertLessEqual(row["proposed_allocation_usd"], 400.0)

    def test_action_specific_experiment_changes_score_materially(self) -> None:
        scores = {
            a: 10.0
            for a in (
                "HOLD_PAPER",
                "REDUCE_PAPER",
                "PROTECT_PAPER",
                "BUY_PAPER",
                "SKIP_PAPER",
                "SELL_PAPER",
                "ROTATE_PAPER",
            )
        }
        exp = {
            "hypothesis_id": "LTB-PROT-AAPL",
            "verdict": "PROMISING",
            "paper_experiment_action": "PAPER_TRAILING_PROTECT_TRIM",
            "hypothesis_type": "PROFIT_PROTECTION",
            "deltas": {"expected_profit_delta_usd": 8.0, "risk_delta": -0.05, "capital_efficiency_delta": -0.5},
            "confidence": 0.7,
            "scoring_method": "read_only_ssot_simulation",
            "affected_tickers": ["AAPL"],
        }
        ctx = _base_ctx(held=True)
        ctx["exp_by_ticker"] = {"AAPL": [exp], "_PORTFOLIO": []}
        evidence: list[str] = []
        with mock.patch(
            "tae_paper_decision_engine.evaluate_pre_entry_hard_risk_compatibility",
            return_value={"compatible": True, "hard_block": False, "risk_level": "LOW", "reasons": []},
        ):
            detail = apply_experiment_capital_evidence("AAPL", scores, evidence, ctx)
        self.assertTrue(detail["allocation_authorized"])
        self.assertIn("REDUCE_PAPER", detail["experiment_score_delta"])
        self.assertGreaterEqual(detail["experiment_score_delta"]["REDUCE_PAPER"], 30.0)
        self.assertLess(scores["HOLD_PAPER"], scores["REDUCE_PAPER"])

    def test_adaptive_weights_consume_eligible_experiments(self) -> None:
        doc = {
            "experiments": [
                {
                    "hypothesis_id": "LTB-PROT-AAPL",
                    "verdict": "PROMISING",
                    "paper_experiment_action": "PAPER_TRAILING_PROTECT_TRIM",
                    "affected_tickers": ["AAPL"],
                    "deltas": {"expected_profit_delta_usd": 8.0},
                },
                {
                    "hypothesis_id": "LTB-DPE-PHIL-001",
                    "verdict": "PROMISING",
                    "paper_experiment_action": "PAPER_DPE_PHILOSOPHY_WEIGHT",
                    "affected_tickers": [],
                    "deltas": {"expected_profit_delta_usd": 100.0},
                },
            ]
        }
        by = aggregate_experiments_by_action(doc)
        self.assertGreaterEqual(by["REDUCE_PAPER"].get("PROMISING", 0), 1)
        self.assertEqual(sum(by["BUY_PAPER"].values()), 0)

    def test_failed_challenger_weakens_influence(self) -> None:
        row = compute_action_weight(
            "REDUCE_PAPER",
            verdict_counts={},
            previous_weight=1.0,
            hints=None,
            knowledge_doc=None,
            attribution_doc={
                "rules": {
                    "LTB-PROT-AAPL": {
                        "associated_action": "REDUCE_PAPER",
                        "recommended_influence_delta": -0.02,
                        "weight_delta": -0.02,
                    }
                }
            },
            global_risk_adj=0.0,
            evidence_sources=[],
            experiment_counts={"REJECT": 1},
            experiment_rows=[{"experiment_id": "LTB-PROT-AAPL", "action": "REDUCE_PAPER", "verdict": "REJECT"}],
        )
        self.assertLess(row["new_weight"], 1.0)

    def test_successful_challenger_can_be_promoted_hint(self) -> None:
        decisions = [
            {
                "ticker": "AAPL",
                "action": "REDUCE_PAPER",
                "experiment_id": "LTB-PROT-AAPL",
                "experiment_verdict": "PROMISING",
                "capital_candidate_status": "ACTIONABLE_CAPITAL_CANDIDATE",
                "experiment_action_mapping": "REDUCE_PAPER",
                "proposed_allocation_usd": 80.0,
                "expected_profit_delta": 8.0,
                "expected_risk_delta": -0.05,
                "allocation_authorized": True,
                "evidence_quality": "SIMULATED",
            }
        ]
        orders = [
            {
                "ticker": "AAPL",
                "executed": True,
                "is_trade": True,
                "fill_shares": 0.8,
                "capital_impact": 80.0,
                "gross_value": 80.0,
                "realized_pnl": 2.5,
            }
        ]
        doc = update_capital_challenger_registry(decisions=decisions, orders=orders)
        chall = next(r for r in doc["challengers"] if r.get("experiment_id") == "LTB-PROT-AAPL")
        self.assertEqual(chall["lifecycle"], "OBSERVED")
        self.assertEqual(chall["promotion_hint"], "PROMOTED_CANDIDATE")
    def test_no_duplicate_authorized_boost_path(self) -> None:
        scores = {
            a: 0.0
            for a in (
                "HOLD_PAPER",
                "REDUCE_PAPER",
                "PROTECT_PAPER",
                "BUY_PAPER",
                "SKIP_PAPER",
                "SELL_PAPER",
                "ROTATE_PAPER",
            )
        }
        exp = {
            "hypothesis_id": "LTB-PROT-AAPL",
            "verdict": "PROMISING",
            "paper_experiment_action": "PAPER_TRAILING_PROTECT_TRIM",
            "hypothesis_type": "PROFIT_PROTECTION",
            "deltas": {"expected_profit_delta_usd": 8.0, "risk_delta": -0.05, "capital_efficiency_delta": -0.5},
            "confidence": 0.7,
            "scoring_method": "read_only_ssot_simulation",
            "affected_tickers": ["AAPL"],
        }
        ctx = _base_ctx(held=True)
        ctx["exp_by_ticker"] = {"AAPL": [exp, exp], "_PORTFOLIO": []}
        with mock.patch(
            "tae_paper_decision_engine.evaluate_pre_entry_hard_risk_compatibility",
            return_value={"compatible": True, "hard_block": False, "risk_level": "LOW", "reasons": []},
        ):
            detail = apply_experiment_capital_evidence("AAPL", scores, [], ctx)
        self.assertGreaterEqual(len(detail["authorized_challengers"]), 1)
        self.assertEqual(detail["authorized_challengers"][0]["experiment_id"], "LTB-PROT-AAPL")

    def test_weight_clamps_prevent_runaway(self) -> None:
        self.assertEqual(clamp_weight(2.0), 1.15)
        self.assertEqual(clamp_delta(0.5), 0.02)


if __name__ == "__main__":
    unittest.main()
