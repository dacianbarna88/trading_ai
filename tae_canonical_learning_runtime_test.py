#!/usr/bin/env python3
"""Isolated tests for canonical PAPER learning runtime (Sprint 1)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import tae_adaptive_paper_weights as aw
import tae_canonical_learning_runtime as clr
import tae_learning_persistence as lp
import tae_longitudinal_outcome_memory as lom
import tae_rule_survival as rs


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _seed_project(base: Path) -> None:
    _write(
        base / "runtime_outputs/paper_decisions/decision_validation_results.json",
        {
            "decisions_consumed": 2,
            "results": [
                {"action": "SELL_PAPER", "verdict": "PROMISING", "ticker": "HSBA.L"},
                {"action": "SKIP_PAPER", "verdict": "REJECT", "ticker": "MRK"},
            ],
        },
    )
    _write(
        base / "runtime_outputs/paper_execution/rule_outcome_attribution.json",
        {"rules": {"RULE_A": {"wins": 1, "losses": 0, "samples": 1}}},
    )
    trades = base / "runtime_outputs/paper_execution/paper_trades.jsonl"
    trades.parent.mkdir(parents=True, exist_ok=True)
    trades.write_text(
        json.dumps({"ticker": "HSBA.L", "action": "SELL_PAPER", "pnl": 1.0}) + "\n",
        encoding="utf-8",
    )
    mem = base / "runtime_outputs/longitudinal_memory/decisions.jsonl"
    mem.parent.mkdir(parents=True, exist_ok=True)
    mem.write_text("", encoding="utf-8")
    # Minimal prior weights so PDE-style consumers can load
    _write(
        base / "runtime_outputs/adaptive_weights/paper_action_weights.json",
        {
            "schema": "tae_adaptive_paper_weights",
            "mode": "PAPER_ONLY",
            "live_promotion_allowed": False,
            "weights": {"BUY_PAPER": {"new_weight": 1.0}},
            "ticker_weights": {},
        },
    )


class CanonicalLearningRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.base = Path(self.tmp)
        self.runtime = self.base / "runtime_outputs" / "canonical_learning"
        self.runtime.mkdir(parents=True)
        _seed_project(self.base)
        self._cwd = os.getcwd()
        os.chdir(self.base)
        os.environ["TAE_CANONICAL_LEARNING_ROOT"] = str(self.runtime)
        # Point learning writers at the temp tree (relative paths after chdir)
        self.patches = [
            mock.patch.object(aw, "OUTPUT_DIR", Path("runtime_outputs/adaptive_weights")),
            mock.patch.object(aw, "WEIGHTS_JSON", Path("runtime_outputs/adaptive_weights/paper_action_weights.json")),
            mock.patch.object(
                aw, "HISTORY_JSONL", Path("runtime_outputs/adaptive_weights/paper_action_weights_history.jsonl")
            ),
            mock.patch.object(
                aw, "VALIDATION_JSON", Path("runtime_outputs/paper_decisions/decision_validation_results.json")
            ),
            mock.patch.object(aw, "ADAPTATION_HINTS_JSON", Path("runtime_outputs/longitudinal_memory/adaptation_hints.json")),
            mock.patch.object(aw, "LONGITUDINAL_KNOWLEDGE_JSON", Path("runtime_outputs/longitudinal_memory/knowledge.json")),
            mock.patch.object(aw, "MEMORY_INDEX_JSON", Path("runtime_outputs/longitudinal_memory/memory_index.json")),
            mock.patch.object(
                aw, "RULE_ATTRIBUTION_JSON", Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
            ),
            mock.patch.object(aw, "CONFIDENCE_JSON", Path("missing_confidence.json")),
            mock.patch.object(aw, "DPE_ADAPTIVE_JSON", Path("missing_dpe.json")),
            mock.patch.object(aw, "EXPERIMENTS_JSON", Path("missing_exp.json")),
            mock.patch.object(aw, "REPORT_MD", Path("TAE_ADAPTIVE_WEIGHTS_REPORT.md")),
            mock.patch.object(lom, "OUTPUT_DIR", Path("runtime_outputs/longitudinal_memory")),
            mock.patch.object(lom, "MEMORY_JSONL", Path("runtime_outputs/longitudinal_memory/decisions.jsonl")),
            mock.patch.object(lom, "MEMORY_INDEX_JSON", Path("runtime_outputs/longitudinal_memory/memory_index.json")),
            mock.patch.object(lom, "KNOWLEDGE_JSON", Path("runtime_outputs/longitudinal_memory/knowledge.json")),
            mock.patch.object(
                lom, "ADAPTATION_HINTS_JSON", Path("runtime_outputs/longitudinal_memory/adaptation_hints.json")
            ),
            mock.patch.object(
                lom, "AUDIT_JSON", Path("runtime_outputs/longitudinal_memory/outcome_source_audit.json")
            ),
            mock.patch.object(rs, "LIFECYCLE_JSON", Path("runtime_outputs/paper_execution/rule_lifecycle.json")),
            mock.patch.object(rs, "REPORT_MD", Path("TAE_RULE_SURVIVAL_REPORT.md")),
            mock.patch.object(
                rs, "ATTRIBUTION_JSON", Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
            )
            if hasattr(rs, "ATTRIBUTION_JSON")
            else mock.patch.object(rs, "LIFECYCLE_JSON", Path("runtime_outputs/paper_execution/rule_lifecycle.json")),
        ]
        # Optional attribution path name varies — detect
        for name in ("ATTRIBUTION_JSON", "RULE_ATTRIBUTION_JSON", "OUTCOME_JSON"):
            if hasattr(rs, name):
                self.patches.append(
                    mock.patch.object(
                        rs, name, Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
                    )
                )
        for p in self.patches:
            p.start()
        # Silence report writers that need extra paths
        self.patches.append(mock.patch.object(lom, "write_reports", lambda **kwargs: None))
        self.patches[-1].start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        os.chdir(self._cwd)
        os.environ.pop("TAE_CANONICAL_LEARNING_ROOT", None)
        # Reset lock state
        lp._LOCK_DEPTH = 0
        if lp._LOCK_FH is not None:
            try:
                lp._LOCK_FH.close()
            except Exception:
                pass
        lp._LOCK_FH = None
        lp._LOCK_PATH = None

    def test_paper_only_guard(self) -> None:
        g = clr.paper_safety_guard()
        self.assertTrue(g["ok"])
        self.assertFalse(g["live_mutation_allowed"])
        with mock.patch.dict(os.environ, {"TAE_FORCE_LIVE_LEARNING": "1"}):
            bad = clr.paper_safety_guard()
            self.assertFalse(bad["ok"])

    def test_live_mutation_prohibited(self) -> None:
        with mock.patch.dict(os.environ, {"TAE_MACHINE_LIVE_PROMOTION_ALLOWED": "true"}):
            r = clr.run_canonical_learning_cycle(
                project_root=self.base,
                runtime_root=self.runtime,
                source="test",
            )
            self.assertEqual(r["result"], "PAPER_SAFETY_VIOLATION")

    def test_no_eligible_outcomes_noop(self) -> None:
        # Remove all feedback artifacts
        for path in [
            self.base / "runtime_outputs/paper_decisions/decision_validation_results.json",
            self.base / "runtime_outputs/longitudinal_memory/decisions.jsonl",
            self.base / "runtime_outputs/paper_execution/rule_outcome_attribution.json",
            self.base / "runtime_outputs/adaptive_weights/paper_action_weights.json",
            self.base / "runtime_outputs/paper_execution/paper_trades.jsonl",
        ]:
            if path.is_file():
                path.unlink()
        r = clr.run_canonical_learning_cycle(
            project_root=self.base,
            runtime_root=self.runtime,
            source="test",
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["result"], "NO_ELIGIBLE_OUTCOMES")
        self.assertEqual(r["learning_updates_applied"], 0)

    def test_idempotent_second_cycle(self) -> None:
        # Stub heavy runners with deterministic docs
        with mock.patch.object(lom, "run_longitudinal_memory", return_value={"ok": True, "index": {"total_records": 2}}), mock.patch.object(
            aw,
            "run_adaptive_paper_weights",
            return_value={
                "ok": True,
                "document": {"weights": {"BUY_PAPER": {"new_weight": 1.02}}, "ticker_weights": {}},
            },
        ), mock.patch.object(
            rs,
            "run_rule_survival",
            return_value={"ok": True, "document": {"rules": {"R1": {"state": "TESTING"}}}},
        ), mock.patch.object(
            clr,
            "load_json_safe",
            side_effect=lambda path: (
                (
                    {"weights": {"BUY_PAPER": {"new_weight": 1.02}}, "ticker_weights": {}}
                    if "paper_action_weights" in str(path)
                    else {"rules": []}
                    if "knowledge" in str(path)
                    else {"rules": {"R1": {"state": "TESTING"}}}
                    if "rule_lifecycle" in str(path)
                    else None
                ),
                None,
            ),
        ):
            # Also need write of knowledge for fingerprint path — simplify: patch content compare
            first = clr.run_canonical_learning_cycle(
                project_root=self.base,
                runtime_root=self.runtime,
                source="test",
                force=False,
            )
            self.assertTrue(first["ok"])
            second = clr.run_canonical_learning_cycle(
                project_root=self.base,
                runtime_root=self.runtime,
                source="test",
                force=False,
            )
            self.assertTrue(second["ok"])
            self.assertEqual(second["result"], "DUPLICATE_SKIPPED")
            self.assertEqual(second["learning_updates_applied"], 0)
            self.assertGreaterEqual(second["duplicates_skipped"], 1)

    def test_duplicate_runtime_blocked(self) -> None:
        lock = self.runtime / "learning_state.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("", encoding="utf-8")
        calls = {"n": 0}
        real_flock = lp.fcntl.flock

        def flock_side_effect(fd: int, flags: int) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                return real_flock(fd, flags)
            raise BlockingIOError("locked")

        with lp.learning_state_lock(lock, blocking=True):
            with mock.patch.object(lp.fcntl, "flock", side_effect=flock_side_effect):
                # Reset depth path simulation: second acquire on different code path
                # Force non-nested by temporarily clearing depth after outer held via mock only
                pass
        # Direct non-blocking busy path
        with mock.patch.object(lp.fcntl, "flock", side_effect=BlockingIOError("busy")):
            with self.assertRaises(lp.LearningLockBusy):
                with lp.learning_state_lock(lock, blocking=False):
                    pass

    def test_concurrent_cycle_protection(self) -> None:
        with mock.patch.object(lom, "run_longitudinal_memory", return_value={"ok": True, "index": {"total_records": 1}}), mock.patch.object(
            aw, "run_adaptive_paper_weights", return_value={"ok": True, "document": {"weights": {}}}
        ), mock.patch.object(
            rs, "run_rule_survival", return_value={"ok": True, "document": {"rules": {}}}
        ), mock.patch.object(
            clr,
            "learning_state_lock",
            side_effect=lp.LearningLockBusy(self.runtime / "learning_state.lock"),
        ):
            r = clr.run_canonical_learning_cycle(
                project_root=self.base,
                runtime_root=self.runtime,
                source="concurrent",
                force=True,
                blocking_lock=False,
            )
        self.assertEqual(r["result"], "DUPLICATE_RUNTIME")
        self.assertFalse(r["ok"])

    def test_stale_lock_recovery(self) -> None:
        clr.write_pid(999999, root=self.runtime)
        out = clr.recover_stale_lock(root=self.runtime)
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"], "STALE_PID_CLEARED")
        self.assertIsNone(clr.read_pid(root=self.runtime))

    def test_atomic_write_preserves_previous(self) -> None:
        target = self.runtime / "atomic_demo.json"
        lp.atomic_write_json(target, {"v": 1})
        self.assertEqual(json.loads(target.read_text())["v"], 1)
        # Simulate crash mid-write: leftover tmp should not replace
        tmp = target.parent / f".{target.name}.partial.tmp"
        tmp.write_text("{broken", encoding="utf-8")
        lp.atomic_write_json(target, {"v": 2})
        self.assertEqual(json.loads(target.read_text())["v"], 2)
        self.assertTrue(target.is_file())

    def test_failure_does_not_reset_learning_state(self) -> None:
        weights = self.base / "runtime_outputs/adaptive_weights/paper_action_weights.json"
        before = weights.read_text(encoding="utf-8")
        with mock.patch.object(lom, "run_longitudinal_memory", side_effect=RuntimeError("boom")):
            r = clr.run_canonical_learning_cycle(
                project_root=self.base,
                runtime_root=self.runtime,
                source="test",
                force=True,
            )
            self.assertFalse(r["ok"])
            self.assertEqual(r["result"], "CYCLE_FAILED")
        after = weights.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_malformed_state_safe_stop(self) -> None:
        bad = self.base / "runtime_outputs/adaptive_weights/paper_action_weights.json"
        bad.write_text("{not-json", encoding="utf-8")
        r = clr.run_canonical_learning_cycle(
            project_root=self.base,
            runtime_root=self.runtime,
            source="test",
            force=True,
        )
        self.assertEqual(r["result"], "STATE_CORRUPTION")
        self.assertFalse(r["ok"])

    def test_heartbeat_freshness(self) -> None:
        clr.write_heartbeat(pid=os.getpid(), interval_sec=900, session_active=True, root=self.runtime)
        st = clr.status_snapshot(root=self.runtime)
        self.assertTrue(st["heartbeat_fresh"])

    def test_cycle_failure_visible_in_health(self) -> None:
        clr.write_status(
            {
                **clr._empty_status(),
                "last_result": "CYCLE_FAILED",
                "last_error": "RuntimeError: boom",
                "consecutive_failures": 2,
                "runtime_running": False,
            },
            root=self.runtime,
        )
        # Point status path
        with mock.patch.object(clr, "_root", return_value=self.runtime):
            h = clr.health_snapshot(root=self.runtime)
        self.assertEqual(h["overall_status"], "CYCLE_FAILED")

    def test_restart_preserves_last_applied(self) -> None:
        row = {
            "schema": clr.SCHEMA_LAST,
            "cycle_id": "CLR-TEST",
            "input_fingerprint": "abc",
            "applied": True,
            "updates_applied": 1,
        }
        lp.atomic_write_json(self.runtime / "last_applied.json", row)
        loaded = clr.load_last_applied(self.runtime)
        self.assertEqual(loaded["cycle_id"], "CLR-TEST")
        # Simulate stop/start status rewrite
        clr.write_status({**clr._empty_status(), "runtime_running": False}, root=self.runtime)
        loaded2 = clr.load_last_applied(self.runtime)
        self.assertEqual(loaded2["input_fingerprint"], "abc")

    def test_pde_reads_updated_learning_state(self) -> None:
        doc = {
            "weights": {"BUY_PAPER": {"new_weight": 1.1}},
            "ticker_weights": {},
        }
        scores = {"BUY_PAPER": 10.0, "HOLD_PAPER": 9.0}
        evidence: list[str] = []
        ctx = {"paper_action_weights": doc}
        from tae_paper_decision_engine import apply_adaptive_paper_weights

        apply_adaptive_paper_weights(scores, evidence, ctx, "MRK")
        self.assertAlmostEqual(scores["BUY_PAPER"], 11.0, places=5)

    def test_session_window_function(self) -> None:
        # Smoke: function returns bool without raising
        self.assertIn(clr.session_window_active(), (True, False))


class LearningPersistenceTest(unittest.TestCase):
    def test_atomic_write_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            lp.atomic_write_json(path, {"a": 1}, sort_keys=True)
            self.assertEqual(json.loads(path.read_text())["a"], 1)


if __name__ == "__main__":
    unittest.main()
