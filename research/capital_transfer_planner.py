import pandas as pd

from core.portfolio import open_buy_row_mask

gap = pd.read_csv("allocation_gap.csv")
portfolio = pd.read_csv("portfolio.csv")

# Summing Current_Value across every row (as before) double-counts: SELL
# rows carry the sale proceeds in Current_Value, and a closed-then-reopened
# ticker leaves a stale closed BUY row alongside the fresh one. Only open
# BUY rows represent value still held.
portfolio["Current_Value"] = pd.to_numeric(portfolio["Current_Value"], errors="coerce")
open_value = portfolio.loc[open_buy_row_mask(portfolio), "Current_Value"].fillna(0).sum()
total_value = open_value

rows = []

for _, row in gap.iterrows():

    market = row["Market"]

    gap_pct = float(row["Gap_%"])

    capital = round(
        total_value * gap_pct / 100,
        2
    )

    action = "HOLD"

    if capital > 0:
        action = "ADD"

    elif capital < 0:
        action = "REDUCE"

    rows.append({
        "Market": market,
        "Action": action,
        "Gap_%": gap_pct,
        "Capital_$": capital
    })

df = pd.DataFrame(rows)

df.to_csv(
    "capital_transfer_plan.csv",
    index=False
)

print("\n===== CAPITAL TRANSFER PLAN =====\n")
print(df.to_string(index=False))

print("\nPortfolio Value:", round(total_value, 2))
