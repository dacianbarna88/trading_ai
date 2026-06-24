from pathlib import Path
import pandas as pd

portfolio_file = Path("portfolio.csv")

if not portfolio_file.exists():
    raise SystemExit("portfolio.csv not found")

df = pd.read_csv(portfolio_file)
df["Action"] = df["Action"].astype(str).str.upper()

for col in ["Price", "Shares", "Current_Price", "Highest_Price", "Trailing_Stop"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

alerts = []

for ticker in df["Ticker"].dropna().unique():
    rows = df[df["Ticker"] == ticker]
    buys = rows[rows["Action"] == "BUY"]
    sells = rows[rows["Action"] == "SELL"]

    if buys.empty:
        continue

    buy_shares = buys["Shares"].sum()
    sell_shares = sells["Shares"].sum() if not sells.empty else 0
    open_shares = buy_shares - sell_shares

    if open_shares <= 0:
        continue

    latest_buy = buys.iloc[-1]

    trailing_active = str(latest_buy.get("Trailing_Active", "")).lower() == "true"
    trailing_stop = latest_buy.get("Trailing_Stop")
    current_price = latest_buy.get("Current_Price")

    if trailing_active and pd.notna(trailing_stop) and pd.notna(current_price):
        if float(current_price) <= float(trailing_stop):
            alerts.append({
                "Ticker": ticker,
                "Current_Price": round(float(current_price), 2),
                "Trailing_Stop": round(float(trailing_stop), 2),
                "Status": "OVERNIGHT_GAP_TRAILING_BREACH",
                "Required_Action": "SELL_REQUIRED",
            })

alerts_df = pd.DataFrame(alerts)
alerts_df.to_csv("overnight_gap_risk_report.csv", index=False)

lines = [
    "===== V12.6 OVERNIGHT GAP RISK GUARD =====",
    "",
    f"Gap Breaches Detected: {len(alerts_df)}",
    "",
]

if alerts:
    lines.append("Breaches:")
    for a in alerts:
        lines.append(
            f"{a['Ticker']} | Current {a['Current_Price']} <= "
            f"Trailing Stop {a['Trailing_Stop']} | {a['Required_Action']}"
        )
else:
    lines.append("No overnight trailing gap breaches detected.")

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

summary = "\n".join(lines)

Path("overnight_gap_risk_summary.txt").write_text(summary)

print(summary)
