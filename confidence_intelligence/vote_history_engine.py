import pandas as pd
from pathlib import Path
from datetime import datetime

HISTORY_FILE = "vote_history.csv"

votes = [
    ("THRESHOLD", "NEUTRAL"),
    ("REGIONAL", "BULLISH_US"),
    ("SECTOR", "BULLISH_TECH"),
    ("HORIZON", "LONG_TERM_US"),
    ("MACRO", "MACRO_BULLISH")
]

timestamp = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

records = []

for vote_name, vote_value in votes:
    records.append({
        "Timestamp": timestamp,
        "Vote": vote_name,
        "Decision": vote_value,
        "Outcome": "PENDING"
    })

new_df = pd.DataFrame(records)

if Path(HISTORY_FILE).exists():
    old = pd.read_csv(HISTORY_FILE)

    new_df = pd.concat(
        [old, new_df],
        ignore_index=True
    )

new_df.to_csv(
    HISTORY_FILE,
    index=False
)

print(
    new_df.tail(len(votes))
)
