import pandas as pd
from pathlib import Path
from datetime import datetime

source_file = "threshold_80_virtual_candidates.csv"
tracker_file = "threshold_virtual_tracker.csv"

if not Path(source_file).exists():
    raise SystemExit("threshold_80_virtual_candidates.csv not found")

df = pd.read_csv(source_file)

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

records = []

for _, row in df.iterrows():
    records.append({
        "Timestamp": now,
        "Ticker": row["Ticker"],
        "Entry_Price": row["Price"],
        "Score": row["Score"],
        "Signal": row["Signal"],
        "Status": "TRACKING"
    })

new_df = pd.DataFrame(records)

if Path(tracker_file).exists():
    old = pd.read_csv(tracker_file)
    new_df = pd.concat([old, new_df], ignore_index=True)

new_df.to_csv(tracker_file, index=False)

summary = [
    "===== V14.5 THRESHOLD VIRTUAL TRACKER =====",
    "",
    f"Candidates Added: {len(records)}",
    "",
    "Tracking:"
]

for _, row in df.iterrows():
    summary.append(
        f"{row['Ticker']} | Score {row['Score']} | Entry {row['Price']}"
    )

summary.extend([
    "",
    "Mode:",
    "TRACKING_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(summary)

Path(
    "threshold_virtual_tracker_summary.txt"
).write_text(text)

print(text)
