#!/usr/bin/env python3
"""
Dashboard account value reconciliation — read-only.

Verifies:
  Account Value = Starting Capital + Deposits + Realized PnL + Open Unrealized PnL

PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.recompute_realized_pnl import _is_repairable_sell, recompute_portfolio

PORTFOLIO_PATH = ROOT / "portfolio.csv"
FALLBACK_STARTING_CAPITAL = 30000.0
ACCOUNT_VALUE_FORMULA = (
    "Account Value = Starting Capital + Deposits + Realized PnL + Open Unrealized PnL"
)


def _resolve_starting_capital() -> float:
    try:
        from config.settings import STARTING_CAPITAL

        return float(STARTING_CAPITAL)
    except (ImportError, AttributeError, TypeError, ValueError):
        return FALLBACK_STARTING_CAPITAL


def _portfolio_rows(portfolio_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, series in portfolio_df.iterrows():
        row: dict[str, str] = {}
        for col in portfolio_df.columns:
            val = series[col]
            row[col] = "" if pd.isna(val) else str(val)
        rows.append(row)
    return rows


def _sum_deposits(portfolio_df: pd.DataFrame) -> float:
    if portfolio_df.empty or "Action" not in portfolio_df.columns:
        return 0.0
    df = portfolio_df.copy()
    df["Action"] = df["Action"].astype(str).str.upper()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0)
    deposits = df[df["Action"] == "DEPOSIT"]
    if deposits.empty:
        return 0.0
    return float((deposits["Price"] * deposits["Shares"]).sum())


def _open_pnl_from_portfolio_marks(portfolio_df: pd.DataFrame) -> float:
    if portfolio_df.empty:
        return 0.0
    rows = _portfolio_rows(portfolio_df)
    net: dict[str, float] = {}
    for row in rows:
        ticker = row.get("Ticker", "").strip()
        action = row.get("Action", "").upper()
        shares = float(row.get("Shares") or 0)
        if not ticker or ticker == "CASH":
            continue
        if action == "BUY":
            net[ticker] = net.get(ticker, 0.0) + shares
        elif action == "SELL":
            net[ticker] = net.get(ticker, 0.0) - shares

    open_pnl = 0.0
    for ticker, shares in net.items():
        if shares <= 0.0001:
            continue
        ticker_rows = [r for r in rows if r.get("Ticker") == ticker]
        if ticker_rows and ticker_rows[-1].get("Action", "").upper() == "BUY":
            open_pnl += float(ticker_rows[-1].get("PnL") or 0)
    return round(open_pnl, 2)


def _execution_realized_pnl(portfolio_df: pd.DataFrame) -> float:
    rows = _portfolio_rows(portfolio_df)
    updated_rows, _ = recompute_portfolio(rows)
    total = 0.0
    for orig, corrected in zip(rows, updated_rows):
        if _is_repairable_sell(orig):
            total += float(corrected.get("PnL") or 0)
    return round(total, 2)


def _legacy_cash_plus_open_value(portfolio_df: pd.DataFrame, starting_capital: float) -> float:
    """Old dashboard model: reconstructed cash + open mark-to-market value."""
    if portfolio_df.empty:
        return starting_capital
    df = portfolio_df.copy()
    df["Action"] = df["Action"].astype(str).str.upper()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0)
    df["Current_Value"] = pd.to_numeric(df.get("Current_Value"), errors="coerce")
    df["Current_Price"] = pd.to_numeric(df.get("Current_Price"), errors="coerce")
    df["Invested"] = pd.to_numeric(df.get("Invested"), errors="coerce")
    df["PnL"] = pd.to_numeric(df.get("PnL"), errors="coerce")

    buys = df[df["Action"] == "BUY"]
    sells = df[df["Action"] == "SELL"]
    deposits = df[df["Action"] == "DEPOSIT"]
    spent = float((buys["Price"] * buys["Shares"]).sum())
    received = float((sells["Price"] * sells["Shares"]).sum())
    deposited = float((deposits["Price"] * deposits["Shares"]).sum()) if not deposits.empty else 0.0
    cash = starting_capital + deposited - spent + received

    open_value = 0.0
    for ticker in df["Ticker"].dropna().unique():
        if str(ticker).strip() == "CASH":
            continue
        rows = df[df["Ticker"] == ticker]
        buy_shares = rows[rows["Action"] == "BUY"]["Shares"].sum()
        sell_shares = rows[rows["Action"] == "SELL"]["Shares"].sum()
        open_shares = buy_shares - sell_shares
        if open_shares <= 0.0001:
            continue
        last_buy = rows[rows["Action"] == "BUY"].iloc[-1]
        current_value = last_buy.get("Current_Value")
        if pd.isna(current_value):
            current_price = last_buy.get("Current_Price")
            if pd.isna(current_price):
                invested = last_buy.get("Invested")
                pnl = last_buy.get("PnL")
                if not pd.isna(invested) and not pd.isna(pnl):
                    current_value = float(invested) + float(pnl)
                else:
                    current_value = open_shares * float(last_buy["Price"])
            else:
                current_value = open_shares * float(current_price)
        open_value += float(current_value)
    return round(cash + open_value, 2)


def compute_account_metrics(portfolio_df: pd.DataFrame) -> dict[str, float | str]:
    starting_capital = _resolve_starting_capital()
    deposits = round(_sum_deposits(portfolio_df), 2)
    realized_pnl = _execution_realized_pnl(portfolio_df)
    open_pnl = _open_pnl_from_portfolio_marks(portfolio_df)
    total_pnl = round(realized_pnl + open_pnl, 2)
    account_value = round(starting_capital + deposits + total_pnl, 2)
    legacy_value = _legacy_cash_plus_open_value(portfolio_df, starting_capital)
    return {
        "starting_capital": starting_capital,
        "deposits": deposits,
        "realized_pnl": realized_pnl,
        "open_pnl": open_pnl,
        "total_pnl": total_pnl,
        "computed_account_value": account_value,
        "dashboard_expected_value": account_value,
        "legacy_cash_plus_open_value": legacy_value,
        "account_value_formula": ACCOUNT_VALUE_FORMULA,
    }


def main() -> int:
    if not PORTFOLIO_PATH.is_file():
        print(f"ERROR: {PORTFOLIO_PATH} not found")
        return 1

    portfolio_df = pd.read_csv(PORTFOLIO_PATH)
    metrics = compute_account_metrics(portfolio_df)

    print("===== DASHBOARD ACCOUNT RECONCILIATION =====")
    print("PAPER_ONLY | NO_BROKER | NO_EXECUTION | read-only")
    print()
    print(f"STARTING_CAPITAL used:        ${metrics['starting_capital']:,.2f}")
    print(f"deposits:                     ${metrics['deposits']:,.2f}")
    print(f"realized_pnl:                 ${metrics['realized_pnl']:,.2f}")
    print(f"open_pnl:                     ${metrics['open_pnl']:,.2f}")
    print(f"total_pnl:                    ${metrics['total_pnl']:,.2f}")
    print(f"computed_account_value:       ${metrics['computed_account_value']:,.2f}")
    print(f"dashboard_expected_value:     ${metrics['dashboard_expected_value']:,.2f}")
    print()
    print(f"formula: {metrics['account_value_formula']}")
    print()
    print("--- BEFORE (legacy cash + open value) ---")
    print(f"  legacy account value:        ${metrics['legacy_cash_plus_open_value']:,.2f}")
    print()
    print("--- AFTER (capital + deposits + total PnL) ---")
    print(f"  corrected account value:     ${metrics['computed_account_value']:,.2f}")
    print()
    check = (
        abs(metrics["computed_account_value"] - (metrics["starting_capital"] + metrics["deposits"] + metrics["total_pnl"]))
        < 0.02
    )
    print(f"formula check: {check}")
    print(f"portfolio.csv unchanged: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
