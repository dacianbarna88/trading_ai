import pandas as pd
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = "benchmark_history.csv"

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
    rows.append({
        "Timestamp": timestamp,
        "Ticker": ticker,
        "Category": category
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
