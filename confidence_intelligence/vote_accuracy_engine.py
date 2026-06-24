import pandas as pd
from pathlib import Path

HISTORY_FILE = "vote_history.csv"
OUTPUT_FILE = "vote_accuracy_summary.txt"
CSV_FILE = "vote_accuracy.csv"

if not Path(HISTORY_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

rows = []

for vote in sorted(df["Vote"].unique()):
    sub = df[df["Vote"] == vote]

    completed = sub[sub["Outcome"].isin(["CORRECT", "WRONG"])]

    total_completed = len(completed)
    correct = len(completed[completed["Outcome"] == "CORRECT"])

    if total_completed == 0:
        accuracy = 0
        confidence = "INSUFFICIENT_DATA"
        weight = 1.0
    else:
        accuracy = round(correct / total_completed * 100, 1)

        if accuracy >= 70:
            confidence = "HIGH"
            weight = 1.3
        elif accuracy >= 50:
            confidence = "MEDIUM"
            weight = 1.0
        else:
            confidence = "LOW"
            weight = 0.7

    rows.append({
        "Vote": vote,
        "Completed": total_completed,
        "Correct": correct,
        "Accuracy_%": accuracy,
        "Confidence": confidence,
        "Weight": weight
    })

out = pd.DataFrame(rows)
out.to_csv(CSV_FILE, index=False)

summary = [
    "===== V20.1 VOTE ACCURACY ENGINE =====",
    "",
    "Vote Accuracy:",
]

for _, r in out.iterrows():
    summary.append(
        f"{r['Vote']} | "
        f"Completed {r['Completed']} | "
        f"Correct {r['Correct']} | "
        f"Accuracy {r['Accuracy_%']}% | "
        f"Confidence {r['Confidence']} | "
        f"Weight {r['Weight']}"
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
