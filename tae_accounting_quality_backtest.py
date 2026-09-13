"""
Accounting-quality (Piotroski F-Score adaptation) backtest — does the
accounting-quality score correlate with realized PnL on the real V1/V2
closed-trade history?

Methodological caveat, same as Phase 4's tae_fundamental_quality_
backtest.py: this scores every historical trade against CURRENT
financial statements (yfinance's free endpoint has no historical
point-in-time statement archive), not what was actually filed as of the
trade date. Fundamentals move far more slowly than price, so this is an
acceptable first directional read, not a rigorous validation — stated
plainly, not hidden.

Run: python3 tae_accounting_quality_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import tae_accounting_quality_score as fscore
import tae_financial_statements_snapshot as fss
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

    print(f"Loading financial statements for {len(tickers)} tickers (cached)...")
    snapshot = fss.fetch_statements(tickers)
    fscores = {t: fscore.compute_f_score(snapshot.get(t) or {}) for t in tickers}
    unscored = [t for t in tickers if fscores[t]["score"] is None]
    print(f"Scored {len(tickers) - len(unscored)}/{len(tickers)} tickers (unscored: {unscored}).")

    scoreable_counts = [fscores[t]["scoreable"] for t in tickers if fscores[t]["score"] is not None]
    if scoreable_counts:
        print(f"Criteria scoreable per ticker: min={min(scoreable_counts)} "
              f"median={statistics.median(scoreable_counts):.0f} max={max(scoreable_counts)} (of 9)")

    enriched = [
        {**t, "f_score": fscores[t["ticker"]]["score"]}
        for t in combined
        if fscores.get(t["ticker"], {}).get("score") is not None
    ]
    print(f"\n{len(enriched)}/{len(combined)} trades matched with an accounting-quality score.")
    if not enriched:
        return

    qs = [t["f_score"] for t in enriched]
    pnls = [t["pnl"] for t in enriched]
    print(f"\nSpearman(f_score, pnl) = {_spearman(qs, pnls):.3f}")

    sorted_by_q = sorted(enriched, key=lambda t: t["f_score"])
    n = len(sorted_by_q)
    print("\n=== By accounting-quality (F-Score) tercile at entry ===")
    for i, label in enumerate(("LOW quality", "MED", "HIGH quality")):
        lo = i * n // 3
        hi = (i + 1) * n // 3 if i < 2 else n
        _bucket_report(f"{label}", sorted_by_q[lo:hi])

    print("\n=== Baseline ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
