#!/usr/bin/env python3
"""Targeted tests for canonical ROI queue SSOT and single-active invariant."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_roi001_challenger import (
    ROI_QUEUE_JSON,
    ensure_single_active_roi,
    load_roi_queue_ssot,
    run_roi_economic_orchestration,
)
from tae_roi_queue_ssot import bootstrap_roi_queue_if_absent


class RoiQueueSsotTest(unittest.TestCase):
    def test_missing_queue_blocks_orchestration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "tae_roi_queue.json"
            with mock.patch("tae_roi001_challenger.ROI_QUEUE_JSON", queue_path):
                doc = ensure_single_active_roi(load_roi_queue_ssot())
                self.assertEqual(doc.get("active_count"), 0)
                self.assertIn("orchestration_error", doc)
                result = run_roi_economic_orchestration(write_outputs=False)
                self.assertFalse(result.get("ok"))
                self.assertEqual(result.get("verdict"), "BLOCKED_BY_ROI_STATE_CONFLICT")

    def test_restored_queue_enforces_single_active_roi(self) -> None:
        raw = subprocess.check_output(["git", "show", "d7b67c2:tae_roi_queue.json"])
        doc = ensure_single_active_roi(json.loads(raw))
        self.assertEqual(doc.get("active_count"), 1)
        self.assertIsNone(doc.get("orchestration_error"))
        active = [row for row in doc.get("queue", []) if row.get("active")]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].get("roi_id"), "ROI-002")
        self.assertFalse(active[0].get("production_enabled"))

    def test_bootstrap_restores_single_active_roi(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "tae_roi_queue.json"
            with mock.patch("tae_roi001_challenger.ROI_QUEUE_JSON", queue_path), mock.patch(
                "tae_roi_queue_ssot.ROI_QUEUE_JSON", queue_path
            ):
                self.assertTrue(bootstrap_roi_queue_if_absent())
                doc = ensure_single_active_roi(load_roi_queue_ssot())
                self.assertEqual(doc.get("active_count"), 1)
                self.assertIsNone(doc.get("orchestration_error"))

    def test_live_queue_passes_orchestration(self) -> None:
        if not ROI_QUEUE_JSON.is_file():
            self.skipTest("tae_roi_queue.json not bootstrapped on disk")
        result = run_roi_economic_orchestration(write_outputs=False)
        self.assertTrue(result.get("ok"))
        self.assertNotEqual(result.get("verdict"), "BLOCKED_BY_ROI_STATE_CONFLICT")
        self.assertFalse(result.get("production_enabled"))


if __name__ == "__main__":
    unittest.main()
