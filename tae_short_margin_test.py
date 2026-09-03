#!/usr/bin/env python3
"""
Regression coverage for the new short-selling + margin arm
(tae_paper_execution_short.py + tae_parallel_paper_short_margin.py).

Context: every long-only accounting path in tae_paper_execution.py hard-
clamps sells to existing shares and hard-asserts fill_shares > 0 /
before.shares > 0 as integrity gates (tae_paper_execution.py:2654-2662,
4005-4009, 4060-4066, 4854) — those are untouched by this change. This new,
separate module adds negative-share ("short") positions with their own
open/cover primitives and its own validator, used only by the new isolated
exp_short_margin arm. The most important thing these tests prove is (a) the
sign/cash-flow conventions are correct in both directions (open credits
cash + reserves margin, cover debits cash + releases margin, PnL sign
mirrors a long close), and (b) V1/V2/V3 are provably untouched.
"""

from __future__ import annotations

import unittest

import tae_paper_execution_short as pes


def _fresh_portfolio(cash: float = 30000.0) -> dict:
    return {"cash": cash, "positions": {}, "realized_pnl": 0.0, "margin_reserved": 0.0}


class OpenShortTest(unittest.TestCase):
    def test_open_short_credits_cash_and_creates_negative_shares(self) -> None:
        pf = _fresh_portfolio()
        shares, pos = pes._open_short(pf, "XYZ", 1000.0, 100.0, margin_requirement_pct=0.5)
        self.assertEqual(shares, 10.0)
        self.assertEqual(pos["shares"], -10.0)
        self.assertEqual(pos["avg_price"], 100.0)
        self.assertEqual(pf["cash"], 31000.0, "cash must be CREDITED on a short sale")
        self.assertEqual(pos["margin_reserved"], 500.0)
        self.assertEqual(pf["margin_reserved"], 500.0)

    def test_adding_to_an_existing_short_averages_price(self) -> None:
        pf = _fresh_portfolio()
        pes._open_short(pf, "XYZ", 1000.0, 100.0)
        pes._open_short(pf, "XYZ", 500.0, 90.0)
        pos = pf["positions"]["XYZ"]
        # weighted avg: (10*100 + 500)/(10 + 5.5555...) -- computed via notional/shares directly
        self.assertAlmostEqual(pos["shares"], -(10.0 + 500.0 / 90.0), places=4)
        self.assertGreater(pos["avg_price"], 90.0)
        self.assertLess(pos["avg_price"], 100.0)

    def test_refuses_to_short_an_existing_long_position(self) -> None:
        pf = _fresh_portfolio()
        pf["positions"]["XYZ"] = {"shares": 5.0, "avg_price": 50.0}
        shares, pos = pes._open_short(pf, "XYZ", 1000.0, 100.0)
        self.assertEqual(shares, 0.0)
        self.assertEqual(pf["positions"]["XYZ"]["shares"], 5.0, "existing long must be untouched")

    def test_invalid_price_or_notional_is_a_no_op(self) -> None:
        pf = _fresh_portfolio()
        shares, pos = pes._open_short(pf, "XYZ", 0.0, 100.0)
        self.assertEqual(shares, 0.0)
        self.assertNotIn("XYZ", pf["positions"])
        shares, pos = pes._open_short(pf, "XYZ", 1000.0, 0.0)
        self.assertEqual(shares, 0.0)


