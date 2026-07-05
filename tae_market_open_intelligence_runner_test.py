#!/usr/bin/env python3
"""Tests for tae_market_open_intelligence_runner.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tae_market_open_intelligence_runner import (
    FORBIDDEN,
    MODULE_PIPELINE,
    PROTECTED_FILES,
    build_report,
    render_markdown,
    write_outputs,
)


class MarketOpenIntelligenceRunnerTest(unittest.TestCase):
    def test_runner_handles_missing_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline = [
                {"id": "missing_mod", "script": "does_not_exist.py"},
                {"id": "second", "script": "also_missing.py"},
            ]
            report = build_report(root=root, python_bin="python3", pipeline=pipeline)
            self.assertEqual(report["modules"][0]["status"], "WARN")
            self.assertIn("missing", report["modules"][0]["detail"].lower())

    def test_runner_continues_after_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            (root / "fail.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
            pipeline = [
                {"id": "first", "script": "ok.py"},
                {"id": "second", "script": "fail.py"},
                {"id": "third", "script": "ok.py"},
            ]

            def fake_run(cmd, **kwargs):
                script = Path(cmd[-1]).name
                if script == "fail.py":
                    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")
                return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

            with mock.patch("tae_market_open_intelligence_runner.subprocess.run", side_effect=fake_run):
                report = build_report(root=root, python_bin="python3", pipeline=pipeline)

            statuses = [m["status"] for m in report["modules"]]
            self.assertEqual(statuses, ["PASS", "FAIL", "PASS"])
            self.assertEqual(len(report["modules"]), 3)

    def test_order_is_correct(self) -> None:
        expected_ids = [m["id"] for m in MODULE_PIPELINE]
        self.assertEqual(expected_ids[0], "infrastructure_health")
        self.assertEqual(expected_ids[-2], "knowledge_base")
        self.assertEqual(expected_ids[-1], "decision_governor")
        self.assertEqual(len(expected_ids), 11)

    def test_json_md_output_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = {
                "schema": "tae_market_open_intelligence_runner",
                "generated_at": "2026-07-03",
                "mode": "SHADOW_ONLY",
                "summary": {"overall_status": "PASS", "pass": 1, "warn": 0, "fail": 0, "total": 1},
                "modules": [{"order": 1, "id": "test", "script": "x.py", "status": "PASS", "duration_seconds": 0.1, "detail": "ok"}],
                "pipeline_order": ["test"],
                "protected_files_unchanged": True,
                "live_trading_recommendations_detected": [],
            }
            out_json = base / "out.json"
            out_md = base / "out.md"
            log = base / "runner.log"
            import tae_market_open_intelligence_runner as mod

            orig = (mod.OUTPUT_JSON, mod.OUTPUT_MD, mod.LOG_FILE)
            mod.OUTPUT_JSON, mod.OUTPUT_MD, mod.LOG_FILE = out_json, out_md, log
            try:
                write_outputs(report)
            finally:
                mod.OUTPUT_JSON, mod.OUTPUT_MD, mod.LOG_FILE = orig
            self.assertTrue(out_json.is_file())
            self.assertTrue(out_md.is_file())
            loaded = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "tae_market_open_intelligence_runner")
            md = out_md.read_text(encoding="utf-8")
            self.assertIn("Executive summary", md)
            self.assertIn("SHADOW_ONLY", md)

    def test_no_live_trading_files_modified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in PROTECTED_FILES:
                (root / name).write_text(f"content-{name}\n", encoding="utf-8")
            (root / "noop.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            pipeline = [{"id": "noop", "script": "noop.py"}]

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch("tae_market_open_intelligence_runner.subprocess.run", side_effect=fake_run):
                report = build_report(root=root, python_bin="python3", pipeline=pipeline)
            self.assertTrue(report["protected_files_unchanged"])

    def test_no_buy_sell_live_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tae_decision_replay.json").write_text(
                json.dumps({"recommendations": ["CONTINUE_OBSERVATION", "TEST_TRAILING_SHADOW"]}),
                encoding="utf-8",
            )
            report = build_report(root=root, python_bin="python3", pipeline=[])
            for rec in report.get("recommendations_observed") or []:
                self.assertNotIn(rec, FORBIDDEN)
            self.assertEqual(report.get("live_trading_recommendations_detected"), [])

    def test_render_markdown_includes_failures(self) -> None:
        md = render_markdown(
            {
                "generated_at": "2026-07-03",
                "summary": {"overall_status": "FAIL", "pass": 1, "warn": 0, "fail": 1, "total": 2},
                "modules": [
                    {"order": 1, "id": "a", "script": "a.py", "status": "PASS", "duration_seconds": 1, "detail": "ok"},
                    {"order": 2, "id": "b", "script": "b.py", "status": "FAIL", "duration_seconds": 2, "detail": "bad", "stderr_tail": "err"},
                ],
                "pipeline_order": ["a", "b"],
                "protected_files_unchanged": True,
                "live_trading_recommendations_detected": [],
            }
        )
        self.assertIn("Failures (bot continues)", md)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
