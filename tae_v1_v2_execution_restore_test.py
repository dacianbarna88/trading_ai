#!/usr/bin/env python3
"""Regression tests: restore isolated executable V1/V2 parallel PAPER arms."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_parallel_paper_config as ppc
import tae_parallel_paper_runtime as pprun


def _marks(prices: dict[str, float], *, score: float = 90.0, signal: str = "STRONG BUY"):
    def provider(tickers):
        out = {}
        for t in tickers or list(prices):
            t = str(t).upper()
            if t not in prices:
                out[t] = {
                    "mark_price": None,
                    "score": score,
                    "signal": "WAIT",
                    "eligible": False,
                    "mark_freshness": "MARK_UNAVAILABLE",
                    "data_fresh": False,
                    "mark_status": "MARK_UNAVAILABLE",
                }
                continue
            sig = str(signal).upper()
            eligible = sig in {"STRONG BUY", "BUY"}
            out[t] = {
                "mark_price": prices[t],
                "score": score if eligible else min(float(score), 40.0),
                "signal": signal,
                "eligible": eligible,
                "mark_freshness": "FRESH",
                "mark_age_seconds": 0.0,
                "data_fresh": True,
                "mark_status": "FRESH",
            }
        return out

    return provider


class V1V2ExecutionRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "parallel_paper"
        self._patchers = [
            mock.patch.object(ppc, "ROOT", self.root),
            mock.patch.object(ppc, "V1_DIR", self.root / "v1"),
            mock.patch.object(ppc, "V2_DIR", self.root / "v2"),
            mock.patch.object(ppc, "REPORTS_DIR", self.root / "reports"),
        ]
        for p in self._patchers:
            p.start()
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
                    "V1_MODE": "ISOLATED_PARALLEL_PAPER",
                    "V2_MODE": "ISOLATED_PARALLEL_PAPER",
                    "WATCHLIST": ["AAA", "BBB"],
                }
            ),
            encoding="utf-8",
        )
        self.canonical = Path(self.tmp) / "canonical_paper.json"
        self.canonical.write_text(
            json.dumps(
                {
                    "cash": 17000.0,
                    "total_value": 29000.0,
                    "realized_pnl": -100.0,
                    "unrealized_pnl": 50.0,
                    "open_positions_value": 12000.0,
                    "starting_value": 30000.0,
                    "positions": {"ZZZ": {"shares": 1, "avg_price": 100, "current_price": 110}},
                    "created_at": "2026-07-01T00:00:00Z",
                    "updated_at": "2026-07-24T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        for p in self._patchers:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cfg(self, **kw):
        c = ppc.load_parallel_paper_config(self.cfg_path)
        c.update(kw)
        return c

    def test_v1_buy_executor_fill_cash_position_canonical_unchanged(self):
        from tae_test_isolation import isolate_adaptive_deployment

        # DRAFT adaptive so AAA is in scope; live canary would BLOCKED_TICKER_SCOPE.
        isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )
        cfg = self._cfg()
        pprun.bootstrap(cfg)
        p = ppc.paths()
        before_canon = hashlib.sha256(self.canonical.read_bytes()).hexdigest()
        # Point optional canonical path at temp (must stay untouched)
        cfg["CANONICAL_PAPER_PORTFOLIO"] = str(self.canonical)
        live_csv = Path(self.tmp) / "portfolio.csv"
        live_csv.write_text("Date,Ticker,Action\n", encoding="utf-8")
        before_live = hashlib.sha256(live_csv.read_bytes()).hexdigest()
        before_v1 = hashlib.sha256(p["v1_portfolio"].read_bytes()).hexdigest() if p["v1_portfolio"].is_file() else None

        v1_before = pprun.load_portfolio(p["v1_portfolio"], starting=30000, arm="V1")
        cash_before = float(v1_before["cash"])
        c = pprun.run_cycle(cfg=cfg, mark_provider=_marks({"AAA": 100.0}), tickers=["AAA"])
        self.assertTrue(c.get("ok"))
        d1 = [d for d in c.get("v1_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d1["action"], "BUY")
        self.assertTrue(d1.get("executor_called") or d1.get("mutates_portfolio"))
        self.assertEqual(d1.get("v1_mode"), "ISOLATED_PARALLEL_PAPER")

        v1 = json.loads(p["v1_portfolio"].read_text(encoding="utf-8"))
        self.assertIn("AAA", v1["positions"])
        self.assertLess(float(v1["cash"]), cash_before)
        self.assertTrue(p["v1_trades"].is_file())
        trades = p["v1_trades"].read_text(encoding="utf-8")
        self.assertIn('"action": "BUY"', trades)
        self.assertIn("AAA", trades)
        execs = p["v1_executions"].read_text(encoding="utf-8")
        self.assertIn('"executed": true', execs.lower().replace("True", "true") if False else execs)

        after_v1 = hashlib.sha256(p["v1_portfolio"].read_bytes()).hexdigest()
        self.assertNotEqual(before_v1, after_v1)
        self.assertEqual(hashlib.sha256(self.canonical.read_bytes()).hexdigest(), before_canon)
        self.assertEqual(hashlib.sha256(live_csv.read_bytes()).hexdigest(), before_live)

    def test_v1_take_profit_sell(self):
        """V1's take-profit exit is now an armed trailing stop (Phase 1 of
        the profit-improvement sprint), not a hard +5% cap: at +6% V1 must
        ARM and HOLD (letting a winner run), then only sell once price
        pulls back 2% off the peak it reaches. This replaced the old fixed
        +5%/-3% bracket after an audit found it produced negative
        expectancy at V1's real ~28.6% win rate (a large win capped at
        exactly +5% can't offset frequent -3% losses) — see
        tae_strategy_v1_trailing.py.
        """
        cfg = self._cfg(WATCHLIST=["AAA"])
        pprun.bootstrap(cfg)
        p = ppc.paths()
        # Seed position then mark above the +5% arm threshold.
        port = pprun.empty_portfolio(30000, arm="V1")
        shares, after = __import__("tae_paper_execution", fromlist=["_buy_shares"])._buy_shares(
            port, "AAA", 1000.0, 100.0
        )
        self.assertGreater(shares, 0)
        after["strategy_version"] = "V1"
        after["avg_price"] = 100.0
        pprun.save_portfolio(p["v1_portfolio"], port)

        # Cycle 1: +6% — must ARM trailing and HOLD, not sell at a fixed cap.
        c1 = pprun.run_cycle(
            cfg=cfg, mark_provider=_marks({"AAA": 106.0}, signal="WAIT"), tickers=["AAA"]
        )
        d1 = [d for d in c1.get("v1_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d1["action"], "HOLD")
        v1_armed = json.loads(p["v1_portfolio"].read_text(encoding="utf-8"))
        pos_armed = v1_armed["positions"]["AAA"]
        self.assertTrue(pos_armed["trailing_armed"])
        self.assertAlmostEqual(pos_armed["highest_price"], 106.0)

        # Cycle 2: price rises further to a new peak (stop ratchets up, still holds).
        c2 = pprun.run_cycle(
            cfg=cfg, mark_provider=_marks({"AAA": 112.0}, signal="WAIT"), tickers=["AAA"]
        )
        d2 = [d for d in c2.get("v1_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d2["action"], "HOLD")

        # Cycle 3: pullback below the trailing stop (112 * 0.98 = 109.76) sells.
        c3 = pprun.run_cycle(
            cfg=cfg, mark_provider=_marks({"AAA": 109.0}, signal="WAIT"), tickers=["AAA"]
        )
        d3 = [d for d in c3.get("v1_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d3["action"], "SELL")
        self.assertIn("TRAILING", str(d3.get("reason") or "").upper())
        v1 = json.loads(p["v1_portfolio"].read_text(encoding="utf-8"))
        self.assertNotIn("AAA", v1.get("positions") or {})
        self.assertGreater(
            float(v1.get("realized_pnl") or 0),
            0,
            "should lock in a gain well above the old flat +5% cap (~+9%, not +5%)",
        )

    def test_v1_stop_loss_sell(self):
        cfg = self._cfg(WATCHLIST=["AAA"])
        pprun.bootstrap(cfg)
        p = ppc.paths()
        port = pprun.empty_portfolio(30000, arm="V1")
        __import__("tae_paper_execution", fromlist=["_buy_shares"])._buy_shares(port, "AAA", 1000.0, 100.0)
        port["positions"]["AAA"]["strategy_version"] = "V1"
        pprun.save_portfolio(p["v1_portfolio"], port)
        c = pprun.run_cycle(
            cfg=cfg, mark_provider=_marks({"AAA": 96.0}, signal="WAIT"), tickers=["AAA"]
        )
        d1 = [d for d in c.get("v1_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d1["action"], "SELL")
        self.assertIn("STOP", str(d1.get("reason") or "").upper())
        v1 = json.loads(p["v1_portfolio"].read_text(encoding="utf-8"))
        self.assertNotIn("AAA", v1.get("positions") or {})
        self.assertLess(float(v1.get("realized_pnl") or 0), 0)

    def test_v2_open_add_close_plus10_and_minus5(self):
        from tae_test_isolation import isolate_adaptive_deployment

        isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )
        cfg = self._cfg(WATCHLIST=["AAA"])
        pprun.bootstrap(cfg)
        p = ppc.paths()
        # OPEN
        c1 = pprun.run_cycle(cfg=cfg, mark_provider=_marks({"AAA": 100.0}), tickers=["AAA"])
        d2 = [d for d in c1.get("v2_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d2["action"], "OPEN")
        self.assertTrue(d2.get("executor_called") or d2.get("mutates_portfolio"))
        v2 = json.loads(p["v2_portfolio"].read_text(encoding="utf-8"))
        self.assertIn("AAA", v2["positions"])
        avg = float(v2["positions"]["AAA"]["avg_price"])
        # ADD: drop 3%
        c2 = pprun.run_cycle(cfg=cfg, mark_provider=_marks({"AAA": avg * 0.96}), tickers=["AAA"])
        d_add = [d for d in c2.get("v2_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d_add["action"], "ADD")
        v2b = json.loads(p["v2_portfolio"].read_text(encoding="utf-8"))
        self.assertGreater(float(v2b["positions"]["AAA"]["shares"]), float(v2["positions"]["AAA"]["shares"]))
        # CLOSE +10% — WAIT prevents entry OPEN from overwriting manage CLOSE
        avg2 = float(v2b["positions"]["AAA"]["avg_price"])
        c3 = pprun.run_cycle(
            cfg=cfg, mark_provider=_marks({"AAA": avg2 * 1.11}, signal="WAIT"), tickers=["AAA"]
        )
        d_close = [d for d in c3.get("v2_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d_close["action"], "CLOSE")
        self.assertIn("PROFIT", str(d_close.get("reason") or "").upper())

        # Fresh OPEN then −6%: V2 keeps ADD path while accumulating.
        # Price drawdown (−3%/−5%) is informational — not HARD_RISK CLOSE (SSOT hard_risk_adapter).
        c4 = pprun.run_cycle(cfg=cfg, mark_provider=_marks({"BBB": 50.0}), tickers=["BBB"])
        self.assertEqual([d for d in c4.get("v2_decisions") or [] if d.get("ticker") == "BBB"][0]["action"], "OPEN")
        v2c = json.loads(p["v2_portfolio"].read_text(encoding="utf-8"))
        avg_b = float(v2c["positions"]["BBB"]["avg_price"])
        c5 = pprun.run_cycle(
            cfg=cfg, mark_provider=_marks({"BBB": avg_b * 0.94}, signal="WAIT"), tickers=["BBB"]
        )
        d_m5 = [d for d in c5.get("v2_decisions") or [] if d.get("ticker") == "BBB"][0]
        self.assertIn(d_m5["action"], {"ADD", "HOLD", "STOP_ACCUMULATION"})
        self.assertNotEqual(d_m5["action"], "CLOSE")
        self.assertNotIn("HARD_RISK", str(d_m5.get("reason") or "").upper())
        # Position still open — no cross-arm forced liquidation on informational drawdown
        v2d = json.loads(p["v2_portfolio"].read_text(encoding="utf-8"))
        self.assertIn("BBB", v2d.get("positions") or {})

    def test_mark_freshness_no_fake_zero_upnl(self):
        port = pprun.empty_portfolio(30000, arm="V1")
        port["positions"] = {
            "AAA": {
                "ticker": "AAA",
                "shares": 10.0,
                "avg_price": 100.0,
                "current_price": 100.0,
                "strategy_version": "V1",
            }
        }
        # Missing mark must NOT silently keep avg as fresh MTM inventing certainty
        av, inv = pprun.portfolio_mtm(port, marks={}, mark_meta={})
        self.assertEqual(port["positions"]["AAA"]["mark_status"], "MARK_UNAVAILABLE")
        self.assertIsNone(port["positions"]["AAA"].get("unrealized_pnl"))
        # Fresh different mark updates current_price != avg
        av2, _ = pprun.portfolio_mtm(
            port,
            marks={"AAA": 110.0},
            mark_meta={"AAA": {"mark_freshness": "FRESH", "mark_timestamp": "2026-07-25T00:00:00Z"}},
        )
        self.assertEqual(port["positions"]["AAA"]["current_price"], 110.0)
        self.assertNotEqual(port["positions"]["AAA"]["current_price"], port["positions"]["AAA"]["avg_price"])
        self.assertGreater(port["unrealized_pnl"], 0)

        # Arm holds with MARK_UNAVAILABLE instead of false exit
        cfg = self._cfg(WATCHLIST=["AAA"])
        pprun.bootstrap(cfg)
        p = ppc.paths()
        pprun.save_portfolio(p["v1_portfolio"], port)
        c = pprun.run_cycle(
            cfg=cfg,
            mark_provider=_marks({}),  # no usable prices
            tickers=["AAA"],
        )
        d1 = [d for d in c.get("v1_decisions") or [] if d.get("ticker") == "AAA"][0]
        self.assertEqual(d1["action"], "HOLD")
        self.assertIn(d1.get("reason"), {"MARK_UNAVAILABLE", "MARK_STALE"})

    def test_isolation_both_mutate_canonical_unchanged(self):
        from tae_test_isolation import isolate_adaptive_deployment

        isolate_adaptive_deployment(
            self, extra_env={"DEFER_NEW_BUY_DURING_OPENING_NOISE": "false"}
        )
        cfg = self._cfg(WATCHLIST=["AAA", "BBB"])
        cfg["CANONICAL_PAPER_PORTFOLIO"] = str(self.canonical)
        pprun.bootstrap(cfg)
        p = ppc.paths()
        before_c = hashlib.sha256(self.canonical.read_bytes()).hexdigest()
        before_v1 = hashlib.sha256(p["v1_portfolio"].read_bytes()).hexdigest()
        before_v2 = hashlib.sha256(p["v2_portfolio"].read_bytes()).hexdigest()
        pprun.run_cycle(cfg=cfg, mark_provider=_marks({"AAA": 100.0, "BBB": 50.0}), tickers=["AAA", "BBB"])
        after_v1 = hashlib.sha256(p["v1_portfolio"].read_bytes()).hexdigest()
        after_v2 = hashlib.sha256(p["v2_portfolio"].read_bytes()).hexdigest()
        after_c = hashlib.sha256(self.canonical.read_bytes()).hexdigest()
        self.assertNotEqual(before_v1, after_v1)
        self.assertNotEqual(before_v2, after_v2)
        self.assertEqual(before_c, after_c)
        # No cross arm in journals
        for line in p["v1_decisions"].read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.assertEqual(json.loads(line).get("arm"), "V1")
        for line in p["v2_decisions"].read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.assertEqual(json.loads(line).get("arm"), "V2")

    def test_default_config_is_isolated_not_mirror(self):
        cfg = ppc.load_parallel_paper_config(self.cfg_path)
        self.assertEqual(cfg["V1_MODE"], "ISOLATED_PARALLEL_PAPER")
        self.assertFalse(cfg.get("V2_LIVE_ENABLED"))


if __name__ == "__main__":
    unittest.main()
