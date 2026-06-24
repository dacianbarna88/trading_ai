import pandas as pd
from pathlib import Path

from core.portfolio import get_open_positions, get_cash_available
from core.market_sessions import get_ticker_region
from core.market_regime import get_max_positions
from live_bot import get_market_regime

OUTPUT = Path("slot_pressure_summary.txt")

df = pd.read_csv("portfolio.csv")
positions = get_open_positions(df.copy())

regime = get_market_regime()
max_positions = get_max_positions(regime)
free_slots = max(max_positions - len(positions), 0)
cash = get_cash_available(df.copy())

rows = []

for ticker, pos in positions.items():
    buys = df[
        (df["Ticker"] == ticker)
        & (df["Action"].astype(str).str.upper() == "BUY")
    ].copy()

    if buys.empty:
        continue

    last = buys.tail(1).iloc[0]

    current = pd.to_numeric(last.get("Current_Price"), errors="coerce")
    avg = float(pos["avg_price"])
    shares = float(pos["shares"])

    current_value = current * shares if pd.notna(current) else None
    pnl_pct = ((current - avg) / avg) * 100 if pd.notna(current) and avg else None

    if pnl_pct is None:
        pressure = 100
        action = "NO_PRICE_REVIEW"
    elif pnl_pct < 0:
        pressure = 90
        action = "WEAK_SLOT"
    elif pnl_pct < 0.25:
        pressure = 70
        action = "LOW_EDGE_SLOT"
    elif pnl_pct < 0.75:
        pressure = 50
        action = "WATCH_SLOT"
    else:
        pressure = 20
        action = "HEALTHY_SLOT"

    rows.append({
        "Ticker": ticker,
        "Region": get_ticker_region(ticker),
        "Current_Value": round(float(current_value), 2) if current_value is not None else None,
        "PnL_%": round(pnl_pct, 2) if pnl_pct is not None else None,
        "Pressure": pressure,
        "Action": action,
    })

out = pd.DataFrame(rows)

if out.empty:
    summary = "===== SLOT PRESSURE MONITOR =====\n\nNo open positions.\n"
else:
    out = out.sort_values(["Pressure", "PnL_%"], ascending=[False, True])

    summary = f"""
===== SLOT PRESSURE MONITOR =====

Market Regime: {regime}
Max Positions: {max_positions}
Open Positions: {len(positions)}
Free Slots: {free_slots}
Cash Available: ${cash:.2f}

Slot Pressure Active: {"YES" if free_slots == 0 else "NO"}

Top Slot Review Candidates:
{out.head(5).to_string(index=False)}

Summary:
{out["Action"].value_counts().to_string()}

Mode:
ANALYSIS_ONLY
NO_AUTO_SELL
NO_BROKER
"""

OUTPUT.write_text(summary, encoding="utf-8")

print(summary)
