from pathlib import Path
import json

INPUT_FILE = "macro_intelligence/macro_snapshot.json"
OUTPUT_FILE = "economic_regime_summary.txt"

default_snapshot = {
    "GDP_Trend": "UNKNOWN",
    "Unemployment_Trend": "UNKNOWN",
    "Inflation_Trend": "UNKNOWN",
    "Rates_Trend": "UNKNOWN"
}

if not Path(INPUT_FILE).exists():
    Path(INPUT_FILE).write_text(
        json.dumps(default_snapshot, indent=2)
    )

snapshot = json.loads(
    Path(INPUT_FILE).read_text()
)

gdp = snapshot.get("GDP_Trend", "UNKNOWN")
unemployment = snapshot.get("Unemployment_Trend", "UNKNOWN")
inflation = snapshot.get("Inflation_Trend", "UNKNOWN")
rates = snapshot.get("Rates_Trend", "UNKNOWN")

if gdp == "UP" and unemployment == "DOWN" and inflation in ["DOWN", "STABLE"]:
    regime = "EXPANSION"
elif gdp == "DOWN" and unemployment == "UP":
    regime = "RECESSION_RISK"
elif gdp == "UP" and unemployment == "UP":
    regime = "RECOVERY_OR_MIXED"
elif inflation == "UP" and rates == "UP":
    regime = "INFLATION_PRESSURE"
else:
    regime = "MACRO_UNCLEAR"

summary = f"""
===== V19.1 ECONOMIC REGIME ENGINE =====

Inputs:
GDP Trend: {gdp}
Unemployment Trend: {unemployment}
Inflation Trend: {inflation}
Rates Trend: {rates}

Economic Regime:
{regime}

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
