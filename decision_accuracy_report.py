from pathlib import Path
import pandas as pd
import yfinance as yf

BASELINE_FILE = "decision_accuracy_baseline.csv"
REPORT_FILE = "decision_accuracy_report.txt"

df = pd.read_csv(BASELINE_FILE)

rows = []

for _, row in df.iterrows():
    ticker = row["Ticker"]
    entry = float(row["Entry_Price"])
    decision = row["Decision"]

    try:
        hist = yf.Ticker(ticker).history(period="1d")
        current = float(hist["Close"].iloc[-1])
        pnl_pct = round((current - entry) / entry * 100, 2)
    except Exception:
        current = None
        pnl_pct = None

    rows.append({
        "Ticker": ticker,
        "Decision": decision,
        "Entry": entry,
        "Current": current,
        "PnL_%": pnl_pct,
    })

result = pd.DataFrame(rows)

approved = result[result["Decision"] == "APPROVED"]
rejected = result[result["Decision"] == "REJECTED"]

approved_avg = round(approved["PnL_%"].dropna().mean(), 2) if not approved.empty else 0
rejected_avg = round(rejected["PnL_%"].dropna().mean(), 2) if not rejected.empty else 0

edge = round(approved_avg - rejected_avg, 2)

lines = [
    "===== DECISION ACCURACY REPORT =====",
    "",
]

for _, r in result.iterrows():
    lines.append(
        f"{r['Ticker']} | {r['Decision']} | "
        f"Entry {r['Entry']} | Current {round(r['Current'], 2)} | "
        f"PnL {r['PnL_%']}%"
    )

lines.extend([
    "",
    f"Approved Average: {approved_avg}%",
    f"Rejected Average: {rejected_avg}%",
    f"Committee Edge: {edge}%",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(lines)

Path(REPORT_FILE).write_text(text)

print(text)
