import pandas as pd
from pathlib import Path

REPORT_FILE = "threshold_outcome_report.csv"
OUTPUT_FILE = "threshold_confidence_summary.txt"

if not Path(REPORT_FILE).exists():
    summary = """
===== V14.8 THRESHOLD CONFIDENCE ENGINE =====

STATUS:
NO_THRESHOLD_DATA

RECOMMENDATION:
KEEP_THRESHOLD_90

Mode:
AUDIT_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""
    Path(OUTPUT_FILE).write_text(summary)
    print(summary)
    raise SystemExit

df = pd.read_csv(REPORT_FILE)

total = len(df)
winners = len(df[df["Verdict"] == "VIRTUAL_WINNER"])
losers = len(df[df["Verdict"] == "VIRTUAL_LOSER"])
neutral = len(df[df["Verdict"] == "NEUTRAL"])

avg_perf = round(df["Virtual_Performance_%"].mean(), 2)

if total == 0:
    confidence = 0
else:
    confidence = round(max(0, min(100, 50 + avg_perf * 10)), 1)

if total < 10:
    recommendation = "KEEP_THRESHOLD_90_MORE_DATA_NEEDED"
elif confidence >= 65:
    recommendation = "THRESHOLD_80_READY_FOR_EXTENDED_TEST"
elif confidence <= 45:
    recommendation = "THRESHOLD_80_NOT_READY"
else:
    recommendation = "KEEP_THRESHOLD_90"

summary = f"""
===== V14.8 THRESHOLD CONFIDENCE ENGINE =====

Records Analyzed: {total}

Performance:
Average Virtual Performance: {avg_perf}%
Winners: {winners}
Neutral: {neutral}
Losers: {losers}

Confidence Score:
{confidence}%

Recommendation:
{recommendation}

Interpretation:
Threshold 80 is still under observation.
Current evidence is not strong enough to lower the real buy threshold.

Mode:
AUDIT_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)
print(summary)
