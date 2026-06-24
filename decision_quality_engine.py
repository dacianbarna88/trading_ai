import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
OUTPUT = "decision_quality_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY)

total = len(df)

completed = df[
    df["Outcome"] != "PENDING"
].copy()

wins = len(
    completed[
        completed["Outcome"] == "WIN"
    ]
)

losses = len(
    completed[
        completed["Outcome"] == "LOSS"
    ]
)

win_rate = round(
    wins / len(completed) * 100,
    2
) if len(completed) > 0 else 0

avg_confidence = round(
    df["Confidence_%"].mean(),
    2
)

summary = []

summary.append(
    "===== V30.1 DECISION QUALITY ENGINE ====="
)

summary.append("")
summary.append(
    f"Total Decisions: {total}"
)

summary.append(
    f"Completed Decisions: {len(completed)}"
)

summary.append(
    f"Wins: {wins}"
)

summary.append(
    f"Losses: {losses}"
)

summary.append(
    f"Win Rate: {win_rate}%"
)

summary.append(
    f"Average Confidence: {avg_confidence}%"
)

summary.append("")

if len(completed) == 0:

    quality = "INSUFFICIENT_DATA"

elif win_rate >= 70:

    quality = "EXCELLENT"

elif win_rate >= 55:

    quality = "GOOD"

elif win_rate >= 40:

    quality = "AVERAGE"

else:

    quality = "POOR"

summary.append(
    f"Decision Quality: {quality}"
)

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(
    OUTPUT
).write_text(text)

print(text)
