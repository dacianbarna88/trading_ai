import pandas as pd
from pathlib import Path

SOURCE = "watchlist_candidates.csv"
OUTPUT = "watchlist.txt"
SUMMARY = "universe_from_candidates_summary.txt"

if not Path(SOURCE).exists():
    print("watchlist_candidates.csv missing")
    raise SystemExit

df = pd.read_csv(SOURCE)

tickers = (
    df["Ticker"]
    .dropna()
    .astype(str)
    .str.strip()
    .drop_duplicates()
    .tolist()
)

Path(OUTPUT).write_text("\n".join(tickers) + "\n")

summary = f"""
===== V36.0 UNIVERSE FROM CANDIDATES =====

Source:
{SOURCE}

Tickers Written:
{len(tickers)}

Output:
{OUTPUT}

Mode:
UNIVERSE_EXPANSION
PAPER_ONLY
"""

Path(SUMMARY).write_text(summary)

print(summary)
