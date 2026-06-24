import pandas as pd
from pathlib import Path

INPUT_FILE = "benchmark_price_history.csv"
OUTPUT_FILE = "benchmark_data_quality_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_BENCHMARK_PRICE_HISTORY")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

latest_timestamp = df["Timestamp"].dropna().iloc[-1]

latest = df[df["Timestamp"] == latest_timestamp].copy()

valid_prices = latest["Price"].notna().sum()
missing_prices = latest["Price"].isna().sum()
total = len(latest)

if missing_prices == 0 and total > 0:
    status = "VALID"
else:
    status = "WARNING_MISSING_PRICES"

summary = [
    "===== V25.2 BENCHMARK DATA QUALITY GUARD =====",
    "",
    f"Latest Timestamp: {latest_timestamp}",
    f"Benchmarks Checked: {total}",
    f"Valid Prices: {valid_prices}",
    f"Missing Prices: {missing_prices}",
    "",
    f"Data Quality Status: {status}",
    "",
    "Benchmark Prices:",
]

for _, r in latest.iterrows():
    summary.append(
        f"{r['Ticker']} | {r['Category']} | Price {r['Price']}"
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
