"""
Accounting-quality (F-Score) horizon backtest — the MAXIMUM version.

The trade-level backtest (tae_accounting_quality_backtest.py) tested
F-Score against our own system's actual trades, which are held ~7 days
on average — too short, plausibly, for a slow-moving fundamental signal
to show up. This decouples entirely from our own trade durations and
tests the raw thesis directly: over the longest price history yfinance
will give us (period="max") for each ticker, does a higher current
F-Score correspond to better trailing total return at increasing
horizons (30/60/90/180/365 days and the full available history)?

Still carries the same look-ahead caveat as every fundamentals backtest
this sprint: F-Score is computed from TODAY's statements only (no
historical point-in-time archive available for free), so this measures
"would today's quality companies have been the better performers over
their own trailing history" — a real, if imperfect, test of whether
quality has mattered for these specific names, not a walk-forward proof.

Run: python3 tae_accounting_quality_horizon_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import pandas as pd

import tae_accounting_quality_score as fscore
import tae_financial_statements_snapshot as fss
import tae_score_decile_backtest as scoredecile
from tae_network_hard_timeout import hard_timeout

FETCH_TIMEOUT_SECONDS = 180.0
HORIZONS_DAYS = [30, 60, 90, 180, 365, None]  # None = full available history ("max")


def fetch_max_history(tickers: list[str]) -> dict[str, pd.Series]:
    import yfinance as yf

    if not tickers:
        return {}
    with hard_timeout(FETCH_TIMEOUT_SECONDS):
        data = yf.download(
            tickers, period="max", interval="1d", group_by="ticker", auto_adjust=True, progress=False
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


def _bucket_report(label: str, rows: list[dict[str, Any]], ret_key: str) -> None:
    if not rows:
        print(f"    {label}: n=0")
        return
    rets = [r[ret_key] for r in rows]
    wins = sum(1 for r in rets if r > 0)
    wr = wins / len(rows) * 100
    avg = statistics.mean(rets)
    print(f"    {label}: n={len(rows):3d}  positive_rate={wr:5.1f}%  avg_return={avg:7.2f}%")


def main() -> None:
    v1_trades = scoredecile.collect_v1_closed_trades()
    v2_trades = scoredecile.collect_v2_closed_trades()
    v1v2_tickers = sorted({t["ticker"] for t in v1_trades + v2_trades})

    print(f"Loading cached F-Scores for {len(v1v2_tickers)} tickers...")
    snapshot = fss.fetch_statements(v1v2_tickers)
    fscores = {t: fscore.compute_f_score(snapshot.get(t) or {})["score"] for t in v1v2_tickers}
    scored_tickers = [t for t in v1v2_tickers if fscores[t] is not None]
    print(f"{len(scored_tickers)}/{len(v1v2_tickers)} tickers have a usable F-Score.")

    print(f"\nFetching MAXIMUM available price history for {len(scored_tickers)} tickers (period='max')...")
    history = fetch_max_history(scored_tickers)
    print(f"Got price history for {len(history)}/{len(scored_tickers)} tickers.")

    rows = []
    for t in scored_tickers:
        closes = history.get(t)
        if closes is None or len(closes) < 30:
            continue
        rows.append({"ticker": t, "f_score": fscores[t], "closes": closes})

    print(f"\n{len(rows)} tickers usable for the horizon test.")
    print(f"Trailing-history length available: min={min(len(r['closes']) for r in rows)} "
          f"max={max(len(r['closes']) for r in rows)} trading days "
          f"(median={statistics.median(len(r['closes']) for r in rows):.0f})")

    for horizon in HORIZONS_DAYS:
        label = f"{horizon}d" if horizon is not None else "FULL HISTORY (max)"
        print(f"\n=== Horizon: {label} ===")
        enriched = []
        for r in rows:
            closes = r["closes"]
            if horizon is None:
                start_price = float(closes.iloc[0])
            else:
                if len(closes) <= horizon:
                    continue
                start_price = float(closes.iloc[-1 - horizon])
            end_price = float(closes.iloc[-1])
            if start_price <= 0:
                continue
            ret_pct = (end_price - start_price) / start_price * 100
            enriched.append({"ticker": r["ticker"], "f_score": r["f_score"], "ret_pct": ret_pct})

        if len(enriched) < 6:
            print(f"    too few tickers with enough history ({len(enriched)}) -- skipping")
            continue

        qs = [e["f_score"] for e in enriched]
        rets = [e["ret_pct"] for e in enriched]
        print(f"  n={len(enriched)}  Spearman(f_score, return) = {_spearman(qs, rets):.3f}")

        sorted_by_q = sorted(enriched, key=lambda e: e["f_score"])
        n = len(sorted_by_q)
        for i, blabel in enumerate(("LOW quality", "MED", "HIGH quality")):
            lo = i * n // 3
            hi = (i + 1) * n // 3 if i < 2 else n
            _bucket_report(blabel, sorted_by_q[lo:hi], "ret_pct")


if __name__ == "__main__":
    main()
