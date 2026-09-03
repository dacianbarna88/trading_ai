#!/usr/bin/env python3
"""
Regression coverage for V1's trailing-stop exit (isolated parallel-paper arm
only — canonical live_bot.py is untouched by this change).

Context: V1's real trade history (35 closed trades, 40 days) showed a
28.6% win rate combined with the old fixed +5%/-3% bracket producing
negative expectancy (-$15/trade): the +5% take-profit cap discarded exactly
the large winners that would have offset the frequent -3% losses. V2 — same
infra, same universe — uses an armed trailing stop instead and has a
profit factor of 10.49. tae_strategy_v1_trailing.py ports that same,
already-generic (tae_strategy_v2_trailing.py) mechanism onto V1's position
dicts, which have no "cycle" store the way V2 does.

These tests exercise the adapter directly with plain position dicts (the
trailing math itself is pure float logic, already covered independently by
V2's usage of the same primitives) rather than a full mocked runtime cycle.
"""

from __future__ import annotations

import unittest

import tae_strategy_v1_trailing as v1trail


def _pos(avg_price: float, **extra) -> dict:
    pos = {"avg_price": avg_price, "shares": 1.0}
    pos.update(extra)
    return pos


class EntryStopStillFiresTest(unittest.TestCase):
    def test_unarmed_loss_triggers_stop_loss(self) -> None:
        pos = _pos(100.0)
        act, reason = v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=96.5, now_iso="2026-09-02T10:00:00Z"
        )
        self.assertEqual(act, "SELL_STOP_LOSS")
        self.assertEqual(reason, "STRATEGY_STOP_V1")
        self.assertEqual(reason, v1trail.V1_STOP_LOSS_REASON)

    def test_unarmed_small_loss_holds(self) -> None:
        pos = _pos(100.0)
        act, reason = v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=98.5, now_iso="2026-09-02T10:00:00Z"
        )
        self.assertIsNone(act)
        self.assertIsNone(reason)
        self.assertFalse(pos["trailing_armed"])


class ArmAndTrailTest(unittest.TestCase):
    def test_arms_at_plus_five_percent_and_holds_not_sells(self) -> None:
        """The whole point of this change: hitting +5% must NOT sell anymore."""
        pos = _pos(100.0)
        act, reason = v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=105.5, now_iso="2026-09-02T10:00:00Z"
        )
        self.assertIsNone(act, "arming at +5% must hold, not sell (old fixed +5% cap is gone)")
        self.assertTrue(pos["trailing_armed"])
        self.assertAlmostEqual(pos["highest_price"], 105.5)
        # trail 2% off the peak: 105.5 * 0.98
        self.assertAlmostEqual(pos["trailing_stop"], 105.5 * 0.98, places=4)

    def test_further_gains_ratchet_the_stop_up(self) -> None:
        pos = _pos(100.0)
        v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=106.0, now_iso="2026-09-02T10:00:00Z"
        )
        first_stop = pos["trailing_stop"]
        v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=112.0, now_iso="2026-09-02T11:00:00Z"
        )
        second_stop = pos["trailing_stop"]
        self.assertGreater(second_stop, first_stop)
        self.assertAlmostEqual(second_stop, 112.0 * 0.98, places=4)

    def test_pullback_from_peak_triggers_trailing_sell(self) -> None:
        pos = _pos(100.0)
        v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=110.0, now_iso="2026-09-02T10:00:00Z"
        )
        # armed at peak 110, stop = 110*0.98 = 107.8; a pullback below that sells.
        act, reason = v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=107.0, now_iso="2026-09-02T11:00:00Z"
        )
        self.assertEqual(act, "SELL_TRAILING")
        self.assertEqual(reason, v1trail.V1_PROFIT_TRAILING_REASON)
        self.assertEqual(reason, "V1_PROFIT_TRAILING_5_2")

    def test_stop_never_ratchets_down_on_a_lower_but_still_above_stop_tick(self) -> None:
        pos = _pos(100.0)
        v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=120.0, now_iso="2026-09-02T10:00:00Z"
        )
        stop_at_peak = pos["trailing_stop"]
        act, _ = v1trail.v1_trailing_exit_action(
            pos, avg_price=100.0, current_price=118.0, now_iso="2026-09-02T11:00:00Z"
        )
        self.assertIsNone(act)
        self.assertEqual(pos["trailing_stop"], stop_at_peak)


class PersistedStateShapeTest(unittest.TestCase):
    def test_persisted_fields_match_v2_schema(self) -> None:
        """V1 positions should gain the same field names V2 already writes,
        so downstream reporting doesn't need two schemas."""
        pos = _pos(50.0)
        v1trail.v1_trailing_exit_action(
            pos, avg_price=50.0, current_price=51.0, now_iso="2026-09-02T10:00:00Z"
        )
        for key in ("trailing_armed", "highest_price", "trailing_stop", "armed_at", "updated_at"):
            self.assertIn(key, pos)


class CustomStopLossPctTest(unittest.TestCase):
    def test_caller_supplied_stop_loss_pct_is_honored(self) -> None:
        """Phase 3 will pass a volatility-adjusted stop instead of -3.0 —
        confirm the adapter actually uses the caller's value, not a
        hardcoded default."""
        pos = _pos(100.0)
        act, reason = v1trail.v1_trailing_exit_action(
            pos,
            avg_price=100.0,
            current_price=97.5,  # -2.5%, would NOT trip a -3% stop
            now_iso="2026-09-02T10:00:00Z",
            stop_loss_pct=-2.0,  # but DOES trip a tighter -2% stop
        )
        self.assertEqual(act, "SELL_STOP_LOSS")
        self.assertEqual(reason, "STRATEGY_STOP_V1")


class RuntimeWiringSmokeTest(unittest.TestCase):
    """Confirms tae_parallel_paper_runtime.py actually imports and can call
    the new adapter (catches a broken import/signature mismatch that a pure
    unit test of this module alone wouldn't)."""

    def test_runtime_imports_v1trail_module(self) -> None:
        import tae_parallel_paper_runtime as ppr

        self.assertTrue(hasattr(ppr, "v1trail"))
        self.assertTrue(hasattr(ppr.v1trail, "v1_trailing_exit_action"))


if __name__ == "__main__":
    unittest.main()
