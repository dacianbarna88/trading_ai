from pathlib import Path
import pandas as pd

HISTORY = "decision_outcome_history.csv"
OUTPUT = "outcome_evolution_summary.txt"

if not Path(HISTORY).exists():
    print("decision_outcome_history.csv missing")
    raise SystemExit

df = pd.read_csv(HISTORY)

summary = [
    "===== V33.1 OUTCOME EVOLUTION ENGINE =====",
    "",
    f"Total History Records: {len(df)}",
    "",
]

if len(df) == 0:
    summary.append("No outcome history available.")

else:
    grouped = df.groupby(
        ["Ticker", "Decision", "Entry_Price"]
    )

    for (ticker, decision, entry), group in grouped:

        days_tracked = len(group)

        current_return = round(
            group["Return_%"].iloc[-1],
            2
        )

        best_return = round(
            group["Return_%"].max(),
            2
        )

        worst_return = round(
            group["Return_%"].min(),
            2
        )

        latest_outcome = group["Outcome"].iloc[-1]

        avg_confidence = round(
            group["Confidence_%"].mean(),
            2
        )

        summary.append(f"Ticker: {ticker}")
        summary.append(f"Decision: {decision}")
        summary.append(f"Entry Price: {entry}")
        summary.append(f"Days/Records Tracked: {days_tracked}")
        summary.append(f"Average Confidence: {avg_confidence}%")
        summary.append(f"Current Return: {current_return}%")
        summary.append(f"Best Return: {best_return}%")
        summary.append(f"Worst Return: {worst_return}%")
        summary.append(f"Latest Outcome: {latest_outcome}")
        summary.append("")

summary.extend([
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path(OUTPUT).write_text(text)

print(text)
