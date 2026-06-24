import pandas as pd
from pathlib import Path

WEIGHTS_FILE = "adaptive_weights.csv"
OUTPUT_FILE = "weighted_committee_decision.txt"

BASE_VOTES = {
    "THRESHOLD": "BUY",
    "REGIONAL": "BUY",
    "SECTOR": "WAIT",
    "HORIZON": "BUY",
    "MACRO": "WAIT",
}


def vote_score(vote):
    if vote == "BUY":
        return 1
    if vote == "SELL":
        return -1
    return 0


if not Path(WEIGHTS_FILE).exists():
    print("adaptive_weights.csv missing")
    raise SystemExit

weights = pd.read_csv(WEIGHTS_FILE)

total_score = 0
total_weight = 0
lines = []

for _, row in weights.iterrows():
    vote_name = row["Vote"]
    weight = float(row["New_Weight"])

    decision = BASE_VOTES.get(vote_name, "WAIT")
    score = vote_score(decision) * weight

    total_score += score
    total_weight += weight

    lines.append(
        f"{vote_name} | Vote {decision} | Weight {weight} | Score {round(score, 2)}"
    )

confidence = 0

if total_weight > 0:
    confidence = round(abs(total_score) / total_weight * 100, 2)

if total_score >= 1:
    final_decision = "BUY"
elif total_score <= -1:
    final_decision = "SELL"
else:
    final_decision = "WAIT"

summary = "\n".join([
    "===== V27.7 WEIGHTED COMMITTEE DECISION =====",
    "",
    *lines,
    "",
    f"Total Weighted Score: {round(total_score, 2)}",
    f"Total Weight: {round(total_weight, 2)}",
    f"Confidence: {confidence}%",
    f"Final Decision: {final_decision}",
    "",
    "Mode:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

Path(OUTPUT_FILE).write_text(summary)

print(summary)
