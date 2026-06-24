import pandas as pd

from core.indicators import get_latest_price
from data.storage import load_portfolio, save_portfolio
from utils.logger import log


def update_portfolio_prices():
    portfolio = load_portfolio()

    if portfolio.empty:
        return

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    for i, row in portfolio.iterrows():
        ticker = row["Ticker"]

        if pd.isna(ticker):
            continue

        current_price = get_latest_price(ticker, log)

        if current_price is None:
            current_price = row["Price"]

        price = float(row["Price"])
        shares = float(row["Shares"])

        invested = price * shares
        current_value = float(current_price) * shares
        pnl = current_value - invested
        pnl_pct = (pnl / invested) * 100 if invested else 0

        portfolio.loc[i, "Current_Price"] = round(current_price, 2)
        portfolio.loc[i, "Invested"] = round(invested, 4)
        portfolio.loc[i, "Current_Value"] = round(current_value, 4)
        portfolio.loc[i, "PnL"] = round(pnl, 4)
        portfolio.loc[i, "PnL_%"] = round(pnl_pct, 4)

    save_portfolio(portfolio)
    log("portfolio.csv actualizat cu prețuri live.")
