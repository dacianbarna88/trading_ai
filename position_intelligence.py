import pandas as pd
from pathlib import Path

df = pd.read_csv("portfolio.csv")
df["Action"] = df["Action"].astype(str).str.upper()

for col in ["Price", "Shares", "Current_Price", "PnL_%"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

rows_out = []

for ticker in df["Ticker"].dropna().unique():
    rows = df[df["Ticker"] == ticker]
    buys = rows[rows["Action"] == "BUY"]
    sells = rows[rows["Action"] == "SELL"]

    open_shares = buys["Shares"].sum() - sells["Shares"].sum()

    if open_shares <= 0:
        continue

    latest = buys.iloc[-1]
    pnl_pct = float(latest.get("PnL_%", 0))

    if pnl_pct <= -3:
        action = "EXIT_NOW"
        risk = "HIGH"
    elif pnl_pct <= -2:
        action = "WATCH_CLOSE"
        risk = "MEDIUM_HIGH"
    elif pnl_pct >= 4:
        action = "PROTECT_PROFIT"
        risk = "LOW"
    elif pnl_pct > 0:
        action = "HOLD"
        risk = "LOW"
    else:
        action = "WATCH"
        risk = "MEDIUM"

    rows_out.append({
        "Ticker": ticker,
        "Open_Shares": round(open_shares, 4),
        "Entry_Price": round(float(latest["Price"]), 2),
        "Current_Price": round(float(latest["Current_Price"]), 2),
        "PnL_%": round(pnl_pct, 2),
        "Risk_Level": risk,
        "Recommended_Action": action,
    })

out = pd.DataFrame(rows_out)
out.to_csv("position_intelligence_report.csv", index=False)

summary = ["===== V12.7 POSITION INTELLIGENCE =====", ""]

for _, r in out.iterrows():
    summary.append(
        f"{r['Ticker']} | PnL {r['PnL_%']}% | {r['Risk_Level']} | {r['Recommended_Action']}"
    )

summary.extend(["", "Status:", "PAPER_ONLY", "NO_BROKER", "NO_AUTO_EXECUTION"])

Path("position_intelligence_summary.txt").write_text("\n".join(summary))

print("\n".join(summary))
