import pandas as pd

from config.allocation_settings import (
    MAX_MIGRATION_PCT,
    CORE_US_TICKERS,
    MIN_GLOBAL_RANK_SCORE,
)

transfer = pd.read_csv("capital_transfer_plan.csv")
reduce_df = pd.read_csv("capital_reduce_candidates.csv")
add_df = pd.read_csv("capital_add_candidates.csv")
gap_df = pd.read_csv("allocation_gap.csv")

portfolio_value = float(pd.read_csv("portfolio.csv")["Current_Value"].fillna(0).sum())

max_cycle = round(
    portfolio_value * MAX_MIGRATION_PCT / 100,
    2
)

reduce_df = reduce_df[
    ~reduce_df["Ticker"].isin(CORE_US_TICKERS)
]

add_df = add_df[
    add_df["Global_Rank_Score"] >= MIN_GLOBAL_RANK_SCORE
]

remaining = max_cycle

sell_rows = []

for _, row in reduce_df.iterrows():

    if remaining <= 0:
        break

    amount = min(
        float(row["Position_Value"]),
        remaining
    )

    sell_rows.append({
        "Action": "SELL",
        "Ticker": row["Ticker"],
        "Amount_$": round(amount, 2)
    })

    remaining -= amount

buy_rows = []

qualified = add_df.sort_values(
    "Global_Rank_Score",
    ascending=False
)

sell_total = sum(row["Amount_$"] for row in sell_rows)

if len(qualified) > 0 and sell_total > 0:

    per_position = round(
        sell_total / len(qualified),
        2
    )

    for _, row in qualified.iterrows():

        buy_rows.append({
            "Action": "BUY",
            "Ticker": row["Ticker"],
            "Market": row["Market"],
            "Amount_$": per_position
        })

result = pd.DataFrame(
    sell_rows + buy_rows
)

result.to_csv(
    "safe_migration_plan.csv",
    index=False
)

print("\n===== SAFE MIGRATION PLAN =====\n")
print(result.to_string(index=False))
print()
print("Portfolio Value:", round(portfolio_value, 2))
print("Max Cycle:", max_cycle)
print("Protected Core:", CORE_US_TICKERS)
