"""
Overbought-reversion backtest — roadmap item 6 (2026-09-14): does a
statistical "overbought" signal (the mirror image of the mean-reversion
arm's oversold entry, tae_mean_reversion_signal.py) predict a real,
tradeable DOWN move? exp_short_margin's current entry (`score <= 20`,
the bearish end of the SAME shared long score) is self-admittedly crude
and was paused Sprint 2 (PF 0.08). This tests a real, independently-
backtestable bearish thesis before considering un-pausing the arm with
a better signal.

Mechanism (exact mirror of tae_mean_reversion_signal.py's LONG entry,
z<=-2 and RSI<=30): short when z>=+2 (price statistically far ABOVE its
own 20-day mean) AND RSI>=70 (overbought) -- betting on reversion DOWN,
not momentum continuation up. Same exit family: cover on reversion to
the mean, a flat stop-loss (price keeps rising against the short), or a
max holding period.

Uses the SAME 2y real price history and simulation shape as
tae_meanreversion_backtest.py, just testing the mirrored side.

Run: python3 tae_overbought_reversion_backtest.py
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import tae_mean_reversion_signal as mrsig
import tae_meanreversion_backtest as mrbt
from tae_network_hard_timeout import hard_timeout

Z_SHORT_THRESHOLD = 2.0
RSI_OVERBOUGHT = 70.0
MAX_HOLD_DAYS = mrsig.MAX_HOLD_DAYS
STOP_LOSS_PCT = mrsig.STOP_LOSS_PCT  # symmetric magnitude, applied against the short direction


def short_entry_signal(closes: list[float]) -> dict[str, Any]:
    """Mirror of mrsig.entry_signal — same insufficient-history/degenerate
    handling, opposite direction (overbought, not oversold)."""
    if not closes or len(closes) < mrsig.SMA_WINDOW + mrsig.RSI_WINDOW:
        return {"entry": False, "reason": "INSUFFICIENT_HISTORY"}
    z, sma = mrsig.zscore_vs_sma(closes)
    r = mrsig.rsi(closes)
    if z is None or r is None:
        return {"entry": False, "reason": "INSUFFICIENT_HISTORY", "z": z, "rsi": r, "sma20": sma}
    entry = z >= Z_SHORT_THRESHOLD and r >= RSI_OVERBOUGHT
    return {"entry": entry, "z": round(z, 3), "rsi": round(r, 2), "sma20": round(sma, 4) if sma else sma}


def simulate_short_ticker(df) -> list[dict[str, Any]]:
    closes_list = [float(c) for c in df["Close"]]
    trades: list[dict[str, Any]] = []
    in_position = False
    entry_price = 0.0
    entry_idx = -1

    min_history = mrsig.SMA_WINDOW + mrsig.RSI_WINDOW
    for i in range(min_history, len(closes_list)):
        price = closes_list[i]
        history_so_far = closes_list[: i + 1]
        if not in_position:
            sig = short_entry_signal(history_so_far)
            if sig.get("entry"):
                in_position = True
                entry_price = price
                entry_idx = i
        else:
            days_held = i - entry_idx
            _, current_sma20 = mrsig.zscore_vs_sma(history_so_far)
            sma20 = current_sma20 if current_sma20 is not None else entry_price
            # Short PnL%: price falling is a GAIN for the short (mirror sign
            # of the long-style formula mrsig.exit_signal uses).
            pnl_pct = (entry_price - price) / entry_price * 100 if entry_price else 0.0
            reverted = price <= sma20
            stopped = pnl_pct <= STOP_LOSS_PCT  # price rose against the short by more than the stop allows
            timed_out = days_held >= MAX_HOLD_DAYS
            if reverted or stopped or timed_out:
                reason = "REVERTED" if reverted else ("STOP_LOSS" if stopped else "TIMED_OUT")
                trades.append({"days_held": days_held, "pnl_pct": pnl_pct, "exit_reason": reason})
                in_position = False
    return trades


def main() -> None:
    tickers = mrbt._load_watchlist()
    print(f"Fetching 1y daily history for {len(tickers)} tickers...")
    history = mrbt.fetch_history(tickers)
    print(f"Got usable history for {len(history)}/{len(tickers)} tickers.")

    all_trades: list[dict[str, Any]] = []
    for ticker, df in history.items():
        for t in simulate_short_ticker(df):
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

    print(f"\n=== Overbought-reversion short backtest: {len(all_trades)} trades across {len(history)} tickers, 1y ===")
    print(f"  win_rate={win_rate:.1f}%  profit_factor={pf:.2f}  avg_pnl_pct={avg_pnl:.2f}%  avg_days_held={avg_days:.1f}")
    print(f"  exit reasons: {Counter(t['exit_reason'] for t in all_trades)}")


if __name__ == "__main__":
    main()
