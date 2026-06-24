import pandas as pd
import yfinance as yf
from pathlib import Path

df = pd.read_csv("portfolio.csv")

rebalances = df[
    df["Reason"].astype(str).str.contains(
        "REBALANCE|REDUCE",
        case=False,
        na=False
    )
]

results = []

good = 0
neutral = 0
bad = 0

for _, row in rebalances.iterrows():

    ticker = row["Ticker"]
    sell_price = float(row["Price"])
    reason = row["Reason"]

    try:
        data = yf.download(
            ticker,
            period="5d",
            progress=False,
            auto_adjust=False
        )

        if len(data) == 0:
            continue

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        current_price = float(data["Close"].iloc[-1])

    except:
        continue

    perf = round(
        ((current_price - sell_price) / sell_price) * 100,
        2
    )

    if perf <= -3:
        verdict = "GOOD_REBALANCE"
        good += 1

    elif perf >= 3:
        verdict = "BAD_REBALANCE"
        bad += 1

    else:
        verdict = "NEUTRAL_REBALANCE"
        neutral += 1

    results.append({
        "Ticker": ticker,
        "Sell_Price": sell_price,
        "Current_Price": round(current_price,2),
        "After_Rebalance_%": perf,
        "Reason": reason,
        "Verdict": verdict
    })

audit = pd.DataFrame(results)

if not audit.empty:
    edge = round(
        (
            good - bad
        ) / len(audit) * 100,
        2
    )
else:
    edge = 0

audit.to_csv(
    "rebalance_edge_report.csv",
    index=False
)

summary = f"""
===== V13.4 REBALANCE EDGE ENGINE =====

Rebalances Checked: {len(audit)}

Good Rebalances:
{good}

Neutral Rebalances:
{neutral}

Bad Rebalances:
{bad}

Rebalance Edge:
{edge}%

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path(
    "rebalance_edge_summary.txt"
).write_text(summary)

print(summary)

if not audit.empty:
    print(
        audit.to_string(index=False)
    )
