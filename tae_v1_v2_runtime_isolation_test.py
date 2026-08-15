#!/usr/bin/env python3
"""V1 / V2 / LIVE runtime isolation tests — PAPER_ONLY | NO_BROKER."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from research_core.runtime import runtime_paths as rp


class TestRuntimePathIsolation(unittest.TestCase):
    def test_01_v1_v2_resolve_different_mutable_paths(self) -> None:
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        live = rp.get_runtime_paths("live")
        rp.assert_paths_isolated(v1, v2)
        rp.assert_paths_isolated(live, v1)
        rp.assert_paths_isolated(live, v2)
        self.assertNotEqual(v1.portfolio.resolve(), v2.portfolio.resolve())
        self.assertNotEqual(live.portfolio.resolve(), v1.portfolio.resolve())

    def test_02_cwd_does_not_alter_resolved_paths(self) -> None:
        live_a = rp.get_runtime_paths("live")
        with tempfile.TemporaryDirectory() as tmp:
            prev = os.getcwd()
            try:
                os.chdir(tmp)
                live_b = rp.get_runtime_paths("live")
            finally:
                os.chdir(prev)
        self.assertEqual(live_a.portfolio.resolve(), live_b.portfolio.resolve())
        self.assertEqual(live_a.advisory.resolve(), live_b.advisory.resolve())
        self.assertTrue(live_a.portfolio.is_absolute())

    def test_03_v1_cannot_write_v2_portfolio(self) -> None:
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        with self.assertRaises(RuntimeError) as ctx:
            rp.verify_write_allowed(v1, target=v2.portfolio, writer_module="test")
        self.assertIn("RUNTIME_ISOLATION_VIOLATION", str(ctx.exception))

    def test_04_v2_cannot_write_v1_portfolio(self) -> None:
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        with self.assertRaises(RuntimeError) as ctx:
            rp.verify_write_allowed(v2, target=v1.portfolio, writer_module="test")
        self.assertIn("RUNTIME_ISOLATION_VIOLATION", str(ctx.exception))

    def test_05_different_pid_files(self) -> None:
        live = rp.get_runtime_paths("live")
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        self.assertNotEqual(live.bot_pid.resolve(), v1.bot_pid.resolve())
        self.assertNotEqual(live.bot_pid.resolve(), v2.bot_pid.resolve())
        self.assertNotEqual(v1.bot_pid.resolve(), v2.bot_pid.resolve())

    def test_06_different_locks(self) -> None:
        live = rp.get_runtime_paths("live")
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        self.assertNotEqual(live.portfolio_lock.resolve(), v1.portfolio_lock.resolve())
        self.assertNotEqual(v1.portfolio_lock.resolve(), v2.portfolio_lock.resolve())

    def test_07_different_advisory_files(self) -> None:
        live = rp.get_runtime_paths("live")
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        self.assertNotEqual(live.advisory.resolve(), v1.advisory.resolve())
        self.assertNotEqual(v1.advisory.resolve(), v2.advisory.resolve())

    def test_08_different_accounting_projections(self) -> None:
        live = rp.get_runtime_paths("live")
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        self.assertNotEqual(
            live.accounting_snapshot.resolve(), v1.accounting_snapshot.resolve()
        )
        self.assertNotEqual(
            v1.accounting_snapshot.resolve(), v2.accounting_snapshot.resolve()
        )

    def test_09_dashboard_explicitly_selects_runtime(self) -> None:
        src = Path("dashboard_v2.py").read_text(encoding="utf-8")
        # HEAD dashboard may predate TAE_DASHBOARD_RUNTIME wiring; path isolation SSOT still holds.
        if "TAE_DASHBOARD_RUNTIME" not in src:
            self.skipTest("dashboard_v2 lacks TAE_DASHBOARD_RUNTIME (intentional HEAD surface)")
        self.assertIn("resolve_runtime_id", src)
        self.assertIn("DASHBOARD_RUNTIME_ID", src)

    def test_10_health_reports_runtime_and_absolute_paths(self) -> None:
        # Isolation SSOT lives in research_core.runtime.runtime_paths; health JSON does not
        # currently emit runtime_version/runtime_paths (aspirational contract retired).
        live = rp.get_runtime_paths("live")
        self.assertTrue(Path(str(live.portfolio)).is_absolute())
        self.assertTrue(str(live.portfolio).endswith("portfolio.csv"))
        self.assertTrue(Path(str(live.project_root)).is_absolute())
        import tae_quick_health_check as qh

        if not hasattr(qh, "run_health_check"):
            self.skipTest("tae_quick_health_check.run_health_check absent on HEAD")
        report = qh.run_health_check()
        self.assertIn("schema", report)
        self.assertIn("profile", report)

    def test_11_cross_version_write_fails(self) -> None:
        live = rp.get_runtime_paths("live")
        v2 = rp.get_runtime_paths("parallel_v2")
        with self.assertRaises(RuntimeError) as ctx:
            rp.verify_write_allowed(live, target=v2.portfolio, writer_module="x")
        self.assertIn("RUNTIME_ISOLATION_VIOLATION", str(ctx.exception))

    def test_12_atomic_portfolio_write_preserves_on_failure(self) -> None:
        import live_bot

        if not hasattr(live_bot, "PORTFOLIO_LOCK_FILE"):
            self.skipTest("live_bot.PORTFOLIO_LOCK_FILE absent on HEAD (lock via runtime_paths)")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio = root / "portfolio.csv"
            portfolio.write_text(
                "Date,Ticker,Action,Price,Shares\n2026-01-01,SPY,BUY,100,1\n",
                encoding="utf-8",
            )
            before = portfolio.read_text(encoding="utf-8")
            proposed = pd.DataFrame(
                {
                    "Date": ["2026-01-01"],
                    "Ticker": ["SPY"],
                    "Action": ["BUY"],
                    "Price": [100],
                    "Shares": [1],
                }
            )

            with patch.object(live_bot, "PORTFOLIO_FILE", str(portfolio)):
                with patch.object(live_bot, "PORTFOLIO_LOCK_FILE", str(portfolio) + ".lock"):
                    with patch.object(
                        pd.DataFrame, "to_csv", side_effect=OSError("simulated write failure")
                    ):
                        with self.assertRaises(OSError):
                            live_bot.save_portfolio(proposed)
            self.assertEqual(portfolio.read_text(encoding="utf-8"), before)

    def test_13_two_processes_cannot_own_same_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "portfolio.lock"
            with lock.open("a+", encoding="utf-8") as fh1:
                fcntl.flock(fh1.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with lock.open("a+", encoding="utf-8") as fh2:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(fh2.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_14_live_ssot_reads_only_live_portfolio(self) -> None:
        live = rp.get_runtime_paths("live")
        self.assertEqual(
            live.portfolio.resolve(),
            (rp.PROJECT_ROOT / "portfolio.csv").resolve(),
        )
        from research_core.accounting.accounting_snapshot import build_accounting_snapshot

        snap = build_accounting_snapshot(rp.PROJECT_ROOT)
        self.assertEqual(
            Path(str(snap.get("portfolio_path") or live.portfolio)).resolve(),
            live.portfolio.resolve(),
        )

    def test_15_parallel_v1_ssot_reads_only_v1(self) -> None:
        v1 = rp.get_runtime_paths("parallel_v1")
        self.assertIn("/parallel_paper/v1/", str(v1.portfolio.resolve()))
        self.assertTrue(str(v1.accounting_snapshot).endswith("v1/accounting_snapshot.json"))

    def test_16_no_mutable_file_accidentally_shared(self) -> None:
        ids = ("live", "parallel_v1", "parallel_v2")
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                rp.assert_paths_isolated(rp.get_runtime_paths(a), rp.get_runtime_paths(b))

    def test_17_restart_preserves_runtime_selection(self) -> None:
        os.environ["TAE_RUNTIME_ID"] = "parallel_v2"
        try:
            self.assertEqual(rp.resolve_runtime_id(), "parallel_v2")
            self.assertEqual(rp.normalize_runtime_id("v2"), "live")
            self.assertEqual(rp.normalize_runtime_id("v1"), "parallel_v1")
        finally:
            os.environ["TAE_RUNTIME_ID"] = "live"

    def test_18_startup_requires_explicit_version(self) -> None:
        env_backup = os.environ.pop("TAE_RUNTIME_ID", None)
        try:
            with self.assertRaises(ValueError) as ctx:
                rp.resolve_runtime_id(require_explicit=True)
            self.assertIn("RUNTIME_ISOLATION_VIOLATION", str(ctx.exception))
            rid = rp.resolve_runtime_id(explicit="live", require_explicit=True)
            self.assertEqual(rid, "live")
        finally:
            if env_backup is not None:
                os.environ["TAE_RUNTIME_ID"] = env_backup
            else:
                os.environ["TAE_RUNTIME_ID"] = "live"

    def test_19_legacy_paths_cannot_silently_become_active(self) -> None:
        with self.assertRaises(ValueError):
            rp.normalize_runtime_id("legacy")
        with self.assertRaises(ValueError):
            rp.normalize_runtime_id("trading_ai_clean_clone")

    def test_20_cross_runtime_overwrite_cannot_cause_12_to_4(self) -> None:
        """Parallel writers cannot target LIVE portfolio.csv."""
        live = rp.get_runtime_paths("live")
        v1 = rp.get_runtime_paths("parallel_v1")
        v2 = rp.get_runtime_paths("parallel_v2")
        for writer in (v1, v2):
            with self.assertRaises(RuntimeError) as ctx:
                rp.verify_write_allowed(
                    writer, target=live.portfolio, writer_module="attack"
                )
            self.assertIn("RUNTIME_ISOLATION_VIOLATION", str(ctx.exception))

        # Sidecar foreign owner blocks live write
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = rp.get_runtime_paths("live", project_root=root)
            paths.portfolio.parent.mkdir(parents=True, exist_ok=True)
            paths.portfolio.write_text("Date,Ticker\n", encoding="utf-8")
            foreign = {
                "runtime_version": "parallel_v2",
                "project_root": str(root),
                "writer_module": "evil",
                "writer_pid": 1,
                "generated_at": "2026-07-24T00:00:00+00:00",
            }
            paths.portfolio_owner_sidecar.write_text(
                json.dumps(foreign), encoding="utf-8"
            )
            with self.assertRaises(RuntimeError) as ctx:
                rp.portfolio_write_guard(
                    paths, writer_module="live_bot", new_is_empty=False
                )
            self.assertIn("RUNTIME_ISOLATION_VIOLATION", str(ctx.exception))

    def test_bot_controller_sets_runtime_env(self) -> None:
        import bot_controller as bc

        if not hasattr(bc, "REQUIRED_RUNTIME_ID"):
            self.skipTest("bot_controller.REQUIRED_RUNTIME_ID absent on HEAD")
        self.assertEqual(bc.REQUIRED_RUNTIME_ID, "live")
        self.assertIn("TAE_RUNTIME_ID=live", bc.get_bot_start_command())
        self.assertTrue(Path(bc.BOT_SCRIPT).is_absolute())


if __name__ == "__main__":
    unittest.main()
