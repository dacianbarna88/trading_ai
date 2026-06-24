import pandas as pd
from pathlib import Path

REGISTRY = "decision_registry.csv"
SNAPSHOTS = "market_session_snapshots.csv"
OUTPUT = "pattern_discovery_summary.txt"

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY)

completed = df[
    df["Outcome"].isin(["WIN", "LOSS"])
]

summary = [
    "===== V31.3 PATTERN DISCOVERY ENGINE =====",
    "",
    f"Total Decisions: {len(df)}",
    f"Completed Decisions: {len(completed)}",
    "",
]

if len(completed) < 5:
    summary.extend([
        "Pattern Status: INSUFFICIENT_HISTORY",
        "",
        "Reason:",
        "At least 5 completed WIN/LOSS outcomes are needed before reliable pattern discovery.",
        "",
        "Engine Status:",
        "READY_BUT_WAITING_FOR_DATA",
    ])

else:
    summary.append("Patterns By Decision Type:")
    summary.append("")

    for decision in sorted(completed["Decision"].unique()):
        subset = completed[completed["Decision"] == decision]
        total = len(subset)
        wins = len(subset[subset["Outcome"] == "WIN"])
        win_rate = round(wins / total * 100, 2) if total > 0 else 0
        avg_return = round(subset["Return_%"].mean(), 2)

        summary.append(f"{decision}")
        summary.append(f"Total: {total}")
        summary.append(f"Win Rate: {win_rate}%")
        summary.append(f"Average Return: {avg_return}%")
        summary.append("")

    summary.append("Patterns By Confidence Band:")
    summary.append("")

    bands = [
        ("HIGH_CONFIDENCE_80_PLUS", 80, 100),
        ("MID_CONFIDENCE_60_79", 60, 79.999),
        ("LOW_CONFIDENCE_0_59", 0, 59.999),
    ]

    for label, low, high in bands:
        subset = completed[
            (completed["Confidence_%"] >= low)
            &
            (completed["Confidence_%"] <= high)
        ]

        total = len(subset)
        wins = len(subset[subset["Outcome"] == "WIN"])
        win_rate = round(wins / total * 100, 2) if total > 0 else 0

        summary.append(label)
        summary.append(f"Total: {total}")
        summary.append(f"Win Rate: {win_rate}%")
        summary.append("")

    if Path(SNAPSHOTS).exists():
        snapshots = pd.read_csv(SNAPSHOTS)

        summary.append("Session Snapshot Coverage:")
        summary.append("")

        for session in sorted(snapshots["Session"].unique()):
            count = len(snapshots[snapshots["Session"] == session])
            summary.append(f"{session}: {count}")

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
