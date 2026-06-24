import pandas as pd
import yfinance as yf
from pathlib import Path

signals_file = "live_signals.csv"
portfolio_file = "portfolio.csv"
watchlist_file = "watchlist.txt"

signals = pd.read_csv(signals_file)
portfolio = pd.read_csv(portfolio_file)

watchlist = []
if Path(watchlist_file).exists():
    watchlist = [
        x.strip().upper()
        for x in Path(watchlist_file).read_text().splitlines()
        if x.strip()
    ]

portfolio["Action"] = portfolio["Action"].astype(str).str.upper()

open_positions = []

for ticker in portfolio["Ticker"].dropna().unique():
    rows = portfolio[portfolio["Ticker"] == ticker]
    buys = rows[rows["Action"] == "BUY"]["Shares"].sum()
    sells = rows[rows["Action"] == "SELL"]["Shares"].sum()

    if buys - sells > 0:
        open_positions.append(ticker)

rows_out = []

for _, row in signals.iterrows():
    ticker = str(row["Ticker"]).upper()
    current_price = float(row["Price"])
    score = float(row["Score"])
    signal = str(row["Signal"])

    try:
        data = yf.download(
            ticker,
            period="2d",
            auto_adjust=False,
            progress=False,
        )

        if data.empty or len(data) < 2:
            daily_change = 0
        else:
            if len(data.columns.names) > 1:
                data.columns = data.columns.droplevel(1)

            prev_close = float(data["Close"].iloc[-2])
            last_close = float(data["Close"].iloc[-1])
            daily_change = ((last_close - prev_close) / prev_close) * 100

    except Exception:
        daily_change = 0

    in_portfolio = ticker in open_positions
    in_watchlist = ticker in watchlist

    if in_portfolio:
        missed_reason = "ALREADY_IN_PORTFOLIO"
        verdict = "CAPTURED"
    elif signal != "STRONG BUY":
        missed_reason = "NOT_STRONG_BUY"
        verdict = "NOT_ELIGIBLE"
    elif score < 90:
        missed_reason = "SCORE_BELOW_BUY_THRESHOLD"
        verdict = "MISSED_BY_SCORE"
    else:
        missed_reason = "ELIGIBLE_NOT_HELD"
        verdict = "POTENTIAL_MISSED_WINNER"

    rows_out.append({
        "Ticker": ticker,
        "Daily_Change_%": round(daily_change, 2),
        "Price": round(current_price, 2),
        "Score": score,
        "Signal": signal,
        "In_Watchlist": in_watchlist,
        "In_Open_Portfolio": in_portfolio,
        "Missed_Reason": missed_reason,
        "Verdict": verdict,
    })

audit = pd.DataFrame(rows_out)
audit = audit.sort_values("Daily_Change_%", ascending=False)

audit.to_csv("missed_winners_audit_report.csv", index=False)

top = audit.head(10)

captured = len(audit[audit["Verdict"] == "CAPTURED"])
potential = len(audit[audit["Verdict"] == "POTENTIAL_MISSED_WINNER"])
missed_score = len(audit[audit["Verdict"] == "MISSED_BY_SCORE"])

lines = [
    "===== V13.2 MISSED WINNERS AUDIT ENGINE =====",
    "",
    f"Signals Checked: {len(audit)}",
    f"Captured Winners: {captured}",
    f"Potential Missed Winners: {potential}",
    f"Missed By Score: {missed_score}",
    "",
    "Top Daily Movers:",
]

for _, r in top.iterrows():
    lines.append(
        f"{r['Ticker']} | {r['Daily_Change_%']}% | Score {r['Score']} | {r['Signal']} | {r['Verdict']}"
    )

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

Path("missed_winners_audit_summary.txt").write_text("\n".join(lines))

print("\n".join(lines))
