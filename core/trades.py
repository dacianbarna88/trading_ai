from datetime import datetime

import pandas as pd

from config.settings import MIN_CASH_RESERVE
from core.portfolio import get_cash_available, get_open_positions
from utils.logger import log
from utils.telegram import send_telegram

ACCOUNTING_CHECK_NEGATIVE = " | ACCOUNTING_CHECK: NEGATIVE_REALIZED"
ACCOUNTING_CHECK_POSITIVE = " | ACCOUNTING_CHECK: POSITIVE_REALIZED"
ACCOUNTING_WARNING_AVG_COST = " | ACCOUNTING_WARNING: AVG_COST_MISSING"


def compute_realized_pnl(sell_execution_price: float, avg_buy_cost: float, shares_sold: float) -> float:
    return (sell_execution_price - avg_buy_cost) * shares_sold


def compute_realized_pnl_pct(sell_execution_price: float, avg_buy_cost: float) -> float:
    if avg_buy_cost <= 0:
        return 0.0
    return ((sell_execution_price - avg_buy_cost) / avg_buy_cost) * 100


def annotate_reason_accounting_check(reason: str, signal: str, realized_pnl: float) -> str:
    """Append accounting check tags when reason/signal contradicts realized PnL."""
    updated = reason or ""
    reason_upper = updated.upper()
    signal_upper = (signal or "").upper()

    if realized_pnl < 0:
        if (
            "PROFIT" in reason_upper or "TAKE PROFIT" in reason_upper
            or "TAKE PROFIT" in signal_upper
        ):
            if ACCOUNTING_CHECK_NEGATIVE not in updated:
                updated += ACCOUNTING_CHECK_NEGATIVE
    elif realized_pnl > 0:
        if "STOP LOSS" in reason_upper:
            if ACCOUNTING_CHECK_POSITIVE not in updated:
                updated += ACCOUNTING_CHECK_POSITIVE

    return updated


def is_immutable_portfolio_row(action: str, reason: str = "", signal: str = "") -> bool:
    """Rows whose realized accounting must not be overwritten by live price refresh."""
    action_upper = (action or "").upper()
    reason_upper = (reason or "").upper()
    signal_upper = (signal or "").upper()

    if action_upper in ("DEPOSIT",):
        return True
    if action_upper == "SELL":
        if "REBALANCE" in reason_upper or signal_upper == "REBALANCE":
            return False
        return True
    return False


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
    sell_price = float(row["Price"])

    positions = get_open_positions(portfolio)

    if ticker not in positions:
        return portfolio

    shares = round(positions[ticker]["shares"], 4)
    avg_buy_cost = float(positions[ticker]["avg_price"])

    final_reason = reason
    if avg_buy_cost <= 0:
        cost_basis = sell_price * shares
        proceeds = sell_price * shares
        pnl = 0.0
        pnl_pct = 0.0
        if ACCOUNTING_WARNING_AVG_COST not in final_reason:
            final_reason += ACCOUNTING_WARNING_AVG_COST
    else:
        cost_basis = avg_buy_cost * shares
        proceeds = sell_price * shares
        pnl = compute_realized_pnl(sell_price, avg_buy_cost, shares)
        pnl_pct = compute_realized_pnl_pct(sell_price, avg_buy_cost)

    final_reason = annotate_reason_accounting_check(
        final_reason,
        str(row.get("Signal", "")),
        pnl,
    )

    new_trade = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": ticker,
        "Action": "SELL",
        "Price": round(sell_price, 2),
        "Shares": shares,
        "Score": int(row["Score"]),
        "Signal": row["Signal"],
        "Reason": final_reason,
        "Current_Price": round(sell_price, 2),
        "Invested": round(cost_basis, 4),
        "Current_Value": round(proceeds, 4),
        "PnL": round(pnl, 4),
        "PnL_%": round(pnl_pct, 4),
        "Highest_Price": None,
        "Trailing_Active": False,
        "Trailing_Stop": None,
    }

    portfolio = pd.concat([portfolio, pd.DataFrame([new_trade])], ignore_index=True)

    log(
        f"SELL executat: {ticker} | {shares} shares @ {sell_price:.2f} | "
        f"realized PnL ${pnl:.2f} ({pnl_pct:.2f}%) | {final_reason}"
    )

    send_telegram(
        f"💰 AUTO SELL\n\n"
        f"Ticker: {ticker}\n"
        f"Price: {sell_price:.2f}\n"
        f"Shares: {shares}\n"
        f"PnL: ${pnl:.2f}\n"
        f"PnL %: {pnl_pct:.2f}%\n"
        f"Reason: {final_reason}"
    )

    return portfolio
