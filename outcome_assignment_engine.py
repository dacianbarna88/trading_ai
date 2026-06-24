import pandas as pd
from pathlib import Path

REGISTRY_FILE = "decision_registry.csv"
OUTPUT_FILE = "outcome_assignment_summary.txt"

if not Path(REGISTRY_FILE).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY_FILE)

pending = df[df["Outcome"] == "PENDING"]

summary = []

summary.append(
    "===== V28.5 OUTCOME ASSIGNMENT ENGINE ====="
)

summary.append("")
summary.append(f"Total Decisions: {len(df)}")
summary.append(f"Pending Decisions: {len(pending)}")
summary.append("")

if len(pending) > 0:

    summary.append("Pending Registry:")

    for _, row in pending.iterrows():

        summary.append(
            f"{row['Timestamp']} | "
            f"{row['Decision']} | "
            f"{row['Confidence_%']}%"
        )

else:

    summary.append(
        "No pending decisions."
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
