import pandas as pd

from config.settings import STARTING_CAPITAL


def get_open_positions(portfolio):
    positions = {}

    if portfolio.empty:
        return positions

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    for ticker in portfolio["Ticker"].dropna().unique():
        rows = portfolio[portfolio["Ticker"] == ticker]
        actions = rows["Action"].astype(str).str.upper()

        # SELLs in this system always fully liquidate the current holding, so
        # only BUY rows after the most recent SELL belong to the open position —
        # otherwise a closed-then-reopened ticker would blend the stale closed
        # lot's cost basis into the new position's average price.
        sell_idx = rows.index[actions == "SELL"]
        if len(sell_idx):
            rows = rows[rows.index > sell_idx.max()]

        buys = rows[rows["Action"].astype(str).str.upper() == "BUY"]
        buy_shares = buys["Shares"].sum()

        if buy_shares > 0:
            buy_value = (buys["Price"] * buys["Shares"]).sum()
            avg_price = buy_value / buy_shares

            positions[ticker] = {
                "shares": buy_shares,
                "avg_price": avg_price,
            }

    return positions


def get_cash_available(portfolio):
    if portfolio.empty:
        return STARTING_CAPITAL

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    actions = portfolio["Action"].astype(str).str.upper()

    buys = portfolio[actions == "BUY"]
    sells = portfolio[actions == "SELL"]
    deposits = portfolio[actions == "DEPOSIT"]

    spent = (buys["Price"] * buys["Shares"]).sum()
    received = (sells["Price"] * sells["Shares"]).sum()
    deposited = (deposits["Price"] * deposits["Shares"]).sum()

    return STARTING_CAPITAL + deposited - spent + received
