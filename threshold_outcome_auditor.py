import pandas as pd
import yfinance as yf
from pathlib import Path

tracker_file = "threshold_virtual_tracker.csv"

if not Path(tracker_file).exists():
    raise SystemExit("threshold_virtual_tracker.csv not found")

df = pd.read_csv(tracker_file)

results = []

for _, row in df.iterrows():
    ticker = row["Ticker"]
    entry_price = float(row["Entry_Price"])

    try:
        data = yf.download(
            ticker,
            period="5d",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            current_price = entry_price
        else:
            if len(data.columns.names) > 1:
                data.columns = data.columns.droplevel(1)

            current_price = float(data["Close"].iloc[-1])

    except Exception:
        current_price = entry_price

    perf = ((current_price - entry_price) / entry_price) * 100

    if perf >= 3:
        verdict = "VIRTUAL_WINNER"
    elif perf <= -3:
        verdict = "VIRTUAL_LOSER"
    else:
        verdict = "NEUTRAL"

    results.append({
        "Ticker": ticker,
        "Entry_Price": round(entry_price, 2),
        "Current_Price": round(current_price, 2),
        "Virtual_Performance_%": round(perf, 2),
        "Score": row["Score"],
        "Signal": row["Signal"],
        "Verdict": verdict,
    })

out = pd.DataFrame(results)
out.to_csv("threshold_outcome_report.csv", index=False)

avg_perf = round(out["Virtual_Performance_%"].mean(), 2) if not out.empty else 0
winners = len(out[out["Verdict"] == "VIRTUAL_WINNER"])
losers = len(out[out["Verdict"] == "VIRTUAL_LOSER"])
neutral = len(out[out["Verdict"] == "NEUTRAL"])

if avg_perf > 1:
    conclusion = "THRESHOLD_80_SHOWING_PROMISE"
elif avg_perf < -1:
    conclusion = "THRESHOLD_80_WEAK"
else:
    conclusion = "INSUFFICIENT_EDGE"

lines = [
    "===== V14.6 THRESHOLD OUTCOME AUDITOR =====",
    "",
    f"Virtual Positions Checked: {len(out)}",
    f"Average Virtual Performance: {avg_perf}%",
    f"Winners: {winners}",
    f"Neutral: {neutral}",
    f"Losers: {losers}",
    "",
    f"Conclusion: {conclusion}",
    "",
    "Virtual Positions:",
]

for _, r in out.iterrows():
    lines.append(
        f"{r['Ticker']} | {r['Virtual_Performance_%']}% | {r['Verdict']}"
    )

lines.extend([
    "",
    "Mode:",
    "AUDIT_ONLY",
    "NO_AUTO_CHANGE",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(lines)

Path("threshold_outcome_summary.txt").write_text(text)

print(text)
