import pandas as pd
from pathlib import Path

REGISTRY_FILE = "vote_outcome_registry.csv"
OUTPUT_FILE = "vote_outcome_registry_summary.txt"

DEFAULT_VOTES = [
    "THRESHOLD",
    "REGIONAL",
    "SECTOR",
    "HORIZON",
    "MACRO"
]

if Path(REGISTRY_FILE).exists():
    df = pd.read_csv(REGISTRY_FILE)
else:
    df = pd.DataFrame([
        {
            "Vote": vote,
            "Total_Scored": 0,
            "Correct": 0,
            "Wrong": 0,
            "Accuracy_%": 0,
            "Weight": 1.0
        }
        for vote in DEFAULT_VOTES
    ])

df.to_csv(REGISTRY_FILE, index=False)

summary = [
    "===== V22.1 VOTE OUTCOME REGISTRY =====",
    "",
    "Registry Status:",
    "ACTIVE",
    "",
    "Tracked Votes:",
]

for _, r in df.iterrows():
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
