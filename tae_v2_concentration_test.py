#!/usr/bin/env python3
"""
Regression coverage for V2's active concentration trim.

Context: raising V2_MAX_POSITIONS only stops further growth — it does
nothing for a book that's already over-diversified. This adds an active
trim that closes flat/going-nowhere positions once V2 is above
V2_CONCENTRATION_TARGET, freeing capital for Kelly-sized, higher-conviction
entries — while protecting positions that are actually working (trailing
armed) and staying out of the way of the real stop-loss/exit logic
(only fires when the existing exit_policy would otherwise HOLD).

Also covers a real bug found live on 2026-09-08: a freshly-opened position
starts near 0% pnl, which without an age guard looks identical to a "flat,
going-nowhere" position — SAP.DE was observed opening, getting immediately
re-trimmed, and reopening in a churn loop with no economic purpose. Fixed
with a minimum-age requirement read from position_cycle_id's embedded open
timestamp.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tae_strategy_v2_concentration as v2conc


def _old_cycle_id(ticker: str, *, hours_ago: float = 24.0) -> str:
    opened = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return f"PPC-{ticker}-{opened.strftime('%Y%m%dT%H%M%S')}-TESTHASH"


def _portfolio(n_positions: int, *, hours_ago: float = 24.0) -> dict:
    positions = {
        f"T{i}": {
            "shares": 1.0,
            "avg_price": 100.0,
            "current_price": 100.0,
            "position_cycle_id": _old_cycle_id(f"T{i}", hours_ago=hours_ago),
        }
        for i in range(n_positions)
    }
    return {"positions": positions}


class UnderTargetTest(unittest.TestCase):
    def test_no_trim_when_at_or_below_target(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET)
        pos = pf["positions"]["T0"]
        result = v2conc.should_concentration_trim(
            portfolio=pf,
            pos=pos,
            cycle=None,
            current_price=100.0,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result)


class OverTargetTest(unittest.TestCase):
    def test_flat_position_over_target_is_trimmed(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        pos = pf["positions"]["T0"]  # avg=100, flat
        result = v2conc.should_concentration_trim(
            portfolio=pf,
            pos=pos,
            cycle=None,
            current_price=100.2,  # +0.2%, below the 1.0% cutoff
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertEqual(result, v2conc.V2_CONCENTRATION_TRIM_REASON)

    def test_working_winner_is_protected_by_pnl_threshold(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        pos = pf["positions"]["T0"]
        result = v2conc.should_concentration_trim(
            portfolio=pf,
            pos=pos,
            cycle=None,
            current_price=105.0,  # +5%, above the 1.0% cutoff
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result)

    def test_trailing_armed_position_is_never_trimmed_even_if_flat_now(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        pos = pf["positions"]["T0"]
        pos["trailing_armed"] = True
        result = v2conc.should_concentration_trim(
            portfolio=pf,
            pos=pos,
            cycle=None,
            current_price=100.2,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result, "a working trailing winner must never be trimmed for concentration")

    def test_trailing_armed_on_cycle_also_protects(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        pos = pf["positions"]["T0"]
        result = v2conc.should_concentration_trim(
            portfolio=pf,
            pos=pos,
            cycle={"trailing_armed": True},
            current_price=100.2,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result)

    def test_flat_or_missing_position_is_a_no_op(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        result = v2conc.should_concentration_trim(
            portfolio=pf,
            pos=None,
            cycle=None,
            current_price=100.0,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result)


class MinimumAgeGuardTest(unittest.TestCase):
    """Regression for the real SAP.DE open/trim/open churn bug."""

    def test_freshly_opened_position_is_not_trimmed(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5, hours_ago=0.1)  # 6 minutes old
        pos = pf["positions"]["T0"]
        result = v2conc.should_concentration_trim(
            portfolio=pf, pos=pos, cycle=None, current_price=100.0,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result, "a brand-new position must never be immediately re-trimmed")

    def test_position_older_than_min_age_is_eligible(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5, hours_ago=v2conc.V2_TRIM_MIN_AGE_HOURS + 1)
        pos = pf["positions"]["T0"]
        result = v2conc.should_concentration_trim(
            portfolio=pf, pos=pos, cycle=None, current_price=100.0,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertEqual(result, v2conc.V2_CONCENTRATION_TRIM_REASON)

    def test_missing_position_cycle_id_fails_safe_to_no_trim(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        pos = pf["positions"]["T0"]
        pos.pop("position_cycle_id")
        result = v2conc.should_concentration_trim(
            portfolio=pf, pos=pos, cycle=None, current_price=100.0,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result, "unparseable age must fail safe (no trim), not assume old enough")

    def test_unparseable_cycle_id_fails_safe(self) -> None:
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
        pos = pf["positions"]["T0"]
        pos["position_cycle_id"] = "not-a-real-cycle-id"
        result = v2conc.should_concentration_trim(
            portfolio=pf, pos=pos, cycle=None, current_price=100.0,
            trades_path="/nonexistent/trades.jsonl",
        )
        self.assertIsNone(result)


class RateLimitTest(unittest.TestCase):
    def test_recent_trim_blocks_a_second_trim_within_the_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            recent = datetime.now(timezone.utc) - timedelta(minutes=5)
            with path.open("w") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": recent.isoformat().replace("+00:00", "Z"),
                            "reason": v2conc.V2_CONCENTRATION_TRIM_REASON,
                        }
                    )
                    + "\n"
                )
            pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
            pos = pf["positions"]["T0"]
            result = v2conc.should_concentration_trim(
                portfolio=pf, pos=pos, cycle=None, current_price=100.0, trades_path=path
            )
            self.assertIsNone(result, "must not trim again within V2_TRIM_MIN_GAP_MINUTES")

    def test_old_trim_allows_a_new_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            old = datetime.now(timezone.utc) - timedelta(hours=3)
            with path.open("w") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": old.isoformat().replace("+00:00", "Z"),
                            "reason": v2conc.V2_CONCENTRATION_TRIM_REASON,
                        }
                    )
                    + "\n"
                )
            pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
            pos = pf["positions"]["T0"]
            result = v2conc.should_concentration_trim(
                portfolio=pf, pos=pos, cycle=None, current_price=100.0, trades_path=path
            )
            self.assertEqual(result, v2conc.V2_CONCENTRATION_TRIM_REASON)

    def test_unrelated_trades_in_journal_do_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.jsonl"
            recent = datetime.now(timezone.utc) - timedelta(minutes=2)
            with path.open("w") as fh:
                fh.write(
                    json.dumps({"ts": recent.isoformat().replace("+00:00", "Z"), "reason": "SOME_OTHER_REASON"})
                    + "\n"
                )
            pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 5)
            pos = pf["positions"]["T0"]
            result = v2conc.should_concentration_trim(
                portfolio=pf, pos=pos, cycle=None, current_price=100.0, trades_path=path
            )
            self.assertEqual(result, v2conc.V2_CONCENTRATION_TRIM_REASON)


class SelfLimitingConvergenceTest(unittest.TestCase):
    def test_trimming_naturally_stops_once_target_is_reached(self) -> None:
        """Simulates removing positions one at a time and confirms the
        function stops recommending trims exactly at the target, not below."""
        pf = _portfolio(v2conc.V2_CONCENTRATION_TARGET + 3)
        removed = 0
        for i in range(10):
            open_count = v2conc._open_position_count(pf)
            if open_count <= v2conc.V2_CONCENTRATION_TARGET:
                break
            ticker = f"T{i}"
            pos = pf["positions"].get(ticker)
            result = v2conc.should_concentration_trim(
                portfolio=pf, pos=pos, cycle=None, current_price=100.0,
                trades_path="/nonexistent/trades.jsonl",
            )
            self.assertEqual(result, v2conc.V2_CONCENTRATION_TRIM_REASON)
            pf["positions"].pop(ticker)
            removed += 1
        self.assertEqual(removed, 3)
        self.assertEqual(v2conc._open_position_count(pf), v2conc.V2_CONCENTRATION_TARGET)


class RuntimeWiringSmokeTest(unittest.TestCase):
    def test_runtime_imports_v2conc_module(self) -> None:
        import tae_parallel_paper_runtime as ppr

        self.assertTrue(hasattr(ppr, "v2conc"))
        self.assertTrue(hasattr(ppr.v2conc, "should_concentration_trim"))


if __name__ == "__main__":
    unittest.main()
