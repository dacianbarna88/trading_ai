import yfinance as yf
from pathlib import Path

TICKERS = {
    "US": "SPY",
    "EU": "VGK",
    "UK": "EWU",
}

CACHE_DIR = Path("data_cache")
CACHE_DIR.mkdir(exist_ok=True)

for market, ticker in TICKERS.items():
    print(f"Downloading {market} {ticker}...")

    df = yf.download(
        ticker,
        period="10y",
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        print(f"FAILED: {ticker}")
        continue

    path = CACHE_DIR / f"{ticker}_10y.csv"
    df.to_csv(path)

    print(f"Saved: {path}")

print("Historical cache complete.")
