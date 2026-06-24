import pandas as pd
from pathlib import Path

COMMITTEE_FILE = "strategic_committee_summary.txt"
ADAPTIVE_WEIGHTS_FILE = "adaptive_weights.csv"
OUTPUT_FILE = "weighted_committee_summary.txt"

if not Path(COMMITTEE_FILE).exists():
    print("NO_COMMITTEE_SUMMARY")
    raise SystemExit

if not Path(ADAPTIVE_WEIGHTS_FILE).exists():
    print("NO_ADAPTIVE_WEIGHTS")
    raise SystemExit

committee = Path(COMMITTEE_FILE).read_text()
adaptive_weights = pd.read_csv(ADAPTIVE_WEIGHTS_FILE)

weights = dict(
    zip(
        adaptive_weights["Vote"],
        adaptive_weights["New_Weight"]
    )
)

committee_vote = "NEUTRAL"
committee_confidence = 0

for line in committee.splitlines():
    if line.startswith("Committee Vote:"):
        committee_vote = line.split(":", 1)[1].strip()

    if line.startswith("Confidence:"):
        raw = line.split(":", 1)[1].strip().replace("%", "")
        try:
            committee_confidence = float(raw)
        except Exception:
            committee_confidence = 0

vote_map = {
    "THRESHOLD": "BUY",
    "REGIONAL": "BUY",
    "SECTOR": "NEUTRAL",
    "HORIZON": "BUY",
    "MACRO": "NEUTRAL",
}

score = 0
max_score = 0
details = []

for vote, decision in vote_map.items():
    weight = float(weights.get(vote, 1.0))
    max_score += weight

    if decision == "BUY":
        score += weight
        signal = "BULLISH"
    elif decision == "SELL":
        score -= weight
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    details.append(
        (vote, decision, weight, signal)
    )

weighted_confidence = round(
    abs(score) / max_score * 100,
    2
) if max_score > 0 else 0

if score >= 1:
    final_decision = "BUY"
elif score <= -1:
    final_decision = "SELL"
else:
    final_decision = "WAIT"

summary = [
    "===== V28.1 ADAPTIVE WEIGHTED COMMITTEE ENGINE =====",
    "",
    "Source:",
    "strategic_committee_summary.txt",
    "adaptive_weights.csv",
    "",
    f"Strategic Committee Vote: {committee_vote}",
    f"Strategic Committee Confidence: {committee_confidence}%",
    "",
    "Adaptive Weighted Votes:",
]

for vote, decision, weight, signal in details:
    summary.append(
        f"{vote} | Vote {decision} | Weight {weight} | {signal}"
    )

summary.extend([
    "",
    f"Weighted Score: {round(score, 2)}",
    f"Max Weight: {round(max_score, 2)}",
    f"Weighted Confidence: {weighted_confidence}%",
    "",
    f"FINAL ADAPTIVE DECISION: {final_decision}",
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
