"""
Idea #3 (2026-09-13) — VIX/liquidity were validated and wired for ENTRY
only. This tests the EXIT side: among real V1/V2 closed trades, does the
regime AT EXIT (not entry) correlate with worse outcomes? If exiting
during HIGH-VIX or into illiquidity tends to produce worse realized PnL
than the trade's own unrealized state would suggest, that's evidence for
a tighter/faster exit rule under adverse regime -- not yet a wired rule,
just a test, same discipline as every other signal this sprint.

Run: python3 tae_exit_regime_backtest.py
"""
from __future__ import annotations

from typing import Any

import pandas as pd

import tae_liquidity_signal as liq
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
        exit_ts = t.get("exit_ts")
        if not exit_ts:
            continue
        exit_date = pd.Timestamp(exit_ts).tz_localize(None)

        regime = macro_bt._regime_as_of(macro_hist, exit_date)
        vix_tercile_at_exit = regime["vix_tercile"]

        vol = vol_hist.get(t["ticker"])
        liquidity_bucket = "UNKNOWN"
        if vol is not None:
            window = vol[vol.index <= exit_date]
            if len(window) >= liq.AVG_VOLUME_WINDOW + 1:
                avg_vol = liq.average_volume([float(v) for v in window])
                if avg_vol is not None:
                    liquidity_bucket = "HIGH" if avg_vol >= liq.MIN_AVG_VOLUME else "LOW_OR_MED"

        enriched.append({**t, "vix_at_exit": vix_tercile_at_exit, "liquidity_at_exit": liquidity_bucket})

    print(f"\n{len(enriched)}/{len(combined)} trades classified by exit-time regime.")

    print("\n=== By VIX tercile AT EXIT ===")
    for k in ("LOW", "MED", "HIGH", "UNKNOWN"):
        _bucket_report(k, [t for t in enriched if t["vix_at_exit"] == k])

    print("\n=== By liquidity bucket AT EXIT ===")
    for k in ("HIGH", "LOW_OR_MED", "UNKNOWN"):
        _bucket_report(k, [t for t in enriched if t["liquidity_at_exit"] == k])

    print("\n=== Baseline ===")
    _bucket_report("ALL", enriched)


if __name__ == "__main__":
    main()
