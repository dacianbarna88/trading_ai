import pandas as pd
from pathlib import Path

INPUT_FILE = "strategic_bias.csv"
OUTPUT_FILE = "strategic_allocation_summary.txt"
CSV_FILE = "strategic_allocation.csv"

if not Path(INPUT_FILE).exists():
    print("NO_STRATEGIC_BIAS_DATA")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

base_allocations = {
    "US": 40,
    "EUROPE": 25,
    "UK": 15,
    "ASIA": 20,
}

adjustments = {
    "OVERWEIGHT": 10,
    "NEUTRAL": 0,
    "UNDERWEIGHT": -10,
}

rows = []

for _, r in df.iterrows():
    region = r["Region"]
    bias = r["Strategic_Bias"]
    strength = float(r["Regional_Strength"])

    base = base_allocations.get(region, 0)
    adj = adjustments.get(bias, 0)

    allocation = max(5, base + adj)

    rows.append({
        "Region": region,
        "Regional_Strength": strength,
        "Strategic_Bias": bias,
        "Base_Allocation_%": base,
        "Adjustment_%": adj,
        "Recommended_Allocation_%": allocation,
    })

out = pd.DataFrame(rows)

total = out["Recommended_Allocation_%"].sum()

out["Normalized_Allocation_%"] = (
    out["Recommended_Allocation_%"] / total * 100
).round(2)

out.to_csv(CSV_FILE, index=False)

summary = [
    "===== V16.4 STRATEGIC ALLOCATION ENGINE =====",
    "",
    "Recommended Allocation:",
]

for _, r in out.iterrows():
    summary.append(
        f"{r['Region']} | "
        f"Bias {r['Strategic_Bias']} | "
        f"Strength {r['Regional_Strength']} | "
        f"Allocation {r['Normalized_Allocation_%']}%"
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
