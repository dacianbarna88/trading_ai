import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = "benchmark_price_history.csv"

benchmarks = [
    ("SPY", "MARKET"),
    ("QQQ", "US_TECH"),
    ("XLK", "TECHNOLOGY"),
    ("VGK", "EUROPE"),
    ("EWU", "UK"),
    ("IWM", "US_SMALL_CAP"),
]

timestamp = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

rows = []

for ticker, category in benchmarks:

    try:
        data = yf.download(
            ticker,
            period="5d",
            progress=False,
            auto_adjust=True
        )

        close = data["Close"]

        if isinstance(close, pd.DataFrame):
            close = close[ticker]

        close = close.dropna()

        if close.empty:
            price = None
        else:
            price = round(
                float(close.iloc[-1]),
                2
            )

    except Exception:
        price = None

    rows.append({
        "Timestamp": timestamp,
        "Ticker": ticker,
        "Category": category,
        "Price": price
    })

new_df = pd.DataFrame(rows)

if Path(OUTPUT_FILE).exists():
    old = pd.read_csv(OUTPUT_FILE)

    new_df = pd.concat(
        [old, new_df],
        ignore_index=True
    )

new_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print(
    new_df.tail(len(benchmarks))
)
