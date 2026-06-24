import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
OUTPUT = "confidence_calibration_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY)

completed = df[
    df["Outcome"].isin(
        ["WIN", "LOSS"]
    )
]

bands = [
    ("80_PLUS", 80, 100),
    ("60_TO_79", 60, 79.999),
    ("0_TO_59", 0, 59.999),
]

summary = []
summary.append(
    "===== V30.3 CONFIDENCE CALIBRATION ENGINE ====="
)
summary.append("")

summary.append(
    f"Completed Decisions: {len(completed)}"
)
summary.append("")

for label, low, high in bands:

    band_df = completed[
        (completed["Confidence_%"] >= low)
        &
        (completed["Confidence_%"] <= high)
    ]

    total = len(band_df)

    wins = len(
        band_df[
            band_df["Outcome"] == "WIN"
        ]
    )

    losses = len(
        band_df[
            band_df["Outcome"] == "LOSS"
        ]
    )

    win_rate = round(
        wins / total * 100,
        2
    ) if total > 0 else 0

    summary.append(
        f"{label}"
    )
    summary.append(
        f"Decisions: {total}"
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
    summary.append("")

summary.extend([
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT).write_text(text)

print(text)
