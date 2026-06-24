import json
import pandas as pd
from pathlib import Path
from datetime import datetime

HISTORY_FILE = "vote_history.csv"
RULES_FILE = "validation_rules.json"
OUTPUT_FILE = "automatic_outcome_assignment_summary.txt"

if not Path(HISTORY_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

if not Path(RULES_FILE).exists():
    print("NO_VALIDATION_RULES")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)
rules = json.loads(Path(RULES_FILE).read_text())

now = datetime.now()

assigned = 0
protected = 0
not_ready = 0

lines = [
    "===== V22.4 AUTOMATIC OUTCOME ASSIGNMENT ENGINE =====",
    "",
    "Assignment Review:",
]

for idx, row in df.iterrows():
    vote = row["Vote"]
    outcome = row["Outcome"]

    rule = rules.get(vote, {})
    required_days = int(rule.get("validation_days", 30))

    ts = datetime.strptime(
        row["Timestamp"],
        "%Y-%m-%d %H:%M:%S"
    )

    age_days = (now - ts).days

    if outcome != "PENDING":
        status = "SKIPPED_ALREADY_VALIDATED"
        protected += 1

    elif age_days < required_days:
        status = "PROTECTED_NOT_READY"
        not_ready += 1

    else:
        status = "READY_BUT_NO_AUTOMATED_BENCHMARK_YET"
        protected += 1

    lines.append(
        f"{vote} | Age {age_days}d | Required {required_days}d | {status}"
    )

df.to_csv(HISTORY_FILE, index=False)

lines.extend([
    "",
    f"Assigned Outcomes: {assigned}",
    f"Protected Records: {protected}",
    f"Not Ready: {not_ready}",
    "",
    "Protection:",
    "No outcome is assigned without benchmark data.",
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
