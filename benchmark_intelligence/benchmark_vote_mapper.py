import pandas as pd
import json
from pathlib import Path

VOTE_FILE = "vote_history.csv"
RULES_FILE = "validation_rules.json"
OUTPUT_FILE = "benchmark_vote_mapper_summary.txt"
CSV_FILE = "benchmark_vote_map.csv"

votes = pd.read_csv(VOTE_FILE)
rules = json.loads(Path(RULES_FILE).read_text())

rows = []

for _, row in votes.iterrows():
    vote = row["Vote"]
    decision = row["Decision"]
    outcome = row["Outcome"]
    rule = rules.get(vote, {})

    rows.append({
        "Vote": vote,
        "Decision": decision,
        "Outcome": outcome,
        "Validation_Days": rule.get("validation_days", 30),
        "Benchmark": rule.get("benchmark", "MISSING"),
        "Correct_If": rule.get("correct_if", "MISSING"),
        "Status": "MAPPED" if vote in rules else "MISSING_RULE"
    })

out = pd.DataFrame(rows)
out.to_csv(CSV_FILE, index=False)

summary = [
    "===== V24.1 BENCHMARK VOTE MAPPER =====",
    "",
    "Mapped Votes:",
]

for _, r in out.iterrows():
    summary.append(
        f"{r['Vote']} | {r['Decision']} | "
        f"{r['Validation_Days']}d | "
        f"{r['Benchmark']} | {r['Status']}"
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
