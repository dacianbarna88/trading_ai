import pandas as pd

target = pd.read_csv("strategic_allocations.csv")

portfolio = pd.read_csv("portfolio.csv")

open_buys = portfolio[
    portfolio["Action"].astype(str).str.upper() == "BUY"
]

market_map = {
    "US": 0.0,
    "EU": 0.0,
    "UK": 0.0,
}

for _, row in open_buys.iterrows():

    ticker = str(row["Ticker"])

    value = float(row.get("Current_Value", 0))

    if ticker.endswith(".PA") or ticker.endswith(".DE"):
        market_map["EU"] += value

    elif ticker.endswith(".L"):
        market_map["UK"] += value

    else:
        market_map["US"] += value

total = sum(market_map.values())

rows = []

for _, row in target.iterrows():

    market = row["Market"]

    current_pct = 0

    if total > 0:
        current_pct = round(
            market_map[market] / total * 100,
            1
        )

    target_pct = float(row["Allocation_%"])

    gap = round(
        target_pct - current_pct,
        1
    )

    rows.append({
        "Market": market,
        "Current_%": current_pct,
        "Target_%": target_pct,
        "Gap_%": gap
    })

df = pd.DataFrame(rows)

df.to_csv(
    "allocation_gap.csv",
    index=False
)

print(df.to_string(index=False))
