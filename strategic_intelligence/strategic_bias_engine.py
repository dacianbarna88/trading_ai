import pandas as pd
from pathlib import Path

INPUT_FILE = "regional_strength.csv"
OUTPUT_FILE = "strategic_bias_summary.txt"
CSV_FILE = "strategic_bias.csv"

if not Path(INPUT_FILE).exists():
    print("NO_REGIONAL_STRENGTH_DATA")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

rows = []

for _, r in df.iterrows():
    region = r["Region"]
    strength = float(r["Regional_Strength"])

    if strength >= 10:
        bias = "OVERWEIGHT"
    elif strength >= 6:
        bias = "NEUTRAL"
    else:
        bias = "UNDERWEIGHT"

    rows.append({
        "Region": region,
        "Regional_Strength": strength,
        "Strategic_Bias": bias,
    })

out = pd.DataFrame(rows)

out.to_csv(CSV_FILE, index=False)

summary = [
    "===== V16.3 STRATEGIC BIAS ENGINE =====",
    "",
    "Strategic Bias:",
]

for _, r in out.iterrows():
    summary.append(
        f"{r['Region']} | Strength {r['Regional_Strength']} | {r['Strategic_Bias']}"
    )

summary.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(OUTPUT_FILE).write_text(text)

print(text)
