import pandas as pd

from core.market_sessions import get_ticker_region
from core.portfolio import open_buy_row_mask

target = pd.read_csv("strategic_allocations.csv")

portfolio = pd.read_csv("portfolio.csv")

# A plain Action == "BUY" filter includes a closed-then-reopened ticker's
# stale, already-sold BUY row alongside its fresh one, inflating that
# market's allocation. Only rows after the ticker's most recent SELL are
# still open.
open_buys = portfolio[open_buy_row_mask(portfolio)]

target_markets = set(target["Market"].astype(str))
market_map = {market: 0.0 for market in target_markets}

for _, row in open_buys.iterrows():

    ticker = str(row["Ticker"])

    value = float(row.get("Current_Value", 0))

    region = get_ticker_region(ticker)

    if region not in market_map:
        continue

    market_map[region] += value

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
