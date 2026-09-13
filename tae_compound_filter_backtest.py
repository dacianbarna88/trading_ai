"""
Compound-filter backtest (Idea #2, 2026-09-13) — VIX regime and the
liquidity floor were each validated INDEPENDENTLY (tae_macro_regime_
backtest.py, tae_liquidity_backtest.py). This tests whether combining
them (LOW-VIX AND HIGH-liquidity simultaneously) compounds the effect
beyond either alone, on the same real V1/V2 closed-trade history.

Run: python3 tae_compound_filter_backtest.py
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import tae_liquidity_signal as liq
import tae_macro_regime as macro
import tae_macro_regime_backtest as macro_bt
import tae_liquidity_backtest as liq_bt
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


def main() -> None:
    v1_trades = scoredecile.collect_v1_closed_trades()
    v2_trades = scoredecile.collect_v2_closed_trades()
    combined = v1_trades + v2_trades
    tickers = sorted({t["ticker"] for t in combined})

    print("Fetching macro (VIX/SPY) history...")
    macro_hist = macro_bt.fetch_macro_history()
    print("Fetching per-ticker volume history...")
    vol_hist = liq_bt.fetch_volume_history(tickers)

    enriched = []
    for t in combined:
        entry_ts = t.get("entry_ts")
        if not entry_ts:
            continue
        entry_date = pd.Timestamp(entry_ts).tz_localize(None)

        regime = macro_bt._regime_as_of(macro_hist, entry_date)
        vix_tercile = regime["vix_tercile"]

        vol = vol_hist.get(t["ticker"])
        if vol is None:
            continue
        window = vol[vol.index <= entry_date]
        if len(window) < liq.AVG_VOLUME_WINDOW + 1:
            continue
        avg_vol = liq.average_volume([float(v) for v in window])
        if avg_vol is None:
            continue
        liquidity_bucket = "HIGH" if avg_vol >= liq.MIN_AVG_VOLUME else "LOW_OR_MED"

        enriched.append({**t, "vix_tercile": vix_tercile, "liquidity_bucket": liquidity_bucket})

    print(f"\n{len(enriched)}/{len(combined)} trades classified on both dimensions.")

    print("\n=== Individual filters (baseline for comparison) ===")
    _bucket_report("VIX=LOW (any liquidity)", [t for t in enriched if t["vix_tercile"] == "LOW"])
    _bucket_report("liquidity=HIGH (any VIX)", [t for t in enriched if t["liquidity_bucket"] == "HIGH"])

    print("\n=== Compound filter: VIX=LOW AND liquidity=HIGH together ===")
    both = [t for t in enriched if t["vix_tercile"] == "LOW" and t["liquidity_bucket"] == "HIGH"]
    _bucket_report("BOTH (compound)", both)

    print("\n=== For comparison: neither condition met ===")
    neither = [t for t in enriched if t["vix_tercile"] != "LOW" and t["liquidity_bucket"] != "HIGH"]
    _bucket_report("NEITHER", neither)

    print("\n=== One but not the other ===")
    vix_only = [t for t in enriched if t["vix_tercile"] == "LOW" and t["liquidity_bucket"] != "HIGH"]
    liq_only = [t for t in enriched if t["vix_tercile"] != "LOW" and t["liquidity_bucket"] == "HIGH"]
    _bucket_report("VIX=LOW only", vix_only)
    _bucket_report("liquidity=HIGH only", liq_only)

    print("\n=== Baseline (all trades) ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
