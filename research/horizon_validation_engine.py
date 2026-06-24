import pandas as pd
from pathlib import Path

df = pd.read_csv("multi_horizon_backtest.csv")

winner_2y = df.sort_values(
    "Return_2Y_%",
    ascending=False
).iloc[0]

winner_5y = df.sort_values(
    "Return_5Y_%",
    ascending=False
).iloc[0]

winner_10y = df.sort_values(
    "Return_10Y_%",
    ascending=False
).iloc[0]

votes = {}

for market in [
    winner_2y["Market"],
    winner_5y["Market"],
    winner_10y["Market"]
]:
    votes[market] = votes.get(market, 0) + 1

consensus = max(
    votes,
    key=votes.get
)

confidence = round(
    votes[consensus] / 3 * 100,
    1
)

summary = f"""
===== HORIZON VALIDATION =====

2Y Winner: {winner_2y['Market']}
5Y Winner: {winner_5y['Market']}
10Y Winner: {winner_10y['Market']}

Consensus Leader: {consensus}

Confidence: {confidence}%
"""

Path(
    "horizon_validation_summary.txt"
).write_text(summary)

out = pd.DataFrame([{
    "Winner_2Y": winner_2y["Market"],
    "Winner_5Y": winner_5y["Market"],
    "Winner_10Y": winner_10y["Market"],
    "Consensus_Leader": consensus,
    "Confidence_%": confidence
}])

out.to_csv(
    "horizon_validation.csv",
    index=False
)

print(summary)
