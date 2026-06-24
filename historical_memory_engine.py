from pathlib import Path
from datetime import datetime
import pandas as pd

decision_file = Path("historical_decision_alignment.csv")

if not decision_file.exists():
    raise SystemExit("historical_decision_alignment.csv not found")

decisions = pd.read_csv(decision_file)

memory_file = Path("historical_memory.csv")

if memory_file.exists():
    memory = pd.read_csv(memory_file)
else:
    memory = pd.DataFrame()

rows = []

for _, row in decisions.iterrows():
    rows.append({
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": row["Ticker"],
        "Decision": row["Decision"],
        "Historical_Score": row["Historical_Score"],
        "Historical_Rank": row["Historical_Rank"],
        "Committee_Vote": "CAUTIOUS",
        "Market_Regime": "BULL",
        "Outcome": "",
        "Outcome_PnL": "",
    })

memory = pd.concat(
    [memory, pd.DataFrame(rows)],
    ignore_index=True
)

memory.to_csv(memory_file, index=False)

summary = f"""
===== V11 HISTORICAL MEMORY ENGINE =====

Records Stored:
{len(memory)}

New Records Added:
{len(rows)}

Status:
ACTIVE

PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(
    "historical_memory_summary.txt"
).write_text(summary)

print(summary)
