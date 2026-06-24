import pandas as pd
from pathlib import Path

hist = pd.read_csv("historical_intelligence.csv")

leader = hist.sort_values(
    "Bull_Probability",
    ascending=False
).iloc[0]

long_term_market = leader["Market"]

rotation_text = Path(
    "market_rotation_summary.txt"
).read_text()

if "Market Rotation Bias: EUROPE" in rotation_text:
    short_term_market = "EU"

elif "Market Rotation Bias: USA" in rotation_text:
    short_term_market = "US"

elif "Market Rotation Bias: UK" in rotation_text:
    short_term_market = "UK"

else:
    short_term_market = "UNKNOWN"

summary = f"""STRATEGIC HORIZON

Short-Term Bias: {short_term_market}

Long-Term Bias: {long_term_market}

Combined View:
Rotate new capital into {short_term_market}
Keep core exposure in {long_term_market}
"""

Path(
    "strategic_horizon_summary.txt"
).write_text(summary)

print(summary)
