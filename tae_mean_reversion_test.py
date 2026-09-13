#!/usr/bin/env python3
"""
Regression coverage for the new mean-reversion arm
(tae_mean_reversion_signal.py + tae_parallel_paper_mean_reversion.py).

Context: 2026-09-13 audit found V1/V2/V3/exp_short_margin all decide off
one shared trend-following score (tae_score_decile_backtest.py /
tae_cross_arm_overlap_report.py). This arm trades a backtested, genuinely
different signal (buy statistically oversold, sell on reversion to mean)
via a new, isolated module that reuses only already-generic shared
infrastructure (default_mark_provider/portfolio_mtm/empty_portfolio,
tae_paper_execution._buy_shares/_sell_shares) — it never imports or is
imported by V1/V2/V3/exp_short_margin's own decision code.
"""

from __future__ import annotations

import math
import unittest

import tae_mean_reversion_signal as mrsig


def _noisy_baseline(n: int = 34) -> list[float]:
    """Deterministic, low-amplitude oscillation -- a flat/zero-variance
    baseline makes the z-score threshold degenerate (any tiny move reads
    as many standard deviations), which isn't representative of a real
    ticker's day-to-day noise."""
    return [100.0 + 0.5 * math.sin(i * 0.9) for i in range(n)]


def _fresh_portfolio(cash: float = 30000.0) -> dict:
    return {"cash": cash, "positions": {}, "realized_pnl": 0.0}


class SignalMathTest(unittest.TestCase):
    def test_insufficient_history_never_enters(self) -> None:
        result = mrsig.entry_signal([100.0] * 10)
        self.assertFalse(result["entry"])
        self.assertEqual(result["reason"], "INSUFFICIENT_HISTORY")

    def test_flat_price_series_never_enters(self) -> None:
        # zero variance -> zscore_vs_sma returns z=None (degenerate), never a false entry
        result = mrsig.entry_signal([100.0] * 40)
        self.assertFalse(result["entry"])

    def test_deep_oversold_triggers_entry(self) -> None:
        # realistic low-amplitude noise, then a sharp drop far below the rolling mean/stdev
        closes = _noisy_baseline() + [95.0, 92.0, 88.0]
        result = mrsig.entry_signal(closes)
        self.assertTrue(result["entry"])
        self.assertLessEqual(result["z"], mrsig.Z_ENTRY_THRESHOLD)
        self.assertLessEqual(result["rsi"], mrsig.RSI_OVERSOLD)

    def test_mild_dip_does_not_trigger_entry(self) -> None:
        # a dip well within the ticker's own normal noise band must not
        # read as "statistically oversold"
        closes = _noisy_baseline() + [99.7, 99.5, 99.4]
        result = mrsig.entry_signal(closes)
        self.assertFalse(result["entry"])

    def test_exit_on_reversion_to_mean(self) -> None:
        out = mrsig.exit_signal(current_price=101.0, sma20=100.0, entry_price=95.0, days_held=3)
        self.assertTrue(out["exit"])
        self.assertEqual(out["reason"], "REVERTED")

    def test_exit_on_stop_loss(self) -> None:
        out = mrsig.exit_signal(current_price=90.0, sma20=100.0, entry_price=95.0, days_held=2)
        self.assertTrue(out["exit"])
        self.assertEqual(out["reason"], "STOP_LOSS")
        self.assertLessEqual(out["pnl_pct"], mrsig.STOP_LOSS_PCT)

    def test_exit_on_timeout(self) -> None:
        out = mrsig.exit_signal(current_price=94.0, sma20=100.0, entry_price=95.0, days_held=mrsig.MAX_HOLD_DAYS)
        self.assertTrue(out["exit"])
        self.assertEqual(out["reason"], "TIMED_OUT")

    def test_holds_when_no_exit_condition_met(self) -> None:
        out = mrsig.exit_signal(current_price=94.5, sma20=100.0, entry_price=95.0, days_held=2)
        self.assertFalse(out["exit"])
        self.assertEqual(out["reason"], "HOLD")

    def test_reversion_checked_before_timeout_at_the_boundary(self) -> None:
        # At the exact hold-limit day, a price that has already reverted
        # must report REVERTED, not TIMED_OUT -- priority order matters
        # for the reason logged, even though both would exit.
        out = mrsig.exit_signal(current_price=101.0, sma20=100.0, entry_price=95.0, days_held=mrsig.MAX_HOLD_DAYS)
        self.assertEqual(out["reason"], "REVERTED")


