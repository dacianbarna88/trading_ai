import pandas as pd
from pathlib import Path

HISTORY_FILE = "vote_history.csv"
OUTPUT_FILE = "vote_outcome_summary.txt"

if not Path(HISTORY_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

pending = len(
    df[df["Outcome"] == "PENDING"]
)

correct = len(
    df[df["Outcome"] == "CORRECT"]
)

wrong = len(
    df[df["Outcome"] == "WRONG"]
)

summary = f"""
===== V21.0 OUTCOME VALIDATION ENGINE =====

Vote Records:
{len(df)}

Pending:
{pending}

Correct:
{correct}

Wrong:
{wrong}

Validation Status:
READY_FOR_AUTOMATION

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
