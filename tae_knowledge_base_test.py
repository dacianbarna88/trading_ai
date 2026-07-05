#!/usr/bin/env python3
"""Tests for tae_knowledge_base.py — X.KNOWLEDGE-1A read-only aggregator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tae_knowledge_base import (
    FORBIDDEN_RECOMMENDATIONS,
    SHADOW_RECOMMENDATIONS,
    assign_status_confidence,
    build_knowledge_base,
    dedupe_entries,
    make_entry,
    map_confidence_evolution_status,
    normalize_confidence_evolution,
    normalize_evidence_report,
    normalize_intraday_discovery,
    normalize_learning_memory,
    sanitize_recommendation,
    write_knowledge_outputs,
)


class KnowledgeBaseTest(unittest.TestCase):
    def test_missing_files_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = build_knowledge_base(
                intraday_discovery=base / "missing.json",
                evidence_report=base / "missing2.json",
                learning_memory=base / "missing3.json",
                fade_history=base / "missing.csv",
                fade_daily_summary=base / "missing4.json",
                knowledge_candidates=base / "missing5.json",
                discovery_rankings=base / "missing6.json",
                confidence_evolution=base / "missing7.json",
            )
            self.assertEqual(report["schema"], "tae_knowledge_base")
            self.assertEqual(report["entries"], [])
            self.assertFalse(any(report["sources_loaded"].values()))

    def test_intraday_discovery_normalization(self) -> None:
        data = {
            "generated_at": "2026-07-01T12:00:00",
            "patterns": [
                {
                    "id": "P001",
                    "pattern_type": "HIGH_FADE_TICKER",
                    "scope": "ticker",
                    "subject": "PM",
                    "observations": 14,
                    "metric": "total_missed_opportunity",
                    "value": 129.84,
                    "confidence": "MEDIUM",
                    "recommendation": "PRIORITIZE_TRACKING",
                }
            ],
            "ticker_learning": [],
        }
        entries = normalize_intraday_discovery(data, "tae_intraday_discovery_engine.json")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "intraday_discovery")
        self.assertEqual(entries[0]["status"], "EXPERIMENTAL")
        self.assertEqual(entries[0]["confidence"], "LOW")

    def test_evidence_normalization(self) -> None:
        data = {
            "generated_at": "2026-06-30T19:00:00",
            "evidence_items": [
                {
                    "evidence_id": "accounting_verified",
                    "title": "Accounting verified",
                    "conclusion": "FIFO ledger aligned.",
                    "status": "CONFIRMED",
                    "source_ref": "tae_independent_double_entry_verification.json",
                    "registered_at": "2026-06-30T19:00:00",
                }
            ],
        }
        entries = normalize_evidence_report(data, "tae_evidence_engine_report.json")
        self.assertEqual(entries[0]["status"], "CONFIRMED")
        self.assertEqual(entries[0]["confidence"], "HIGH")
        self.assertEqual(entries[0]["category"], "evidence")

    def test_learning_memory_normalization(self) -> None:
        data = {
            "generated_at": "2026-06-30T19:00:00",
            "top_ranked_strategy": "SCORE_90_PLUS",
            "top_ranking_score": 0.94,
            "paper_tracking_needs": [
                {
                    "candidate_id": "BLOCKED_ONE",
                    "tracking_status": "BLOCKED",
                    "current_trades": 9,
                    "sample_insufficient": True,
                    "tracking_note": "Need more trades",
                }
            ],
            "conflict_warnings": [],
        }
        entries = normalize_learning_memory(data, "tae_runtime_learning_memory.json")
        blocked = next(e for e in entries if e["subject"] == "BLOCKED_ONE")
        self.assertEqual(blocked["status"], "EXPERIMENTAL")
        self.assertEqual(blocked["recommendation"], "INSUFFICIENT_DATA")

    def test_deduplication(self) -> None:
        a = make_entry(
            entry_id="a",
            title="A",
            description="",
            source="intraday_discovery",
            source_file="f.json",
            category="intraday_fade",
            subject="PM",
            pattern_type="HIGH_FADE_TICKER",
            first_seen="2026-07-01",
            last_seen="2026-07-01",
            observations=2,
            confidence="LOW",
            status="EXPERIMENTAL",
            recommendation="PRIORITIZE_TRACKING",
        )
        b = make_entry(
            entry_id="b",
            title="B",
            description="",
            source="intraday_discovery",
            source_file="f.json",
            category="intraday_fade",
            subject="PM",
            pattern_type="HIGH_FADE_TICKER",
            first_seen="2026-07-02",
            last_seen="2026-07-02",
            observations=5,
            confidence="LOW",
            status="EXPERIMENTAL",
            recommendation="PRIORITIZE_TRACKING",
        )
        merged = dedupe_entries([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["observations"], 5)

    def test_confidence_scoring_rules(self) -> None:
        self.assertEqual(assign_status_confidence(source="x", observations=10, intraday=True), ("EXPERIMENTAL", "LOW"))
        self.assertEqual(assign_status_confidence(source="x", observations=50, intraday=True), ("LEARNING", "MEDIUM"))
        self.assertEqual(assign_status_confidence(source="x", observations=120, intraday=True), ("CONFIRMED", "HIGH"))

    def test_status_assignment_evidence(self) -> None:
        status, conf = assign_status_confidence(source="evidence", observations=1, upstream_status="CONFIRMED")
        self.assertEqual((status, conf), ("CONFIRMED", "HIGH"))

    def test_no_buy_sell_recommendations(self) -> None:
        self.assertEqual(sanitize_recommendation("BUY"), "CONTINUE_OBSERVATION")
        self.assertEqual(sanitize_recommendation("SELL"), "CONTINUE_OBSERVATION")
        self.assertNotIn("BUY", SHADOW_RECOMMENDATIONS)
        self.assertNotIn("SELL", SHADOW_RECOMMENDATIONS)
        self.assertIn("BUY", FORBIDDEN_RECOMMENDATIONS)

    def test_json_and_markdown_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            intraday = base / "intraday.json"
            intraday.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-01T12:00:00",
                        "patterns": [
                            {
                                "id": "P1",
                                "pattern_type": "LOW_CONFIDENCE_INSUFFICIENT_SAMPLE",
                                "scope": "dataset",
                                "subject": "all",
                                "observations": 5,
                                "metric": "observations",
                                "value": 5,
                                "recommendation": "INSUFFICIENT_DATA",
                            }
                        ],
                        "ticker_learning": [],
                    }
                ),
                encoding="utf-8",
            )
            report = build_knowledge_base(
                intraday_discovery=intraday,
                evidence_report=base / "none.json",
                learning_memory=base / "none2.json",
                fade_history=base / "none.csv",
                fade_daily_summary=base / "none3.json",
                knowledge_candidates=base / "none4.json",
                discovery_rankings=base / "none5.json",
                confidence_evolution=base / "none6.json",
            )

            import tae_knowledge_base as kb

            out_json = base / "out.json"
            out_md = base / "out.md"
            out_sum = base / "sum.md"
            orig = (kb.OUTPUT_JSON, kb.OUTPUT_MD, kb.OUTPUT_SUMMARY_MD)
            kb.OUTPUT_JSON, kb.OUTPUT_MD, kb.OUTPUT_SUMMARY_MD = out_json, out_md, out_sum
            try:
                write_knowledge_outputs(report)
            finally:
                kb.OUTPUT_JSON, kb.OUTPUT_MD, kb.OUTPUT_SUMMARY_MD = orig

            self.assertTrue(out_json.exists())
            self.assertTrue(out_md.exists())
            self.assertTrue(out_sum.exists())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["view_type"], "MATERIALIZED_VIEW")
            md_text = out_md.read_text(encoding="utf-8")
            self.assertIn("Experimental Knowledge", md_text)
            self.assertNotIn("BUY", md_text)
            self.assertNotIn("SELL", md_text)

    def test_confidence_evolution_missing_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = build_knowledge_base(confidence_evolution=base / "missing.json")
            self.assertFalse(report["sources_loaded"][str(base / "missing.json")])

    def test_confidence_evolution_entries_ingested(self) -> None:
        data = {
            "generated_at": "2026-07-03T16:00:00",
            "confidence_evolution_entries": [
                {
                    "id": "ce_score_persistence_after_stop",
                    "hypothesis": "SCORE_PERSISTENCE_AFTER_STOP",
                    "evidence_count": 10,
                    "confidence_before": "HIGH",
                    "confidence_after": "HIGH",
                    "confidence_delta": 0,
                    "trend": "IMPROVING",
                    "status": "LEARNING",
                    "reason": "10/10 score persistence",
                    "recommendation": "SCORE_DECAY_SHADOW",
                },
                {
                    "id": "ce_cooldown_15m",
                    "hypothesis": "COOLDOWN_15M_HYPOTHESIS",
                    "evidence_count": 10,
                    "confidence_before": "LOW",
                    "confidence_after": "MEDIUM",
                    "trend": "STABLE",
                    "status": "DO_NOT_PROMOTE",
                    "reason": "small sample",
                    "recommendation": "TEST_15M_COOLDOWN_SHADOW",
                },
            ],
            "score_decay_candidates": [],
        }
        entries = normalize_confidence_evolution(data, "tae_confidence_evolution.json")
        self.assertEqual(len(entries), 2)
        sp = next(e for e in entries if e["pattern_type"] == "SCORE_PERSISTENCE_AFTER_STOP")
        self.assertEqual(sp["source"], "confidence_evolution")
        self.assertEqual(sp["category"], "score_decay")
        self.assertTrue(sp["shadow_only"])
        self.assertEqual(sp["status"], "LEARNING")
        dn = next(e for e in entries if e["pattern_type"] == "COOLDOWN_15M_HYPOTHESIS")
        self.assertEqual(dn["status"], "EXPERIMENTAL")
        self.assertEqual(dn["recommendation"], "DO_NOT_PROMOTE_TO_ADVISORY_YET")

    def test_score_decay_candidate_ingested(self) -> None:
        data = {
            "generated_at": "2026-07-03T16:00:00",
            "confidence_evolution_entries": [],
            "score_decay_candidates": [
                {
                    "ticker": "MU",
                    "stop_time": "2026-07-01 16:31:02",
                    "reentry_time": "2026-07-01 16:32:22",
                    "original_score": 100.0,
                    "shadow_adjusted_score": 80.0,
                    "decay_window_minutes": 30,
                    "reason": "second STOP confirmed",
                    "outcome": "REENTRY_SECOND_STOP",
                    "confidence": "HIGH",
                    "recommendation": "SCORE_DECAY_SHADOW",
                }
            ],
        }
        entries = normalize_confidence_evolution(data, "tae_confidence_evolution.json")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["subject"], "MU|2026-07-01 16:31:02")
        self.assertEqual(entry["category"], "score_decay")
        self.assertEqual(entry["recommendation"], "SCORE_DECAY_SHADOW")
        self.assertNotIn(entry["recommendation"], FORBIDDEN_RECOMMENDATIONS)

    def test_confidence_evolution_markdown_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ce = base / "ce.json"
            ce.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-03",
                        "confidence_evolution_entries": [
                            {
                                "id": "ce_stop_reentry_churn",
                                "hypothesis": "STOP_REENTRY_CHURN",
                                "evidence_count": 7,
                                "confidence_after": "MEDIUM",
                                "status": "WATCH",
                                "trend": "IMPROVING",
                                "reason": "immediate reentries",
                                "recommendation": "TEST_15M_COOLDOWN_SHADOW",
                            }
                        ],
                        "score_decay_candidates": [],
                    }
                ),
                encoding="utf-8",
            )
            report = build_knowledge_base(confidence_evolution=ce)
            import tae_knowledge_base as kb

            out_md = base / "out.md"
            orig_md = kb.OUTPUT_MD
            kb.OUTPUT_MD = out_md
            try:
                write_knowledge_outputs(report)
            finally:
                kb.OUTPUT_MD = orig_md
            md = out_md.read_text(encoding="utf-8")
            self.assertIn("Confidence Evolution (X.KNOWLEDGE-1B/1C)", md)
            self.assertIn("confidence_evolution", json.dumps(report["entries"]))

    def test_materialized_view_not_ssot(self) -> None:
        report = build_knowledge_base(confidence_evolution=Path("tae_confidence_evolution.json"))
        self.assertEqual(report["view_type"], "MATERIALIZED_VIEW")
        self.assertIn("ssot_note", report)

    def test_map_confidence_evolution_status_rules(self) -> None:
        self.assertEqual(map_confidence_evolution_status("HIGH", "WATCH"), "LEARNING")
        self.assertEqual(map_confidence_evolution_status("MEDIUM", "WATCH"), "WATCH")
        self.assertEqual(map_confidence_evolution_status("LOW", "LEARNING"), "EXPERIMENTAL")
        self.assertEqual(map_confidence_evolution_status("MEDIUM", "DO_NOT_PROMOTE"), "EXPERIMENTAL")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
