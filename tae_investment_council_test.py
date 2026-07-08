#!/usr/bin/env python3
"""Tests for tae_investment_council.py — synthesis only."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_investment_council import (
    _build_action_plan,
    _executive_recommendation,
    _hard_risk_alerts,
    _merge_buy_candidates,
    build_council_synthesis,
)


class InvestmentCouncilTest(unittest.TestCase):
    def test_merge_buy_candidates(self) -> None:
        pde = [{"ticker": "AAPL", "action": "BUY_PAPER", "confidence": 0.8}]
        gii = [{"ticker": "AAPL"}, {"ticker": "LLY", "growth_score": 90}]
        merged = _merge_buy_candidates(pde, gii)
        self.assertEqual(len(merged), 2)
        self.assertTrue(merged[0]["pde_buy"])
        self.assertTrue(merged[0]["gii_top_growth"])

    def test_hard_risk_alerts_from_decisions(self) -> None:
        decisions = [
            {
                "ticker": "QQQ",
                "action": "SELL_PAPER",
                "hard_risk_discipline": {
                    "override": True,
                    "status": "STOP_LOSS_BREACHED",
                    "hard_rule": "HARD_STOP_LOSS_-3",
                    "pnl_pct": -3.2,
                    "required_action": "SELL_REQUIRED",
                },
            }
        ]
        alerts = _hard_risk_alerts(None, decisions)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["ticker"], "QQQ")

    def test_action_plan_blocked_when_governance_blocked(self) -> None:
        plan = _build_action_plan([{"ticker": "AAPL", "action": "SELL_PAPER", "confidence": 0.9}], governance_blocked=True)
        self.assertEqual(plan[0]["action"], "NO_PAPER_ACTION")

    def test_executive_recommendation_blocked(self) -> None:
        text = _executive_recommendation(
            governance_verdict="BLOCKED_WITH_REASONS",
            block_reasons=["reconciliation FAIL"],
            morning_verdict="WATCH",
            pde_summary={},
            hard_alerts=[],
            dpe_view={},
            capital={},
            action_plan=[],
        )
        self.assertIn("BLOCKED", text)

    def test_build_council_synthesis_minimal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dec_dir = root / "runtime_outputs/paper_decisions"
            dec_dir.mkdir(parents=True)
            (dec_dir / "paper_decisions.json").write_text(
                json.dumps(
                    {
                        "decisions": [
                            {"ticker": "QQQ", "action": "SELL_PAPER", "confidence": 0.9, "evidence": "hard risk"},
                        ],
                        "action_summary": {"SELL_PAPER": 1},
                    }
                ),
                encoding="utf-8",
            )
            (root / "runtime_outputs/governance").mkdir(parents=True)
            (root / "runtime_outputs/governance/structural_governance.json").write_text(
                json.dumps({"final_verdict": "READY_FOR_PAPER_DAY", "block_reasons": []}),
                encoding="utf-8",
            )
            with mock.patch("tae_investment_council.DECISIONS_JSON", dec_dir / "paper_decisions.json"), mock.patch(
                "tae_investment_council.GOVERNANCE_JSON", root / "runtime_outputs/governance/structural_governance.json"
            ), mock.patch("tae_investment_council.COUNCIL_JSON", root / "council.json"            ), mock.patch(
                "tae_investment_council._canonical_vs_paper", return_value={"ok": True, "delta": {}}
            ):
                payload = build_council_synthesis(include_morning_audit=False)
        self.assertEqual(payload["governance_verdict"], "READY_FOR_PAPER_DAY")
        self.assertTrue(payload["synthesis_only"])
        self.assertEqual(payload["top_sell_candidates"][0]["ticker"], "QQQ")


if __name__ == "__main__":
    unittest.main()