class CoverShortTest(unittest.TestCase):
    def test_cover_at_profit_debits_cash_and_credits_realized_pnl(self) -> None:
        pf = _fresh_portfolio()
        pes._open_short(pf, "XYZ", 1000.0, 100.0, margin_requirement_pct=0.5)  # -10 shares @ 100
        cash_after_open = pf["cash"]
        realized, gross_cost, after = pes._cover_short(pf, "XYZ", 10.0, 80.0)  # price fell -> profit
        self.assertAlmostEqual(realized, (100.0 - 80.0) * 10.0)  # +200
        self.assertAlmostEqual(gross_cost, 800.0)
        self.assertAlmostEqual(pf["cash"], cash_after_open - 800.0)
        self.assertAlmostEqual(pf["realized_pnl"], 200.0)
        self.assertIsNone(after, "fully covered position must be removed")
        self.assertNotIn("XYZ", pf["positions"])
        self.assertAlmostEqual(pf["margin_reserved"], 0.0)

    def test_cover_at_loss_produces_negative_realized_pnl(self) -> None:
        pf = _fresh_portfolio()
        pes._open_short(pf, "XYZ", 1000.0, 100.0)  # -10 shares @ 100
        realized, gross_cost, after = pes._cover_short(pf, "XYZ", 10.0, 120.0)  # price rose -> loss
        self.assertAlmostEqual(realized, (100.0 - 120.0) * 10.0)  # -200
        self.assertLess(realized, 0.0)

    def test_partial_cover_reduces_position_and_releases_proportional_margin(self) -> None:
        pf = _fresh_portfolio()
        pes._open_short(pf, "XYZ", 1000.0, 100.0, margin_requirement_pct=0.5)  # -10 @ 100, margin 500
        realized, gross_cost, after = pes._cover_short(pf, "XYZ", 4.0, 100.0)
        self.assertIsNotNone(after)
        self.assertAlmostEqual(after["shares"], -6.0)
        self.assertAlmostEqual(after["margin_reserved"], 300.0)  # 500 * (6/10) remaining
        self.assertAlmostEqual(pf["margin_reserved"], 300.0)

    def test_cover_on_flat_or_long_position_is_a_no_op(self) -> None:
        pf = _fresh_portfolio()
        realized, gross_cost, after = pes._cover_short(pf, "XYZ", 5.0, 100.0)
        self.assertEqual(realized, 0.0)
        pf["positions"]["XYZ"] = {"shares": 5.0, "avg_price": 50.0}
        realized, gross_cost, after = pes._cover_short(pf, "XYZ", 5.0, 100.0)
        self.assertEqual(realized, 0.0)
        self.assertEqual(pf["positions"]["XYZ"]["shares"], 5.0)


class RoundTripReconciliationTest(unittest.TestCase):
    def test_open_then_cover_flat_at_same_price_returns_to_starting_cash(self) -> None:
        pf = _fresh_portfolio(cash=30000.0)
        pes._open_short(pf, "XYZ", 1000.0, 100.0)
        pes._cover_short(pf, "XYZ", 10.0, 100.0)
        self.assertAlmostEqual(pf["cash"], 30000.0)
        self.assertAlmostEqual(pf["realized_pnl"], 0.0)
        self.assertAlmostEqual(pf["margin_reserved"], 0.0)
        self.assertNotIn("XYZ", pf["positions"])


class MarginCallTest(unittest.TestCase):
    def test_margin_call_triggers_when_equity_falls_below_maintenance(self) -> None:
        pf = _fresh_portfolio()
        pes._open_short(pf, "XYZ", 1000.0, 100.0, margin_requirement_pct=0.5)  # margin 500
        pos = pf["positions"]["XYZ"]
        # Price rises sharply against the short: unrealized loss = (180-100)*10 = 800 > margin 500
        triggered = pes.check_margin_call(pos, current_price=180.0, maintenance_margin_pct=0.25)
        self.assertTrue(triggered)

    def test_no_margin_call_when_equity_is_healthy(self) -> None:
        pf = _fresh_portfolio()
        pes._open_short(pf, "XYZ", 1000.0, 100.0, margin_requirement_pct=0.5)
        pos = pf["positions"]["XYZ"]
        triggered = pes.check_margin_call(pos, current_price=102.0, maintenance_margin_pct=0.25)
        self.assertFalse(triggered)

    def test_margin_call_never_fires_on_a_long_or_flat_position(self) -> None:
        pos = {"shares": 5.0, "avg_price": 50.0, "margin_reserved": 0.0}
        self.assertFalse(pes.check_margin_call(pos, current_price=1000.0, maintenance_margin_pct=0.25))


class ValidateShortTradeRecordTest(unittest.TestCase):
    def test_short_requires_flat_or_short_before_state(self) -> None:
        ok, err = pes.validate_short_trade_record(
            {"action": "SHORT_PAPER", "shares": 10.0}, before_shares=5.0
        )
        self.assertFalse(ok)
        ok, err = pes.validate_short_trade_record(
            {"action": "SHORT_PAPER", "shares": 10.0}, before_shares=0.0
        )
        self.assertTrue(ok)

    def test_cover_requires_an_existing_short(self) -> None:
        ok, err = pes.validate_short_trade_record(
            {"action": "COVER_PAPER", "shares": 5.0}, before_shares=0.0
        )
        self.assertFalse(ok)
        ok, err = pes.validate_short_trade_record(
            {"action": "COVER_PAPER", "shares": 5.0}, before_shares=-10.0
        )
        self.assertTrue(ok)

    def test_zero_or_negative_fill_shares_always_rejected(self) -> None:
        ok, err = pes.validate_short_trade_record(
            {"action": "SHORT_PAPER", "shares": 0.0}, before_shares=0.0
        )
        self.assertFalse(ok)


