import pandas as pd
from data.storage import load_portfolio
from core.portfolio import get_open_positions

positions = get_open_positions(load_portfolio())
ranking = pd.read_csv("global_opportunity_ranking.csv")
plan = pd.read_csv("capital_transfer_plan.csv")

reduce_budget = abs(float(plan[plan["Market"] == "US"]["Capital_$"].iloc[0]))
eu_budget = float(plan[plan["Market"] == "EU"]["Capital_$"].iloc[0])
uk_budget = float(plan[plan["Market"] == "UK"]["Capital_$"].iloc[0])

rows = []
for ticker, pos in positions.items():
    if not ticker.endswith(".PA") and not ticker.endswith(".DE") and not ticker.endswith(".L"):
        rows.append({
            "Ticker": ticker,
            "Market": "US",
            "Position_Value": round(pos["shares"] * pos["avg_price"], 2),
            "Action": "REDUCE_CANDIDATE"
        })

reduce_df = pd.DataFrame(rows).sort_values("Position_Value", ascending=False)

add_df = ranking[ranking["Market"].isin(["EU", "UK"])].copy()
add_df["Action"] = "ADD_CANDIDATE"

cols = ["Market", "Ticker", "Global_Rank_Score", "Score", "Signal", "Market_Open", "Action"]

reduce_df.to_csv("capital_reduce_candidates.csv", index=False)
add_df[cols].to_csv("capital_add_candidates.csv", index=False)

print("===== REDUCE US CANDIDATES =====")
print(reduce_df.head(10).to_string(index=False))
print()
print("Reduce Budget:", round(reduce_budget, 2))

print()
print("===== ADD EU/UK CANDIDATES =====")
print(add_df[cols].head(10).to_string(index=False))
print()
print("EU Budget:", round(eu_budget, 2))
print("UK Budget:", round(uk_budget, 2))
