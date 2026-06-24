import pandas as pd
from pathlib import Path

health_df = pd.read_csv("allocator_health.csv")
progress_df = pd.read_csv("migration_progress.csv")

total_gap = health_df["Gap_%"].abs().sum()

allocator_health = max(
    0,
    round(100 - total_gap / 2, 1)
)

migration_progress = float(
    progress_df.iloc[0]["Progress_%"]
)

horizon_bonus = 0

try:

    txt = Path(
        "strategic_horizon_summary.txt"
    ).read_text()

    if "Short-Term Bias: EU" in txt:
        horizon_bonus += 10

    if "Long-Term Bias: US" in txt:
        horizon_bonus += 10

except:
    pass

score = round(
    allocator_health * 0.5 +
    migration_progress * 0.3 +
    horizon_bonus,
    1
)

score = min(100, score)

summary = pd.DataFrame([{
    "Allocator_Health": allocator_health,
    "Migration_Progress": migration_progress,
    "Horizon_Bonus": horizon_bonus,
    "Strategic_Portfolio_Score": score
}])

summary.to_csv(
    "strategic_portfolio_score.csv",
    index=False
)

print("\n===== STRATEGIC PORTFOLIO SCORE =====\n")
print(summary.to_string(index=False))
