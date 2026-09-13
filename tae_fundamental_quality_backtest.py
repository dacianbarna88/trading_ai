"""
Fundamental quality backtest — does a cross-sectional composite quality
score (PEG, ROE, debt/equity, earnings/revenue growth, profit margins)
correlate with realized PnL on the real V1/V2 closed-trade history?

Methodological caveat, stated plainly rather than hidden: yfinance's
free `.info` only gives TODAY's fundamentals, not a historical time
series — every historical trade in this backtest is scored against
CURRENT fundamentals, not what they were on the actual trade date. This
is a real approximation (some lookahead risk), acceptable for a first
directional read since fundamentals move far more slowly than price, but
NOT something to claim as rigorous once real money/priority is on the
line — a paid historical-fundamentals feed would be needed to do this
properly.

Run: python3 tae_fundamental_quality_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import tae_fundamental_quality_score as fq
import tae_fundamentals_snapshot as fs
import tae_score_decile_backtest as scoredecile


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

    print(f"Loading fundamentals snapshot for {len(tickers)} tickers (cached)...")
    snapshot = fs.fetch_snapshot(tickers)
    quality = fq.compute_quality_scores(snapshot)
    unknown = [t for t in tickers if quality.get(t) is None]
    print(f"Scored {len(tickers) - len(unknown)}/{len(tickers)} tickers (unscored: {unknown}).")

    enriched = [
        {**t, "quality": quality[t["ticker"]]}
        for t in combined
        if quality.get(t["ticker"]) is not None
    ]
    print(f"\n{len(enriched)}/{len(combined)} trades matched with a quality score.")
    if not enriched:
        return

    qs = [t["quality"] for t in enriched]
    pnls = [t["pnl"] for t in enriched]
    print(f"\nSpearman(quality, pnl) = {_spearman(qs, pnls):.3f}")

    sorted_by_q = sorted(enriched, key=lambda t: t["quality"])
    n = len(sorted_by_q)
    print("\n=== By fundamental-quality tercile (current snapshot, see caveat) ===")
    for i, label in enumerate(("LOW quality", "MED", "HIGH quality")):
        lo = i * n // 3
        hi = (i + 1) * n // 3 if i < 2 else n
        _bucket_report(f"{label}", sorted_by_q[lo:hi])

    print("\n=== Baseline ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
