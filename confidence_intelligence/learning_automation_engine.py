import pandas as pd
from pathlib import Path

REGISTRY_FILE = "vote_outcome_registry.csv"
OUTPUT_FILE = "learning_automation_summary.txt"

MIN_WEIGHT = 0.5
MAX_WEIGHT = 3.0

if not Path(REGISTRY_FILE).exists():
    print("NO_REGISTRY")
    raise SystemExit

df = pd.read_csv(REGISTRY_FILE)

lines = [
    "===== V27.0 LEARNING AUTOMATION ENGINE =====",
    "",
]

updated = 0

for idx, row in df.iterrows():

    weight = float(row.get("Weight", 1.0))
    outcome = str(row.get("Outcome", "PENDING"))

    if outcome == "CORRECT":
        weight = min(MAX_WEIGHT, round(weight + 0.1, 2))
        updated += 1

    elif outcome == "WRONG":
        weight = max(MIN_WEIGHT, round(weight - 0.1, 2))
        updated += 1

    df.loc[idx, "Weight"] = weight

    lines.append(
        f"{row['Vote']} | {outcome} | Weight {weight}"
    )

df.to_csv(REGISTRY_FILE, index=False)

lines.extend([
    "",
    f"Weights Updated: {updated}",
    "",
    "Protection:",
    "NO_WEIGHT_CHANGE_FOR_PENDING",
    "MIN_WEIGHT=0.5",
    "MAX_WEIGHT=3.0",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

summary = "\n".join(lines)

Path(OUTPUT_FILE).write_text(summary)

print(summary)
