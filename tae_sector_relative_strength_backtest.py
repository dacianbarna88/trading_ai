"""
Sector relative-strength backtest — does a ticker's trailing return
relative to its own sector peers (from tae_fundamentals_snapshot's free
`sector` field) correlate with realized PnL on the real V1/V2 closed-
trade history?

Analysis-only, same pattern as tae_macro_regime_backtest.py /
tae_liquidity_backtest.py. Run: python3 tae_sector_relative_strength_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import pandas as pd

import tae_fundamentals_snapshot as fs
import tae_score_decile_backtest as scoredecile
import tae_sector_relative_strength as srs
from tae_network_hard_timeout import hard_timeout

FETCH_TIMEOUT_SECONDS = 120.0


def fetch_close_history(tickers: list[str]) -> dict[str, pd.Series]:
    import yfinance as yf

    if not tickers:
        return {}
    with hard_timeout(FETCH_TIMEOUT_SECONDS):
        data = yf.download(
            tickers, period="2y", interval="1d", group_by="ticker", auto_adjust=True, progress=False
        )
    out: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            closes = data[t]["Close"].dropna() if len(tickers) > 1 else data["Close"].dropna()
        except (KeyError, TypeError):
            continue
        if not closes.empty:
            out[t] = closes
    return out


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


def main() -> None:
    v1_trades = scoredecile.collect_v1_closed_trades()
    v2_trades = scoredecile.collect_v2_closed_trades()
    combined = v1_trades + v2_trades
    tickers = sorted({t["ticker"] for t in combined})

    print(f"Fetching fundamentals (sector) for {len(tickers)} tickers...")
    snapshot = fs.fetch_snapshot(tickers)
    sector_of = {t: (snapshot.get(t) or {}).get("sector") for t in tickers}
    unknown = [t for t in tickers if not sector_of.get(t)]
    print(f"Got sector for {len(tickers) - len(unknown)}/{len(tickers)} tickers (unknown: {unknown}).")

    print("Fetching 2y close history for the same tickers...")
    close_hist = fetch_close_history(tickers)
    print(f"Got price history for {len(close_hist)}/{len(tickers)} tickers.")

    sector_members: dict[str, list[str]] = {}
    for t, sec in sector_of.items():
        if sec:
            sector_members.setdefault(sec, []).append(t)

    enriched: list[dict[str, Any]] = []
    for t in combined:
        ticker = t["ticker"]
        sec = sector_of.get(ticker)
        entry_ts = t.get("entry_ts")
        closes_series = close_hist.get(ticker)
        if not sec or not entry_ts or closes_series is None:
            continue
        entry_date = pd.Timestamp(entry_ts).tz_localize(None)
        window = closes_series[closes_series.index <= entry_date]
        ticker_ret = srs.trailing_return_pct([float(c) for c in window])
        if ticker_ret is None:
            continue
        peer_returns = []
        for peer in sector_members.get(sec, []):
            if peer == ticker:
                continue
            peer_series = close_hist.get(peer)
            if peer_series is None:
                continue
            peer_window = peer_series[peer_series.index <= entry_date]
            peer_returns.append(srs.trailing_return_pct([float(c) for c in peer_window]))
        rel = srs.relative_strength(ticker_ret, peer_returns)
        if rel is None:
            continue
        enriched.append({**t, "sector": sec, "ticker_return": ticker_ret, "relative_strength": rel})

    print(f"\n{len(enriched)}/{len(combined)} trades matched with usable sector+return data.")
    if not enriched:
        return

    rels = [t["relative_strength"] for t in enriched]
    pnls = [t["pnl"] for t in enriched]
    print(f"\nSpearman(relative_strength, pnl) = {_spearman(rels, pnls):.3f}")

    sorted_by_rel = sorted(enriched, key=lambda t: t["relative_strength"])
    n = len(sorted_by_rel)
    print("\n=== By sector relative-strength tercile at entry ===")
    for i, label in enumerate(("LOW (lagging sector)", "MED", "HIGH (leading sector)")):
        lo = i * n // 3
        hi = (i + 1) * n // 3 if i < 2 else n
        _bucket_report(f"{label}", sorted_by_rel[lo:hi])

    print("\n=== Baseline ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
