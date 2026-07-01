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


if __name__ == "__main__":
    raise SystemExit(unittest.main())
