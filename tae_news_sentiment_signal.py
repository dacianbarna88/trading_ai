"""Shadow news-sentiment signal — item 1 of the post-Sprint-3 roadmap
(2026-09-14): the first genuinely independent (non-price-derived) signal
in this system.

Reuses the proven, already-working pieces of `research/news_intelligence.
py` (confirmed live 2026-09-14: `yf.Ticker(t).news` needs no API key and
returned real headlines) — the free news pull and its keyword-based
sentiment score — but does NOT resurrect that script's file-handoff
design (`news_intelligence.csv` -> `news_sentiment_summary.csv` ->
`market_scanner.py`'s `get_news_adjustment()`), because that consumer
chain isn't in the live V1/V2/V3 path anyway, and the aggregation step it
needs was never actually implemented (confirmed: no code in this repo
writes the wide-format summary file its own consumers expect).

**Why this is shadow/log-only, not backtested-then-wired like VIX/
liquidity**: `yfinance.news` only returns *current* headlines — there is
no historical news archive to backtest "what would sentiment have said
on 2026-07-23." This can only be validated prospectively: log it now,
correlate with real outcomes as they happen over the coming weeks, then
decide on promotion — same "prove it before it controls money" discipline
as `tae_shadow_entry_scorer.py`.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

POSITIVE_WORDS = [
    "beat", "beats", "growth", "upgrade", "strong", "record", "surge",
    "rally", "profit", "optimistic", "raises", "outperform", "buy",
]

NEGATIVE_WORDS = [
    "miss", "misses", "downgrade", "weak", "loss", "falls", "drop",
    "lawsuit", "probe", "warning", "cuts", "underperform", "sell",
]

NEWS_FETCH_TIMEOUT_SECONDS = 15.0
DEFAULT_HEADLINE_LIMIT = 5

# Disk-backed cache (2026-09-14): each hourly cycle is a fresh `python3
# tae.py parallel-paper-run-once` process, so an in-memory cache buys
# nothing across cycles -- same JSON-snapshot-with-TTL pattern already
# used by tae_fundamentals_snapshot.py/tae_financial_statements_snapshot.
# py. Headlines don't need re-fetching every hourly cycle for a
# shadow/log-only signal, and up to ~90 un-batchable per-ticker network
# calls every cycle is exactly the "serial network call" slowdown already
# found and fixed elsewhere this project.
CACHE_PATH = Path("runtime_outputs/news_sentiment_shadow_cache.json")
NEWS_CACHE_TTL_SECONDS = 3 * 3600.0


def score_text(text: str) -> int:
    """+1 per positive-word hit, -1 per negative-word hit, substring
    match on the lowercased text (same rule as research/news_intelligence.
    py's score_text, reused verbatim for continuity)."""
    lowered = str(text).lower()
    positive = sum(1 for word in POSITIVE_WORDS if word in lowered)
    negative = sum(1 for word in NEGATIVE_WORDS if word in lowered)
    return positive - negative


def score_headlines(headlines: list[str]) -> dict[str, Any]:
    """Pure aggregation, no network — the part unit-tested directly.
    Empty input reads as "no news today" (neutral, news_count=0), not an
    error."""
    if not headlines:
        return {
            "news_count": 0,
            "sentiment_avg": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "bias": "NEUTRAL",
        }
    scores = [score_text(h) for h in headlines]
    positive_count = sum(1 for s in scores if s > 0)
    negative_count = sum(1 for s in scores if s < 0)
    neutral_count = sum(1 for s in scores if s == 0)
    sentiment_avg = sum(scores) / len(scores)
    if sentiment_avg > 0:
        bias = "POSITIVE"
    elif sentiment_avg < 0:
        bias = "NEGATIVE"
    else:
        bias = "NEUTRAL"
    return {
        "news_count": len(headlines),
        "sentiment_avg": round(sentiment_avg, 4),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "bias": bias,
    }


def _normalize_headline(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    content = item.get("content") or {}
    title = item.get("title") or content.get("title") or ""
    return str(title).strip()


def fetch_ticker_news(ticker: str, *, limit: int = DEFAULT_HEADLINE_LIMIT) -> list[str]:
    """Trailing headlines for one ticker, most-recent-first (whatever
    order yfinance returns), fail-soft: any fetch problem returns []
    (reads as "no news"), never raises into a caller's real decision
    path."""
    try:
        import yfinance as yf

        from tae_network_hard_timeout import hard_timeout

        with hard_timeout(NEWS_FETCH_TIMEOUT_SECONDS):
            raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    headlines: list[str] = []
    for item in raw:
        title = _normalize_headline(item)
        if title:
            headlines.append(title)
        if len(headlines) >= limit:
            break
    return headlines


def shadow_news_sentiment(ticker: str, *, limit: int = DEFAULT_HEADLINE_LIMIT) -> dict[str, Any] | None:
    """Fetch + score for ONE ticker, uncached — direct fetch, for tests
    and one-off use. Never raises — shadow-only. Real per-cycle callers
    should use fetch_shadow_news_batch() instead (cached, one disk round
    trip for the whole watchlist rather than N)."""
    try:
        headlines = fetch_ticker_news(ticker, limit=limit)
        result = score_headlines(headlines)
        result["fetched_at"] = datetime.now().isoformat()
        return result
    except Exception as exc:  # pragma: no cover - defensive, shadow-only
        return {"error": str(exc)}


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


def fetch_shadow_news_batch(
    tickers: list[str], *, limit: int = DEFAULT_HEADLINE_LIMIT, ttl_seconds: float = NEWS_CACHE_TTL_SECONDS
) -> dict[str, dict[str, Any]]:
    """One-per-cycle entry point: returns {ticker: shadow_result} for
    every ticker, using a disk cache so a ticker already fetched within
    `ttl_seconds` (default 3h) is never re-fetched. Each ticker not yet
    cached (or expired) gets ONE fetch_ticker_news() call — still N
    network calls the first time a ticker is seen, but not every single
    hourly cycle thereafter."""
    cache = _load_cache()
    data: dict[str, Any] = dict(cache.get("data") or {})
    now = time.time()

    out: dict[str, dict[str, Any]] = {}
    changed = False
    for t in tickers:
        t_u = str(t).upper()
        entry = data.get(t_u)
        if entry is not None and (now - float(entry.get("_cached_at") or 0.0)) < ttl_seconds:
            out[t_u] = entry
            continue
        result = shadow_news_sentiment(t_u, limit=limit)
        result = dict(result or {})
        result["_cached_at"] = now
        data[t_u] = result
        out[t_u] = result
        changed = True

    if changed:
        _save_cache({"fetched_at": now, "data": data})
    return out
