#!/usr/bin/env python3
"""
TAE V5.1 Policy Shadow Regression Test — observation-only divergence logging.

CONNECTED_SHADOW_VALIDATION | OBSERVABILITY_ONLY | NO_EXECUTION | PAPER_ONLY

Locks down core/v51_policy_shadow.py: it must log where live_bot.py's
static policy and live_bot_v5_1.py's dynamic policy would decide
differently, and must never raise, block a BUY, or force a SELL.
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import core.v51_policy_shadow as shadow


def _read_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _signals(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_regime_check_always_logged_agree_true_when_same() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="BULL"), \
             patch.object(shadow, "get_max_positions", return_value=12):
            shadow.run_v51_policy_shadow(
                signals_df=None,
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="c1",
            )
        rows = _read_events(events_path)
        regime_rows = [r for r in rows if r["check_type"] == "REGIME"]
        assert len(regime_rows) == 1
        assert regime_rows[0]["agree"] == "true"


def test_regime_divergence_logged_agree_false() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="NEUTRAL"), \
             patch.object(shadow, "get_max_positions", return_value=8):
            shadow.run_v51_policy_shadow(
                signals_df=None,
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="c1",
            )
        rows = _read_events(events_path)
        regime_rows = [r for r in rows if r["check_type"] == "REGIME"]
        assert regime_rows[0]["agree"] == "false"
        assert regime_rows[0]["live_value"] == "BULL"
        assert regime_rows[0]["dynamic_value"] == "NEUTRAL"


def test_max_positions_divergence_when_caps_disagree_on_block() -> None:
    positions = {f"T{i}": {"shares": 1, "avg_price": 100} for i in range(8)}
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="NEUTRAL"), \
             patch.object(shadow, "get_max_positions", return_value=8):
            shadow.run_v51_policy_shadow(
                signals_df=None,
                positions=positions,
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="c1",
            )
        rows = _read_events(events_path)
        cap_rows = [r for r in rows if r["check_type"] == "MAX_POSITIONS"]
        assert cap_rows[0]["agree"] == "false"
        assert "dynamic_would_block_new_buy=True" in cap_rows[0]["detail"]
        assert "live_would_block_new_buy=False" in cap_rows[0]["detail"]


def test_entry_threshold_divergence_for_candidate_between_thresholds() -> None:
    signals_df = _signals([
        {"Ticker": "AAPL", "Signal": "STRONG BUY", "Score": 92, "Price": 100.0},
    ])
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="BULL"), \
             patch.object(shadow, "get_max_positions", return_value=12), \
             patch.object(shadow, "get_dynamic_min_score_to_buy", return_value=95):
            shadow.run_v51_policy_shadow(
                signals_df=signals_df,
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="c1",
            )
        rows = _read_events(events_path)
        entry_rows = [r for r in rows if r["check_type"] == "ENTRY_THRESHOLD"]
        assert len(entry_rows) == 1
        assert entry_rows[0]["ticker"] == "AAPL"
        assert "live_would_buy=True" in entry_rows[0]["detail"]
        assert "dynamic_would_buy=False" in entry_rows[0]["detail"]


def test_entry_threshold_skipped_when_thresholds_equal() -> None:
    signals_df = _signals([
        {"Ticker": "AAPL", "Signal": "STRONG BUY", "Score": 92, "Price": 100.0},
    ])
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="BULL"), \
             patch.object(shadow, "get_max_positions", return_value=12), \
             patch.object(shadow, "get_dynamic_min_score_to_buy", return_value=90):
            shadow.run_v51_policy_shadow(
                signals_df=signals_df,
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="c1",
            )
        rows = _read_events(events_path)
        entry_rows = [r for r in rows if r["check_type"] == "ENTRY_THRESHOLD"]
        assert entry_rows == []


def test_exit_strategy_divergence_trailing_would_sell_fixed_would_hold() -> None:
    positions = {"AAPL": {"shares": 10, "avg_price": 100.0}}
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        trailing_path = Path(tmp) / "trailing_state.csv"

        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="BULL"), \
             patch.object(shadow, "get_max_positions", return_value=12), \
             patch.object(shadow, "get_dynamic_min_score_to_buy", return_value=90):
            # Cycle 1: price runs up to +10%, establishing a peak.
            shadow.run_v51_policy_shadow(
                signals_df=_signals([{"Ticker": "AAPL", "Signal": "WAIT", "Score": 0, "Price": 110.0}]),
                positions=positions,
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=50,   # generous bounds: live never exits in this test
                live_stop_loss_pct=-50,
                live_bot_cycle_id="c1",
                trailing_state_path=trailing_path,
            )
            # Cycle 2: price retreats to +4% — still above trailing-activate
            # (4%) but below the trailing stop set off the earlier +10% peak
            # (110 * 0.95 = 104.5), so the dynamic policy would exit while
            # the static fixed-band policy would still hold.
            shadow.run_v51_policy_shadow(
                signals_df=_signals([{"Ticker": "AAPL", "Signal": "WAIT", "Score": 0, "Price": 104.0}]),
                positions=positions,
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=50,
                live_stop_loss_pct=-50,
                live_bot_cycle_id="c2",
                trailing_state_path=trailing_path,
            )

        rows = _read_events(events_path)
        exit_rows = [r for r in rows if r["check_type"] == "EXIT_STRATEGY"]
        assert len(exit_rows) == 1
        assert exit_rows[0]["ticker"] == "AAPL"
        assert "HOLD" in exit_rows[0]["live_value"]
        assert "EXIT" in exit_rows[0]["dynamic_value"]


def test_exit_strategy_state_cleared_for_closed_position() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        trailing_path = Path(tmp) / "trailing_state.csv"

        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", return_value="BULL"), \
             patch.object(shadow, "get_max_positions", return_value=12), \
             patch.object(shadow, "get_dynamic_min_score_to_buy", return_value=90):
            shadow.run_v51_policy_shadow(
                signals_df=_signals([{"Ticker": "AAPL", "Signal": "WAIT", "Score": 0, "Price": 110.0}]),
                positions={"AAPL": {"shares": 10, "avg_price": 100.0}},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=50,
                live_stop_loss_pct=-50,
                live_bot_cycle_id="c1",
                trailing_state_path=trailing_path,
            )
            assert trailing_path.is_file()
            state = pd.read_csv(trailing_path)
            assert "AAPL" in set(state["Ticker"])

            # Position closed (sold) — no longer in `positions`.
            shadow.run_v51_policy_shadow(
                signals_df=_signals([{"Ticker": "AAPL", "Signal": "WAIT", "Score": 0, "Price": 95.0}]),
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=50,
                live_stop_loss_pct=-50,
                live_bot_cycle_id="c2",
                trailing_state_path=trailing_path,
            )
            state = pd.read_csv(trailing_path)
            assert "AAPL" not in set(state["Ticker"])


def test_never_raises_on_empty_or_bad_input() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        events_path = Path(tmp) / "events.csv"
        trailing_path = Path(tmp) / "trailing_state.csv"
        with patch.object(shadow, "get_default_ledger", return_value=shadow.PolicyShadowLedger(events_path)), \
             patch.object(shadow, "get_dynamic_market_regime", side_effect=Exception("network down")):
            shadow.run_v51_policy_shadow(
                signals_df=None,
                positions={},
                live_regime="BULL",
                live_max_positions=12,
                live_min_score_to_buy=90,
                live_take_profit_pct=5,
                live_stop_loss_pct=-3,
                live_bot_cycle_id="c1",
                trailing_state_path=trailing_path,
            )
    # No exception escaped — that is the assertion.


def main() -> int:
    tests = [
        test_regime_check_always_logged_agree_true_when_same,
        test_regime_divergence_logged_agree_false,
        test_max_positions_divergence_when_caps_disagree_on_block,
        test_entry_threshold_divergence_for_candidate_between_thresholds,
        test_entry_threshold_skipped_when_thresholds_equal,
        test_exit_strategy_divergence_trailing_would_sell_fixed_would_hold,
        test_exit_strategy_state_cleared_for_closed_position,
        test_never_raises_on_empty_or_bad_input,
    ]

    failed = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")

    print(f"\nResult: {len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
