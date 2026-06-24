import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
OUTPUT = "outcome_analytics_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY)

completed = df[
    df["Outcome"].isin(
        ["WIN", "LOSS"]
    )
]

summary = []
summary.append(
    "===== V30.5 OUTCOME ANALYTICS ENGINE ====="
)
summary.append("")

summary.append(
    f"Completed Decisions: {len(completed)}"
)
summary.append("")

if len(completed) == 0:

    summary.extend([
        "No completed outcomes available.",
        "",
        "Mode:",
        "ANALYSIS_ONLY",
        "PAPER_ONLY",
        "NO_BROKER",
    ])

else:

    decision_types = sorted(
        completed["Decision"].unique()
    )

    for decision in decision_types:

        subset = completed[
            completed["Decision"] == decision
        ]

        total = len(subset)

        wins = len(
            subset[
                subset["Outcome"] == "WIN"
            ]
        )

        losses = len(
            subset[
                subset["Outcome"] == "LOSS"
            ]
        )

        win_rate = round(
            wins / total * 100,
            2
        ) if total > 0 else 0

        avg_return = round(
            subset["Return_%"].mean(),
            2
        ) if "Return_%" in subset.columns else 0

        summary.append(
            f"Decision Type: {decision}"
        )
        summary.append(
            f"Total: {total}"
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
            f"Average Return: {avg_return}%"
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
