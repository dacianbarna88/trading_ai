from pathlib import Path

summary = """
===== V21.1 VALIDATION HORIZON ENGINE =====

Validation Rules:

THRESHOLD:
30 DAYS

REGIONAL:
30 DAYS

SECTOR:
30 DAYS

MACRO:
90 DAYS

HORIZON:
180 DAYS

Interpretation:

Threshold, Regional and Sector votes
can be validated after 30 days.

Macro votes require longer cycles.

Horizon votes require the longest cycle.

Validation Status:
ACTIVE

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(
    "validation_horizon_summary.txt"
).write_text(summary)

print(summary)
