import pandas as pd
from pathlib import Path
from datetime import datetime

HISTORY_FILE = "vote_history.csv"
OUTPUT_FILE = "automatic_outcome_evaluator_summary.txt"

VALIDATION_DAYS = {
    "THRESHOLD": 30,
    "REGIONAL": 30,
    "SECTOR": 30,
    "MACRO": 90,
    "HORIZON": 180,
}

if not Path(HISTORY_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

now = datetime.now()

eligible = 0
not_ready = 0

lines = [
    "===== V21.2 AUTOMATIC OUTCOME EVALUATOR =====",
    "",
    "Vote Validation Readiness:",
]

for _, row in df.iterrows():
    vote = row["Vote"]
    outcome = row["Outcome"]

    ts = datetime.strptime(
        row["Timestamp"],
        "%Y-%m-%d %H:%M:%S"
    )

    age_days = (now - ts).days
    required_days = VALIDATION_DAYS.get(vote, 30)

    if outcome != "PENDING":
        status = "ALREADY_VALIDATED"
    elif age_days >= required_days:
        status = "READY_FOR_VALIDATION"
        eligible += 1
    else:
        status = "NOT_READY"
        not_ready += 1

    lines.append(
        f"{vote} | Age {age_days}d | Required {required_days}d | {status}"
    )

lines.extend([
    "",
    f"Ready For Validation: {eligible}",
    f"Not Ready: {not_ready}",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(lines)

Path(OUTPUT_FILE).write_text(text)

print(text)
