#!/usr/bin/env python3
from pathlib import Path

import pandas as pd
import yfinance as yf

from config.settings import STARTING_CAPITAL

PORTFOLIO_FILE = "portfolio.csv"
CAPITAL_BASELINE = 30000


def load_portfolio(path=PORTFOLIO_FILE):
    portfolio_path = Path(path)
    if not portfolio_path.exists():
        raise SystemExit(f"{path} not found")

    df = pd.read_csv(portfolio_path)
    if df.empty:
        return df

    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce")
    df["Action"] = df["Action"].astype(str).str.upper()
    return df


def get_live_price(ticker):
    try:
        data = yf.download(ticker, period="5d", auto_adjust=False, progress=False)
        if data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            close = data[("Close", ticker)].dropna()
        else:
            close = data["Close"].dropna()

        if close.empty:
            return None

        return float(close.iloc[-1])
    except Exception:
        return None


def get_latest_portfolio_price(ticker_rows):
    if "Current_Price" not in ticker_rows.columns:
        return None

    prices = pd.to_numeric(ticker_rows["Current_Price"], errors="coerce").dropna()
    if prices.empty:
        return None

    return float(prices.iloc[-1])


def compute_cash(portfolio):
    if portfolio.empty:
        return float(STARTING_CAPITAL)

    buys = portfolio[portfolio["Action"] == "BUY"]
    sells = portfolio[portfolio["Action"] == "SELL"]
    deposits = portfolio[portfolio["Action"] == "DEPOSIT"]

    spent = (buys["Price"] * buys["Shares"]).sum()
    received = (sells["Price"] * sells["Shares"]).sum()
    deposited = (deposits["Price"] * deposits["Shares"]).sum() if not deposits.empty else 0

    return float(STARTING_CAPITAL + deposited - spent + received)


def reconstruct_open_positions(portfolio):
    if portfolio.empty:
        return pd.DataFrame()

    rows = []

    for ticker in portfolio["Ticker"].dropna().unique():
        ticker = str(ticker).strip()
        if not ticker or ticker.upper() == "CASH":
            continue

        ticker_rows = portfolio[portfolio["Ticker"] == ticker]
        buy_rows = ticker_rows[ticker_rows["Action"] == "BUY"]
        sell_rows = ticker_rows[ticker_rows["Action"] == "SELL"]

        buy_shares = buy_rows["Shares"].sum()
        sell_shares = sell_rows["Shares"].sum()
        shares_open = buy_shares - sell_shares

        if shares_open <= 0:
            continue

        buy_cost = (buy_rows["Price"] * buy_rows["Shares"]).sum()
        avg_price = buy_cost / buy_shares if buy_shares else 0
        invested = shares_open * avg_price

        current_price = get_live_price(ticker)
        if current_price is None:
            current_price = get_latest_portfolio_price(ticker_rows)
        if current_price is None:
            current_price = avg_price

        current_value = shares_open * current_price
        pnl = current_value - invested
        pnl_pct = (pnl / invested * 100) if invested else 0

        rows.append(
            {
                "Ticker": ticker,
                "Shares Open": shares_open,
                "Invested Cost Basis": invested,
                "Current Value": current_value,
                "PnL": pnl,
                "PnL %": pnl_pct,
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("Ticker").reset_index(drop=True)


def format_money(value):
    return f"${value:,.2f}"


def format_pct(value):
    return f"{value:+.2f}%"


def print_table(df):
    display = df.copy()
    display["Shares Open"] = display["Shares Open"].map(lambda x: f"{x:.4f}")
    display["Invested Cost Basis"] = display["Invested Cost Basis"].map(format_money)
    display["Current Value"] = display["Current Value"].map(format_money)
    display["PnL"] = display["PnL"].map(format_money)
    display["PnL %"] = display["PnL %"].map(format_pct)
    print(display.to_string(index=False))


def main():
    portfolio = load_portfolio()
    open_positions = reconstruct_open_positions(portfolio)
    cash = compute_cash(portfolio)

    total_open_invested = (
        open_positions["Invested Cost Basis"].sum() if not open_positions.empty else 0
    )
    total_open_value = open_positions["Current Value"].sum() if not open_positions.empty else 0
    open_pnl = open_positions["PnL"].sum() if not open_positions.empty else 0
    open_pnl_pct = (open_pnl / total_open_invested * 100) if total_open_invested else 0

    account_value = cash + total_open_value
    account_pnl = account_value - CAPITAL_BASELINE
    account_return_pct = (account_pnl / CAPITAL_BASELINE * 100) if CAPITAL_BASELINE else 0

    print("===== REAL OPEN POSITIONS =====")
    print()
    if open_positions.empty:
        print("No open positions.")
    else:
        print_table(open_positions)

    print()
    print("===== ACCOUNT AUDIT =====")
    print()
    print(f"Total Open Invested: {format_money(total_open_invested)}")
    print(f"Total Open Value: {format_money(total_open_value)}")
    print(f"Open PnL: {format_money(open_pnl)}")
    print(f"Open PnL %: {format_pct(open_pnl_pct)}")
    print()
    print(f"Capital Baseline: {format_money(CAPITAL_BASELINE)}")
    print(f"Current Cash: {format_money(cash)}")
    print(f"Open Position Value: {format_money(total_open_value)}")
    print(f"Account Value: {format_money(account_value)}")
    print(f"Return vs Baseline: {format_pct(account_return_pct)} ({format_money(account_pnl)})")


if __name__ == "__main__":
    main()
