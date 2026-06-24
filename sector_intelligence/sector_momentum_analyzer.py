import pandas as pd
from pathlib import Path

HISTORY_FILE = "sector_rotation_history.csv"
OUTPUT_FILE = "sector_momentum_summary.txt"

if not Path(HISTORY_FILE).exists():
    print("NO_SECTOR_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

lines = [
    "===== V17.3 SECTOR MOMENTUM ANALYZER =====",
    ""
]

for sector in sorted(df["Sector"].unique()):

    s = df[df["Sector"] == sector]

    if len(s) < 3:
        velocity = 0
        momentum = "INSUFFICIENT_HISTORY"
    else:
        s1 = float(s.iloc[-3]["Sector_Score"])
        s2 = float(s.iloc[-2]["Sector_Score"])
        s3 = float(s.iloc[-1]["Sector_Score"])

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
        f"{sector} | Velocity {velocity} | {momentum}"
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
