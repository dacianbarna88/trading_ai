from pathlib import Path

SOURCE_FILE = "weighted_committee_decision.txt"
OUTPUT_FILE = "weighted_committee_decision_summary.txt"

if not Path(SOURCE_FILE).exists():
    print("weighted_committee_decision.txt missing")
    raise SystemExit

text = Path(SOURCE_FILE).read_text()

lines = text.splitlines()

decision = "UNKNOWN"
confidence = "UNKNOWN"

for line in lines:

    if "Decision:" in line:
        decision = line.split(":", 1)[1].strip()

    if "Confidence:" in line:
        confidence = line.split(":", 1)[1].strip()

summary = f"""
===== V27.8 WEIGHTED DECISION SUMMARY =====

Final Decision: {decision}

Confidence: {confidence}

Mode:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
