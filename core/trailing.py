import pandas as pd

from config.settings import TRAILING_ACTIVATE_PCT, TRAILING_DISTANCE_PCT
from utils.logger import log


def update_trailing_state(portfolio, ticker, price, avg_price):
    ticker_mask = portfolio["Ticker"].astype(str).str.upper() == str(ticker).upper()

    # SELLs in this system always fully liquidate the current holding, so
    # only rows after the most recent SELL belong to the open position —
    # otherwise a closed-then-reopened ticker could pick up a stale
    # Highest_Price from the earlier, now-closed round and set the new
    # position's trailing stop off a phantom peak.
    sell_idx = portfolio.index[
        ticker_mask & (portfolio["Action"].astype(str).str.upper() == "SELL")
    ]
    if len(sell_idx):
        ticker_mask = ticker_mask & (portfolio.index > sell_idx.max())

    buy_mask = ticker_mask & (portfolio["Action"].astype(str).str.upper() == "BUY")

    if not buy_mask.any():
        return portfolio, False, None

    existing_highest = pd.to_numeric(
        portfolio.loc[buy_mask, "Highest_Price"],
        errors="coerce",
    ).max()

    previous_trailing_active = (
        portfolio.loc[buy_mask, "Trailing_Active"]
        .astype(str)
        .str.upper()
        .isin(["TRUE", "1", "YES"])
        .any()
    )

    if pd.isna(existing_highest):
        existing_highest = avg_price

    highest_price = max(float(existing_highest), float(price), float(avg_price))
    pnl_from_avg = ((float(price) - float(avg_price)) / float(avg_price)) * 100 if avg_price else 0

    trailing_active = bool(pnl_from_avg >= TRAILING_ACTIVATE_PCT)
    trailing_stop = None

    if trailing_active:
        trailing_stop = highest_price * (1 - TRAILING_DISTANCE_PCT / 100)

    portfolio.loc[buy_mask, "Highest_Price"] = round(highest_price, 2)
    portfolio.loc[buy_mask, "Trailing_Active"] = trailing_active
    portfolio.loc[buy_mask, "Trailing_Stop"] = round(trailing_stop, 2) if trailing_stop else None

    if trailing_active and not previous_trailing_active:
        log(
            f"Trailing ACTIVAT: {ticker} | PnL {pnl_from_avg:.2f}% | "
            f"High {highest_price:.2f} | Stop {trailing_stop:.2f}"
        )

    should_sell = bool(trailing_active and trailing_stop and float(price) <= trailing_stop)
    return portfolio, should_sell, trailing_stop
