import pandas as pd
from pathlib import Path

HISTORY_FILE = "vote_history.csv"
OUTPUT_FILE = "outcome_scoring_summary.txt"

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

total_scored = correct + wrong

if total_scored == 0:
    accuracy = 0
else:
    accuracy = round(
        correct / total_scored * 100,
        1
    )

summary = f"""
===== V22.0 OUTCOME SCORING ENGINE =====

Total Votes:
{len(df)}

Pending:
{pending}

Correct:
{correct}

Wrong:
{wrong}

Scored Accuracy:
{accuracy}%

Scoring Status:
READY_FOR_AUTOMATED_SCORING

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
