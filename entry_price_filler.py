import pandas as pd
from pathlib import Path
import yfinance as yf

REGISTRY_FILE = "decision_registry.csv"

if not Path(REGISTRY_FILE).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY_FILE)

updated = 0

for idx, row in df.iterrows():

    if row["Outcome"] != "PENDING":
        continue

    if float(row["Entry_Price"]) != 0.0:
        continue

    ticker = row["Ticker"]

    data = yf.download(
        ticker,
        period="5d",
        interval="1d",
        progress=False,
        auto_adjust=True
    )

    if data.empty:
        print(f"No price data for {ticker}")
        continue

    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        price = round(float(close[ticker].iloc[-1]), 2)
    else:
        price = round(float(close.iloc[-1]), 2)

    df.loc[idx, "Entry_Price"] = price
    updated += 1

    print(f"{ticker} entry price set to {price}")

df.to_csv(REGISTRY_FILE, index=False)

print()
print("===== V28.7 ENTRY PRICE FILLER =====")
print(f"Rows updated: {updated}")
print()
print(df.to_string(index=False))
