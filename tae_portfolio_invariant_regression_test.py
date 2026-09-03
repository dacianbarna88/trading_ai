#!/usr/bin/env python3
"""
TAE Portfolio Invariant Regression Test — SELLs always fully liquidate.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Covers the single invariant behind most bugs fixed in this codebase: a SELL
row always fully liquidates the current holding, so only BUY rows *after*
a ticker's most recent SELL belong to its open position. A closed-then-
reopened ticker must never blend its stale closed lot into the new one.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from core.portfolio import get_cash_available, get_open_positions, open_buy_row_mask


def _portfolio(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "Date", "Ticker", "Action", "Price", "Shares", "Score", "Signal",
        "Reason", "Current_Price", "Invested", "Current_Value", "PnL", "PnL_%",
    ]
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def test_open_positions_excludes_stale_closed_lot() -> None:
    portfolio = _portfolio([
        {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "SELL", "Price": 120.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "BUY", "Price": 150.0, "Shares": 5},
    ])
    positions = get_open_positions(portfolio)
    assert positions["AAPL"]["shares"] == 5
    assert positions["AAPL"]["avg_price"] == 150.0


def test_open_positions_no_reopen_gives_no_position() -> None:
    portfolio = _portfolio([
        {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "SELL", "Price": 120.0, "Shares": 10},
    ])
    positions = get_open_positions(portfolio)
    assert "AAPL" not in positions


def test_open_positions_multiple_buys_average_correctly() -> None:
    portfolio = _portfolio([
        {"Ticker": "MSFT", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Ticker": "MSFT", "Action": "BUY", "Price": 200.0, "Shares": 10},
    ])
    positions = get_open_positions(portfolio)
    assert positions["MSFT"]["shares"] == 20
    assert positions["MSFT"]["avg_price"] == 150.0


def test_open_positions_empty_portfolio() -> None:
    assert get_open_positions(_portfolio([])) == {}


def test_open_buy_row_mask_matches_get_open_positions_shares() -> None:
    portfolio = _portfolio([
        {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "SELL", "Price": 120.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "BUY", "Price": 150.0, "Shares": 5},
        {"Ticker": "MSFT", "Action": "BUY", "Price": 200.0, "Shares": 3},
    ])
    mask = open_buy_row_mask(portfolio)
    positions = get_open_positions(portfolio)

    masked_shares_by_ticker = (
        portfolio.loc[mask].groupby("Ticker")["Shares"].sum().to_dict()
    )
    expected = {t: p["shares"] for t, p in positions.items()}
    assert masked_shares_by_ticker == expected


def test_open_buy_row_mask_excludes_closed_ticker_entirely() -> None:
    portfolio = _portfolio([
        {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "SELL", "Price": 120.0, "Shares": 10},
    ])
    mask = open_buy_row_mask(portfolio)
    assert not mask.any()


def test_open_buy_row_mask_only_flags_buy_rows_after_last_sell() -> None:
    portfolio = _portfolio([
        {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},   # idx 0: stale
        {"Ticker": "AAPL", "Action": "SELL", "Price": 120.0, "Shares": 10},  # idx 1
        {"Ticker": "AAPL", "Action": "BUY", "Price": 150.0, "Shares": 5},    # idx 2: open
    ])
    mask = open_buy_row_mask(portfolio)
    assert list(mask) == [False, False, True]


def test_open_buy_row_mask_empty_portfolio() -> None:
    mask = open_buy_row_mask(_portfolio([]))
    assert not mask.any()


def test_cash_available_basic_arithmetic() -> None:
    portfolio = _portfolio([
        {"Ticker": "AAPL", "Action": "BUY", "Price": 100.0, "Shares": 10},
        {"Ticker": "AAPL", "Action": "SELL", "Price": 120.0, "Shares": 10},
        {"Ticker": "CASH", "Action": "DEPOSIT", "Price": 1.0, "Shares": 500},
    ])
    from config.settings import STARTING_CAPITAL

    cash = get_cash_available(portfolio)
    assert cash == STARTING_CAPITAL + 500 - 1000 + 1200


def test_cash_available_empty_portfolio_returns_starting_capital() -> None:
    from config.settings import STARTING_CAPITAL

    assert get_cash_available(_portfolio([])) == STARTING_CAPITAL


def test_update_portfolio_prices_skips_closed_lot_rows() -> None:
    """A closed-then-reopened ticker: the stale closed BUY row must not be
    rewritten with today's live price/PnL, only the fresh open BUY row."""
    from core.portfolio_prices import update_portfolio_prices

    portfolio = _portfolio([
        {
            "Date": "2026-01-01", "Ticker": "AAPL", "Action": "BUY",
            "Price": 100.0, "Shares": 10, "Current_Price": 100.0,
            "Invested": 1000.0, "Current_Value": 1000.0, "PnL": 0.0, "PnL_%": 0.0,
        },
        {
            "Date": "2026-01-02", "Ticker": "AAPL", "Action": "SELL",
            "Price": 120.0, "Shares": 10, "Current_Price": 120.0,
            "Invested": 1000.0, "Current_Value": 1200.0, "PnL": 200.0, "PnL_%": 20.0,
        },
        {
            "Date": "2026-01-03", "Ticker": "AAPL", "Action": "BUY",
            "Price": 150.0, "Shares": 5, "Current_Price": 150.0,
            "Invested": 750.0, "Current_Value": 750.0, "PnL": 0.0, "PnL_%": 0.0,
        },
    ])

    saved: dict[str, pd.DataFrame] = {}

    with tempfile.TemporaryDirectory():
        with patch("core.portfolio_prices.load_portfolio", return_value=portfolio), \
             patch("core.portfolio_prices.save_portfolio", side_effect=lambda df: saved.__setitem__("df", df)), \
             patch("core.portfolio_prices.get_latest_price", return_value=200.0):
            update_portfolio_prices()

    result = saved["df"]
    stale_row = result.iloc[0]
    open_row = result.iloc[2]

    # Stale closed BUY row: untouched (still reflects its original values).
    assert stale_row["Current_Price"] == 100.0
    assert stale_row["Current_Value"] == 1000.0

    # Open BUY row: rewritten with the live price.
    assert open_row["Current_Price"] == 200.0
    assert open_row["Current_Value"] == 1000.0  # 200 * 5 shares
    assert open_row["PnL"] == 250.0  # 1000 - 750 invested


def main() -> int:
    tests = [
        test_open_positions_excludes_stale_closed_lot,
        test_open_positions_no_reopen_gives_no_position,
        test_open_positions_multiple_buys_average_correctly,
        test_open_positions_empty_portfolio,
        test_open_buy_row_mask_matches_get_open_positions_shares,
        test_open_buy_row_mask_excludes_closed_ticker_entirely,
        test_open_buy_row_mask_only_flags_buy_rows_after_last_sell,
        test_open_buy_row_mask_empty_portfolio,
        test_cash_available_basic_arithmetic,
        test_cash_available_empty_portfolio_returns_starting_capital,
        test_update_portfolio_prices_skips_closed_lot_rows,
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
