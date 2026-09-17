"""
Earnings-surprise backtest — does the most recent, already-reported
quarterly EPS surprise (%) at entry correlate with realized PnL on the
real V1/V2 closed-trade history?

Context (2026-09-17): the roadmap's "paid faster-acting data source"
item assumed earnings-surprise/analyst-revision data required a paid
subscription (e.g. FMP, ~$59-149/mo). Checked live: yfinance's free
`Ticker(t).earnings_dates` already returns EPS estimate vs. actual vs.
Surprise(%) tied to real historical earnings-report dates, going back
several years — no paid data needed to TEST this. Analyst-revision
counts (`eps_revisions`/`eps_trend`) and price targets/recommendations
are present-moment snapshots with no historical time series, so — same
reasoning as `tae_news_sentiment_signal.py` — they cannot be backtested
this way; only earnings-surprise history (this module) can be, since
each row is a real, dated historical event.

Analysis-only, same pattern as tae_liquidity_backtest.py: reuses
tae_score_decile_backtest's real trade collectors, fetches earnings-date
history for the exact tickers involved, joins each trade to the most
recent ALREADY-REPORTED surprise strictly before its entry date (no
lookahead), buckets outcomes.

Run: python3 tae_earnings_surprise_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import pandas as pd

import tae_score_decile_backtest as scoredecile
from tae_network_hard_timeout import hard_timeout

FETCH_TIMEOUT_SECONDS = 30.0


def fetch_earnings_surprise_history(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """One yfinance.Ticker(t).earnings_dates call per ticker -- yfinance
    has no batched endpoint for this. Fine for a one-off analysis script;
    not a per-cycle hot path (see tae_slow_call_guard.py's whole reason
    for existing if this pattern were ever moved into one)."""
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            with hard_timeout(FETCH_TIMEOUT_SECONDS):
                df = yf.Ticker(t).earnings_dates
        except Exception:
            continue
        if df is None or df.empty:
            continue
        out[t] = df
    return out


def most_recent_surprise_before(df: pd.DataFrame, entry_date: pd.Timestamp) -> float | None:
    """Most recent already-reported EPS surprise (%) strictly before
    entry_date. No lookahead: only rows with a real "Reported EPS"
    (earnings already announced) and an earnings date before the trade's
    own entry are eligible."""
    if df is None or df.empty or "Reported EPS" not in df or "Surprise(%)" not in df:
        return None
    reported = df[df["Reported EPS"].notna()]
    if reported.empty:
        return None
    idx = reported.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
        reported = reported.set_axis(idx)
    entry_naive = entry_date.tz_localize(None) if entry_date.tzinfo is not None else entry_date
    prior = reported[reported.index < entry_naive]
    if prior.empty:
        return None
    latest = prior.sort_index().iloc[-1]
    val = latest.get("Surprise(%)")
    if val is None or val != val:  # NaN check without importing numpy/math here
        return None
    return float(val)


def _bucket_report(label: str, trades: list[dict[str, Any]]) -> None:
    if not trades:
        print(f"  {label}: n=0")
        return
    pnls = [t["pnl"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(trades) * 100
    total = sum(pnls)
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    print(f"  {label}: n={len(trades):3d}  win_rate={wr:5.1f}%  total_pnl=${total:8.2f}  PF={pf:.2f}")


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3:
        return 0.0
    rx, ry = _rank(xs), _rank(ys)
    mean_rx, mean_ry = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x**0.5 * var_y**0.5)


def enrich_with_prior_surprise(
    trades: list[dict[str, Any]], history: dict[str, pd.DataFrame]
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for t in trades:
        df = history.get(t["ticker"])
        entry_ts = t.get("entry_ts")
        if df is None or not entry_ts:
            continue
        surprise = most_recent_surprise_before(df, pd.Timestamp(entry_ts))
        if surprise is None:
            continue
        enriched.append({**t, "prior_surprise_pct": surprise})
    return enriched


def main() -> None:
    v1_trades = scoredecile.collect_v1_closed_trades()
    v2_trades = scoredecile.collect_v2_closed_trades()
    combined = v1_trades + v2_trades
    tickers = sorted({t["ticker"] for t in combined})
    print(f"Fetching earnings-surprise history for {len(tickers)} tickers involved in {len(combined)} trades...")
    history = fetch_earnings_surprise_history(tickers)
    print(f"Got earnings-surprise history for {len(history)}/{len(tickers)} tickers.")

    enriched = enrich_with_prior_surprise(combined, history)
    print(f"\n{len(enriched)}/{len(combined)} trades matched with a prior (no-lookahead) reported surprise.")
    if not enriched:
        return

    surprises = [t["prior_surprise_pct"] for t in enriched]
    pnls = [t["pnl"] for t in enriched]
    print(f"\nSpearman(prior_surprise_pct, pnl) = {_spearman(surprises, pnls):.3f}")

    print("\n=== By sign of prior surprise ===")
    _bucket_report("POSITIVE (beat)", [t for t in enriched if t["prior_surprise_pct"] > 0])
    _bucket_report("NEGATIVE (miss)", [t for t in enriched if t["prior_surprise_pct"] < 0])
    _bucket_report("FLAT (== 0)", [t for t in enriched if t["prior_surprise_pct"] == 0])

    sorted_by_surprise = sorted(enriched, key=lambda t: t["prior_surprise_pct"])
    n = len(sorted_by_surprise)
    print("\n=== By prior-surprise tercile ===")
    for i, label in enumerate(("LOW (biggest miss)", "MED", "HIGH (biggest beat)")):
        lo = i * n // 3
        hi = (i + 1) * n // 3 if i < 2 else n
        _bucket_report(f"{label}", sorted_by_surprise[lo:hi])

    print("\n=== Baseline ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
