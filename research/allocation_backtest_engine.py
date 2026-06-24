import pandas as pd
from pathlib import Path

benchmarks = {
    "US": "SPY",
    "EU": "VGK",
    "UK": "EWU",
}

rows = []

for market, ticker in benchmarks.items():
    path = Path("data_cache") / f"{ticker}_10y.csv"

    if not path.exists():
        print(f"Lipsește cache: {path}")
        continue

    data = pd.read_csv(path)

    close_col = "Close"
    if close_col not in data.columns:
        close_candidates = [c for c in data.columns if "Close" in c]
        if not close_candidates:
            print(f"Nu găsesc Close pentru {ticker}")
            continue
        close_col = close_candidates[0]

    close = pd.to_numeric(data[close_col], errors="coerce").dropna()

    if len(close) < 100:
        continue

    start_price = float(close.iloc[0])
    end_price = float(close.iloc[-1])

    total_return = round(((end_price / start_price) - 1) * 100, 2)

    rows.append({
        "Market": market,
        "Ticker": ticker,
        "Return_10Y_%": total_return,
    })

df = pd.DataFrame(rows)
df.to_csv("allocation_backtest_baseline.csv", index=False)

print("\n===== BACKTEST BASELINE FROM CACHE =====\n")
print(df.to_string(index=False))
