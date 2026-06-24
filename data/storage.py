from pathlib import Path

import pandas as pd

from config.settings import WATCHLIST_FILE, PORTFOLIO_FILE


def load_watchlist():
    path = Path(WATCHLIST_FILE)

    if path.exists():
        tickers = [
            line.strip().upper()
            for line in path.read_text().splitlines()
            if line.strip()
        ]

        if tickers:
            return tickers

    return ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


def load_csv_safe(file, columns):
    path = Path(file)

    if path.exists():
        try:
            df = pd.read_csv(path)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    for col in columns:
        if col not in df.columns:
            df[col] = None

    return df[columns]


def load_portfolio():
    columns = [
        "Date", "Ticker", "Action", "Price", "Shares", "Score", "Signal",
        "Reason", "Current_Price", "Invested", "Current_Value", "PnL",
        "PnL_%", "Highest_Price", "Trailing_Active", "Trailing_Stop",
    ]

    return load_csv_safe(PORTFOLIO_FILE, columns)


def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False)
