#!/usr/bin/env python3
"""
Regression coverage for the short/margin arm's volatility-adjusted stop
(2026-09-10).

Context: tae_parallel_paper_short_margin.py's STOP_LOSS_PCT=3.0 was a
direct copy of V1's original flat mechanical bracket -- the exact bug
class already found and fixed on V1 (tae_strategy_v1_vol_stop.py). Real
trade history: 7 of 8 short covers to date are SHORT_STOP_LOSS (losses)
vs 1 real trailing win, yet the currently-open book was net +$291.81
unrealized -- entries look directionally fine, the flat 3% stop is what
keeps cutting them short on ordinary noise before they can work. Fixed
by reusing the same fix already proven on V1: k std-devs of the ticker's
own realized volatility, clamped to [2%, 6%], instead of a flat 3%.

evaluate_short_exit's stop_loss_pct is a positive magnitude ("price
rising this much AGAINST the short"), while vol_adjusted_stop_pct()
returns a long-style negative value -- the wiring must abs() it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tae_parallel_paper_short_margin as sm
import tae_strategy_v1_vol_stop as v1volstop


def _portfolio_with_short(ticker: str, *, avg_price: float, shares: float = -10.0) -> dict:
    notional = avg_price * abs(shares)
    return {
        "cash": 30000.0,
        "margin_reserved": notional * 0.5,
        "positions": {
            ticker: {
                "shares": shares,
                "avg_price": avg_price,
                "current_price": avg_price,
                "lowest_price": avg_price,
                "trailing_armed": False,
                "trailing_stop": None,
                # Healthy margin cushion so check_margin_call() doesn't
                # short-circuit before the stop-loss path is even reached.
                "margin_reserved": notional * 0.5,
            }
        },
    }


def _paths(tmp: Path) -> dict[str, Path]:
    j = tmp / "journals"
    return {"dir": tmp, "portfolio": tmp / "portfolio.json", "decisions": j / "decisions.jsonl",
            "trades": j / "trades.jsonl", "errors": j / "errors.jsonl"}


class VolAdjustedStopWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.p = _paths(Path(self._tmp.name))

    def _run(self, *, ticker: str, avg_price: float, mark: float, closes: list[float] | None):
        portfolio = _portfolio_with_short(ticker, avg_price=avg_price)
        snap = {
            "mark_price": mark, "mark_status": "FRESH", "mark_freshness": "FRESH",
            "mark_age_seconds": 0.0, "eligible": True, "data_fresh": True, "score": 10.0,
        }
        with mock.patch.object(v1volstop, "fetch_recent_closes", return_value=closes):
            dec = sm._decide_and_execute_ticker(
                portfolio=portfolio, ticker=ticker, snap=snap, p=self.p, decision_id="TEST-1",
            )
        return dec, portfolio

    def test_wide_volatility_holds_a_move_that_would_have_hit_the_old_flat_3pct_stop(self) -> None:
        # Adverse move of +4% against the short (price rose 4%): the OLD
        # flat 3% stop would have covered here. High realized volatility
        # (big daily swings) should widen the stop past 4%, so it holds.
        high_vol_closes = [100.0, 108.0, 96.0, 110.0, 94.0, 109.0, 95.0, 108.0, 96.0, 107.0] * 3
        dec, portfolio = self._run(ticker="ZZZ", avg_price=100.0, mark=104.0, closes=high_vol_closes)
        self.assertEqual(dec.get("action"), "HOLD")
        self.assertIn("ZZZ", portfolio["positions"])
        self.assertLess(portfolio["positions"]["ZZZ"]["shares"], 0)  # still short, not covered

    def test_narrow_volatility_still_stops_out_a_small_adverse_move(self) -> None:
        # A calm ticker (tiny historical swings) should keep a tight
        # (near the 2% floor) stop, so even a modest 2.5% adverse move
        # still covers.
        low_vol_closes = [100.0 + (0.05 if i % 2 == 0 else -0.05) for i in range(40)]
        dec, portfolio = self._run(ticker="ZZZ", avg_price=100.0, mark=102.5, closes=low_vol_closes)
        self.assertEqual(dec.get("action"), "COVER")
        self.assertEqual(dec.get("reason"), sm.COVER_STOP_LOSS_REASON)

    def test_missing_closes_falls_back_to_default_not_a_crash(self) -> None:
        dec, _ = self._run(ticker="ZZZ", avg_price=100.0, mark=110.0, closes=None)
        self.assertIn(dec.get("action"), {"COVER", "HOLD"})

    def test_diagnostics_are_stored_on_the_position(self) -> None:
        closes = [100.0, 101.0, 99.0, 102.0, 98.0] * 8
        portfolio = _portfolio_with_short("ZZZ", avg_price=100.0)
        snap = {
            "mark_price": 100.5, "mark_status": "FRESH", "mark_freshness": "FRESH",
            "mark_age_seconds": 0.0, "eligible": True, "data_fresh": True, "score": 10.0,
        }
        with mock.patch.object(v1volstop, "fetch_recent_closes", return_value=closes):
            sm._decide_and_execute_ticker(
                portfolio=portfolio, ticker="ZZZ", snap=snap, p=self.p, decision_id="TEST-2",
            )
        self.assertIn("short_vol_stop_diag", portfolio["positions"]["ZZZ"])

    def test_stop_pct_passed_to_evaluate_short_exit_is_a_positive_magnitude(self) -> None:
        """vol_adjusted_stop_pct() returns a negative (long-style) value;
        the short-side caller must abs() it before use."""
        captured: dict[str, float] = {}
        real_evaluate = sm.pes.evaluate_short_exit

        def _capturing_evaluate(avg_price, current_price, state, *, stop_loss_pct, **kw):
            captured["stop_loss_pct"] = stop_loss_pct
            return real_evaluate(avg_price, current_price, state, stop_loss_pct=stop_loss_pct, **kw)

        closes = [100.0, 104.0, 96.0, 103.0, 97.0] * 8
        with mock.patch.object(v1volstop, "fetch_recent_closes", return_value=closes), \
             mock.patch.object(sm.pes, "evaluate_short_exit", side_effect=_capturing_evaluate):
            self._run(ticker="ZZZ", avg_price=100.0, mark=100.5, closes=closes)
        self.assertIn("stop_loss_pct", captured)
        self.assertGreater(captured["stop_loss_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
