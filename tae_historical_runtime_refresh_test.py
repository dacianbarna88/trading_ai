#!/usr/bin/env python3
"""Tests for tae_historical_runtime_refresh.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_historical_runtime_refresh import (
    HISTORICAL_SOURCES,
    audit_all_sources,
    confidence_penalty,
    run_historical_runtime_refresh,
)


def _plant_refresh_scripts(root: Path) -> None:
    """Create stub refresh owners so critical freshness still applies."""
    for spec in HISTORICAL_SOURCES:
        script = root / spec.refresh_script
        script.parent.mkdir(parents=True, exist_ok=True)
        if not script.is_file():
            script.write_text("print('stub')\n", encoding="utf-8")


class HistoricalRuntimeRefreshTest(unittest.TestCase):
    def test_audit_detects_owner_absent_without_blocking(self) -> None:
        """Empty tree with no refresh scripts → owner-absent, not HARD-critical."""
        with tempfile.TemporaryDirectory() as tmp:
            audit = audit_all_sources(root=Path(tmp))
            self.assertGreater(len(audit.get("refresh_owner_absent") or []), 0)
            self.assertTrue(audit["critical_all_fresh"])
            self.assertEqual(audit["missing_count"], 0)

    def test_audit_detects_missing_when_owners_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _plant_refresh_scripts(base)
            audit = audit_all_sources(root=base)
            self.assertGreater(audit["missing_count"], 0)
            self.assertFalse(audit["all_fresh"])

    def test_confidence_penalty_scales(self) -> None:
        self.assertEqual(confidence_penalty([]), 0.0)
        self.assertGreater(confidence_penalty(["historical_intelligence_csv"]), 0.0)

    def test_refresh_marks_stale_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _plant_refresh_scripts(base)
            with mock.patch(
                "tae_historical_runtime_refresh._run_script",
                return_value=(False, "network error"),
            ), mock.patch(
                "tae_historical_runtime_refresh.RUNTIME_DIR",
                base / "runtime_outputs/historical_runtime",
            ), mock.patch(
                "tae_historical_runtime_refresh.REPORT_MD",
                base / "TAE_HISTORICAL_RUNTIME_REPORT.md",
            ), mock.patch(
                "tae_historical_runtime_refresh.STATE_JSON",
                base / "runtime_outputs/historical_runtime/runtime_state.json",
            ):
                state = run_historical_runtime_refresh(root=base)
                self.assertFalse(state["all_fresh"])
                self.assertGreater(state["confidence_penalty"], 0)
                self.assertTrue(state["never_silent_stale"])

    def test_runtime_state_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state_path = base / "runtime_outputs/historical_runtime/runtime_state.json"
            with mock.patch("tae_historical_runtime_refresh.RUNTIME_DIR", state_path.parent), mock.patch(
                "tae_historical_runtime_refresh.STATE_JSON", state_path
            ), mock.patch("tae_historical_runtime_refresh.REPORT_MD", base / "report.md"), mock.patch(
                "tae_historical_runtime_refresh.refresh_source",
                side_effect=lambda spec, root: {
                    "source_id": spec.source_id,
                    "refresh_attempted": True,
                    "refresh_ok": True,
                    "status": "REFRESHED",
                    "age_hours_after": 0.1,
                },
            ), mock.patch(
                "tae_historical_runtime_refresh.recompute_dependents",
                return_value=[],
            ):
                for spec_path in (
                    "historical_intelligence.csv",
                    "multi_horizon_backtest.csv",
                    "global_market_scanner.csv",
                    "regional_strength.csv",
                    "strategic_intelligence_summary.txt",
                    "horizon_vote_summary.txt",
                ):
                    p = base / spec_path
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text("x", encoding="utf-8")
                state = run_historical_runtime_refresh(root=base)
                self.assertTrue(state_path.is_file())
                loaded = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertIn("audit_after", loaded)


if __name__ == "__main__":
    unittest.main()
