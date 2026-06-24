import pandas as pd
from pathlib import Path
from datetime import datetime

REPORT_FILE = "threshold_outcome_report.csv"
HISTORY_FILE = "threshold_history.csv"
SUMMARY_FILE = "threshold_history_summary.txt"

if not Path(REPORT_FILE).exists():
    print("NO_THRESHOLD_REPORT")
    raise SystemExit

df = pd.read_csv(REPORT_FILE)

avg_perf = round(df["Virtual_Performance_%"].mean(), 2)

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

new_record = pd.DataFrame([{
    "Timestamp": timestamp,
    "Records": len(df),
    "Average_Performance_%": avg_perf
}])

if Path(HISTORY_FILE).exists():
    history = pd.read_csv(HISTORY_FILE)
    history = pd.concat([history, new_record], ignore_index=True)
else:
    history = new_record

history.to_csv(HISTORY_FILE, index=False)

if len(history) < 2:
    trend = "INSUFFICIENT_HISTORY"
else:
    previous = float(history.iloc[-2]["Average_Performance_%"])
    current = float(history.iloc[-1]["Average_Performance_%"])

    if current > previous:
        trend = "IMPROVING"
    elif current < previous:
        trend = "DETERIORATING"
    else:
        trend = "STABLE"

summary = f"""
===== V14.9 THRESHOLD HISTORY ENGINE =====

History Records: {len(history)}
Latest Batch Size: {len(df)}
Latest Average Performance: {avg_perf}%

Trend:
{trend}

Mode:
AUDIT_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(SUMMARY_FILE).write_text(summary)

print(summary)
