import pandas as pd
import json
from pathlib import Path

VOTE_FILE = "vote_history.csv"
RULES_FILE = "validation_rules.json"

OUTPUT_FILE = "benchmark_execution_summary.txt"

if not Path(VOTE_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

if not Path(RULES_FILE).exists():
    print("NO_VALIDATION_RULES")
    raise SystemExit

votes = pd.read_csv(VOTE_FILE)
rules = json.loads(
    Path(RULES_FILE).read_text()
)

lines = [
    "===== V24.0 BENCHMARK EXECUTION ENGINE =====",
    "",
    "Execution Status:",
]

ready = 0
blocked = 0

for _, row in votes.iterrows():

    vote = row["Vote"]

    if vote in rules:
        status = "EXECUTABLE"
        ready += 1
    else:
        status = "BLOCKED"
        blocked += 1

    lines.append(
        f"{vote} | {status}"
    )

lines.extend([
    "",
    f"Executable: {ready}",
    f"Blocked: {blocked}",
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
