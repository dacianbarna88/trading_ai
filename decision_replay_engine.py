import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
OUTPUT = "decision_replay_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY)

completed = df[
    df["Outcome"].isin(["WIN", "LOSS"])
]

summary = []
summary.append("===== V31.1 DECISION REPLAY ENGINE =====")
summary.append("")
summary.append(f"Total Decisions: {len(df)}")
summary.append(f"Completed Decisions: {len(completed)}")
summary.append("")

if len(completed) < 5:
    summary.extend([
        "Replay Status: INSUFFICIENT_HISTORY",
        "",
        "Reason:",
        "At least 5 completed WIN/LOSS decisions are needed before replay analysis is useful.",
        "",
        "Current Engine Status:",
        "READY_BUT_WAITING_FOR_DATA",
    ])

else:
    summary.append("Replay Analysis By Decision Type:")
    summary.append("")

    for decision in sorted(completed["Decision"].unique()):

        subset = completed[
            completed["Decision"] == decision
        ]

        total = len(subset)
        wins = len(subset[subset["Outcome"] == "WIN"])
        losses = len(subset[subset["Outcome"] == "LOSS"])

        win_rate = round(
            wins / total * 100,
            2
        ) if total > 0 else 0

        avg_return = round(
            subset["Return_%"].mean(),
            2
        ) if "Return_%" in subset.columns else 0

        avg_confidence = round(
            subset["Confidence_%"].mean(),
            2
        )

        summary.append(f"Decision: {decision}")
        summary.append(f"Total: {total}")
        summary.append(f"Wins: {wins}")
        summary.append(f"Losses: {losses}")
        summary.append(f"Win Rate: {win_rate}%")
        summary.append(f"Average Return: {avg_return}%")
        summary.append(f"Average Confidence: {avg_confidence}%")
        summary.append("")

    summary.append("Replay Insight:")
    summary.append("Use repeated patterns to adjust confidence, thresholds, and guard rules.")

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path(OUTPUT).write_text(text)

print(text)
