from pathlib import Path
import pandas as pd
import yfinance as yf

TICKERS = ["SPY", "QQQ", "HSBA.L", "ALV.DE"]
HORIZONS = {
    "2Y": "2y",
    "5Y": "5y",
    "10Y": "10y",
    "20Y": "20y",
}

def get_close(ticker, period):
    data = yf.download(ticker, period=period, auto_adjust=False, progress=False)

    if data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        close = data[("Close", ticker)].dropna()
    else:
        close = data["Close"].dropna()

    return close if not close.empty else None

rows = []

for ticker in TICKERS:
    for horizon_name, period in HORIZONS.items():
        try:
            close = get_close(ticker, period)

            if close is None or len(close) < 2:
                rows.append({
                    "Ticker": ticker,
                    "Horizon": horizon_name,
                    "Start_Price": None,
                    "End_Price": None,
                    "Return_%": None,
                    "Max_Drawdown_%": None,
                    "Volatility_%": None,
                    "Status": "NO_DATA",
                })
                continue

            start_price = float(close.iloc[0])
            end_price = float(close.iloc[-1])
            total_return = ((end_price - start_price) / start_price) * 100

            rolling_max = close.cummax()
            drawdown = (close - rolling_max) / rolling_max * 100
            max_drawdown = float(drawdown.min())

            daily_returns = close.pct_change().dropna()
            volatility = float(daily_returns.std() * (252 ** 0.5) * 100)

            rows.append({
                "Ticker": ticker,
                "Horizon": horizon_name,
                "Start_Price": round(start_price, 2),
                "End_Price": round(end_price, 2),
                "Return_%": round(total_return, 2),
                "Max_Drawdown_%": round(max_drawdown, 2),
                "Volatility_%": round(volatility, 2),
                "Status": "OK",
            })

        except Exception as e:
            rows.append({
                "Ticker": ticker,
                "Horizon": horizon_name,
                "Start_Price": None,
                "End_Price": None,
                "Return_%": None,
                "Max_Drawdown_%": None,
                "Volatility_%": None,
                "Status": f"ERROR: {e}",
            })

df = pd.DataFrame(rows)
df.to_csv("historical_intelligence.csv", index=False)

valid = df[df["Status"] == "OK"].copy()
valid["Return_%"] = pd.to_numeric(valid["Return_%"], errors="coerce")

best_by_horizon = []
for horizon in HORIZONS.keys():
    h = valid[valid["Horizon"] == horizon]
    if not h.empty:
        best = h.sort_values("Return_%", ascending=False).iloc[0]
        best_by_horizon.append(
            f"{horizon}: {best['Ticker']} | Return {best['Return_%']}% | Drawdown {best['Max_Drawdown_%']}% | Vol {best['Volatility_%']}%"
        )

lines = [
    "===== V10 HISTORICAL INTELLIGENCE ENGINE =====",
    "",
    "Tickers analyzed:",
    ", ".join(TICKERS),
    "",
    "Horizons:",
    ", ".join(HORIZONS.keys()),
    "",
    "Best By Horizon:",
]

lines.extend(best_by_horizon)

lines.extend([
    "",
    "Full Results:",
])

for _, r in df.iterrows():
    lines.append(
        f"{r['Ticker']} | {r['Horizon']} | "
        f"Return {r['Return_%']}% | "
        f"MaxDD {r['Max_Drawdown_%']}% | "
        f"Vol {r['Volatility_%']}% | "
        f"{r['Status']}"
    )

lines.extend([
    "",
    "Status:",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

summary = "\n".join(lines)
Path("historical_intelligence_summary.txt").write_text(summary)

print(summary)