class DecideAndExecuteTickerTest(unittest.TestCase):
    def _oversold_closes(self) -> list:
        return [100.0] * 34 + [99.0, 98.0, 90.0]

    def _run(self, **kwargs):
        import tae_parallel_paper_mean_reversion as mr
        from unittest import mock

        with mock.patch.object(mr, "_paths", return_value={"decisions": None, "trades": None}), mock.patch.object(
            mr, "_append_jsonl"
        ):
            return mr._decide_and_execute_ticker(p=mr._paths(), **kwargs)

    def test_buy_on_oversold_signal_with_room(self) -> None:
        portfolio = _fresh_portfolio()
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=self._oversold_closes(),
            mark_price=90.0,
            decision_id="T1",
        )
        self.assertEqual(dec["action"], "BUY")
        self.assertEqual(dec["reason"], "MEAN_REVERSION_OVERSOLD")
        self.assertIn("ZZZ", portfolio["positions"])
        self.assertGreater(portfolio["positions"]["ZZZ"]["shares"], 0.0)

    def test_no_buy_without_oversold_signal(self) -> None:
        portfolio = _fresh_portfolio()
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=[100.0] * 40,
            mark_price=100.0,
            decision_id="T1",
        )
        self.assertEqual(dec["action"], "HOLD")
        self.assertNotIn("ZZZ", portfolio.get("positions") or {})

    def test_illiquid_ticker_blocks_an_otherwise_qualifying_entry(self) -> None:
        """Sprint 3 Phase 2 (2026-09-13): same liquidity floor gating
        V1/V2/V3 (LOW PF 0.39 vs HIGH PF 0.92) -- a market-microstructure
        risk, not specific to any one entry signal."""
        portfolio = _fresh_portfolio()
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=self._oversold_closes(),
            mark_price=90.0,
            decision_id="T5",
            liquid=False,
        )
        self.assertEqual(dec["action"], "HOLD")
        self.assertEqual(dec["reason"], "MR_BLOCKED_ILLIQUID")
        self.assertNotIn("ZZZ", portfolio.get("positions") or {})

    def test_position_cap_blocks_new_entries(self) -> None:
        import tae_parallel_paper_mean_reversion as mr

        portfolio = _fresh_portfolio()
        portfolio["positions"] = {
            f"T{i}": {"shares": 1.0, "avg_price": 10.0, "current_price": 10.0} for i in range(mr.MAX_POSITIONS)
        }
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=self._oversold_closes(),
            mark_price=90.0,
            decision_id="T1",
        )
        self.assertEqual(dec["action"], "HOLD")
        self.assertNotIn("ZZZ", portfolio.get("positions") or {})

    def test_sell_on_reversion(self) -> None:
        portfolio = _fresh_portfolio()
        portfolio["positions"]["ZZZ"] = {
            "shares": 10.0,
            "avg_price": 95.0,
            "current_price": 95.0,
            "days_held": 2,
            "last_sma20": 100.0,
        }
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=[101.0] * 40,  # flat-ish so sma20 ~101, price>=sma20 -> reverted
            mark_price=101.0,
            decision_id="T2",
        )
        self.assertEqual(dec["action"], "SELL")
        self.assertEqual(dec["reason"], "MEAN_REVERSION_REVERTED")
        self.assertNotIn("ZZZ", portfolio.get("positions") or {})
        self.assertGreater(portfolio["realized_pnl"], 0.0)

    def test_sell_on_stop_loss(self) -> None:
        portfolio = _fresh_portfolio()
        portfolio["positions"]["ZZZ"] = {
            "shares": 10.0,
            "avg_price": 100.0,
            "current_price": 100.0,
            "days_held": 1,
            "last_sma20": 110.0,
        }
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=None,
            mark_price=90.0,  # -10% vs entry, past the -5% stop; sma20 fallback stays 110 (no revert)
            decision_id="T3",
        )
        self.assertEqual(dec["action"], "SELL")
        self.assertEqual(dec["reason"], "MEAN_REVERSION_STOP_LOSS")
        self.assertLess(portfolio["realized_pnl"], 0.0)

    def test_holds_open_position_with_no_exit_condition(self) -> None:
        portfolio = _fresh_portfolio()
        portfolio["positions"]["ZZZ"] = {
            "shares": 10.0,
            "avg_price": 95.0,
            "current_price": 95.0,
            "days_held": 1,
            "last_sma20": 100.0,
        }
        dec = self._run(
            portfolio=portfolio,
            ticker="ZZZ",
            closes=None,
            mark_price=96.0,
            decision_id="T4",
        )
        self.assertEqual(dec["action"], "HOLD")
        self.assertIn("ZZZ", portfolio["positions"])


class IsolationFromExistingArmsTest(unittest.TestCase):
    """Same proof pattern as tae_short_margin_test.py's isolation tests:
    this arm must be a one-way dependency (it may read shared helpers,
    nothing shared may know it exists), and running it must never touch
    V1/V2/V3/exp_short_margin's own files."""

    def test_mean_reversion_module_not_imported_by_any_existing_arm(self) -> None:
        import inspect

        import tae_parallel_paper_runtime as ppr
        import tae_parallel_paper_short_margin as sm

        self.assertNotIn("tae_parallel_paper_mean_reversion", inspect.getsource(ppr))
        self.assertNotIn("tae_parallel_paper_mean_reversion", inspect.getsource(sm))

    def test_real_v1_v2_v3_short_margin_portfolios_untouched_by_import(self) -> None:
        import hashlib
        from pathlib import Path

        arms = ("v1", "v2", "v3", "exp_short_margin")
        before = {}
        for arm in arms:
            path = Path(f"runtime_outputs/parallel_paper/{arm}/portfolio.json")
            if path.exists():
                before[arm] = hashlib.sha256(path.read_bytes()).hexdigest()

        import tae_parallel_paper_mean_reversion  # noqa: F401

        for arm, digest in before.items():
            path = Path(f"runtime_outputs/parallel_paper/{arm}/portfolio.json")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, f"{arm} portfolio changed on import")


class RuntimeSmokeTest(unittest.TestCase):
    def test_module_exposes_expected_api(self) -> None:
        import tae_parallel_paper_mean_reversion as mr

        self.assertTrue(hasattr(mr, "run_mean_reversion_cycle"))
        self.assertEqual(mr.STARTING_CAPITAL, 30000.0)
        self.assertEqual(mr.ARM_ID, "exp_mean_reversion")


if __name__ == "__main__":
    unittest.main()
