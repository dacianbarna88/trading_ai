import pandas as pd
import yfinance as yf
from pathlib import Path

portfolio = pd.read_csv("portfolio.csv")
portfolio["Action"] = portfolio["Action"].astype(str).str.upper()

sells = portfolio[portfolio["Action"] == "SELL"].copy()

rows = []

for _, row in sells.iterrows():
    ticker = row["Ticker"]
    sell_price = float(row["Price"])
    reason = str(row.get("Reason", ""))

    try:
        data = yf.download(
            ticker,
            period="10d",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            current_price = sell_price
        else:
            if len(data.columns.names) > 1:
                data.columns = data.columns.droplevel(1)

            current_price = float(data["Close"].iloc[-1])

    except Exception:
        current_price = sell_price

    after_sell_perf = ((current_price - sell_price) / sell_price) * 100

    if after_sell_perf > 3:
        verdict = "SOLD_TOO_EARLY"
    elif after_sell_perf < -3:
        verdict = "GOOD_SELL"
    else:
        verdict = "ACCEPTABLE_SELL"

    rows.append({
        "Date": row["Date"],
        "Ticker": ticker,
        "Sell_Price": round(sell_price, 2),
        "Current_Price": round(current_price, 2),
        "After_Sell_Performance_%": round(after_sell_perf, 2),
        "Sell_Reason": reason,
        "Verdict": verdict,
    })

audit = pd.DataFrame(rows)
audit.to_csv("post_sell_audit_report.csv", index=False)

too_early = len(audit[audit["Verdict"] == "SOLD_TOO_EARLY"])
good_sell = len(audit[audit["Verdict"] == "GOOD_SELL"])
acceptable = len(audit[audit["Verdict"] == "ACCEPTABLE_SELL"])

summary = f"""
===== V13.1 POST-SELL AUDIT ENGINE =====

Sells Checked:
{len(audit)}

Sold Too Early:
{too_early}

Good Sells:
{good_sell}

Acceptable Sells:
{acceptable}

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("post_sell_audit_summary.txt").write_text(summary)

print(summary)
print(audit.to_string(index=False))
