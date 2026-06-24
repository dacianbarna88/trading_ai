import pandas as pd
from pathlib import Path

SNAPSHOT_FILE = "market_session_snapshots.csv"
OUTPUT_FILE = "session_intelligence_summary.txt"

if not Path(SNAPSHOT_FILE).exists():
    print("market_session_snapshots.csv missing")
    raise SystemExit

df = pd.read_csv(SNAPSHOT_FILE)

summary = []
summary.append("===== V29.6 SESSION INTELLIGENCE ENGINE =====")
summary.append("")

summary.append(f"Total Snapshots: {len(df)}")
summary.append("")

sessions = sorted(df["Session"].unique())

for session in sessions:

    session_df = df[df["Session"] == session]

    avg_confidence = round(
        session_df["Confidence_%"].mean(),
        2
    )

    decision_counts = (
        session_df["Decision"]
        .value_counts()
        .to_dict()
    )

    summary.append(f"Session: {session}")
    summary.append(
        f"Snapshots: {len(session_df)}"
    )
    summary.append(
        f"Average Confidence: {avg_confidence}%"
    )

    for decision, count in decision_counts.items():
        summary.append(
            f"{decision}: {count}"
        )

    summary.append("")

overall_confidence = round(
    df["Confidence_%"].mean(),
    2
)

summary.extend([
    f"Overall Confidence: {overall_confidence}%",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
