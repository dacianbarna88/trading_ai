from pathlib import Path

AUDIT_FILE = "threshold_outcome_summary.txt"
OUTPUT_FILE = "threshold_decision_summary.txt"

if not Path(AUDIT_FILE).exists():
    summary = """
===== THRESHOLD DECISION GATE =====

STATUS: NO_AUDIT_DATA

ACTION:
KEEP_THRESHOLD_90

MODE:
AUDIT_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
"""
else:
    text = Path(AUDIT_FILE).read_text()

    if "OUTPERFORM" in text:
        decision = "CONSIDER_THRESHOLD_80"
    else:
        decision = "KEEP_THRESHOLD_90"

    summary = f"""
===== THRESHOLD DECISION GATE =====

DECISION:
{decision}

MODE:
AUDIT_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
