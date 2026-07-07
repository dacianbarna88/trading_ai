#!/usr/bin/env python3
"""Tests for tae_longitudinal_outcome_memory.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_longitudinal_outcome_memory import (
    aggregate_learning,
    audit_outcome_sources,
    build_memory_record,
    extract_knowledge,
    ingest_decisions,
    load_memory_index,
    save_memory_index,
)


class LongitudinalOutcomeMemoryTest(unittest.TestCase):
    def test_audit_outcome_sources(self) -> None:
        audit = audit_outcome_sources()
        self.assertEqual(audit["schema"], "tae_outcome_source_audit")
        self.assertGreaterEqual(audit["total_count"], 10)

    def test_build_memory_record_fields(self) -> None:
        record = build_memory_record(
            {
                "decision_id": "PDE-001",
                "ticker": "MRK",
                "timestamp": "2026-06-01T12:00:00+00:00",
                "action": "HOLD_PAPER",
                "confidence": 0.72,
                "horizon_context": {"7D": {"return_pct": 1.2, "trend": "UP"}},
            },
            validation={"verdict": "PROMISING", "reason": "aligned"},
            promotion={"promotion_recommendation": "CONTINUE_PAPER"},
            gii_row={"growth_score": 0.8, "capital_efficiency": 0.6, "missed_usd": 100},
            pce_row={},
            philosophy="COLLABORATIVE",
            market_regime="BULL",
            volatility_regime="NORMAL",
            appe_policy="HOLD",
            ppg_posture="KEEP",
            protection_state="SAFE",
            experiment={"experiment_id": "EXP-1"},
        )
        self.assertEqual(record["decision_id"], "PDE-001")
        self.assertEqual(record["action"], "HOLD_PAPER")
        self.assertEqual(record["validation_verdict"], "PROMISING")
        self.assertFalse(record["live_promotion_allowed"])
        self.assertEqual(len(record["checkpoints"]), 8)

    def test_aggregate_and_knowledge(self) -> None:
        records = {
            "A": {"action": "BUY_PAPER", "philosophy": "COLLABORATIVE", "validation_verdict": "PROMISING"},
            "B": {"action": "BUY_PAPER", "philosophy": "COLLABORATIVE", "validation_verdict": "REJECT"},
            "C": {"action": "PROTECT_PAPER", "philosophy": "COMPETITIVE", "validation_verdict": "CONTINUE_TESTING", "expected_risk_delta": -0.1},
            "D": {"action": "PROTECT_PAPER", "philosophy": "COMPETITIVE", "validation_verdict": "PROMISING", "expected_risk_delta": -0.2},
        }
        learning = aggregate_learning(records)
        self.assertIn("BUY_PAPER", learning["action_performance"])
        knowledge = extract_knowledge(records, learning)
        self.assertTrue(any(k["category"] == "action_reliability" for k in knowledge))

    def test_ingest_decisions_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paper_dir = base / "runtime_outputs" / "paper_decisions"
            paper_dir.mkdir(parents=True)
            decisions = {
                "decisions": [
                    {
                        "decision_id": "PDE-TEST-1",
                        "ticker": "MRK",
                        "action": "HOLD_PAPER",
                        "timestamp": "2026-06-01T12:00:00+00:00",
                        "confidence": 0.6,
                    }
                ]
            }
            (paper_dir / "paper_decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
            (paper_dir / "decision_validation_results.json").write_text(
                json.dumps({"results": [{"decision_id": "PDE-TEST-1", "verdict": "PROMISING"}]}),
                encoding="utf-8",
            )
            mem_dir = base / "runtime_outputs" / "longitudinal_memory"
            with mock.patch("tae_longitudinal_outcome_memory.PAPER_DECISIONS_JSON", paper_dir / "paper_decisions.json"), mock.patch(
                "tae_longitudinal_outcome_memory.VALIDATION_JSON", paper_dir / "decision_validation_results.json"
            ), mock.patch("tae_longitudinal_outcome_memory.OUTPUT_DIR", mem_dir), mock.patch(
                "tae_longitudinal_outcome_memory.MEMORY_JSONL", mem_dir / "decisions.jsonl"
            ), mock.patch("tae_longitudinal_outcome_memory.PROMOTION_JSON", base / "missing.json"), mock.patch(
                "tae_longitudinal_outcome_memory.EXPERIMENTS_JSON", base / "missing.json"
            ), mock.patch("tae_longitudinal_outcome_memory.ADAPTIVE_JSON", base / "missing.json"), mock.patch(
                "tae_longitudinal_outcome_memory.GII_JSON", base / "missing.json"
            ), mock.patch("tae_longitudinal_outcome_memory.PCE_JSON", base / "missing.json"), mock.patch(
                "tae_longitudinal_outcome_memory.APPE_JSON", base / "missing.json"
            ), mock.patch("tae_longitudinal_outcome_memory.PPG_JSON", base / "missing.json"), mock.patch(
                "tae_longitudinal_outcome_memory.SHADOW_JSON", base / "missing.json"
            ), mock.patch("tae_longitudinal_outcome_memory.ACCOUNTING_JSON", base / "missing.json"):
                records: dict = {}
                new1, _ = ingest_decisions(records)
                self.assertEqual(new1, 1)
                save_memory_index(records)
                records2 = load_memory_index()
                new2, _ = ingest_decisions(records2)
                self.assertEqual(new2, 0)
                self.assertEqual(len(records2), 1)


if __name__ == "__main__":
    unittest.main()
