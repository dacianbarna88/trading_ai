import pandas as pd
from pathlib import Path
from datetime import datetime

SOURCE_FILE = "adaptive_decision_guard_summary.txt"
REGISTRY_FILE = "decision_registry.csv"

if not Path(SOURCE_FILE).exists():
    print("adaptive_decision_guard_summary.txt missing")
    raise SystemExit

text = Path(SOURCE_FILE).read_text()

decision = "UNKNOWN"
confidence = "UNKNOWN"

for line in text.splitlines():

    if line.startswith("Guard Final Decision:"):
        decision = line.split(":", 1)[1].strip()

    if line.startswith("Weighted Confidence:"):
        confidence = line.split(":", 1)[1].strip().replace("%", "")

record = {
    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "Decision": decision,
    "Confidence_%": confidence,
    "Outcome": "PENDING",
    "Mode": "PAPER_ONLY",
}

new_row = pd.DataFrame([record])

if Path(REGISTRY_FILE).exists():
    old = pd.read_csv(REGISTRY_FILE)
    df = pd.concat([old, new_row], ignore_index=True)
else:
    df = new_row

df.to_csv(REGISTRY_FILE, index=False)

print("===== V28.4 DECISION REGISTRY =====")
print()
print(new_row.to_string(index=False))
print()
print("decision_registry.csv updated")