class EvaluateShortExitTest(unittest.TestCase):
    def test_unarmed_adverse_move_triggers_stop_loss(self) -> None:
        # price rose 4% against a short with a 3% stop
        act, pnl_pct, state = pes.evaluate_short_exit(100.0, 104.0, None, stop_loss_pct=3.0)
        self.assertEqual(act, "SELL_STOP_LOSS")
        self.assertLess(pnl_pct, 0.0)

    def test_arms_at_activate_pct_and_holds(self) -> None:
        act, pnl_pct, state = pes.evaluate_short_exit(
            100.0, 94.0, None, activate_pct=5.0
        )  # price fell 6% -- favorable
        self.assertEqual(act, "HOLD")
        self.assertTrue(state["trailing_armed"])
        self.assertAlmostEqual(state["lowest_price"], 94.0)

    def test_rebound_from_low_triggers_trailing_cover(self) -> None:
        _act, _pnl, state = pes.evaluate_short_exit(
            100.0, 90.0, None, activate_pct=5.0, trail_distance_pct=2.0
        )  # arms at 90, trailing_stop = 90*1.02 = 91.8
        act, pnl_pct, state2 = pes.evaluate_short_exit(
            100.0, 92.0, state, activate_pct=5.0, trail_distance_pct=2.0
        )
        self.assertEqual(act, "SELL_TRAILING")

    def test_stop_only_ratchets_more_favorable_never_loosens(self) -> None:
        _act, _pnl, state = pes.evaluate_short_exit(100.0, 80.0, None, activate_pct=5.0)
        stop_at_80 = state["trailing_stop"]
        _act2, _pnl2, state2 = pes.evaluate_short_exit(100.0, 85.0, state, activate_pct=5.0)
        # price ticked back up (still armed, still above the low) -- stop must not loosen
        self.assertEqual(state2["trailing_stop"], stop_at_80)


class MarginUtilizationTest(unittest.TestCase):
    def test_utilization_pct_computed_against_account_value(self) -> None:
        pf = {"account_value": 30000.0, "margin_reserved": 6000.0}
        self.assertAlmostEqual(pes.margin_utilization_pct(pf), 0.2)

    def test_zero_account_value_returns_zero_not_a_crash(self) -> None:
        pf = {"account_value": 0.0, "cash": 0.0, "margin_reserved": 100.0}
        self.assertEqual(pes.margin_utilization_pct(pf), 0.0)


class IsolationFromExistingArmsTest(unittest.TestCase):
    """The whole point of building this as a new module: prove V1/V2/V3's
    long-only accounting is completely unaware this module exists."""

    def test_short_module_does_not_import_or_touch_long_only_execution(self) -> None:
        import tae_paper_execution as pe

        # tae_paper_execution.py must not import the short module (one-way
        # dependency only: short module may reference shared helpers, never
        # the reverse).
        import inspect

        source = inspect.getsource(pe)
        self.assertNotIn("tae_paper_execution_short", source)

    def test_real_v1_v2_v3_portfolios_have_no_negative_shares(self) -> None:
        """Sanity check on real data: confirms the long-only arms have never
        produced a negative share balance (would indicate cross-contamination
        if this ever failed)."""
        import json
        from pathlib import Path

        for arm in ("v1", "v2", "v3"):
            path = Path(f"runtime_outputs/parallel_paper/{arm}/portfolio.json")
            if not path.exists():
                continue
            data = json.loads(path.read_text())
            for ticker, pos in (data.get("positions") or {}).items():
                self.assertGreaterEqual(
                    float(pos.get("shares", 0.0)),
                    0.0,
                    f"{arm}/{ticker} has negative shares — long-only invariant broken",
                )


class RuntimeSmokeTest(unittest.TestCase):
    def test_short_margin_module_imports_and_exposes_expected_api(self) -> None:
        import tae_parallel_paper_short_margin as sm

        self.assertTrue(hasattr(sm, "run_short_margin_cycle"))
        self.assertEqual(sm.STARTING_CAPITAL, 30000.0)
        self.assertEqual(sm.ARM_ID, "exp_short_margin")


if __name__ == "__main__":
    unittest.main()
