
import pandas as pd
from pathlib import Path

csv_file = Path("committee_learning_history.csv")

if not csv_file.exists():
    raise SystemExit("committee_learning_history.csv not found")

df = pd.read_csv(csv_file)

for col in [
    "Confidence",
    "Committee_Edge",
    "Approved_Average",
    "Rejected_Average",
    "Cash_Deployment"
]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

avg_edge = round(df["Committee_Edge"].mean(), 2)
avg_confidence = round(df["Confidence"].mean(), 2)
avg_deployment = round(df["Cash_Deployment"].mean(), 2)

vote_stats = (
    df.groupby("Committee_Vote")["Committee_Edge"]
      .mean()
      .sort_values(ascending=False)
)

best_vote = vote_stats.index[0]
best_edge = round(vote_stats.iloc[0], 2)

summary = f"""
===== COMMITTEE LEARNING ANALYTICS =====

Records:
{len(df)}

Average Edge:
{avg_edge}%

Average Confidence:
{avg_confidence}%

Average Deployment:
{avg_deployment}%

Best Vote:
{best_vote}

Best Vote Edge:
{best_edge}%

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("committee_learning_analytics.txt").write_text(summary)
print(summary)
