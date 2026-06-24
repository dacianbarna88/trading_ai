import pandas as pd

health = pd.read_csv("allocator_health.csv")

total_gap = health["Gap_%"].abs().sum()

current_health = round(
    max(0, 100 - total_gap / 2),
    1
)

rows = []

remaining_gap = total_gap

for cycle in range(4):

    forecast_health = round(
        max(0, 100 - remaining_gap / 2),
        1
    )

    rows.append({
        "Cycle": cycle,
        "Forecast_Health": forecast_health
    })

    remaining_gap *= 0.65

df = pd.DataFrame(rows)

df.to_csv(
    "allocation_drift_forecast.csv",
    index=False
)

print("\n===== ALLOCATION DRIFT FORECAST =====\n")
print(df.to_string(index=False))
