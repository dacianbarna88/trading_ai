import pandas as pd

exposure = pd.read_csv("core_exposure_report.csv")
target = pd.read_csv("strategic_allocations.csv")
safe_plan = pd.read_csv("safe_migration_plan.csv")

rows = []

for _, t in target.iterrows():
    market = t["Market"]
    target_pct = float(t["Allocation_%"])

    current_row = exposure[exposure["Market"] == market]
    current_pct = float(current_row.iloc[0]["Exposure_%"]) if not current_row.empty else 0.0

    gap = round(target_pct - current_pct, 1)

    planned_buy = safe_plan[
        (safe_plan["Action"] == "BUY") &
        (safe_plan["Market"] == market)
    ]["Amount_$"].sum()

    planned_sell = safe_plan[
        (safe_plan["Action"] == "SELL")
    ]["Amount_$"].sum() if market == "US" else 0

    rows.append({
        "Market": market,
        "Current_%": current_pct,
        "Target_%": target_pct,
        "Gap_%": gap,
        "Planned_Buy_$": round(planned_buy, 2),
        "Planned_Sell_$": round(planned_sell, 2),
    })

df = pd.DataFrame(rows)
df.to_csv("portfolio_construction_plan.csv", index=False)

print("\n===== PORTFOLIO CONSTRUCTION PLAN =====\n")
print(df.to_string(index=False))
