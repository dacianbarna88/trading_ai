import pandas as pd

target = pd.read_csv("strategic_allocations.csv")
current = pd.read_csv("core_exposure_report.csv")

rows = []
total_gap = 0.0

for _, t in target.iterrows():
    market = t["Market"]
    target_pct = float(t["Allocation_%"])

    cur = current[current["Market"] == market]

    current_pct = 0.0
    if not cur.empty:
        current_pct = float(cur.iloc[0]["Exposure_%"])

    gap = round(target_pct - current_pct, 1)
    total_gap += abs(gap)

    rows.append({
        "Market": market,
        "Current_%": current_pct,
        "Target_%": target_pct,
        "Gap_%": gap,
    })

health_score = max(0, round(100 - total_gap / 2, 1))

df = pd.DataFrame(rows)
df.to_csv("allocator_health.csv", index=False)

print("\n===== ALLOCATOR HEALTH =====\n")
print(df.to_string(index=False))
print()
print("Health Score:", health_score)
