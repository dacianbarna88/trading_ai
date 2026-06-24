from pathlib import Path
import json

INPUT_FILE = "macro_intelligence/macro_snapshot.json"
OUTPUT_FILE = "rate_intelligence_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_MACRO_SNAPSHOT")
    raise SystemExit

snapshot = json.loads(
    Path(INPUT_FILE).read_text()
)

rates = snapshot.get(
    "Rates_Trend",
    "UNKNOWN"
)

if rates == "DOWN":
    verdict = "RATE_TAILWIND"
elif rates == "UP":
    verdict = "RATE_HEADWIND"
elif rates == "STABLE":
    verdict = "RATE_NEUTRAL"
else:
    verdict = "UNKNOWN"

summary = f"""
===== V19.2 RATE INTELLIGENCE =====

Rates Trend:
{rates}

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
