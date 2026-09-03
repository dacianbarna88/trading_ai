#!/usr/bin/env python3
"""
TAE Portfolio Integrity Guardian Regression Test.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import sys

import pandas as pd

from portfolio_integrity_guardian import check_portfolio_integrity


def _portfolio(rows: list[dict]) -> pd.DataFrame:
    columns = ["Date", "Ticker", "Action", "Price", "Shares"]
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def test_clean_portfolio_has_no_findings() -> None:
    df = _portfolio([
        {"Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Date": "2026-01-02", "Ticker": "AAPL", "Action": "SELL", "Price": 110.0, "Shares": 10},
        {"Date": "2026-01-03", "Ticker": "MSFT", "Action": "BUY", "Price": 50.0, "Shares": 5},
    ])
    assert check_portfolio_integrity(df) == []


def test_missing_required_column_is_critical() -> None:
    df = pd.DataFrame([{"Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY"}])
    findings = check_portfolio_integrity(df)
    assert len(findings) == 1
    assert findings[0]["severity"] == "CRITICAL"
    assert "Missing required column" in findings[0]["issue"]


def test_invalid_action_flagged() -> None:
    df = _portfolio([{"Date": "2026-01-01", "Ticker": "AAPL", "Action": "HOLD", "Price": 100.0, "Shares": 10}])
    findings = check_portfolio_integrity(df)
    assert len(findings) == 1
    assert "Invalid Action" in findings[0]["issue"]


def test_non_positive_price_flagged() -> None:
    df = _portfolio([{"Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY", "Price": -5.0, "Shares": 10}])
    findings = check_portfolio_integrity(df)
    assert any("Non-positive Price" in f["issue"] for f in findings)


def test_non_positive_shares_flagged() -> None:
    df = _portfolio([{"Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 0}])
    findings = check_portfolio_integrity(df)
    assert any("Non-positive Shares" in f["issue"] for f in findings)


def test_orphaned_sell_flagged() -> None:
    df = _portfolio([{"Date": "2026-01-01", "Ticker": "AAPL", "Action": "SELL", "Price": 100.0, "Shares": 10}])
    findings = check_portfolio_integrity(df)
    assert len(findings) == 1
    assert "orphaned SELL" in findings[0]["issue"]


def test_oversell_beyond_open_position_flagged() -> None:
    df = _portfolio([
        {"Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Date": "2026-01-02", "Ticker": "AAPL", "Action": "SELL", "Price": 110.0, "Shares": 15},
    ])
    findings = check_portfolio_integrity(df)
    assert len(findings) == 1
    assert "exceeds open position" in findings[0]["issue"]


def test_reopened_ticker_after_full_sell_is_clean() -> None:
    # Closed-then-reopened ticker: SELL fully liquidates, then a fresh BUY
    # starts a new position — must not be flagged as an oversell.
    df = _portfolio([
        {"Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Date": "2026-01-02", "Ticker": "AAPL", "Action": "SELL", "Price": 110.0, "Shares": 10},
        {"Date": "2026-01-03", "Ticker": "AAPL", "Action": "BUY", "Price": 120.0, "Shares": 5},
        {"Date": "2026-01-04", "Ticker": "AAPL", "Action": "SELL", "Price": 130.0, "Shares": 5},
    ])
    assert check_portfolio_integrity(df) == []


def test_cash_rows_skip_share_invariants() -> None:
    df = _portfolio([{"Date": "2026-01-01", "Ticker": "CASH", "Action": "DEPOSIT", "Price": 1.0, "Shares": 1000}])
    assert check_portfolio_integrity(df) == []


def test_missing_ticker_flagged() -> None:
    df = _portfolio([{"Date": "2026-01-01", "Ticker": None, "Action": "BUY", "Price": 100.0, "Shares": 10}])
    findings = check_portfolio_integrity(df)
    assert len(findings) == 1
    assert findings[0]["issue"] == "Missing Ticker"


def main() -> int:
    tests = [
        test_clean_portfolio_has_no_findings,
        test_missing_required_column_is_critical,
        test_invalid_action_flagged,
        test_non_positive_price_flagged,
        test_non_positive_shares_flagged,
        test_orphaned_sell_flagged,
        test_oversell_beyond_open_position_flagged,
        test_reopened_ticker_after_full_sell_is_clean,
        test_cash_rows_skip_share_invariants,
        test_missing_ticker_flagged,
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
