import yfinance as yf
import pandas as pd
import numpy as np

def safe_series(x):
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x

def get_close(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return pd.to_numeric(df["Close"], errors="coerce").dropna()

def get_historical_profile(ticker: str):
    try:
        data_2y = yf.download(ticker, period="2y", progress=False, auto_adjust=False)
        data_5y = yf.download(ticker, period="5y", progress=False, auto_adjust=False)

        if data_2y is None or data_5y is None:
            return None

        if data_2y.empty or data_5y.empty:
            return None

        close_2y = get_close(data_2y)
        close_5y = get_close(data_5y)

        if len(close_2y) < 5 or len(close_5y) < 5:
            return None

        ret_2y = (close_2y.iloc[-1] / close_2y.iloc[0] - 1) * 100
        ret_5y = (close_5y.iloc[-1] / close_5y.iloc[0] - 1) * 100

        vol_2y = close_2y.pct_change().std() * 100
        vol_5y = close_5y.pct_change().std() * 100

        return {
            "Ticker": ticker,
            "Return_2Y_%": float(ret_2y),
            "Return_5Y_%": float(ret_5y),
            "Volatility_2Y": float(vol_2y),
            "Volatility_5Y": float(vol_5y),
            "Trend_2Y": "UP" if ret_2y > 30 else "FLAT",
            "Trend_5Y": "UP" if ret_5y > 80 else "FLAT",
        }

    except Exception as e:
        print(f"[HIST ERROR] {ticker}: {repr(e)}")
        return None
