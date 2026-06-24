import yfinance as yf
import pandas as pd

def get_data(ticker):

    df = yf.download(ticker, period="10d", interval="1d", progress=False)

    if df is None or df.empty:
        return None

    # 🔥 FLATTEN SAFETY (CRITICAL FIX)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"]

    # force scalar safety
    price = float(close.iloc[-1])

    sma = float(close.rolling(5).mean().iloc[-1])
    if pd.isna(sma):
        sma = price

    delta = close.diff()

    gain = delta.clip(lower=0).mean()
    loss = (-delta.clip(upper=0)).mean()

    if loss == 0 or pd.isna(loss):
        rsi = 50
    else:
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

    return {
        "price": price,
        "sma": sma,
        "rsi": float(rsi)
    }
