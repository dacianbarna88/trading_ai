from pathlib import Path
import pandas as pd

hist_file = Path("historical_intelligence_scores.csv")
committee_file = Path("committee_learning_history.csv")

if not hist_file.exists():
    raise SystemExit("historical_intelligence_scores.csv not found")

df = pd.read_csv(hist_file)

market_regime = "UNKNOWN"

if committee_file.exists():
    cdf = pd.read_csv(committee_file)

    if len(cdf):
        regime = cdf.iloc[-1].get("Market_Regime")

        if pd.notna(regime):
            market_regime = str(regime)

h2 = df[df["Horizon"] == "2Y"]["Score"].mean()
h5 = df[df["Horizon"] == "5Y"]["Score"].mean()
h10 = df[df["Horizon"] == "10Y"]["Score"].mean()
h20 = df[df["Horizon"] == "20Y"]["Score"].mean()

scores = {
    "2Y": round(h2, 2),
    "5Y": round(h5, 2),
    "10Y": round(h10, 2),
    "20Y": round(h20, 2),
}

dominant = max(scores, key=scores.get)

if dominant == "2Y":
    profile = "SHORT_TERM"
elif dominant == "5Y":
    profile = "MEDIUM_TERM"
elif dominant == "10Y":
    profile = "LONG_TERM"
else:
    profile = "SUPER_CYCLE"

summary = f"""
===== V12 REGIME INTELLIGENCE ENGINE =====

Current Market Regime:
{market_regime}

2Y Average Score:
{scores['2Y']}

5Y Average Score:
{scores['5Y']}

10Y Average Score:
{scores['10Y']}

20Y Average Score:
{scores['20Y']}

Dominant Horizon:
{dominant}

Regime Profile:
{profile}

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("regime_intelligence_summary.txt").write_text(summary)

print(summary)
