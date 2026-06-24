from pathlib import Path
import pandas as pd

REGISTRY_FILE = "vote_outcome_registry.csv"
LEARNING_FILE = "learning_automation_summary.txt"

lines = [
    "===== V27.1 LEARNING AUTOMATION SUMMARY =====",
    ""
]

if Path(REGISTRY_FILE).exists():

    df = pd.read_csv(REGISTRY_FILE)

    lines.append("Current Registry State:")
    lines.append("")

    pending = 0
    correct = 0
    wrong = 0

    for _, row in df.iterrows():

        vote = row.get("Vote", "UNKNOWN")
        outcome = row.get("Outcome", "PENDING")
        weight = row.get("Weight", 1.0)

        lines.append(
            f"{vote} | {outcome} | Weight {weight}"
        )

        if outcome == "PENDING":
            pending += 1
        elif outcome == "CORRECT":
            correct += 1
        elif outcome == "WRONG":
            wrong += 1

    lines.extend([
        "",
        f"Pending: {pending}",
        f"Correct: {correct}",
        f"Wrong: {wrong}",
        "",
        "Learning Status:",
        "ACTIVE",
        "",
        "Protection:",
        "NO_WEIGHT_CHANGE_FOR_PENDING",
        "MIN_WEIGHT=0.5",
        "MAX_WEIGHT=3.0",
        "",
        "Mode:",
        "ANALYSIS_ONLY",
        "NO_AUTO_CHANGE",
        "PAPER_ONLY",
        "NO_BROKER"
    ])

else:

    lines.extend([
        "NO_REGISTRY_FOUND"
    ])

summary = "\n".join(lines)

Path(LEARNING_FILE).write_text(summary)

print(summary)
