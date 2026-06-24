from pathlib import Path
import pandas as pd

INPUT_FILE = "sector_rotation.csv"
OUTPUT_FILE = "sector_benchmark_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_SECTOR_ROTATION")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

leader = df.sort_values(
    "Sector_Score",
    ascending=False
).iloc[0]

summary = f"""
===== V23.1 SECTOR BENCHMARK ENGINE =====

Current Sector Leader:

{leader['Sector']}

Ticker:

{leader['Ticker']}

Score:

{leader['Sector_Score']}

Benchmark Status:

ACTIVE

Benchmark Rule:

Sector vote is CORRECT if the voted
sector remains the strongest sector
or outperforms SPY at validation time.

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
