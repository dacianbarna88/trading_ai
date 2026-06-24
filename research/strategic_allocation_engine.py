import pandas as pd
from pathlib import Path

hist = pd.read_csv("historical_intelligence.csv")

alloc = {
    "US": 30,
    "EU": 30,
    "UK": 10,
}

leader = hist.sort_values(
    "Bull_Probability",
    ascending=False
).iloc[0]["Market"]

horizon = Path(
    "strategic_horizon_summary.txt"
).read_text()

if "Long-Term Bias: US" in horizon:
    alloc["US"] += 15

if "Long-Term Bias: EU" in horizon:
    alloc["EU"] += 15

if "Long-Term Bias: UK" in horizon:
    alloc["UK"] += 15

if "Short-Term Bias: EU" in horizon:
    alloc["EU"] += 10

if "Short-Term Bias: US" in horizon:
    alloc["US"] += 10

if "Short-Term Bias: UK" in horizon:
    alloc["UK"] += 10

total = sum(alloc.values())

rows = []

for market, value in alloc.items():

    pct = round(value / total * 100, 1)

    rows.append({
        "Market": market,
        "Allocation_%": pct
    })

df = pd.DataFrame(rows)

df.to_csv(
    "strategic_allocations.csv",
    index=False
)

print(df.to_string(index=False))
