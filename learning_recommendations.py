import pandas as pd
from pathlib import Path

scoreboard = pd.read_csv("learning_scoreboard.csv")

latest = scoreboard.iloc[-1]

sell_quality = float(latest["Sell_Quality_%"])
rebalance_edge = float(latest["Rebalance_Edge_%"])
missed_rate = float(latest["Missed_Winner_Rate_%"])
threshold_opportunity = int(latest["Threshold_Opportunity"])

recommendations = []

if sell_quality >= 80:
    recommendations.append(
        "SELL_ENGINE_OK"
    )
else:
    recommendations.append(
        "REVIEW_SELL_ENGINE"
    )

if rebalance_edge > 5:
    recommendations.append(
        "REBALANCE_ADDING_VALUE"
    )
elif rebalance_edge < -5:
    recommendations.append(
        "REBALANCE_NEEDS_REVIEW"
    )
else:
    recommendations.append(
        "REBALANCE_INCONCLUSIVE"
    )

if missed_rate > 20:
    recommendations.append(
        "WATCH_THRESHOLD_80"
    )

if threshold_opportunity >= 5:
    recommendations.append(
        "THRESHOLD_TEST_RECOMMENDED"
    )

summary = [
    "===== V14.3 LEARNING RECOMMENDATIONS =====",
    "",
    "Current Recommendations:",
    ""
]

for r in recommendations:
    summary.append(f"- {r}")

summary.extend([
    "",
    "Metrics:",
    f"Sell Quality: {sell_quality}%",
    f"Rebalance Edge: {rebalance_edge}%",
    f"Missed Winner Rate: {missed_rate}%",
    f"Threshold Opportunity: +{threshold_opportunity}",
    "",
    "Mode:",
    "AUDIT_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(summary)

Path(
    "learning_recommendations_summary.txt"
).write_text(text)

print(text)
