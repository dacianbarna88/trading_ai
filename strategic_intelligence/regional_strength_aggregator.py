import pandas as pd
from pathlib import Path

INPUT_FILE = "global_market_scanner.csv"
OUTPUT_FILE = "regional_strength_summary.txt"
CSV_FILE = "regional_strength.csv"

if not Path(INPUT_FILE).exists():
    print("NO_GLOBAL_MARKET_SCANNER_DATA")
    raise SystemExit

df = pd.read_csv(INPUT_FILE)

REGIONS = {
    "US": ["US_LARGE_CAP", "US_TECH", "US_BLUE_CHIP", "US_SMALL_CAP"],
    "EUROPE": ["EUROPE", "EUROZONE"],
    "UK": ["UK"],
    "ASIA": ["JAPAN", "HONG_KONG", "INDIA"],
}

rows = []

for region, markets in REGIONS.items():
    sub = df[df["Market"].isin(markets)]

    score = round(
        sub["Strategic_Score"].mean(),
        2
    )

    rows.append({
        "Region": region,
        "Markets": ",".join(markets),
        "Regional_Strength": score,
    })

out = pd.DataFrame(rows).sort_values(
    by="Regional_Strength",
    ascending=False
)

out.to_csv(CSV_FILE, index=False)

leader = out.iloc[0]

summary = [
    "===== V16.2 REGIONAL STRENGTH AGGREGATOR =====",
    "",
    f"Regional Leader: {leader['Region']}",
    f"Regional Strength: {leader['Regional_Strength']}",
    "",
    "Regional Ranking:",
]

for _, r in out.iterrows():
    summary.append(
        f"{r['Region']} | Strength {r['Regional_Strength']}"
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
