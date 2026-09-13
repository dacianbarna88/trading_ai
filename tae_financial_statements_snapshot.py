"""Shared multi-quarter financial-statement snapshot — Sprint 3 Phase 5.

Unlike tae_fundamentals_snapshot.py (one point-in-time ratio snapshot per
ticker via `.info`), this fetches real statement history — 5-7 quarters
of `Ticker.quarterly_financials` (income statement), `.quarterly_balance_
sheet`, `.quarterly_cashflow` — so accounting-quality checks
(tae_accounting_quality_score.py) can compare period-over-period, the way
an actual analyst reads filings, not just today's ratios.

Known data gap (verified 2026-09-13): financial-sector tickers (banks,
insurers) report differently — HSBA.L has no cash-flow statement via this
endpoint at all, and bank tickers generally lack "Gross Profit" (no COGS
concept). Every consumer of this snapshot must treat a missing row/period
as "unknown", never as zero or a bad score.

3 calls per ticker (heavier than the 1-call `.info` snapshot), so this
caches with a 7-day TTL, not 24h — quarterly statements barely change
day to day. Fail-soft per ticker: one ticker's fetch failure never blocks
the rest of the snapshot.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

CACHE_PATH = Path("runtime_outputs/financial_statements_snapshot.json")
CACHE_TTL_SECONDS = 7 * 24 * 3600.0
PER_TICKER_TIMEOUT_SECONDS = 20.0

STATEMENTS = ("income", "balance_sheet", "cashflow")


def _serialize_df(df: Any) -> dict[str, dict[str, float | None]]:
    """DataFrame (rows=line items, columns=period Timestamps) -> plain
    nested dict {row_name: {period_iso: value_or_None}} for JSON caching."""
    if df is None or df.empty:
        return {}
    out: dict[str, dict[str, float | None]] = {}
    for row_name in df.index:
        row: dict[str, float | None] = {}
        for col in df.columns:
            val = df.loc[row_name, col]
            try:
                row[str(col.date())] = None if val is None else float(val)
            except (TypeError, ValueError):
                row[str(col.date())] = None
        out[str(row_name)] = row
    return out


def _fetch_one(ticker: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf

        from tae_network_hard_timeout import hard_timeout

        with hard_timeout(PER_TICKER_TIMEOUT_SECONDS):
            t = yf.Ticker(ticker)
            income = t.quarterly_financials
            balance_sheet = t.quarterly_balance_sheet
            cashflow = t.quarterly_cashflow
        result = {
            "income": _serialize_df(income),
            "balance_sheet": _serialize_df(balance_sheet),
            "cashflow": _serialize_df(cashflow),
        }
        if not any(result.values()):
            return None
        return result
    except Exception:
        return None


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        return {"fetched_at": 0.0, "data": {}}
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "data" in raw:
            return raw
    except (OSError, json.JSONDecodeError):
        pass
    return {"fetched_at": 0.0, "data": {}}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=2, default=str), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def fetch_statements(
    tickers: list[str], *, force: bool = False, ttl_seconds: float = CACHE_TTL_SECONDS
) -> dict[str, dict[str, Any]]:
    """Returns {ticker: {"income": {...}, "balance_sheet": {...},
    "cashflow": {...}}} for every ticker with usable data. A missing
    ticker (fetch failure, no data at all) is simply absent — callers
    must treat that as unknown, never as a bad score."""
    cache = _load_cache()
    age = time.time() - float(cache.get("fetched_at") or 0.0)
    data: dict[str, Any] = dict(cache.get("data") or {})

    missing = [t for t in tickers if force or age >= ttl_seconds or t not in data]
    if missing:
        for t in missing:
            row = _fetch_one(t)
            if row is not None:
                data[t] = row
        cache = {"fetched_at": time.time(), "data": data}
        _save_cache(cache)

    return {t: data[t] for t in tickers if t in data}


if __name__ == "__main__":
    import sys

    tickers = sys.argv[1:] or ["AAPL", "MU"]
    snap = fetch_statements(tickers)
    print(json.dumps(snap, indent=2, default=str))
