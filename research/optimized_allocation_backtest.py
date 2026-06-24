import pandas as pd

baseline = pd.read_csv("allocation_backtest_baseline.csv")

# limite de diversificare
MIN_ALLOC = 5
MAX_ALLOC = 80
STEP = 5

returns = {
    row["Market"]: float(row["Return_10Y_%"])
    for _, row in baseline.iterrows()
}

best = None

for us in range(MIN_ALLOC, MAX_ALLOC + 1, STEP):
    for eu in range(MIN_ALLOC, MAX_ALLOC + 1, STEP):
        uk = 100 - us - eu

        if uk < MIN_ALLOC or uk > MAX_ALLOC:
            continue

        total = (
            us * returns["US"] +
            eu * returns["EU"] +
            uk * returns["UK"]
        ) / 100

        row = {
            "US_%": us,
            "EU_%": eu,
            "UK_%": uk,
            "Return_10Y_%": round(total, 2),
        }

        if best is None or row["Return_10Y_%"] > best["Return_10Y_%"]:
            best = row

df = pd.DataFrame([best])
df.to_csv("optimized_allocation_backtest.csv", index=False)

print("\n===== OPTIMIZED ALLOCATION BACKTEST =====\n")
print(df.to_string(index=False))
