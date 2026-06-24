from pathlib import Path
import pandas as pd

STOP_LIMIT = -3.0
CRITICAL_LIMIT = -5.0

portfolio_file = Path("portfolio.csv")

if not portfolio_file.exists():
    raise SystemExit("portfolio.csv not found")

df = pd.read_csv(portfolio_file)
df["Action"] = df["Action"].astype(str).str.upper()
df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce")
df["Current_Price"] = pd.to_numeric(df["Current_Price"], errors="coerce")
df["PnL_%"] = pd.to_numeric(df["PnL_%"], errors="coerce")

open_rows = []

for ticker in df["Ticker"].dropna().unique():
    rows = df[df["Ticker"] == ticker]
    buy_shares = rows[rows["Action"] == "BUY"]["Shares"].sum()
    sell_shares = rows[rows["Action"] == "SELL"]["Shares"].sum()
    open_shares = buy_shares - sell_shares

    if open_shares > 0:
        last_buy = rows[rows["Action"] == "BUY"].iloc[-1]
        current_price = float(last_buy["Current_Price"])
        entry_price = float(last_buy["Price"])
        pnl_pct = round(((current_price - entry_price) / entry_price) * 100, 2)

        status = "OK"
        action = "HOLD"

        if pnl_pct <= CRITICAL_LIMIT:
            status = "CRITICAL_LOSS"
            action = "FORCE_SELL_REQUIRED"
        elif pnl_pct <= STOP_LIMIT:
            status = "STOP_LOSS_BREACHED"
            action = "SELL_REQUIRED"

        open_rows.append({
            "Ticker": ticker,
            "Entry_Price": entry_price,
            "Current_Price": current_price,
            "PnL_%": pnl_pct,
            "Status": status,
            "Required_Action": action,
        })

risk_df = pd.DataFrame(open_rows)
risk_df.to_csv("hard_risk_guardian_report.csv", index=False)

breaches = risk_df[risk_df["Status"] != "OK"] if not risk_df.empty else pd.DataFrame()

lines = [
    "===== V12.3 HARD RISK GUARDIAN =====",
    "",
    f"Open Positions Checked: {len(risk_df)}",
    f"Risk Breaches: {len(breaches)}",
    "",
]

if not breaches.empty:
    lines.append("Breaches:")
    for _, r in breaches.iterrows():
        lines.append(
            f"{r['Ticker']} | PnL {r['PnL_%']}% | {r['Status']} | {r['Required_Action']}"
        )
else:
    lines.append("No open position currently breaches hard risk limits.")

lines.extend([
    "",
    "Rules:",
    f"STOP_LIMIT: {STOP_LIMIT}%",
    f"CRITICAL_LIMIT: {CRITICAL_LIMIT}%",
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

summary = "\n".join(lines)
Path("hard_risk_guardian_summary.txt").write_text(summary)

print(summary)
print()
print(risk_df.to_string(index=False))
