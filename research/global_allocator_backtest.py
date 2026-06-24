import pandas as pd

baseline = pd.read_csv("allocation_backtest_baseline.csv")
alloc = pd.read_csv("strategic_allocations.csv")

merged = baseline.merge(
    alloc,
    on="Market",
    how="inner"
)

merged["Weighted_Return_%"] = (
    merged["Return_10Y_%"] *
    merged["Allocation_%"] / 100
)

allocator_return = round(
    merged["Weighted_Return_%"].sum(),
    2
)

spy_return = float(
    baseline[baseline["Market"] == "US"]["Return_10Y_%"].iloc[0]
)

excess_return = round(
    allocator_return - spy_return,
    2
)

result = pd.DataFrame([{
    "Period": "10Y",
    "SPY_Buy_Hold_%": spy_return,
    "Global_Allocator_%": allocator_return,
    "Excess_Return_%": excess_return
}])

result.to_csv(
    "global_allocator_backtest.csv",
    index=False
)

print("\n===== GLOBAL ALLOCATOR BACKTEST =====\n")
print(merged.to_string(index=False))
print()
print(result.to_string(index=False))
