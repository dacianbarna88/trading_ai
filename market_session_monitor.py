from pathlib import Path
from datetime import datetime, time
import pandas as pd
import yfinance as yf

REGISTRY = "decision_registry.csv"
OUTPUT = "market_session_history.csv"
SUMMARY = "market_session_monitor_summary.txt"

SESSIONS = {
    "EU_SESSION": {
        "start": time(9, 0),
        "end": time(17, 30),
        "watchlists": ["watchlist_eu.txt", "watchlist_global.txt"],
    },
    "UK_SESSION": {
        "start": time(10, 0),
        "end": time(18, 30),
        "watchlists": ["watchlist_uk.txt", "watchlist_global.txt"],
    },
    "US_SESSION": {
        "start": time(16, 30),
        "end": time(23, 0),
        "watchlists": ["watchlist_us.txt", "watchlist_global.txt"],
    },
}

columns = [
    "Timestamp",
    "Date",
    "Session",
    "Ticker",
    "Decision",
    "Confidence_%",
    "Entry_Price",
    "Current_Price",
    "Return_%",
    "Outcome",
]

if not Path(REGISTRY).exists():
    print("decision_registry.csv missing")
    raise SystemExit

now = datetime.now()
today = now.date().isoformat()
current_time = now.time()

active_sessions = []

for session, cfg in SESSIONS.items():
    if cfg["start"] <= current_time <= cfg["end"]:
        active_sessions.append(session)

registry = pd.read_csv(REGISTRY)

active_registry = registry[
    registry["Outcome"].astype(str) == "PENDING"
]

if Path(OUTPUT).exists():
    history = pd.read_csv(OUTPUT)
else:
    history = pd.DataFrame(columns=columns)

added = 0
skipped = 0

summary = [
    "===== V34.0 MARKET SESSION MONITOR =====",
    "",
    f"Timestamp: {now}",
    "",
    f"Active Sessions: {', '.join(active_sessions) if active_sessions else 'NONE'}",
    f"Pending Decisions: {len(active_registry)}",
    "",
]

if not active_sessions:
    summary.append("No active market session right now.")
else:
    for session in active_sessions:

        for _, row in active_registry.iterrows():

            ticker = str(row.get("Ticker", "")).strip()
            decision = row.get("Decision", "")
            confidence = row.get("Confidence_%", 0)
            entry = float(row.get("Entry_Price", 0))
            outcome = row.get("Outcome", "PENDING")

            if not ticker or entry <= 0:
                skipped += 1
                continue

            duplicate = history[
                (history["Date"].astype(str) == today)
                &
                (history["Session"].astype(str) == session)
                &
                (history["Ticker"].astype(str) == ticker)
                &
                (
                    pd.to_datetime(history["Timestamp"])
                    .dt.strftime("%H:%M")
                    == now.strftime("%H:%M")
                )
            ]

            if len(duplicate) > 0:
                skipped += 1
                continue

            data = yf.download(
                ticker,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=True
            )

            if data.empty:
                summary.append(f"{session} | {ticker} | SKIPPED | No price data")
                skipped += 1
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

            history.loc[len(history)] = [
                now,
                today,
                session,
                ticker,
                decision,
                confidence,
                entry,
                current_price,
                return_pct,
                outcome,
            ]

            added += 1

            summary.append(
                f"{session} | {ticker} | Entry {entry} | "
                f"Current {current_price} | Return {return_pct}% | {outcome}"
            )

history.to_csv(OUTPUT, index=False)

summary.extend([
    "",
    f"Records Added: {added}",
    f"Records Skipped: {skipped}",
    f"Total Session Records: {len(history)}",
    "",
    "Rule:",
    "Monitor only active market sessions.",
    "Intended cadence: every 30 minutes.",
    "",
    "Mode:",
    "ANALYSIS_ONLY",
    "PAPER_ONLY",
    "NO_BROKER",
    "NO_AUTO_EXECUTION",
])

text = "\n".join(summary)

Path(SUMMARY).write_text(text)

print(text)
