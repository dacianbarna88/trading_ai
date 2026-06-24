from pathlib import Path
import pandas as pd
import yfinance as yf

memory_file = Path("historical_memory.csv")

if not memory_file.exists():
    raise SystemExit("historical_memory.csv not found")

df = pd.read_csv(memory_file)

df["Outcome"] = df.get("Outcome", "").astype("string").fillna("")
df["Outcome_PnL"] = pd.to_numeric(df.get("Outcome_PnL", ""), errors="coerce")

def get_price(ticker):
    data = yf.download(ticker, period="5d", auto_adjust=False, progress=False)
    if data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        close = data[("Close", ticker)].dropna()
    else:
        close = data["Close"].dropna()

    if close.empty:
        return None

    return float(close.iloc[-1])

# Baseline entry prices from V9 paper decision baseline
baseline_file = Path("decision_accuracy_baseline.csv")
baseline = pd.read_csv(baseline_file) if baseline_file.exists() else pd.DataFrame()

entry_map = {}
if not baseline.empty:
    for _, r in baseline.iterrows():
        entry_map[str(r["Ticker"])] = float(r["Entry_Price"])

for idx, row in df.iterrows():
    ticker = row["Ticker"]
    entry_price = entry_map.get(ticker)

    if entry_price is None:
        df.at[idx, "Outcome"] = "NO_ENTRY_PRICE"
        df.at[idx, "Outcome_PnL"] = ""
        continue

    current_price = get_price(ticker)

    if current_price is None:
        df.at[idx, "Outcome"] = "NO_LIVE_PRICE"
        df.at[idx, "Outcome_PnL"] = ""
        continue

    pnl = round(((current_price - entry_price) / entry_price) * 100, 2)

    df.at[idx, "Outcome_PnL"] = pnl

    if row["Decision"] == "APPROVED":
        df.at[idx, "Outcome"] = "WIN" if pnl > 0 else "LOSS"
    elif row["Decision"] == "REJECTED":
        df.at[idx, "Outcome"] = "GOOD_REJECT" if pnl <= 0 else "BAD_REJECT"
    else:
        df.at[idx, "Outcome"] = "UNKNOWN"

df.to_csv(memory_file, index=False)

approved = df[df["Decision"] == "APPROVED"]
rejected = df[df["Decision"] == "REJECTED"]

approved_avg = pd.to_numeric(approved["Outcome_PnL"], errors="coerce").mean()
rejected_avg = pd.to_numeric(rejected["Outcome_PnL"], errors="coerce").mean()

approved_avg = round(approved_avg, 2) if pd.notna(approved_avg) else 0
rejected_avg = round(rejected_avg, 2) if pd.notna(rejected_avg) else 0
outcome_edge = round(approved_avg - rejected_avg, 2)

summary = f"""
===== V11.1 HISTORICAL OUTCOME TRACKER =====

Records Checked:
{len(df)}

Approved Outcome Average:
{approved_avg}%

Rejected Outcome Average:
{rejected_avg}%

Outcome Edge:
{outcome_edge}%

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("historical_outcome_summary.txt").write_text(summary)

print(summary)
print(df.to_string(index=False))
