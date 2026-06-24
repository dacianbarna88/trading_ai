import pandas as pd
from pathlib import Path
from datetime import datetime

REGISTRY_FILE = "vote_outcome_registry.csv"
HISTORY_FILE = "learning_weight_history.csv"
OUTPUT_FILE = "learning_weight_history_summary.txt"

if not Path(REGISTRY_FILE).exists():
    print("NO_REGISTRY")
    raise SystemExit

df = pd.read_csv(REGISTRY_FILE)

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

rows = []

for _, row in df.iterrows():
    rows.append({
        "Timestamp": timestamp,
        "Vote": row.get("Vote", "UNKNOWN"),
        "Weight": row.get("Weight", 1.0),
        "Accuracy_%": row.get("Accuracy_%", 0),
        "Total_Scored": row.get("Total_Scored", 0),
        "Correct": row.get("Correct", 0),
        "Wrong": row.get("Wrong", 0),
        "Outcome": row.get("Outcome", "PENDING")
    })

new_df = pd.DataFrame(rows)

if Path(HISTORY_FILE).exists():
    old = pd.read_csv(HISTORY_FILE)
    new_df = pd.concat([old, new_df], ignore_index=True)

new_df.to_csv(HISTORY_FILE, index=False)

summary = [
    "===== V27.3 LEARNING WEIGHT HISTORY =====",
    "",
    f"Timestamp: {timestamp}",
    f"Records Added: {len(rows)}",
    f"Total History Records: {len(new_df)}",
    "",
    "Latest Weights:",
]

for r in rows:
    summary.append(
        f"{r['Vote']} | Weight {r['Weight']} | Accuracy {r['Accuracy_%']}% | Outcome {r['Outcome']}"
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
