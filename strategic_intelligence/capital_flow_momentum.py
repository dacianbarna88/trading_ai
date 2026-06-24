import pandas as pd
from pathlib import Path

HISTORY_FILE = "regional_strength_history.csv"
OUTPUT_FILE = "capital_flow_momentum_summary.txt"

if not Path(HISTORY_FILE).exists():
    print("NO_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

lines = [
    "===== V16.6.2 CAPITAL FLOW MOMENTUM =====",
    ""
]

for region in sorted(df["Region"].unique()):

    r = df[df["Region"] == region]

    if len(r) < 3:
        momentum = "INSUFFICIENT_HISTORY"
        velocity = 0

    else:
        s1 = float(r.iloc[-3]["Regional_Strength"])
        s2 = float(r.iloc[-2]["Regional_Strength"])
        s3 = float(r.iloc[-1]["Regional_Strength"])

        d1 = s2 - s1
        d2 = s3 - s2

        velocity = round(d2 - d1, 2)

        if velocity > 0:
            momentum = "ACCELERATING"
        elif velocity < 0:
            momentum = "DECELERATING"
        else:
            momentum = "STABLE"

    lines.append(
        f"{region} | Velocity {velocity} | {momentum}"
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
