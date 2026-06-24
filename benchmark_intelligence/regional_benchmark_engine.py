from pathlib import Path
import pandas as pd

INPUT_FILE = "regional_strength.csv"
OUTPUT_FILE = "regional_benchmark_summary.txt"

if not Path(INPUT_FILE).exists():
    print("NO_REGIONAL_STRENGTH")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

leader = df.sort_values(
    "Regional_Strength",
    ascending=False
).iloc[0]

summary = f"""
===== V23.0 REGIONAL BENCHMARK ENGINE =====

Current Regional Leader:

{leader['Region']}

Strength:

{leader['Regional_Strength']}

Benchmark Status:

ACTIVE

Benchmark Rule:

Regional vote is CORRECT if the voted
region remains the strongest region
at validation time.

Mode:
ANALYSIS_ONLY
NO_AUTO_CHANGE
PAPER_ONLY
NO_BROKER
"""

Path(OUTPUT_FILE).write_text(summary)

print(summary)
