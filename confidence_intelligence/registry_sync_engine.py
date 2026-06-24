import pandas as pd
from pathlib import Path

HISTORY_FILE = "vote_history.csv"
REGISTRY_FILE = "vote_outcome_registry.csv"
OUTPUT_FILE = "registry_sync_summary.txt"

DEFAULT_VOTES = [
    "THRESHOLD",
    "REGIONAL",
    "SECTOR",
    "HORIZON",
    "MACRO"
]

if not Path(HISTORY_FILE).exists():
    print("NO_VOTE_HISTORY")
    raise SystemExit

history = pd.read_csv(HISTORY_FILE)

rows = []

for vote in DEFAULT_VOTES:
    sub = history[history["Vote"] == vote]

    correct = len(sub[sub["Outcome"] == "CORRECT"])
    wrong = len(sub[sub["Outcome"] == "WRONG"])
    total = correct + wrong

    if total == 0:
        accuracy = 0
        weight = 1.0
    else:
        accuracy = round(correct / total * 100, 1)

        if accuracy >= 70:
            weight = 1.3
        elif accuracy >= 50:
            weight = 1.0
        else:
            weight = 0.7

    rows.append({
        "Vote": vote,
        "Total_Scored": total,
        "Correct": correct,
        "Wrong": wrong,
        "Accuracy_%": accuracy,
        "Weight": weight
    })

registry = pd.DataFrame(rows)
registry.to_csv(REGISTRY_FILE, index=False)

summary = [
    "===== V22.2 REGISTRY SYNC ENGINE =====",
    "",
    "Registry Updated:",
]

for _, r in registry.iterrows():
    summary.append(
        f"{r['Vote']} | "
        f"Scored {r['Total_Scored']} | "
        f"Correct {r['Correct']} | "
        f"Wrong {r['Wrong']} | "
        f"Accuracy {r['Accuracy_%']}% | "
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
