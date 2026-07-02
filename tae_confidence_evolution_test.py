#!/usr/bin/env python3
"""Tests for tae_confidence_evolution.py (X.KNOWLEDGE-1B)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tae_confidence_evolution import (
    FORBIDDEN,
    build_confidence_entries,
    build_confidence_evolution_report,
    build_dataset_health,
    build_evidence_for_knowledge_base,
    compute_score_decay_candidates,
    merge_advisory_readiness,
    render_markdown,
    write_outputs,
)

SAMPLE_COOLDOWN = {
    "dataset_health": {"stop_reentry_cases": 8},
    "summary": {
        "immediate_reentries": 5,
        "second_stop_count": 2,
        "total_reentries": 8,
        "reentry_wins": 1,
    },
    "score_persistence": {
        "count": 8,
        "cases": [
            {"ticker": "MU", "reentry_score": 100.0, "outcome": "REENTRY_SECOND_STOP", "leg_pnl": -75.71},
            {"ticker": "SIE.DE", "reentry_score": 80.0, "outcome": "REENTRY_WIN", "leg_pnl": 46.48},
        ],
    },
    "cooldown_simulation": {
        "best_cooldown": "cooldown_15m",
        "simulations": {"cooldown_15m": {"net_effect_usd": 23.98}},
    },
    "stop_reentry_sequences": [
        {
            "ticker": "MU",
            "stop_timestamp": "2026-07-01 16:31:02",
            "reentry_timestamp": "2026-07-01 16:32:22",
            "minutes_after_stop": 1.33,
            "reentry_score": 100.0,
            "second_stop": True,
            "leg_pnl": -75.71,
            "outcome": "REENTRY_SECOND_STOP",
        },
        {
            "ticker": "MU",
            "stop_timestamp": "2026-07-01 20:48:20",
            "reentry_timestamp": "2026-07-01 20:49:39",
            "minutes_after_stop": 1.32,
            "reentry_score": 100.0,
            "second_stop": False,
            "leg_pnl": -24.75,
            "outcome": "REENTRY_OPEN_UNREALIZED",
        },
        {
            "ticker": "SIE.DE",
            "stop_timestamp": "2026-06-24 16:11:11",
            "reentry_timestamp": "2026-06-24 16:12:28",
            "minutes_after_stop": 1.28,
            "reentry_score": 80.0,
            "second_stop": False,
            "leg_pnl": 46.48,
            "outcome": "REENTRY_WIN",
        },
    ],
    "gates": {"advisory_readiness": "NOT_READY", "gates_passed": False},
}

SAMPLE_PROTECT = {
    "dataset_health": {"observations": 26, "minimum_sample_warning": True, "data_quality": "LIMITED"},
    "best_strategy": {
        "strategy_id": "shadow_trailing_1",
        "total_value": 579.05,
        "delta_vs_hold_total": 616.18,
        "win_rate": 0.5385,
    },
    "gates": {"advisory_readiness": "NOT_READY", "gates_passed": False, "failed_gates": ["G1", "G3"]},
}

SAMPLE_REPLAY = {
    "final_verdict": {
        "primary_cause": "MISSED_PROFIT_PROTECTION",
        "secondary_cause": "STOP_REENTRY_CHURN",
    }
}

SAMPLE_KNOWLEDGE = {
    "entries": [
        {
            "id": "kb_intraday_P002",
            "pattern_type": "BEST_SHADOW_TRAILING",
            "confidence": "LOW",
            "subject": "shadow_trailing_1",
        }
    ]
}


class ConfidenceEvolutionTest(unittest.TestCase):
    def test_missing_inputs_handled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = build_confidence_evolution_report(
                cooldown_path=base / "missing.json",
                replay_path=base / "missing2.json",
                protect_path=base / "missing3.json",
                knowledge_path=base / "missing4.json",
            )
            health = report["dataset_health"]
            self.assertEqual(health["data_quality"], "INCOMPLETE")
            self.assertTrue(health["missing_required"])
            self.assertIn("SCORE_PERSISTENCE_AFTER_STOP", [e["hypothesis"] for e in report["confidence_evolution_entries"]])

    def test_score_persistence_confidence_update(self) -> None:
        entries = build_confidence_entries(SAMPLE_COOLDOWN, SAMPLE_PROTECT, SAMPLE_REPLAY, SAMPLE_KNOWLEDGE)
        sp = next(e for e in entries if e["hypothesis"] == "SCORE_PERSISTENCE_AFTER_STOP")
        self.assertEqual(sp["evidence_count"], 8)
        self.assertEqual(sp["positive_evidence"], 8)
        self.assertEqual(sp["confidence_after"], "MEDIUM")
        self.assertEqual(sp["trend"], "IMPROVING")

    def test_second_stop_increases_negative_evidence(self) -> None:
        entries = build_confidence_entries(SAMPLE_COOLDOWN, SAMPLE_PROTECT, SAMPLE_REPLAY, SAMPLE_KNOWLEDGE)
        churn = next(e for e in entries if e["hypothesis"] == "STOP_REENTRY_CHURN")
        self.assertEqual(churn["status"], "WATCH")
        self.assertIn("second STOP", churn["reason"])
        self.assertGreater(churn["confidence_delta"], 0)

    def test_missed_profit_protection_strengthens_trailing(self) -> None:
        entries = build_confidence_entries(SAMPLE_COOLDOWN, SAMPLE_PROTECT, SAMPLE_REPLAY, SAMPLE_KNOWLEDGE)
        mpp = next(e for e in entries if e["hypothesis"] == "MISSED_PROFIT_PROTECTION")
        trail = next(e for e in entries if e["hypothesis"] == "TRAILING_1_PROTECTION_HYPOTHESIS")
        self.assertEqual(mpp["trend"], "IMPROVING")
        self.assertGreater(trail["confidence_delta"], 0)

    def test_not_ready_with_insufficient_data(self) -> None:
        readiness = merge_advisory_readiness(SAMPLE_PROTECT, SAMPLE_COOLDOWN)
        self.assertEqual(readiness["final_status"], "NOT_READY")
        report = build_confidence_evolution_report(
            cooldown_path=Path("tae_stop_reentry_cooldown_audit.json"),
            replay_path=Path("tae_decision_replay.json"),
            protect_path=Path("tae_profit_protection_validation.json"),
            knowledge_path=Path("tae_knowledge_base.json"),
        )
        if Path("tae_stop_reentry_cooldown_audit.json").is_file():
            self.assertEqual(report["promotion_readiness"]["final_status"], "NOT_READY")

    def test_score_decay_shadow_recommendation(self) -> None:
        decay = compute_score_decay_candidates(SAMPLE_COOLDOWN["stop_reentry_sequences"])
        self.assertEqual(len(decay), 2)
        self.assertTrue(all(d["recommendation"] == "SCORE_DECAY_SHADOW" for d in decay))
        mu = decay[0]
        self.assertEqual(mu["ticker"], "MU")
        self.assertEqual(mu["shadow_adjusted_score"], 80.0)
        self.assertEqual(mu["decay_window_minutes"], 30)

    def test_no_live_buy_sell_recommendation(self) -> None:
        report = build_confidence_evolution_report(
            cooldown_path=Path("tae_stop_reentry_cooldown_audit.json"),
            replay_path=Path("tae_decision_replay.json"),
            protect_path=Path("tae_profit_protection_validation.json"),
            knowledge_path=Path("tae_knowledge_base.json"),
        )
        for rec in report["recommendations"]:
            self.assertNotIn(rec, FORBIDDEN)
        for entry in report["confidence_evolution_entries"]:
            self.assertNotIn(entry["recommendation"], FORBIDDEN)

    def test_evidence_for_knowledge_base_output(self) -> None:
        entries = build_confidence_entries(SAMPLE_COOLDOWN, SAMPLE_PROTECT, SAMPLE_REPLAY, SAMPLE_KNOWLEDGE)
        decay = compute_score_decay_candidates(SAMPLE_COOLDOWN["stop_reentry_sequences"])
        health = build_dataset_health(
            SAMPLE_COOLDOWN, True, SAMPLE_PROTECT, True, SAMPLE_REPLAY, True, True, True
        )
        evidence = build_evidence_for_knowledge_base(entries, decay, health)
        self.assertGreater(len(evidence), 5)
        hypotheses = {e["hypothesis"] for e in evidence}
        self.assertIn("SCORE_DECAY_AFTER_STOP", hypotheses)
        self.assertIn("SCORE_PERSISTENCE_AFTER_STOP", hypotheses)

    def test_markdown_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "cooldown.json").write_text(json.dumps(SAMPLE_COOLDOWN), encoding="utf-8")
            (base / "protect.json").write_text(json.dumps(SAMPLE_PROTECT), encoding="utf-8")
            (base / "replay.json").write_text(json.dumps(SAMPLE_REPLAY), encoding="utf-8")
            report = build_confidence_evolution_report(
                cooldown_path=base / "cooldown.json",
                protect_path=base / "protect.json",
                replay_path=base / "replay.json",
                knowledge_path=base / "kb.json",
            )
            out_json = base / "out.json"
            out_md = base / "out.md"
            import tae_confidence_evolution as mod

            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD)
            mod.OUTPUT_JSON, mod.OUTPUT_MD = out_json, out_md
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD = orig
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_confidence_evolution")
            md = out_md.read_text(encoding="utf-8")
            self.assertIn("Executive summary", md)
            self.assertIn("SHADOW_ONLY", md)
            self.assertIn("evidence_for_knowledge_base", json.dumps(loaded))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
