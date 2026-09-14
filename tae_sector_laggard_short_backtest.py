"""
Sector-laggard short backtest — roadmap item 6, second candidate
(2026-09-14): does a stock that's badly underperformed its own sector
peers (tae_sector_relative_strength.py, rejected in Sprint 3 as a LONG
entry signal, Spearman 0.001) make a good SHORT candidate instead? The
logic isn't automatically the same in both directions — "who's leading
the sector" failing to predict long entries doesn't mean "who's lagging
badly" fails to predict continued underperformance for a short.

Tests it directly: for every historical point where a ticker's trailing
20-day return underperforms its sector peers' average by >= 15
percentage points ("laggard"), what's its forward 10-day return? If
consistently negative, that supports shorting laggards (continuation).
If flat or positive, laggards tend to REBOUND, which argues against it
(and is what SHORTING oversold reversion already covers from the other
side, tae_meanreversion_signal.py's LONG entry).

Run: python3 tae_sector_laggard_short_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import tae_fundamentals_snapshot as fs
import tae_meanreversion_backtest as mrbt
import tae_sector_relative_strength as srs

HOLD_DAYS = 10
LAGGARD_THRESHOLD_PCT = -15.0
MIN_HISTORY_DAYS = 40


def collect_laggard_forward_returns(
    history: dict[str, Any], sector_of: dict[str, str], *,
    laggard_threshold: float = LAGGARD_THRESHOLD_PCT, hold_days: int = HOLD_DAYS,
) -> list[float]:
    """Pure-ish function over already-fetched data: returns the list of
    forward `hold_days`-day % returns for every (ticker, day) where the
    ticker was a sector laggard by at least `laggard_threshold` points."""
    sector_members: dict[str, list[str]] = {}
    for t, sec in sector_of.items():
        if sec:
            sector_members.setdefault(sec, []).append(t)

    closes_by_ticker = {t: [float(c) for c in df["Close"]] for t, df in history.items()}
    results: list[float] = []
    for t, closes in closes_by_ticker.items():
        sec = sector_of.get(t)
        peers = [p for p in sector_members.get(sec, []) if p != t and p in closes_by_ticker]
        n = len(closes)
        for i in range(MIN_HISTORY_DAYS, n - hold_days):
            ret_t = srs.trailing_return_pct(closes[: i + 1])
            if ret_t is None:
                continue
            peer_rets = [
                srs.trailing_return_pct(closes_by_ticker[p][: i + 1])
                for p in peers
                if len(closes_by_ticker[p]) > i
            ]
            rel = srs.relative_strength(ret_t, [r for r in peer_rets if r is not None])
            if rel is None or rel > laggard_threshold:
                continue
            fwd_ret = (closes[i + hold_days] - closes[i]) / closes[i] * 100
            results.append(fwd_ret)
    return results


def main() -> None:
    tickers = mrbt._load_watchlist()
    print(f"Fetching sector labels for {len(tickers)} tickers...")
    snapshot = fs.fetch_snapshot(tickers)
    sector_of = {t: (snapshot.get(t) or {}).get("sector") for t in tickers if (snapshot.get(t) or {}).get("sector")}
    print(f"{len(sector_of)}/{len(tickers)} tickers have a sector label.")

    print("Fetching 1y price history...")
    history = mrbt.fetch_history(list(sector_of.keys()))
    print(f"Got history for {len(history)} tickers.")

    results = collect_laggard_forward_returns(history, sector_of)
    print(f"\n{len(results)} sector-laggard entry points found (threshold <= {LAGGARD_THRESHOLD_PCT}pp vs sector peers).")
    if not results:
        return
    fell_further = sum(1 for r in results if r < 0)
    print(f"  % where price fell further over the next {HOLD_DAYS} days (good for a short): {fell_further/len(results)*100:.1f}%")
    print(f"  avg forward {HOLD_DAYS}-day return: {statistics.mean(results):.2f}%")
    if statistics.mean(results) > 0:
        print("  Laggards tend to REBOUND, not continue falling -- this argues AGAINST shorting them.")


if __name__ == "__main__":
    main()
