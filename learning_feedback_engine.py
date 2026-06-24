from pathlib import Path
import pandas as pd

memory_file = Path("historical_memory.csv")

if not memory_file.exists():
    raise SystemExit("historical_memory.csv not found")

df = pd.read_csv(memory_file)
df["Outcome_PnL"] = pd.to_numeric(df["Outcome_PnL"], errors="coerce")

approved = df[df["Decision"] == "APPROVED"]
rejected = df[df["Decision"] == "REJECTED"]

approved_avg = approved["Outcome_PnL"].mean()
rejected_avg = rejected["Outcome_PnL"].mean()

approved_avg = round(approved_avg, 2) if pd.notna(approved_avg) else 0
rejected_avg = round(rejected_avg, 2) if pd.notna(rejected_avg) else 0
outcome_edge = round(approved_avg - rejected_avg, 2)

bad_rejects = len(df[df["Outcome"] == "BAD_REJECT"])
good_rejects = len(df[df["Outcome"] == "GOOD_REJECT"])
wins = len(df[df["Outcome"] == "WIN"])
losses = len(df[df["Outcome"] == "LOSS"])

if outcome_edge > 0:
    lesson = "COMMITTEE_SELECTION_CONFIRMED"
    adjustment = "Maintain current selection logic."
elif bad_rejects > 0 and outcome_edge <= 0:
    lesson = "REJECTION_TOO_STRICT"
    adjustment = "Review rejected candidates with strong historical scores before excluding them."
else:
    lesson = "NEUTRAL_OR_INSUFFICIENT_DATA"
    adjustment = "Continue collecting outcomes before changing logic."

lines = [
    "===== V11.2 LEARNING FEEDBACK ENGINE =====",
    "",
    f"Approved Avg Outcome: {approved_avg}%",
    f"Rejected Avg Outcome: {rejected_avg}%",
    f"Outcome Edge: {outcome_edge}%",
    "",
    f"Wins: {wins}",
    f"Losses: {losses}",
    f"Good Rejects: {good_rejects}",
    f"Bad Rejects: {bad_rejects}",
    "",
    f"Learning Lesson: {lesson}",
    f"Suggested Adjustment: {adjustment}",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
]

text = "\n".join(lines)
Path("learning_feedback_summary.txt").write_text(text)

print(text)
