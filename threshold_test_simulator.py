import pandas as pd
from pathlib import Path

signals = pd.read_csv("live_signals.csv")
portfolio = pd.read_csv("portfolio.csv")

portfolio["Action"] = portfolio["Action"].astype(str).str.upper()

open_positions = []

for ticker in portfolio["Ticker"].dropna().unique():
    rows = portfolio[portfolio["Ticker"] == ticker]
    buys = rows[rows["Action"] == "BUY"]["Shares"].sum()
    sells = rows[rows["Action"] == "SELL"]["Shares"].sum()

    if buys - sells > 0:
        open_positions.append(ticker)

threshold_90 = signals[
    (signals["Score"] >= 90) &
    (~signals["Ticker"].isin(open_positions))
].copy()

threshold_80 = signals[
    (signals["Score"] >= 80) &
    (~signals["Ticker"].isin(open_positions))
].copy()

extra_80 = threshold_80[
    ~threshold_80["Ticker"].isin(threshold_90["Ticker"])
].copy()

extra_80.to_csv("threshold_80_virtual_candidates.csv", index=False)

lines = [
    "===== V14.4 THRESHOLD TEST SIMULATOR =====",
    "",
    f"Open Positions: {len(open_positions)}",
    f"Threshold 90 New Candidates: {len(threshold_90)}",
    f"Threshold 80 New Candidates: {len(threshold_80)}",
    f"Extra Candidates at 80: {len(extra_80)}",
    "",
    "Extra 80 Candidates:",
]

if extra_80.empty:
    lines.append("None")
else:
    for _, r in extra_80.iterrows():
        lines.append(
            f"{r['Ticker']} | Score {r['Score']} | {r['Signal']} | Price {r['Price']}"
        )

lines.extend([
    "",
    "Mode:",
    "SIMULATION_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(lines)

Path("threshold_test_simulator_summary.txt").write_text(text)

print(text)
