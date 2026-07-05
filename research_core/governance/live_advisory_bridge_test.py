#!/usr/bin/env python3
"""Tests for live_advisory_bridge governor enrichment (X.DECISION-2B)."""

from __future__ import annotations

import unittest

from research_core.governance.live_advisory_bridge import (
    LiveAdvisoryBridge,
    LiveAdvisoryReport,
)


SAMPLE_GOVERNOR = {
    "schema": "tae_decision_governor",
    "generated_at": "2026-07-05T20:31:02",
    "mode": "SHADOW_ONLY",
    "view_type": "MATERIALIZED_VIEW",
    "overall_advisory_posture": "NOT_READY",
    "governor_note": "Advisory orchestration VIEW only",
    "readiness": {
        "final_status": "NOT_READY",
        "protect_readiness": "WATCH",
        "cooldown_readiness": "NOT_READY",
    },
    "posture_counts": {"ALLOWED": 44, "WATCH": 19, "BLOCKED": 0, "INSUFFICIENT_DATA": 0},
    "shadow_verdict": {
        "primary_cause": "MISSED_PROFIT_PROTECTION",
        "secondary_cause": "STOP_REENTRY_CHURN",
        "best_shadow_hypothesis": "shadow_trailing_1",
    },
    "blocker_summary": [
        {"code": "SHADOW_GATES_NOT_READY", "detail": "PROTECT=WATCH COOLDOWN=NOT_READY"},
    ],
    "ticker_postures": [
        {"ticker": "MU", "posture": "WATCH", "signal": "STRONG BUY", "score": 93.0},
        {"ticker": "SPY", "posture": "ALLOWED", "signal": "STRONG BUY", "score": 100.0},
    ],
    "advisory_notes": ["Primary shadow cause: MISSED_PROFIT_PROTECTION"],
    "sources_loaded": {"tae_decision_replay.json": True, "tae_knowledge_base.json": True},
}


class LiveAdvisoryBridgeGovernorEnrichmentTest(unittest.TestCase):
    def test_extract_governor_enrichment_informational_fields(self) -> None:
        enrichment = LiveAdvisoryBridge._extract_governor_enrichment(SAMPLE_GOVERNOR)
        self.assertTrue(enrichment["present"])
        self.assertTrue(enrichment["informational_only"])
        self.assertFalse(enrichment["controls_live_blocking"])
        self.assertEqual(enrichment["overall_advisory_posture"], "NOT_READY")
        self.assertEqual(enrichment["readiness"]["protect_readiness"], "WATCH")
        self.assertEqual(enrichment["posture_counts"]["WATCH"], 19)
        self.assertEqual(
            enrichment["shadow_verdict"]["primary_cause"],
            "MISSED_PROFIT_PROTECTION",
        )
        self.assertEqual(len(enrichment["ticker_posture_sample"]), 1)
        self.assertEqual(enrichment["ticker_posture_sample"][0]["ticker"], "MU")

    def test_extract_governor_missing_returns_absent(self) -> None:
        enrichment = LiveAdvisoryBridge._extract_governor_enrichment(None)
        self.assertFalse(enrichment["present"])
        self.assertTrue(enrichment["informational_only"])
        self.assertFalse(enrichment["controls_live_blocking"])

    def test_to_dict_includes_governor_without_changing_decision_fields(self) -> None:
        report = LiveAdvisoryReport(
            runtime_snapshot={"open_positions_count": 1},
            tae_snapshot={"total_reports": 1},
            action="SELL_ADVISORY",
            confidence=78,
            reasons=["existing reason"],
            blockers=[],
            governor_enrichment=LiveAdvisoryBridge._extract_governor_enrichment(SAMPLE_GOVERNOR),
        )
        payload = report.to_dict()
        self.assertEqual(payload["action"], "SELL_ADVISORY")
        self.assertEqual(payload["advisory"]["action"], "SELL_ADVISORY")
        self.assertFalse(payload["block_new_buy"])
        self.assertFalse(payload["advisory"]["block_new_buy"])
        self.assertIn("governor_enrichment", payload)
        self.assertTrue(payload["governor_enrichment"]["present"])
        self.assertTrue(payload["safety"]["governor_informational_only"])
        self.assertFalse(payload["safety"]["governor_controls_live_blocking"])

    def test_block_new_buy_only_on_risk_advisory(self) -> None:
        sell = LiveAdvisoryReport(
            runtime_snapshot={},
            tae_snapshot={},
            action="SELL_ADVISORY",
            confidence=50,
            reasons=[],
            blockers=[],
        )
        risk = LiveAdvisoryReport(
            runtime_snapshot={},
            tae_snapshot={},
            action="RISK_ADVISORY",
            confidence=50,
            reasons=[],
            blockers=[],
        )
        self.assertFalse(sell.block_new_buy)
        self.assertTrue(risk.block_new_buy)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
