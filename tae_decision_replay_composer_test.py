#!/usr/bin/env python3
"""Tests for tae_decision_replay_composer.py (X.REPLAY-1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tae_decision_replay_composer import (
    FORBIDDEN,
    SHADOW_RECOMMENDATIONS,
    build_counterfactual_comparison,
    build_replay_report,
    build_top_costly_decisions,
    classify_failure_modes,
    merge_advisory_readiness,
    normalize_accounting,
    normalize_cooldown,
    normalize_protect,
    render_markdown,
    write_outputs,
)

SAMPLE_PROTECT = {
    "generated_at": "2026-07-01",
    "verdict": "PROMISING_BUT_NOT_READY",
    "dataset_health": {"observations": 26, "confidence": "LOW"},
    "best_strategy": {
        "strategy_id": "shadow_trailing_1",
        "total_value": 579.05,
        "delta_vs_hold_total": 616.18,
    },
    "hold_baseline": {"total_value": -37.13},
    "gates": {
        "advisory_readiness": "NOT_READY",
        "gates_passed": False,
        "failed_gates": ["G1"],
    },
    "ticker_breakdown": [
        {
            "ticker": "MU",
            "total_missed_opportunity": 269.72,
            "best_strategy": "shadow_trailing_1",
            "confidence": "LOW",
            "observations": 2,
        }
    ],
    "recommendations": ["DO_NOT_PROMOTE_TO_ADVISORY_YET"],
}

SAMPLE_COOLDOWN = {
    "generated_at": "2026-07-02",
    "verdict": "INSUFFICIENT_SAMPLE",
    "dataset_health": {"stop_reentry_cases": 8},
    "summary": {"immediate_reentries": 5, "second_stop_count": 2},
    "cooldown_simulation": {
        "best_cooldown": "cooldown_15m",
        "simulations": {
            "cooldown_15m": {
                "net_effect_usd": 23.98,
                "avoided_loss_usd": 100.46,
                "missed_gain_usd": 76.48,
            }
        },
    },
    "gates": {"advisory_readiness": "NOT_READY", "gates_passed": False, "failed_gates": ["G1"]},
    "stop_reentry_sequences": [
        {
            "ticker": "MU",
            "reentry_timestamp": "2026-07-01 16:32:22",
            "minutes_after_stop": 1.33,
            "leg_pnl": -75.71,
            "second_stop": True,
            "outcome": "REENTRY_SECOND_STOP",
            "pnl_methodology": "ACTUAL",
        }
    ],
    "score_persistence": {"count": 8, "loss_rate": 0.25},
    "recommendations": ["DO_NOT_PROMOTE_TO_LIVE"],
}


class DecisionReplayComposerTest(unittest.TestCase):
    def test_missing_optional_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = build_replay_report(
                portfolio_path=base / "missing.csv",
                accounting_path=base / "missing_acct.json",
                protect_path=base / "missing_protect.json",
                cooldown_path=base / "missing_cooldown.json",
                knowledge_path=base / "missing_kb.json",
            )
            self.assertFalse(report["sources_loaded"]["tae_accounting_snapshot.json"])
            self.assertIn("DATA_ISSUE", [m["mode"] for m in report["failure_mode_attribution"]])

    def test_normalize_protect(self) -> None:
        n = normalize_protect(SAMPLE_PROTECT, loaded=True)
        self.assertEqual(n["best_strategy_id"], "shadow_trailing_1")
        self.assertEqual(n["protection_delta_vs_hold"], 616.18)

    def test_normalize_cooldown(self) -> None:
        n = normalize_cooldown(SAMPLE_COOLDOWN, loaded=True)
        self.assertEqual(n["best_cooldown_policy"], "cooldown_15m")
        self.assertEqual(n["cooldown_net_effect"], 23.98)

    def test_normalize_accounting(self) -> None:
        n = normalize_accounting(
            {
                "corrected_total_trading_pnl": -22.49,
                "corrected_realized_pnl": 36.65,
                "corrected_unrealized_pnl": -59.15,
            },
            loaded=True,
        )
        self.assertEqual(n["total_pnl"], -22.49)

    def test_failure_mode_classification(self) -> None:
        protect = normalize_protect(SAMPLE_PROTECT, loaded=True)
        cooldown = normalize_cooldown(SAMPLE_COOLDOWN, loaded=True)
        modes = classify_failure_modes(
            protect,
            cooldown,
            {"loaded": True, "total_drag_usd": 0},
            {"tae_profit_protection_validation.json": True},
        )
        mode_names = [m["mode"] for m in modes]
        self.assertIn("MISSED_PROFIT_PROTECTION", mode_names)
        self.assertIn("STOP_REENTRY_CHURN", mode_names)

    def test_combined_estimate_double_count_warning(self) -> None:
        protect = normalize_protect(SAMPLE_PROTECT, loaded=True)
        cooldown = normalize_cooldown(SAMPLE_COOLDOWN, loaded=True)
        cf = build_counterfactual_comparison(protect, cooldown)
        self.assertTrue(cf["double_count_warning"])
        self.assertEqual(cf["combined_methodology"], "ESTIMATED")
        self.assertAlmostEqual(cf["combined_theoretical_effect_usd"], 640.16, places=1)

    def test_top_costly_decision_ranking(self) -> None:
        protect = normalize_protect(SAMPLE_PROTECT, loaded=True)
        cooldown = normalize_cooldown(SAMPLE_COOLDOWN, loaded=True)
        top = build_top_costly_decisions(protect, cooldown, {})
        self.assertGreater(len(top), 0)
        self.assertEqual(top[0]["ticker"], "MU")

    def test_not_ready_when_gates_fail(self) -> None:
        readiness = merge_advisory_readiness(
            normalize_protect(SAMPLE_PROTECT, loaded=True),
            normalize_cooldown(SAMPLE_COOLDOWN, loaded=True),
        )
        self.assertEqual(readiness["final_status"], "NOT_READY")

    def test_no_live_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "protect.json").write_text(json.dumps(SAMPLE_PROTECT), encoding="utf-8")
            (base / "cooldown.json").write_text(json.dumps(SAMPLE_COOLDOWN), encoding="utf-8")
            report = build_replay_report(
                protect_path=base / "protect.json",
                cooldown_path=base / "cooldown.json",
            )
            for rec in report["recommendations"]:
                self.assertNotIn(rec, FORBIDDEN)

    def test_markdown_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "protect.json").write_text(json.dumps(SAMPLE_PROTECT), encoding="utf-8")
            (base / "cooldown.json").write_text(json.dumps(SAMPLE_COOLDOWN), encoding="utf-8")
            report = build_replay_report(
                protect_path=base / "protect.json",
                cooldown_path=base / "cooldown.json",
            )
            out_json = base / "out.json"
            out_md = base / "out.md"
            import tae_decision_replay_composer as mod

            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD)
            mod.OUTPUT_JSON, mod.OUTPUT_MD = out_json, out_md
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD = orig
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_decision_replay")
            md = out_md.read_text(encoding="utf-8")
            self.assertIn("Executive summary", md)
            self.assertIn("SHADOW_ONLY", md)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
