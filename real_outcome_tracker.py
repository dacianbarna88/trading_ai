from pathlib import Path
from datetime import datetime
import pandas as pd

REGISTRY = "decision_registry.csv"
OUTPUT = "decision_outcome_history.csv"

columns = [
    "Date",
    "Timestamp",
    "Ticker",
    "Decision",
    "Confidence_%",
    "Entry_Price",
    "Current_Price",
    "Return_%",
    "Outcome"
]

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

registry = pd.read_csv(REGISTRY)

if Path(OUTPUT).exists():
    history = pd.read_csv(OUTPUT)

    for col in columns:
        if col not in history.columns:
            if col == "Date":
                history[col] = pd.to_datetime(
                    history["Timestamp"]
                ).dt.date.astype(str)
            else:
                history[col] = None

    history = history[columns]

else:
    history = pd.DataFrame(columns=columns)

today = datetime.now().date().isoformat()

added = 0
skipped = 0

for _, row in registry.iterrows():

    ticker = row.get("Ticker", "")
    decision = row.get("Decision", "")
    confidence = row.get("Confidence_%", 0)
    entry = float(row.get("Entry_Price", 0))
    current = float(row.get("Current_Price", entry))
    outcome = row.get("Outcome", "PENDING")

    if entry == 0:
        skipped += 1
        continue

    duplicate = history[
        (history["Date"].astype(str) == today)
        &
        (history["Ticker"].astype(str) == str(ticker))
        &
        (history["Decision"].astype(str) == str(decision))
        &
        (history["Entry_Price"].astype(float) == entry)
    ]

    if len(duplicate) > 0:
        skipped += 1
        continue

    ret = round(
        (current - entry) / entry * 100,
        2
    )

    history.loc[len(history)] = [
        today,
        datetime.now(),
        ticker,
        decision,
        confidence,
        entry,
        current,
        ret,
        outcome
    ]

    added += 1

history.to_csv(
    OUTPUT,
    index=False
)

summary = f"""
===== V33.3 SMART OUTCOME TRACKER =====

Records Added:
{added}

Records Skipped:
{skipped}

Total Records:
{len(history)}

Rule:
Max 1 record per Date + Ticker + Decision + Entry Price

Output:
decision_outcome_history.csv

Mode:
ANALYSIS_ONLY
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(
    "real_outcome_tracker_summary.txt"
).write_text(summary)

print(summary)
