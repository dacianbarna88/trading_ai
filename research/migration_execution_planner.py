import pandas as pd

reduce_df = pd.read_csv("capital_reduce_candidates.csv")
add_df = pd.read_csv("capital_add_candidates.csv")
plan = pd.read_csv("capital_transfer_plan.csv")

reduce_budget = abs(float(plan[plan["Market"] == "US"]["Capital_$"].iloc[0]))
eu_budget = float(plan[plan["Market"] == "EU"]["Capital_$"].iloc[0])
uk_budget = float(plan[plan["Market"] == "UK"]["Capital_$"].iloc[0])

reduce_plan = []
remaining_reduce = reduce_budget

for _, row in reduce_df.iterrows():
    if remaining_reduce <= 0:
        break

    value = float(row["Position_Value"])
    amount = min(value, remaining_reduce)

    reduce_plan.append({
        "Action": "SELL_REDUCE",
        "Ticker": row["Ticker"],
        "Market": "US",
        "Amount_$": round(amount, 2),
    })

    remaining_reduce -= amount

add_plan = []

for market, budget in [("EU", eu_budget), ("UK", uk_budget)]:
    candidates = add_df[add_df["Market"] == market].copy()

    candidates = candidates.sort_values(
        "Global_Rank_Score",
        ascending=False
    )

    if candidates.empty or budget <= 0:
        continue

    top = candidates.head(3)
    per_position = budget / len(top)

    for _, row in top.iterrows():
        add_plan.append({
            "Action": "BUY_ADD",
            "Ticker": row["Ticker"],
            "Market": market,
            "Amount_$": round(per_position, 2),
        })

df = pd.DataFrame(reduce_plan + add_plan)
df.to_csv("migration_execution_plan.csv", index=False)

print("===== MIGRATION EXECUTION PLAN =====")
print(df.to_string(index=False))
