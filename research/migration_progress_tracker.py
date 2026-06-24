import pandas as pd

health = pd.read_csv("allocator_health.csv")
transfer = pd.read_csv("capital_transfer_plan.csv")

total_gap = health["Gap_%"].abs().sum()

progress_pct = round(
    max(0, min(100, 100 - total_gap)),
    1
)

remaining_capital = abs(
    transfer["Capital_$"]
).sum() / 2

cycle_size = 9376.13

cycles_remaining = round(
    remaining_capital / cycle_size,
    1
)

summary = pd.DataFrame([{
    "Progress_%": progress_pct,
    "Remaining_Capital_$": round(
        remaining_capital,
        2
    ),
    "Estimated_Cycles_Remaining":
        cycles_remaining
}])

summary.to_csv(
    "migration_progress.csv",
    index=False
)

print("\n===== MIGRATION PROGRESS =====\n")
print(summary.to_string(index=False))
