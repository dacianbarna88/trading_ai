import pandas as pd
from pathlib import Path

REGISTRY_FILE = "decision_registry.csv"
HISTORY_FILE = "learning_weight_history.csv"
SUMMARY_FILE = "feedback_update_summary.txt"

if not Path(REGISTRY_FILE).exists():
    print("decision_registry.csv missing")
    raise SystemExit

if not Path(HISTORY_FILE).exists():
    print("learning_weight_history.csv missing")
    raise SystemExit

registry = pd.read_csv(REGISTRY_FILE)
history = pd.read_csv(HISTORY_FILE)

completed = registry[registry["Outcome"].isin(["WIN", "LOSS"])]

summary = [
    "===== V29.1 FEEDBACK UPDATE ENGINE =====",
    "",
    f"Completed Decisions: {len(completed)}",
    "",
]

updates = 0

if len(completed) == 0:
    summary.append("No completed outcomes to feed back yet.")

else:
    for _, decision_row in completed.iterrows():

        outcome = decision_row["Outcome"]

        pending_votes = history[history["Outcome"] == "PENDING"]

        if len(pending_votes) == 0:
            summary.append("No pending learning votes found.")
            continue

        for idx in pending_votes.index:

            correct = int(history.loc[idx, "Correct"])
            wrong = int(history.loc[idx, "Wrong"])

            if outcome == "WIN":
                correct += 1
            elif outcome == "LOSS":
                wrong += 1

            total = correct + wrong
            accuracy = round(correct / total * 100, 2) if total > 0 else 0

            history.loc[idx, "Correct"] = correct
            history.loc[idx, "Wrong"] = wrong
            history.loc[idx, "Total_Scored"] = total
            history.loc[idx, "Accuracy_%"] = accuracy
            history.loc[idx, "Outcome"] = outcome

            updates += 1

        summary.append(
            f"Decision {decision_row['Decision']} | Outcome {outcome} | "
            f"Learning votes updated: {len(pending_votes)}"
        )

history.to_csv(HISTORY_FILE, index=False)

summary.extend([
    "",
    f"Total Learning Updates: {updates}",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(SUMMARY_FILE).write_text(text)

print(text)
