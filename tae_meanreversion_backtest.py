"""
Mean-reversion signal backtest — exploring a genuinely different signal
family from the trend-following "Score" (SMA20>SMA50, breakout, RSI 45-70
band) that V1/V2/V3/exp_short_margin all currently share (see
tae_score_decile_backtest.py / tae_cross_arm_overlap_report.py for the
"one shared signal, four slices" finding this is a response to).

Mechanism: buy when price is an extreme distance BELOW its own recent
mean (z-score of price vs 20-day SMA <= -2.0) and RSI(14) is oversold
(<=30) -- the mechanical opposite of the existing breakout/momentum score.
Exit on reversion to the mean, a max holding period, or a stop-loss.

Analysis-only: no execution, no portfolio mutation, no new runtime arm.
Fetches 1y of daily OHLCV for the current live watchlist via a single
batched yf.download call (wrapped in the project's existing SIGALRM hard
timeout, since library-level timeouts don't reliably bound yfinance calls
-- see tae_network_hard_timeout.py).

Run: python3 tae_meanreversion_backtest.py
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import tae_mean_reversion_signal as mrsig
from tae_network_hard_timeout import hard_timeout

SMA_WINDOW = mrsig.SMA_WINDOW
FETCH_TIMEOUT_SECONDS = 180.0


def _load_watchlist() -> list[str]:
    path = Path("live_signals.csv")
    if not path.exists():
        return []
    with path.open() as f:
        rows = list(csv.DictReader(f))
    return sorted({r["Ticker"] for r in rows if r.get("Ticker")})


def _rsi_series(closes: pd.Series, window: int = mrsig.RSI_WINDOW) -> pd.Series:
    """Vectorized RSI over a whole series -- used ONLY by the momentum-
    score-proxy diagnostic below (needs a value at every historical day,
    not just the latest one). The actual traded signal never uses this;
    it calls tae_mean_reversion_signal.rsi() per-day, same as the live arm."""
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _momentum_score_proxy(closes: pd.Series, volume: pd.Series) -> pd.Series:
    """Reimplements the technical part of research/market_scanner.py's
    score formula (price>SMA20, SMA20>SMA50, RSI 45-70, vol>=avg_vol20,
    breakout20) for historical backtesting -- excludes the live news
    adjustment, which has no historical record. Used only to measure
    overlap with the mean-reversion signal's entry days, not to trade."""
    sma20 = closes.rolling(20).mean()
    sma50 = closes.rolling(50).mean()
    rsi = _rsi_series(closes)
    avg_vol20 = volume.rolling(20).mean()
    breakout20 = closes >= closes.rolling(20).max().shift(1)
    score = (
        (closes > sma20).astype(float) * 20
        + (sma20 > sma50).astype(float) * 25
        + ((rsi >= 45) & (rsi <= 70)).astype(float) * 20
        + (volume >= avg_vol20).astype(float) * 15
        + breakout20.astype(float) * 20
    )
    return score


def fetch_history(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    with hard_timeout(FETCH_TIMEOUT_SECONDS):
        data = yf.download(
            tickers, period="1y", interval="1d", group_by="ticker", auto_adjust=True, progress=False
        )
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = data[t].dropna(how="all")
        except (KeyError, TypeError):
            continue
        if df is None or df.empty or "Close" not in df or len(df) < SMA_WINDOW + 5:
            continue
        out[t] = df
    return out


def simulate_ticker(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Walks the series day by day calling the SAME entry_signal()/
    exit_signal() the live arm calls (tae_mean_reversion_signal), so the
    backtested rule and the traded rule can never drift apart."""
    closes_list = [float(c) for c in df["Close"]]
    volume = df["Volume"]
    momentum_score = _momentum_score_proxy(df["Close"], volume)

    trades: list[dict[str, Any]] = []
    in_position = False
    entry_price = 0.0
    entry_idx = -1
    entry_sma20 = 0.0
    entry_momentum_score = 0.0

    min_history = mrsig.SMA_WINDOW + mrsig.RSI_WINDOW
    for i in range(min_history, len(closes_list)):
        price = closes_list[i]
        history_so_far = closes_list[: i + 1]
        if not in_position:
            sig = mrsig.entry_signal(history_so_far)
            if sig.get("entry"):
                in_position = True
                entry_price = price
                entry_idx = i
                entry_sma20 = sig["sma20"]
                entry_momentum_score = float(momentum_score.iloc[i])
        else:
            days_held = i - entry_idx
            # sma20 is recomputed each day (mean-reversion target moves),
            # matching the live arm which recomputes it from fresh closes
            # every cycle rather than freezing it at entry.
            _, current_sma20 = mrsig.zscore_vs_sma(history_so_far)
            out = mrsig.exit_signal(
                current_price=price,
                sma20=current_sma20 if current_sma20 is not None else entry_sma20,
                entry_price=entry_price,
                days_held=days_held,
            )
            if out["exit"]:
                trades.append(
                    {
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "days_held": days_held,
                        "pnl_pct": out["pnl_pct"],
                        "exit_reason": out["reason"],
                        "entry_momentum_score": entry_momentum_score,
                    }
                )
                in_position = False
    return trades


def main() -> None:
    tickers = _load_watchlist()
    print(f"Fetching 1y daily history for {len(tickers)} tickers...")
    history = fetch_history(tickers)
    print(f"Got usable history for {len(history)}/{len(tickers)} tickers.")

    all_trades: list[dict[str, Any]] = []
    for ticker, df in history.items():
        for t in simulate_ticker(df):
            t["ticker"] = ticker
            all_trades.append(t)

    if not all_trades:
        print("No trades produced -- check data/thresholds.")
        return

    pnls = [t["pnl_pct"] for t in all_trades]
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(all_trades) * 100
    gross_win = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    avg_pnl = sum(pnls) / len(pnls)
    avg_days = sum(t["days_held"] for t in all_trades) / len(all_trades)

    print(f"\n=== Mean-reversion backtest: {len(all_trades)} trades across {len(history)} tickers, 1y ===")
    print(f"  win_rate={win_rate:.1f}%  profit_factor={pf:.2f}  avg_pnl_pct={avg_pnl:.2f}%  avg_days_held={avg_days:.1f}")

    from collections import Counter

    print(f"  exit reasons: {Counter(t['exit_reason'] for t in all_trades)}")

    # Diversification check: on days this signal enters, is the existing
    # trend-following momentum score already bullish (score>=60, today's
    # V1/V2 gate before the 2026-09-12 tightening -- use 60 as "would this
    # day also have looked buyable to the existing system")?
    entry_scores = [t["entry_momentum_score"] for t in all_trades]
    also_bullish = sum(1 for s in entry_scores if s >= 60)
    overlap_pct = also_bullish / len(entry_scores) * 100
    avg_entry_score = sum(entry_scores) / len(entry_scores)
    print(f"\n=== Overlap with existing momentum score ===")
    print(f"  avg momentum-score-proxy on mean-reversion entry days: {avg_entry_score:.1f}/100")
    print(f"  {overlap_pct:.1f}% of mean-reversion entries occur on days the existing score would ALSO call buyable (>=60)")
    print("  (low overlap = genuinely different entry days/regime -> real diversification;")
    print("   high overlap = same opportunities, not a second signal)")


if __name__ == "__main__":
    main()
