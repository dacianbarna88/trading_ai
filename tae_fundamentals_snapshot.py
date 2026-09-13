"""Shared fundamentals/sector snapshot — Sprint 3 Phases 3 & 4.

yfinance's free `.info` endpoint returns real, populated values across
the whole watchlist (large-cap US *and* European names — SAP.DE, HSBA.L,
AIR.PA all verified live 2026-09-13) for sector/industry classification
(Phase 3) and valuation/quality fields (Phase 4) — no paid data
subscription needed for a real first version (see the Sprint 3 plan).

`.info` is NOT batchable like yf.download() — it's one HTTP round-trip
per ticker. For a ~100-ticker watchlist that's slow and rate-limit-prone
if repeated every cycle, so this module caches the whole snapshot to a
local JSON file with a 24h TTL (fundamentals don't move intraday — same
caching discipline as tae_shadow_entry_scorer's TTL cache). Every fetch
is fail-soft per ticker: a missing/broken field or a fully failed ticker
never blocks the rest of the snapshot.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

CACHE_PATH = Path("runtime_outputs/fundamentals_snapshot.json")
CACHE_TTL_SECONDS = 24 * 3600.0

FIELDS = [
    "sector",
    "industry",
    "trailingPE",
    "forwardPE",
    "pegRatio",
    "priceToBook",
    "returnOnEquity",
    "debtToEquity",
    "earningsGrowth",
    "revenueGrowth",
    "profitMargins",
    "marketCap",
    "averageVolume",
]

PER_TICKER_TIMEOUT_SECONDS = 15.0


def _fetch_one(ticker: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf

        from tae_network_hard_timeout import hard_timeout

        with hard_timeout(PER_TICKER_TIMEOUT_SECONDS):
            info = yf.Ticker(ticker).info
        if not isinstance(info, dict) or not info:
            return None
        return {f: info.get(f) for f in FIELDS}
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


def fetch_snapshot(
    tickers: list[str], *, force: bool = False, ttl_seconds: float = CACHE_TTL_SECONDS
) -> dict[str, dict[str, Any]]:
    """Returns {ticker: {field: value}} for every ticker with usable data.
    Missing tickers (fetch failure, delisted, empty .info) are simply
    absent from the result — callers must treat that as "unknown", never
    as an error or a reason to block a trade."""
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

    tickers = sys.argv[1:] or ["AAPL", "MSFT", "SAP.DE"]
    snap = fetch_snapshot(tickers)
    print(json.dumps(snap, indent=2, default=str))
