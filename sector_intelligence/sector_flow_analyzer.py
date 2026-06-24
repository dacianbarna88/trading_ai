import pandas as pd
from pathlib import Path

HISTORY_FILE = "sector_rotation_history.csv"
OUTPUT_FILE = "sector_flow_summary.txt"

if not Path(HISTORY_FILE).exists():
    print("NO_SECTOR_HISTORY")
    raise SystemExit

df = pd.read_csv(HISTORY_FILE)

lines = [
    "===== V17.2 SECTOR FLOW ANALYZER =====",
    ""
]

for sector in sorted(df["Sector"].unique()):

    s = df[df["Sector"] == sector]

    if len(s) < 2:
        delta = 0
        status = "INSUFFICIENT_HISTORY"
    else:
        prev = float(s.iloc[-2]["Sector_Score"])
        curr = float(s.iloc[-1]["Sector_Score"])

        delta = round(curr - prev, 2)

        if delta > 0:
            status = "CAPITAL_FLOW_IN"
        elif delta < 0:
            status = "CAPITAL_FLOW_OUT"
        else:
            status = "STABLE"

    lines.append(
        f"{sector} | Delta {delta} | {status}"
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
