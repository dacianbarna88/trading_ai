"""
Macro-regime backtest — does the existing technical score's win rate /
profit factor actually differ across VIX terciles or yield-curve sign, on
the REAL V1/V2 closed-trade history already collected by
tae_score_decile_backtest.py?

Analysis-only: no execution, no live wiring. If this shows a real split,
Phase 1 of Sprint 3 (see the plan) feeds real VIX/SPY-trend/curve values
into V3's existing RegimeGrid; if it's flat, that's said here plainly
before touching any live code.

Run: python3 tae_macro_regime_backtest.py
"""
from __future__ import annotations

import statistics
from typing import Any

import pandas as pd

import tae_macro_regime as macro
import tae_score_decile_backtest as scoredecile
from tae_network_hard_timeout import hard_timeout

FETCH_TIMEOUT_SECONDS = 60.0
MARKET_REGIME_SMA = 200


def fetch_macro_history() -> dict[str, pd.Series]:
    import yfinance as yf

    tickers = ["SPY", macro.VIX_TICKER, macro.TNX_TICKER, macro.IRX_TICKER]
    with hard_timeout(FETCH_TIMEOUT_SECONDS):
        data = yf.download(tickers, period="2y", interval="1d", group_by="ticker", auto_adjust=False, progress=False)
    out: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            closes = data[t]["Close"].dropna()
        except (KeyError, TypeError):
            continue
        if not closes.empty:
            out[t] = closes
    return out


def _regime_as_of(macro_hist: dict[str, pd.Series], entry_date: pd.Timestamp) -> dict[str, Any]:
    """No-lookahead: only uses data with timestamp <= entry_date."""
    result: dict[str, Any] = {"trend": "UNKNOWN", "vix_tercile": "UNKNOWN", "curve": "UNKNOWN"}
    spy = macro_hist.get("SPY")
    if spy is not None:
        window = spy[spy.index <= entry_date]
        if len(window) >= MARKET_REGIME_SMA:
            result["trend"] = macro.classify_trend(list(window.astype(float)), MARKET_REGIME_SMA)
    vix = macro_hist.get(macro.VIX_TICKER)
    if vix is not None:
        window = vix[vix.index <= entry_date]
        if len(window) >= 30:
            result["vix_tercile"] = macro.vix_tercile(list(window.astype(float)))
    tnx = macro_hist.get(macro.TNX_TICKER)
    irx = macro_hist.get(macro.IRX_TICKER)
    if tnx is not None and irx is not None:
        tnx_w = tnx[tnx.index <= entry_date]
        irx_w = irx[irx.index <= entry_date]
        if not tnx_w.empty and not irx_w.empty:
            slope = macro.yield_curve_slope(float(tnx_w.iloc[-1]), float(irx_w.iloc[-1]))
            result["curve"] = macro.curve_regime(slope)
            result["curve_slope"] = slope
    return result


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
    print("Fetching 2y of SPY/VIX/10y/13wk history...")
    macro_hist = fetch_macro_history()
    print(f"Got series for: {list(macro_hist.keys())}")

    v1_trades = scoredecile.collect_v1_closed_trades()
    v2_trades = scoredecile.collect_v2_closed_trades()
    combined = v1_trades + v2_trades
    print(f"\n{len(combined)} closed V1+V2 trades to classify by regime at entry.")

    by_trend: dict[str, list[dict[str, Any]]] = {}
    by_vix: dict[str, list[dict[str, Any]]] = {}
    by_curve: dict[str, list[dict[str, Any]]] = {}

    for t in combined:
        entry_ts = t.get("entry_ts")
        if not entry_ts:
            continue
        entry_date = pd.Timestamp(entry_ts).tz_localize(None)
        regime = _regime_as_of(macro_hist, entry_date)
        by_trend.setdefault(regime["trend"], []).append(t)
        by_vix.setdefault(regime["vix_tercile"], []).append(t)
        by_curve.setdefault(regime["curve"], []).append(t)

    print("\n=== By market trend (SPY vs SMA200) at entry ===")
    for k in ("BULL", "BEAR", "UNKNOWN"):
        _bucket_report(k, by_trend.get(k, []))

    print("\n=== By VIX tercile at entry ===")
    for k in ("LOW", "MED", "HIGH", "UNKNOWN"):
        _bucket_report(k, by_vix.get(k, []))

    print("\n=== By yield-curve regime at entry ===")
    for k in ("NORMAL", "INVERTED", "UNKNOWN"):
        _bucket_report(k, by_curve.get(k, []))

    print("\n=== Baseline (all trades, no regime split) ===")
    _bucket_report("ALL", combined)


if __name__ == "__main__":
    main()
