import pandas as pd
from pathlib import Path
from datetime import datetime

files = {
    "post_sell": "post_sell_audit_report.csv",
    "missed_winners": "missed_winners_audit_report.csv",
    "rebalance": "rebalance_edge_report.csv",
    "threshold": "score_threshold_audit_report.csv",
}

rows = []

for source, file in files.items():
    if not Path(file).exists():
        continue

    df = pd.read_csv(file)

    for _, r in df.iterrows():
        row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Source": source,
        }

        for col in df.columns:
            row[col] = r[col]

        rows.append(row)

learning_df = pd.DataFrame(rows)

if Path("learning_memory.csv").exists():
    old = pd.read_csv("learning_memory.csv")
    learning_df = pd.concat([old, learning_df], ignore_index=True)

learning_df.to_csv("learning_memory.csv", index=False)

summary = [
    "===== V14.0 LEARNING ENGINE - AUDIT MODE =====",
    "",
    f"Learning Records Stored: {len(learning_df)}",
    "",
    "Sources Learned:",
]

for source in files:
    count = len(learning_df[learning_df["Source"] == source]) if "Source" in learning_df.columns else 0
    summary.append(f"- {source}: {count}")

summary.extend([
    "",
    "Mode:",
    "AUDIT_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path("learning_engine_summary.txt").write_text(text)

print(text)
