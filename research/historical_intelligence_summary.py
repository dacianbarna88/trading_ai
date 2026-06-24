import pandas as pd
from pathlib import Path

df = pd.read_csv("historical_intelligence.csv")

best = df.sort_values(
    "Bull_Probability",
    ascending=False
).iloc[0]

text = f"""HISTORICAL INTELLIGENCE

Leader Market: {best['Market']}

{df.to_string(index=False)}
"""

Path(
    "historical_intelligence_summary.txt"
).write_text(text)

print(text)
