import pandas as pd
from pathlib import Path
from datetime import datetime

MAP_FILE = "benchmark_vote_map.csv"
OUTPUT_FILE = "benchmark_readiness_guard_summary.txt"

if not Path(MAP_FILE).exists():
    print("NO_BENCHMARK_MAP")
    raise SystemExit

df = pd.read_csv(MAP_FILE)

now = datetime.now()

ready = 0
not_ready = 0

lines = [
    "===== V24.3 BENCHMARK READINESS GUARD =====",
    "",
    "Readiness Check:",
]

for _, row in df.iterrows():
    vote = row["Vote"]
    outcome = row["Outcome"]
    required_days = int(row["Validation_Days"])

    # vote_history timestamp is not in benchmark_vote_map yet,
    # so first protected version stays NOT_READY.
    age_days = 0

    if outcome != "PENDING":
        status = "ALREADY_VALIDATED"
    elif age_days >= required_days:
        status = "READY_FOR_BENCHMARK"
        ready += 1
    else:
        status = "PROTECTED_NOT_READY"
        not_ready += 1

    lines.append(
        f"{vote} | Age {age_days}d | Required {required_days}d | {status}"
    )

lines.extend([
    "",
    f"Ready: {ready}",
    f"Not Ready: {not_ready}",
    "",
    "Protection:",
    "No benchmark execution before validation horizon.",
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
