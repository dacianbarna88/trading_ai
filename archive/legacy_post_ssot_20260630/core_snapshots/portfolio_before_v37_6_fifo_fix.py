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

        buys = rows[rows["Action"].astype(str).str.upper() == "BUY"]
        sells = rows[rows["Action"].astype(str).str.upper() == "SELL"]

        buy_shares = buys["Shares"].sum()
        sell_shares = sells["Shares"].sum()
        open_shares = buy_shares - sell_shares

        if open_shares > 0:
            buy_value = (buys["Price"] * buys["Shares"]).sum()
            avg_price = buy_value / buy_shares if buy_shares else 0

            positions[ticker] = {
                "shares": open_shares,
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
