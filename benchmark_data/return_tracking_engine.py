import pandas as pd
from pathlib import Path

INPUT_FILE = "benchmark_price_history.csv"
OUTPUT_FILE = "return_tracking_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_BENCHMARK_PRICE_HISTORY")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

lines = [
    "===== V25.4 RETURN TRACKING ENGINE =====",
    ""
]

for ticker in sorted(df["Ticker"].unique()):

    t = df[df["Ticker"] == ticker].copy()
    t["Price"] = pd.to_numeric(t["Price"], errors="coerce")
    t = t.dropna(subset=["Price"])

    if len(t) < 2:

        lines.append(
            f"{ticker} | INSUFFICIENT_HISTORY"
        )

        continue

    start_price = float(t.iloc[-2]["Price"])
    end_price = float(t.iloc[-1]["Price"])

    ret = round(
        ((end_price - start_price) / start_price) * 100,
        2
    )

    lines.append(
        f"{ticker} | Return {ret}%"
    )

lines.extend([
    "",
    "Status:",
    "RETURN_TRACKING_ACTIVE",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(lines)

Path(OUTPUT_FILE).write_text(text)

print(text)
