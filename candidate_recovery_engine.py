from pathlib import Path
import pandas as pd

memory_file = Path("historical_memory.csv")

if not memory_file.exists():
    raise SystemExit("historical_memory.csv not found")

df = pd.read_csv(memory_file)

recoveries = df[
    (df["Outcome"] == "BAD_REJECT")
]

if len(recoveries):

    recoveries = recoveries.sort_values(
        "Historical_Score",
        ascending=False
    )

    recoveries["Recovery_Priority"] = range(
        1,
        len(recoveries) + 1
    )

    recoveries.to_csv(
        "candidate_recovery_watchlist.csv",
        index=False
    )

    lines = [
        "===== V12.2 CANDIDATE RECOVERY ENGINE =====",
        "",
        f"Candidates Recovered: {len(recoveries)}",
        "",
        "Recovery Watchlist:",
        ""
    ]

    for _, row in recoveries.iterrows():
        lines.append(
            f"{row['Ticker']} | "
            f"Historical Score {row['Historical_Score']} | "
            f"Priority {row['Recovery_Priority']}"
        )

else:

    pd.DataFrame().to_csv(
        "candidate_recovery_watchlist.csv",
        index=False
    )

    lines = [
        "===== V12.2 CANDIDATE RECOVERY ENGINE =====",
        "",
        "Candidates Recovered: 0"
    ]

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION"
])

summary = "\n".join(lines)

Path(
    "candidate_recovery_summary.txt"
).write_text(summary)

print(summary)
