#!/usr/bin/env python3
"""
Refresh latest_portfolio.txt from portfolio.csv open positions.

PAPER_ONLY | NO_BROKER | NO_EXECUTION — snapshot refresh only.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PORTFOLIO_PATH = ROOT / "portfolio.csv"
LATEST_PORTFOLIO_PATH = ROOT / "latest_portfolio.txt"
MIN_SHARES = 0.0001


def _safe_float(val: str | None, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _parse_dt(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime.min


def open_tickers(rows: list[dict[str, str]]) -> set[str]:
    net: dict[str, float] = {}
    for row in rows:
        ticker = row.get("Ticker", "").strip()
        action = row.get("Action", "").upper()
        shares = _safe_float(row.get("Shares"))
        if not ticker or ticker == "CASH":
            continue
        if action == "BUY":
            net[ticker] = net.get(ticker, 0.0) + shares
        elif action == "SELL":
            net[ticker] = net.get(ticker, 0.0) - shares
    return {t for t, s in net.items() if s > MIN_SHARES}


def latest_row_per_ticker(rows: list[dict[str, str]], tickers: set[str]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {t: [] for t in tickers}
    for row in rows:
        ticker = row.get("Ticker", "").strip()
        if ticker in grouped:
            grouped[ticker].append(row)
    out: list[dict[str, str]] = []
    for ticker in sorted(tickers):
        items = grouped[ticker]
        if not items:
            continue
        latest = max(items, key=lambda r: _parse_dt(r.get("Date", "")))
        out.append(latest)
    return out


def main() -> int:
    if not PORTFOLIO_PATH.is_file():
        print(f"ERROR: {PORTFOLIO_PATH} not found")
        return 1

    with PORTFOLIO_PATH.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    open_set = open_tickers(rows)
    snapshot_rows = latest_row_per_ticker(rows, open_set)

    optional_cols = ["Highest_Price", "Trailing_Active", "Trailing_Stop"]
    for col in optional_cols:
        if col not in fieldnames:
            fieldnames.append(col)

    with LATEST_PORTFOLIO_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in snapshot_rows:
            writer.writerow(row)

    print("===== REFRESH latest_portfolio.txt =====")
    print(f"Source: {PORTFOLIO_PATH}")
    print(f"Output: {LATEST_PORTFOLIO_PATH}")
    print(f"Open positions: {len(snapshot_rows)}")
    print(f"Tickers: {', '.join(sorted(open_set)) if open_set else '—'}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
