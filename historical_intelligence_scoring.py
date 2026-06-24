from pathlib import Path
import pandas as pd

INPUT = "historical_intelligence.csv"
OUTPUT_CSV = "historical_intelligence_scores.csv"
OUTPUT_TXT = "historical_intelligence_scores_summary.txt"

df = pd.read_csv(INPUT)
df = df[df["Status"] == "OK"].copy()

for col in ["Return_%", "Max_Drawdown_%", "Volatility_%"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["Drawdown_Penalty"] = df["Max_Drawdown_%"].abs()

df["Score"] = (
    df["Return_%"]
    - df["Drawdown_Penalty"] * 0.7
    - df["Volatility_%"] * 0.5
).round(2)

df.to_csv(OUTPUT_CSV, index=False)

best_rows = []

for horizon in ["2Y", "5Y", "10Y", "20Y"]:
    h = df[df["Horizon"] == horizon]
    if not h.empty:
        best = h.sort_values("Score", ascending=False).iloc[0]
        best_rows.append(
            f"{horizon}: {best['Ticker']} | Score {best['Score']} | Return {best['Return_%']}% | MaxDD {best['Max_Drawdown_%']}% | Vol {best['Volatility_%']}%"
        )

overall = (
    df.groupby("Ticker")["Score"]
      .mean()
      .sort_values(ascending=False)
)

lines = [
    "===== V10.1 HISTORICAL INTELLIGENCE SCORING =====",
    "",
    "Best Score By Horizon:",
    *best_rows,
    "",
    "Overall Average Historical Score:",
]

for ticker, score in overall.items():
    lines.append(f"{ticker}: {round(score, 2)}")

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)

Path(OUTPUT_TXT).write_text(text)

print(text)
