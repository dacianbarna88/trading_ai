import pandas as pd

gap = pd.read_csv("allocation_gap.csv")
portfolio = pd.read_csv("portfolio.csv")

total_value = portfolio["Current_Value"].fillna(0).sum()

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
