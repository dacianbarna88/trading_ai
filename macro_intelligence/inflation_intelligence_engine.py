from pathlib import Path
import json

INPUT_FILE = "macro_intelligence/macro_snapshot.json"
OUTPUT_FILE = "inflation_intelligence_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_MACRO_SNAPSHOT")
    raise SystemExit

snapshot = json.loads(
    Path(INPUT_FILE).read_text()
)

inflation = snapshot.get(
    "Inflation_Trend",
    "UNKNOWN"
)

if inflation == "DOWN":
    verdict = "DISINFLATION"
elif inflation == "UP":
    verdict = "INFLATION_PRESSURE"
elif inflation == "STABLE":
    verdict = "INFLATION_STABLE"
else:
    verdict = "UNKNOWN"

summary = f"""
===== V19.3 INFLATION INTELLIGENCE =====

Inflation Trend:
{inflation}

Verdict:
{verdict}

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
