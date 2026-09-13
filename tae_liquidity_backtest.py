"""
Liquidity backtest — does relative volume (today's volume vs. its own
trailing 20-day average) or absolute average volume at entry correlate
with realized PnL on the real V1/V2 closed-trade history?

Analysis-only, same pattern as tae_macro_regime_backtest.py: reuses
tae_score_decile_backtest's real trade collectors, fetches volume history
for the exact tickers/dates involved (no lookahead — only data up to and
including the entry date is used), buckets outcomes.

Run: python3 tae_liquidity_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import pandas as pd

import tae_liquidity_signal as liq
import tae_score_decile_backtest as scoredecile
from tae_network_hard_timeout import hard_timeout

FETCH_TIMEOUT_SECONDS = 120.0


def fetch_volume_history(tickers: list[str]) -> dict[str, pd.Series]:
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
            vol = data[t]["Volume"].dropna() if len(tickers) > 1 else data["Volume"].dropna()
        except (KeyError, TypeError):
            continue
        if not vol.empty:
            out[t] = vol
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
    print(f"Fetching 2y volume history for {len(tickers)} tickers involved in {len(combined)} trades...")
    vol_hist = fetch_volume_history(tickers)
    print(f"Got volume history for {len(vol_hist)}/{len(tickers)} tickers.")

    enriched: list[dict[str, Any]] = []
    for t in combined:
        vol = vol_hist.get(t["ticker"])
        entry_ts = t.get("entry_ts")
        if vol is None or not entry_ts:
            continue
        entry_date = pd.Timestamp(entry_ts).tz_localize(None)
        window = vol[vol.index <= entry_date]
        if len(window) < liq.AVG_VOLUME_WINDOW + 1:
            continue
        volumes = [float(v) for v in window]
        rel = liq.relative_volume(volumes)
        avg = liq.average_volume(volumes)
        if rel is None or avg is None:
            continue
        enriched.append({**t, "relative_volume": rel, "average_volume": avg})

    print(f"\n{len(enriched)}/{len(combined)} trades matched with usable volume history.")
    if not enriched:
        return

    rels = [t["relative_volume"] for t in enriched]
    pnls = [t["pnl"] for t in enriched]
    print(f"\nSpearman(relative_volume, pnl) = {_spearman(rels, pnls):.3f}")

    sorted_by_rel = sorted(enriched, key=lambda t: t["relative_volume"])
    n = len(sorted_by_rel)
    print("\n=== By relative-volume tercile at entry ===")
    for i, label in enumerate(("LOW (quiet)", "MED", "HIGH (active)")):
        lo = i * n // 3
        hi = (i + 1) * n // 3 if i < 2 else n
        _bucket_report(f"{label} rel_vol", sorted_by_rel[lo:hi])

    sorted_by_avg = sorted(enriched, key=lambda t: t["average_volume"])
    print("\n=== By absolute average-volume tercile at entry (liquidity floor check) ===")
    for i, label in enumerate(("LOW (illiquid)", "MED", "HIGH (liquid)")):
        lo = i * n // 3
        hi = (i + 1) * n // 3 if i < 2 else n
        _bucket_report(f"{label} avg_vol", sorted_by_avg[lo:hi])

    print("\n=== Baseline ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
