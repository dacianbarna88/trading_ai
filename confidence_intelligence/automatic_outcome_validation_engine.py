import pandas as pd
from pathlib import Path

VOTE_FILE = "vote_history.csv"
READINESS_FILE = "benchmark_readiness_guard_summary.txt"

OUTPUT_FILE = "automatic_outcome_validation_summary.txt"

if not Path(VOTE_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

votes = pd.read_csv(VOTE_FILE)

ready_votes = []

if Path(READINESS_FILE).exists():

    text = Path(READINESS_FILE).read_text()

    for vote in [
        "THRESHOLD",
        "REGIONAL",
        "SECTOR",
        "HORIZON",
        "MACRO"
    ]:

        if f"{vote}" in text and "READY_FOR_BENCHMARK" in text:
            ready_votes.append(vote)

lines = [
    "===== V26.0 AUTOMATIC OUTCOME VALIDATION ENGINE =====",
    "",
    "Validation Review:"
]

validated = 0
waiting = 0

for _, row in votes.iterrows():

    vote = row["Vote"]

    if vote in ready_votes:

        status = "READY_FOR_VALIDATION"
        validated += 1

    else:

        status = "WAITING_FOR_HORIZON"
        waiting += 1

    lines.append(
        f"{vote} | {status}"
    )

lines.extend([
    "",
    f"Ready: {validated}",
    f"Waiting: {waiting}",
    "",
    "Validation Status:",
    "ACTIVE",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(lines)

Path(OUTPUT_FILE).write_text(text)

print(text)
