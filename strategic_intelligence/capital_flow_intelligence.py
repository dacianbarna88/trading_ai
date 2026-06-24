import pandas as pd
from pathlib import Path
from datetime import datetime

INPUT_FILE = "regional_strength.csv"
HISTORY_FILE = "regional_strength_history.csv"

if not Path(INPUT_FILE).exists():
    print("NO_REGIONAL_STRENGTH_DATA")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

timestamp = datetime.now().strftime(
    "%Y-%m-%d %H:%M:%S"
)

records = []

for _, row in df.iterrows():
    records.append({
        "Timestamp": timestamp,
        "Region": row["Region"],
        "Regional_Strength": row["Regional_Strength"]
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
    new_df.tail(len(df))
)
