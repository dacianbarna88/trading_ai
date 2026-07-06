#!/usr/bin/env python3
"""Tests for tae_profit_protection_shadow.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tae_profit_protection_shadow import (
    SHADOW_ACTIONS,
    analyze_position,
    build_daily_summary,
    build_profit_protection_report,
    confidence_from_observations,
    evaluate_protection_signal,
    evaluate_rules_v1,
    knowledge_prefers_trailing,
    write_outputs,
)


class ProfitProtectionShadowTest(unittest.TestCase):
    def test_profit_protection_watch(self) -> None:
        signal, action, reason = evaluate_protection_signal(
            high_pct=2.5,
            current_pct=0.5,
            drawdown_from_high_pct=-1.2,
            missed_opportunity_usd=40.0,
            shadow={"sell_20": 10, "sell_30": 12, "trailing_1": 8, "trailing_1_5": 7},
        )
        self.assertEqual(signal, "PROFIT_PROTECTION_WATCH")
        self.assertEqual(action, "OBSERVE")
        self.assertIn("SHADOW_ONLY", reason)

    def test_partial_take_profit_shadow_20(self) -> None:
        signal, action, _ = evaluate_protection_signal(
            high_pct=3.5,
            current_pct=0.2,
            drawdown_from_high_pct=-1.6,
            missed_opportunity_usd=50.0,
            shadow={"sell_20": 20, "sell_30": 25, "trailing_1": 15, "trailing_1_5": 14},
        )
        self.assertEqual(signal, "PARTIAL_TAKE_PROFIT_SHADOW_20")
        self.assertEqual(action, "TEST_SELL_20")

    def test_partial_take_profit_shadow_30(self) -> None:
        signal, action, _ = evaluate_protection_signal(
            high_pct=5.22,
            current_pct=-0.97,
            drawdown_from_high_pct=-5.88,
            missed_opportunity_usd=154.0,
            shadow={"sell_20": 6, "sell_30": 22, "trailing_1": 104, "trailing_1_5": 90},
        )
        self.assertEqual(signal, "PARTIAL_TAKE_PROFIT_SHADOW_30")
        self.assertEqual(action, "TEST_SELL_30")

    def test_trailing_when_knowledge_recommends(self) -> None:
        signal, action, _ = evaluate_protection_signal(
            high_pct=2.2,
            current_pct=0.1,
            drawdown_from_high_pct=-2.1,
            missed_opportunity_usd=54.0,
            shadow={"sell_20": 9, "sell_30": 15, "trailing_1": 31, "trailing_1_5": 18},
            discovery_strategy="shadow_trailing_1",
            knowledge_trailing=True,
        )
        self.assertEqual(signal, "TRAILING_PROTECTION_SHADOW")
        self.assertEqual(action, "TEST_TRAILING_1")

    def test_no_protection(self) -> None:
        signal, action, _ = evaluate_protection_signal(
            high_pct=1.0,
            current_pct=0.5,
            drawdown_from_high_pct=-0.3,
            missed_opportunity_usd=5.0,
            shadow={"sell_20": 1, "sell_30": 1, "trailing_1": 1, "trailing_1_5": 1},
        )
        self.assertEqual(signal, "NO_PROTECTION")
        self.assertEqual(action, "OBSERVE")

    def test_confidence_levels(self) -> None:
        self.assertEqual(confidence_from_observations(5), "LOW")
        self.assertEqual(confidence_from_observations(45), "MEDIUM")
        self.assertEqual(confidence_from_observations(120), "HIGH")

    def test_summary_totals(self) -> None:
        positions = [
            {
                "protection_signal": "PROFIT_PROTECTION_WATCH",
                "missed_opportunity_usd": 50,
                "estimated_protected_value_20": 10,
                "estimated_protected_value_30": 12,
                "estimated_trailing_value_1": 15,
                "estimated_trailing_value_1_5": 14,
            },
            {
                "protection_signal": "PARTIAL_TAKE_PROFIT_SHADOW_30",
                "missed_opportunity_usd": 100,
                "estimated_protected_value_20": 20,
                "estimated_protected_value_30": 30,
                "estimated_trailing_value_1": 25,
                "estimated_trailing_value_1_5": 22,
            },
        ]
        summary = build_daily_summary(positions)
        self.assertEqual(summary["total_positions"], 2)
        self.assertEqual(summary["num_watch"], 1)
        self.assertEqual(summary["num_partial30"], 1)
        self.assertEqual(summary["total_missed_opportunity"], 150.0)

    def test_no_buy_sell_as_real_recommendation(self) -> None:
        for action in SHADOW_ACTIONS:
            self.assertNotEqual(action, "BUY")
            self.assertNotEqual(action, "SELL")
        row = analyze_position(
            {
                "ticker": "PM",
                "shares": 10,
                "avg_price": 180,
                "high_pct": 2.5,
                "current_pct": 0.1,
                "drawdown_from_high_pct": -2.0,
                "missed_opportunity_usd": 50,
                "classification": "SIGNIFICANT_INTRADAY_FADE",
                "shadow": {
                    "sell_20_at_high_pnl": 10,
                    "sell_30_at_high_pnl": 12,
                    "trailing_1pct_pnl": 15,
                    "trailing_1_5pct_pnl": 14,
                },
            },
            fifo_shares=10,
            fifo_avg=180,
            obs_count=2,
            discovery_strategy="shadow_trailing_1",
            knowledge_trailing=False,
        )
        self.assertIn("TEST_", row["suggested_shadow_action"])
        self.assertIn("SHADOW_ONLY", row["reason"])

    def test_missing_input_files_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = build_profit_protection_report(
                portfolio_path=base / "missing.csv",
                fade_intelligence_path=base / "missing.json",
                history_csv_path=base / "missing_hist.csv",
                discovery_path=base / "missing_disc.json",
                knowledge_path=base / "missing_kb.json",
            )
            self.assertEqual(report["positions"], [])
            self.assertFalse(any(report["sources_loaded"].values()))

    def test_knowledge_trailing_priority(self) -> None:
        kb = {
            "recommendations": [{"recommendation": "TEST_TRAILING_SHADOW"}],
            "entries": [],
        }
        self.assertTrue(knowledge_prefers_trailing(kb))

    def test_rules_v1_profit_lock(self) -> None:
        rules = evaluate_rules_v1(current_pnl_pct=4.5, peak_pnl_pct=4.5)
        self.assertIn("PROFIT_LOCK_ACTIVE", rules["flags"])
        self.assertTrue(rules["profit_lock_active"])

    def test_rules_v1_profit_at_risk(self) -> None:
        rules = evaluate_rules_v1(current_pnl_pct=2.0, peak_pnl_pct=6.0)
        self.assertIn("PROFIT_LOCK_ACTIVE", rules["flags"])
        self.assertIn("PROFIT_AT_RISK", rules["flags"])
        self.assertTrue(rules["profit_at_risk"])

    def test_rules_v1_partial_take_profit_levels(self) -> None:
        rules = evaluate_rules_v1(current_pnl_pct=10.5, peak_pnl_pct=10.5)
        advisories = rules["partial_take_profit_advisories"]
        self.assertEqual(
            advisories,
            [
                "TAKE_PROFIT_PARTIAL_25",
                "TAKE_PROFIT_PARTIAL_33",
                "TAKE_PROFIT_PARTIAL_50",
            ],
        )

    def test_rules_v1_no_take_profit_when_negative(self) -> None:
        rules = evaluate_rules_v1(current_pnl_pct=-1.0, peak_pnl_pct=8.0)
        self.assertEqual(rules["partial_take_profit_advisories"], [])
        self.assertFalse(any(a.startswith("TAKE_PROFIT_PARTIAL") for a in rules["flags"]))

    def test_rules_v1_reentry_cooldown(self) -> None:
        rules = evaluate_rules_v1(
            current_pnl_pct=2.0,
            peak_pnl_pct=2.0,
            reentry_cooldown=True,
        )
        self.assertIn("REENTRY_COOLDOWN_REQUIRED", rules["flags"])

    def test_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fade = base / "fade.json"
            fade.write_text(
                json.dumps(
                    {
                        "positions": [
                            {
                                "ticker": "MU",
                                "shares": 2,
                                "avg_price": 1000,
                                "high_pct": 5.22,
                                "current_pct": -0.97,
                                "drawdown_from_high_pct": -5.88,
                                "missed_opportunity_usd": 154,
                                "classification": "POTENTIAL_PARTIAL_TAKE_PROFIT",
                                "shadow": {
                                    "sell_20_at_high_pnl": 6,
                                    "sell_30_at_high_pnl": 22,
                                    "trailing_1pct_pnl": 104,
                                    "trailing_1_5pct_pnl": 90,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = build_profit_protection_report(
                portfolio_path=base / "none.csv",
                fade_intelligence_path=fade,
                history_csv_path=base / "none.csv",
                discovery_path=base / "none.json",
                knowledge_path=base / "none.json",
            )
            import tae_profit_protection_shadow as mod

            out_json = base / "out.json"
            out_md = base / "out.md"
            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD)
            mod.OUTPUT_JSON, mod.OUTPUT_MD = out_json, out_md
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD = orig
            self.assertTrue(out_json.exists())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["mode"], "SHADOW_ONLY")
            for pos in loaded.get("positions", []):
                self.assertIn(pos["suggested_shadow_action"], SHADOW_ACTIONS)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
