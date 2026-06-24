from pathlib import Path
import pandas as pd
import re

scores_file = Path("historical_intelligence_scores.csv")
decision_file = Path("paper_trading_decision_summary.txt")

if not scores_file.exists():
    raise SystemExit("historical_intelligence_scores.csv not found")

if not decision_file.exists():
    raise SystemExit("paper_trading_decision_summary.txt not found")

scores = pd.read_csv(scores_file)
decision_text = decision_file.read_text()

approved = []
rejected = []

section = None
for line in decision_text.splitlines():
    line = line.strip()

    if line.startswith("APPROVED CANDIDATES"):
        section = "APPROVED"
        continue

    if line.startswith("REJECTED CANDIDATES"):
        section = "REJECTED"
        continue

    m = re.match(r"^([A-Z0-9\.\-]+)", line)
    if m and "|" in line:
        ticker = m.group(1)
        if section == "APPROVED":
            approved.append(ticker)
        elif section == "REJECTED":
            rejected.append(ticker)

overall = (
    scores.groupby("Ticker")["Score"]
    .mean()
    .sort_values(ascending=False)
    .reset_index()
)

rank_map = {
    row["Ticker"]: i + 1
    for i, row in overall.iterrows()
}

score_map = {
    row["Ticker"]: round(row["Score"], 2)
    for _, row in overall.iterrows()
}

rows = []

for ticker in approved:
    rows.append({
        "Ticker": ticker,
        "Decision": "APPROVED",
        "Historical_Score": score_map.get(ticker),
        "Historical_Rank": rank_map.get(ticker),
    })

for ticker in rejected:
    rows.append({
        "Ticker": ticker,
        "Decision": "REJECTED",
        "Historical_Score": score_map.get(ticker),
        "Historical_Rank": rank_map.get(ticker),
    })

df = pd.DataFrame(rows)
df.to_csv("historical_decision_alignment.csv", index=False)

approved_df = df[df["Decision"] == "APPROVED"]
rejected_df = df[df["Decision"] == "REJECTED"]

approved_avg = round(approved_df["Historical_Score"].dropna().mean(), 2) if not approved_df.empty else 0
rejected_avg = round(rejected_df["Historical_Score"].dropna().mean(), 2) if not rejected_df.empty else 0
alignment_edge = round(approved_avg - rejected_avg, 2)

verdict = "POSITIVE" if alignment_edge > 0 else "NEGATIVE" if alignment_edge < 0 else "NEUTRAL"

lines = [
    "===== V10.2 HISTORICAL DECISION ALIGNMENT =====",
    "",
    "Approved Historical Average:",
    f"{approved_avg}",
    "",
    "Rejected Historical Average:",
    f"{rejected_avg}",
    "",
    "Historical Alignment Edge:",
    f"{alignment_edge}",
    "",
    "Alignment Verdict:",
    verdict,
    "",
    "Decision Alignment Details:",
]

for _, r in df.iterrows():
    lines.append(
        f"{r['Ticker']} | {r['Decision']} | Historical Score {r['Historical_Score']} | Rank {r['Historical_Rank']}"
    )

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)
Path("historical_decision_alignment_summary.txt").write_text(text)

print(text)
