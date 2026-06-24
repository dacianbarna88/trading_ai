import pandas as pd
from pathlib import Path

signals = pd.read_csv("live_signals.csv")

thresholds = [90, 80, 70]

results = []

for threshold in thresholds:

    candidates = signals[
        signals["Score"] >= threshold
    ]

    count = len(candidates)

    avg_score = (
        round(candidates["Score"].mean(), 2)
        if count > 0 else 0
    )

    results.append({
        "Threshold": threshold,
        "Candidates": count,
        "Average_Score": avg_score
    })

df = pd.DataFrame(results)

df.to_csv(
    "score_threshold_audit_report.csv",
    index=False
)

summary = []

summary.append(
    "===== V13.5 SCORE THRESHOLD AUDIT ====="
)

summary.append("")

for _, row in df.iterrows():

    summary.append(
        f"Threshold {int(row['Threshold'])}"
    )

    summary.append(
        f"Candidates: {int(row['Candidates'])}"
    )

    summary.append(
        f"Average Score: {row['Average_Score']}"
    )

    summary.append("")

summary.extend([
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION"
])

text = "\n".join(summary)

Path(
    "score_threshold_audit_summary.txt"
).write_text(text)

print(text)
print()
print(df)
