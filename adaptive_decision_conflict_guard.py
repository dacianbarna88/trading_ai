from pathlib import Path

SOURCE_FILE = "weighted_committee_summary.txt"
OUTPUT_FILE = "adaptive_decision_guard_summary.txt"

if not Path(SOURCE_FILE).exists():
    print("weighted_committee_summary.txt missing")
    raise SystemExit

text = Path(SOURCE_FILE).read_text()

strategic_vote = "UNKNOWN"
adaptive_decision = "UNKNOWN"
weighted_confidence = "UNKNOWN"

for line in text.splitlines():

    if line.startswith("Strategic Committee Vote:"):
        strategic_vote = line.split(":", 1)[1].strip()

    if line.startswith("FINAL ADAPTIVE DECISION:"):
        adaptive_decision = line.split(":", 1)[1].strip()

    if line.startswith("Weighted Confidence:"):
        weighted_confidence = line.split(":", 1)[1].strip()

guard_decision = adaptive_decision
guard_reason = "No conflict detected"

if strategic_vote == "CAUTIOUS" and adaptive_decision == "BUY":
    guard_decision = "CONTROLLED_BUY"
    guard_reason = "Strategic committee is CAUTIOUS while adaptive engine says BUY"

if strategic_vote == "DEFENSIVE" and adaptive_decision == "BUY":
    guard_decision = "WATCH"
    guard_reason = "Strategic committee is DEFENSIVE while adaptive engine says BUY"

summary = f"""
===== V28.2 ADAPTIVE DECISION CONFLICT GUARD =====

Strategic Committee Vote: {strategic_vote}
Adaptive Decision: {adaptive_decision}
Weighted Confidence: {weighted_confidence}

Guard Final Decision: {guard_decision}

Guard Reason:
{guard_reason}

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
