#!/usr/bin/env python3
"""Canonical dual-strategy activation tests — PAPER_ONLY | NO_BROKER | NO_DAEMON."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_canonical_dual_strategy as dual
import tae_parallel_paper_config as ppc
import tae_parallel_paper_runtime as pprun
import tae_paper_execution as pe


def _marks(prices: dict[str, float], *, score: float = 90.0, signal: str = "STRONG BUY"):
    def provider(tickers):
        out = {}
        for t in tickers or list(prices):
            t = str(t).upper()
            if t not in prices:
                out[t] = {
                    "mark_price": None,
                    "score": 10.0,
                    "signal": "WAIT",
                    "eligible": False,
                    "mark_freshness": "MARK_UNAVAILABLE",
                    "data_fresh": False,
                    "mark_status": "MARK_UNAVAILABLE",
                }
                continue
            out[t] = {
                "mark_price": prices[t],
                "score": score,
                "signal": signal,
                "eligible": True,
                "mark_freshness": "FRESH",
                "mark_age_seconds": 0.0,
                "data_fresh": True,
                "mark_status": "FRESH",
            }
        return out

    return provider


class CanonicalDualStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "parallel_paper"
        self.v1_dir = Path(self.tmp) / "paper_execution"
        self.v1_dir.mkdir(parents=True)
        self.v1_portfolio = self.v1_dir / "paper_portfolio.json"
        self.v1_portfolio.write_text(
            json.dumps(
                {
                    "cash": 20000.0,
                    "total_value": 30000.0,
                    "realized_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "open_positions_value": 10000.0,
                    "validation_capital_base": 30000.0,
                    "starting_value": 30000.0,
                    "positions": {
                        "AAA": {"shares": 10, "avg_price": 100.0, "current_price": 100.0}
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.cfg_path = Path(self.tmp) / "cfg.json"
        self.cfg_path.write_text(
            json.dumps(
                {
                    "PARALLEL_PAPER_ENABLED": True,
                    "V1_PARALLEL_ENABLED": True,
                    "V2_PARALLEL_ENABLED": True,
                    "V1_STARTING_CAPITAL": 30000,
                    "V2_STARTING_CAPITAL": 30000,
                    "V1_MIN_CASH_RESERVE": 500,
                    "V2_MIN_CASH_RESERVE": 500,
                    "V2_ACTIVATION_SCOPE": "PARALLEL_PAPER",
                    "V2_LIVE_ENABLED": False,
                    "V2_CANONICAL_PAPER_ENABLED": False,
                    "V2_PARALLEL_PAPER_ENABLED": True,
                    "FAIL_ISOLATION_ENABLED": True,
                    "WATCHLIST": ["AAA", "BBB"],
                }
            ),
            encoding="utf-8",
        )
        self._patchers = [
            mock.patch.object(ppc, "ROOT", self.root),
            mock.patch.object(ppc, "V1_DIR", self.root / "v1"),
            mock.patch.object(ppc, "V2_DIR", self.root / "v2"),
            mock.patch.object(ppc, "REPORTS_DIR", self.root / "reports"),
            mock.patch.object(ppc, "CONFIG_PATH", self.cfg_path),
            mock.patch.object(pe, "OUTPUT_DIR", self.v1_dir),
            mock.patch.object(pe, "PORTFOLIO_JSON", self.v1_portfolio),
            mock.patch.object(dual, "V1_EQUITY_JSONL", self.v1_dir / "paper_daily_equity.jsonl"),
            mock.patch.object(
                dual, "V2_EQUITY_JSONL", self.root / "v2" / "journals" / "daily_equity.jsonl"
            ),
            mock.patch.object(dual, "REPORT_JSON", Path(self.tmp) / "dual_report.json"),
            mock.patch.object(dual, "REPORT_MD", Path(self.tmp) / "dual_report.md"),
        ]
        for p in self._patchers:
            p.start()
        self.cfg = ppc.load_parallel_paper_config()
        pprun.bootstrap(self.cfg)
        paths = ppc.paths(self.cfg)
        # Seed isolated V2 book
        v2_port = {
            "cash": 30000.0,
            "account_value": 30000.0,
            "total_value": 30000.0,
            "starting_capital": 30000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "positions": {},
            "strategy_id": "V2",
        }
        pprun.save_portfolio(paths["v2_portfolio"], v2_port)

    def tearDown(self) -> None:
        for p in reversed(self._patchers):
            p.stop()

    def test_01_no_daemon_module_required(self) -> None:
        # Daemon file must remain unrestored (orchestration intentionally retired)
        self.assertFalse(Path("tae_parallel_paper_daemon.py").is_file())
        self.assertFalse(Path("tae_parallel_paper_autostart.py").is_file())

    def test_02_separate_capital_bases(self) -> None:
        cfg = ppc.load_parallel_paper_config()
        self.assertEqual(float(cfg["V1_STARTING_CAPITAL"]), 30000.0)
        self.assertEqual(float(cfg["V2_STARTING_CAPITAL"]), 30000.0)
        self.assertEqual(cfg["V2_ACTIVATION_SCOPE"], "PARALLEL_PAPER")
        self.assertFalse(bool(cfg.get("V2_CANONICAL_PAPER_ENABLED")))

    def test_03_v1_stamp_does_not_change_cash(self) -> None:
        before = json.loads(self.v1_portfolio.read_text(encoding="utf-8"))
        out = dual.stamp_v1_canonical_portfolio()
        after = json.loads(self.v1_portfolio.read_text(encoding="utf-8"))
        self.assertTrue(out["ok"])
        self.assertEqual(after["strategy_id"], "V1")
        self.assertEqual(float(after["cash"]), float(before["cash"]))
        self.assertEqual(after["portfolio_id"], "canonical_paper_v1")

    def test_04_v2_cycle_does_not_mutate_v1_cash(self) -> None:
        v1_before = float(json.loads(self.v1_portfolio.read_text())["cash"])
        out = dual.run_v2_challenger_cycle(mark_provider=_marks({"AAA": 100.0, "BBB": 50.0}))
        v1_after = float(json.loads(self.v1_portfolio.read_text())["cash"])
        self.assertEqual(v1_before, v1_after)
        self.assertTrue(out.get("v1_cash_untouched"))
        self.assertEqual(out.get("strategy_id"), "V2")
        self.assertGreaterEqual(int(out.get("decisions") or 0), 1)
        rows = out.get("decision_rows") or []
        self.assertTrue(all(r.get("strategy_id") == "V2" for r in rows))

    def test_05_same_ticker_independent_positions(self) -> None:
        # V1 already holds AAA; V2 starts flat then may OPEN AAA independently
        out = dual.run_v2_challenger_cycle(mark_provider=_marks({"AAA": 95.0, "BBB": 40.0}))
        v1 = json.loads(self.v1_portfolio.read_text())
        v2 = pprun.load_portfolio(ppc.paths()["v2_portfolio"], starting=30000.0, arm="v2")
        self.assertIn("AAA", v1.get("positions") or {})
        # V2 may or may not open depending on gates; isolation: books differ
        self.assertNotEqual(
            Path(pe.PORTFOLIO_JSON).resolve(),
            Path(ppc.paths()["v2_portfolio"]).resolve(),
        )
        self.assertEqual(v1.get("strategy_id") or "V1", "V1")
        # After challenger cycle, V2 portfolio stamped
        self.assertEqual(v2.get("strategy_id"), "V2")
        self.assertTrue(out.get("ok") or out.get("accounting_ok"))

    def test_06_learning_events_arm_local(self) -> None:
        paths = ppc.paths()
        # Seed a V2 learning event and ensure V1 learning state untouched
        v1_learn = paths.get("v1_learning_state")
        before = v1_learn.read_text(encoding="utf-8") if v1_learn and v1_learn.is_file() else ""
        dual.run_v2_challenger_cycle(mark_provider=_marks({"AAA": 100.0}))
        after = v1_learn.read_text(encoding="utf-8") if v1_learn and v1_learn.is_file() else ""
        self.assertEqual(before, after)
        v2_events = paths.get("v2_learning_events")
        # File may be empty if no fills — still must not write V1
        if v2_events and v2_events.is_file():
            for line in v2_events.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self.assertEqual(str(row.get("arm") or "").upper(), "V2")

    def test_07_no_cross_strategy_dedup_paths(self) -> None:
        p = ppc.paths()
        self.assertNotEqual(Path(p["v2_portfolio"]).resolve(), Path(pe.PORTFOLIO_JSON).resolve())
        self.assertNotEqual(Path(p["v2_decisions"]).resolve(), Path(pe.OUTPUT_DIR / "x").resolve())

    def test_08_fpc_hook_writes_comparative_report(self) -> None:
        out = dual.run_dual_strategy_for_fpc(orchestration_run_id="TEST-DUAL")
        self.assertTrue(out.get("v1_ok"))
        report = json.loads(Path(self.tmp, "dual_report.json").read_text(encoding="utf-8"))
        self.assertFalse(report.get("daemon_restored"))
        self.assertFalse(report.get("launchagent_restored"))
        self.assertFalse(report.get("duplicate_runtime"))
        self.assertEqual(report["capital"]["v1_capital_base"], 30000.0)
        self.assertEqual(report["capital"]["v2_capital_base"], 30000.0)
        self.assertEqual(report["isolation"]["learning"], "PASS")

    def test_09_trailing_symbols_available_for_v2(self) -> None:
        from tae_strategy_v2_trailing import (
            V2_PROFIT_TRAILING_REASON,
            evaluate_position_exit,
        )

        self.assertEqual(V2_PROFIT_TRAILING_REASON, "V2_PROFIT_TRAILING_5_2")
        self.assertTrue(callable(evaluate_position_exit))
        # LIVE SSOT untouched
        from core import trailing as live_trail

        self.assertFalse(hasattr(live_trail, "V2_PROFIT_TRAILING_REASON"))
        self.assertTrue(hasattr(live_trail, "update_trailing_state"))


if __name__ == "__main__":
    unittest.main()
