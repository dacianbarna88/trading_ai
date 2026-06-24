import pandas as pd
from pathlib import Path
import yfinance as yf

REGISTRY_FILE = "decision_registry.csv"
SUMMARY_FILE = "outcome_evaluator_summary.txt"

if not Path(REGISTRY_FILE).exists():
    print("decision_registry.csv missing")
    raise SystemExit

df = pd.read_csv(REGISTRY_FILE)

summary = [
    "===== V28.8 OUTCOME EVALUATOR =====",
    "",
]

updated = 0

for idx, row in df.iterrows():

    if row["Outcome"] != "PENDING":
        continue

    ticker = row["Ticker"]
    entry = float(row["Entry_Price"])
    target = float(row["Target_Return_%"])
    stop = float(row["Stop_Return_%"])

    if entry <= 0:
        summary.append(f"{ticker} | SKIPPED | Entry price missing")
        continue

    data = yf.download(
        ticker,
        period="5d",
        interval="1d",
        progress=False,
        auto_adjust=True
    )

    if data.empty:
        summary.append(f"{ticker} | SKIPPED | No price data")
        continue

    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        current_price = round(float(close[ticker].iloc[-1]), 2)
    else:
        current_price = round(float(close.iloc[-1]), 2)

    return_pct = round(
        (current_price - entry) / entry * 100,
        2
    )

    outcome = "PENDING"

    if return_pct >= target:
        outcome = "WIN"

    elif return_pct <= stop:
        outcome = "LOSS"

    df.loc[idx, "Current_Price"] = current_price
    df.loc[idx, "Return_%"] = return_pct
    df.loc[idx, "Outcome"] = outcome

    if outcome != "PENDING":
        updated += 1

    summary.append(
        f"{ticker} | Entry {entry} | Current {current_price} | "
        f"Return {return_pct}% | Outcome {outcome}"
    )

df.to_csv(REGISTRY_FILE, index=False)

summary.extend([
    "",
    f"Outcomes Updated: {updated}",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
])

text = "\n".join(summary)

Path(SUMMARY_FILE).write_text(text)

print(text)
