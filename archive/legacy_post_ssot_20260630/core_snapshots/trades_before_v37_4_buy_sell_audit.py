from datetime import datetime

import pandas as pd

from config.settings import MIN_CASH_RESERVE
from core.portfolio import get_cash_available, get_open_positions
from utils.logger import log
from utils.telegram import send_telegram


def buy_position(row, portfolio, trade_usd):
    ticker = row["Ticker"]
    price = float(row["Price"])
    cash = get_cash_available(portfolio)

    if trade_usd <= 0:
        return portfolio

    investable_cash = max(cash - MIN_CASH_RESERVE, 0)

    if investable_cash <= 0:
        log(f"BUY blocat pentru {ticker}: cash reserve ${MIN_CASH_RESERVE:.2f} păstrat.")
        return portfolio

    if investable_cash < trade_usd:
        trade_usd = investable_cash

    shares = round(trade_usd / price, 4)
    invested = round(price * shares, 4)

    new_trade = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": ticker,
        "Action": "BUY",
        "Price": round(price, 2),
        "Shares": shares,
        "Score": int(row["Score"]),
        "Signal": row["Signal"],
        "Reason": "AUTO STRONG BUY DYNAMIC + MARKET REGIME",
        "Current_Price": round(price, 2),
        "Invested": invested,
        "Current_Value": invested,
        "PnL": 0,
        "PnL_%": 0,
        "Highest_Price": round(price, 2),
        "Trailing_Active": False,
        "Trailing_Stop": None,
    }

    portfolio = pd.concat([portfolio, pd.DataFrame([new_trade])], ignore_index=True)

    log(f"BUY executat: {ticker} | ${trade_usd:.2f} | {shares} shares @ {price:.2f} | Score {row['Score']} | Cash reserve ${MIN_CASH_RESERVE:.2f}")

    send_telegram(
        f"🚀 AUTO BUY\n\n"
        f"Ticker: {ticker}\n"
        f"Price: {price:.2f}\n"
        f"Shares: {shares}\n"
        f"Invested: ${invested:.2f}\n"
        f"Score: {row['Score']}\n"
        f"RSI: {row['RSI']}"
    )

    return portfolio


def sell_position(row, portfolio, reason):
    ticker = row["Ticker"]
    price = float(row["Price"])

    positions = get_open_positions(portfolio)

    if ticker not in positions:
        return portfolio

    shares = round(positions[ticker]["shares"], 4)
    avg_price = float(positions[ticker]["avg_price"])

    invested = avg_price * shares
    current_value = price * shares
    pnl = current_value - invested
    pnl_pct = (pnl / invested) * 100 if invested else 0

    new_trade = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": ticker,
        "Action": "SELL",
        "Price": round(price, 2),
        "Shares": shares,
        "Score": int(row["Score"]),
        "Signal": row["Signal"],
        "Reason": reason,
        "Current_Price": round(price, 2),
        "Invested": round(invested, 4),
        "Current_Value": round(current_value, 4),
        "PnL": round(pnl, 4),
        "PnL_%": round(pnl_pct, 4),
        "Highest_Price": None,
        "Trailing_Active": False,
        "Trailing_Stop": None,
    }

    portfolio = pd.concat([portfolio, pd.DataFrame([new_trade])], ignore_index=True)

    log(f"SELL executat: {ticker} | {shares} shares @ {price:.2f} | {reason}")

    send_telegram(
        f"💰 AUTO SELL\n\n"
        f"Ticker: {ticker}\n"
        f"Price: {price:.2f}\n"
        f"Shares: {shares}\n"
        f"PnL: ${pnl:.2f}\n"
        f"PnL %: {pnl_pct:.2f}%\n"
        f"Reason: {reason}"
    )

    return portfolio
