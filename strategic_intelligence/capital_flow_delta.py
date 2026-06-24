import pandas as pd
from pathlib import Path

HISTORY_FILE = "regional_strength_history.csv"
OUTPUT_FILE = "capital_flow_delta_summary.txt"

if not Path(HISTORY_FILE).exists():
    print("NO_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

regions = sorted(df["Region"].unique())

lines = [
    "===== V16.6 CAPITAL FLOW DELTA =====",
    ""
]

for region in regions:

    r = df[df["Region"] == region]

    if len(r) < 2:
        delta = 0
        status = "INSUFFICIENT_DATA"
    else:
        prev = float(r.iloc[-2]["Regional_Strength"])
        curr = float(r.iloc[-1]["Regional_Strength"])

        delta = round(curr - prev, 2)

        if delta > 0:
            status = "CAPITAL_FLOW_IN"
        elif delta < 0:
            status = "CAPITAL_FLOW_OUT"
        else:
            status = "STABLE"

    lines.append(
        f"{region} | Delta {delta} | {status}"
    )

lines.extend([
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER"
])

text = "\n".join(lines)

Path(OUTPUT_FILE).write_text(text)

print(text)
