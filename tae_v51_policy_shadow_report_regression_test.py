#!/usr/bin/env python3
"""
TAE V5.1 Policy Shadow Report Regression Test.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | READ_ONLY
"""

from __future__ import annotations

import sys

import pandas as pd

from v51_policy_shadow_report import build_report


def _events(rows: list[dict]) -> pd.DataFrame:
    columns = ["check_type", "ticker", "live_value", "dynamic_value", "agree", "detail", "live_bot_cycle_id"]
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def test_no_cycles_observed() -> None:
    report = build_report(_events([]))
    assert "No shadow data yet" in report


def test_regime_divergence_rate_computed_correctly() -> None:
    df = _events([
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "BULL", "agree": True},
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "NEUTRAL", "agree": False},
        {"check_type": "MAX_POSITIONS", "ticker": "PORTFOLIO", "live_value": "12", "dynamic_value": "12", "agree": True},
        {"check_type": "MAX_POSITIONS", "ticker": "PORTFOLIO", "live_value": "12", "dynamic_value": "8", "agree": True},
    ])
    report = build_report(df)
    assert "Cycles observed: 2" in report
    assert "Regime divergence: 1/2 cycles (50.0%)" in report
    assert "dynamic regime was NEUTRAL" in report


def test_regime_agree_parsed_as_bool_dtype_still_counted_correctly() -> None:
    # Simulates what pd.read_csv actually produces: lowercase "true"/"false"
    # strings get auto-parsed as a real bool dtype column, not strings.
    df = _events([
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "BULL", "agree": True},
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "NEUTRAL", "agree": False},
        {"check_type": "MAX_POSITIONS", "ticker": "PORTFOLIO", "live_value": "12", "dynamic_value": "12", "agree": True},
        {"check_type": "MAX_POSITIONS", "ticker": "PORTFOLIO", "live_value": "12", "dynamic_value": "12", "agree": True},
    ])
    assert df["agree"].dtype == bool
    report = build_report(df)
    assert "Regime divergence: 1/2 cycles (50.0%)" in report


def test_max_positions_divergence_rate() -> None:
    df = _events([
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "BULL", "agree": True},
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "BULL", "agree": True},
        {"check_type": "MAX_POSITIONS", "ticker": "PORTFOLIO", "live_value": "12", "dynamic_value": "0", "agree": False},
        {"check_type": "MAX_POSITIONS", "ticker": "PORTFOLIO", "live_value": "12", "dynamic_value": "12", "agree": True},
    ])
    report = build_report(df)
    assert "MAX_POSITIONS block/allow divergence: 1/2 cycles (50.0%)" in report


def test_entry_threshold_divergences_counted_by_ticker() -> None:
    df = _events([
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "BULL", "agree": True},
        {"check_type": "ENTRY_THRESHOLD", "ticker": "AAPL", "live_value": "90", "dynamic_value": "95", "agree": False},
        {"check_type": "ENTRY_THRESHOLD", "ticker": "AAPL", "live_value": "90", "dynamic_value": "95", "agree": False},
        {"check_type": "ENTRY_THRESHOLD", "ticker": "MSFT", "live_value": "90", "dynamic_value": "95", "agree": False},
    ])
    report = build_report(df)
    assert "Entry-threshold divergences logged: 3" in report
    assert "AAPL: 2 time(s)" in report
    assert "MSFT: 1 time(s)" in report


def test_exit_strategy_direction_split() -> None:
    df = _events([
        {"check_type": "REGIME", "ticker": "MARKET", "live_value": "BULL", "dynamic_value": "BULL", "agree": True},
        {
            "check_type": "EXIT_STRATEGY", "ticker": "AAPL",
            "live_value": "fixed_tp5_sl-3:HOLD", "dynamic_value": "trailing:EXIT", "agree": False,
        },
        {
            "check_type": "EXIT_STRATEGY", "ticker": "MSFT",
            "live_value": "fixed_tp5_sl-3:EXIT", "dynamic_value": "trailing:HOLD", "agree": False,
        },
    ])
    report = build_report(df)
    assert "Exit-strategy divergences logged: 2" in report
    assert "trailing-stop would exit while fixed TP/SL holds: 1" in report
    assert "fixed TP/SL would exit while trailing-stop holds: 1" in report


def main() -> int:
    tests = [
        test_no_cycles_observed,
        test_regime_divergence_rate_computed_correctly,
        test_regime_agree_parsed_as_bool_dtype_still_counted_correctly,
        test_max_positions_divergence_rate,
        test_entry_threshold_divergences_counted_by_ticker,
        test_exit_strategy_direction_split,
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
