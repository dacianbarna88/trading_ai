"""Shared mean-reversion signal math — used identically by the backtest
(tae_meanreversion_backtest.py) and the live isolated paper arm
(tae_parallel_paper_mean_reversion.py) so the two can never drift out of
sync on what "the signal" means (same principle already used for V3's
build_pseudo_record, tae_strategy_v3_learning_policy.py).

Mechanism: buy when price is Z_ENTRY_THRESHOLD standard deviations below
its own SMA_WINDOW-day mean AND RSI(RSI_WINDOW) is oversold — the
mechanical opposite of the trend-following breakout score V1/V2/V3/
exp_short_margin all share (see tae_score_decile_backtest.py /
tae_cross_arm_overlap_report.py for the "one shared signal, four slices"
finding this is a response to).

Backtested 2026-09-13 on the live 97-ticker watchlist, 1 year of daily
closes: 230 trades, 58.7% win rate, profit factor 1.81, avg +1.91%/trade,
avg 7.1 days held. Diversification check: 0% of entries occurred on days
the existing momentum score would also have called the ticker buyable
(avg momentum-score-proxy on entry days was 22/100) — genuinely
uncorrelated with the existing signal, not another slice of it.

Caveats carried forward deliberately (not yet resolved): single 1-year
window, no walk-forward/out-of-sample split, no portfolio-level position
cap in the backtest (each ticker simulated independently). The live arm
adds real position caps and cash limits; it does not re-validate the
signal on new data before trading it, so watch its own real results
before scaling it up.
"""

from __future__ import annotations

import numpy as np

SMA_WINDOW = 20
Z_ENTRY_THRESHOLD = -2.0
RSI_WINDOW = 14
RSI_OVERSOLD = 30.0
MAX_HOLD_DAYS = 10
STOP_LOSS_PCT = -5.0


def rsi(closes: list[float], window: int = RSI_WINDOW) -> float | None:
    """Wilder-style simple-average RSI over the trailing `window` bars of
    `closes`. Returns None if there isn't enough history."""
    if len(closes) < window + 1:
        return None
    arr = np.asarray(closes[-(window + 1):], dtype=float)
    deltas = np.diff(arr)
    gains = np.clip(deltas, 0, None)
    losses = -np.clip(deltas, None, 0)
    avg_gain = float(gains.mean())
    avg_loss = float(losses.mean())
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def zscore_vs_sma(closes: list[float], window: int = SMA_WINDOW) -> tuple[float | None, float | None]:
    """(z_score, sma) of the latest close vs. its trailing `window`-bar
    mean/stdev. (None, None) if there isn't enough history; (None, sma)
    if the window is degenerate (zero variance)."""
    if len(closes) < window:
        return None, None
    arr = np.asarray(closes[-window:], dtype=float)
    sma = float(arr.mean())
    std = float(arr.std(ddof=1))
    if std == 0:
        return None, sma
    z = (closes[-1] - sma) / std
    return z, sma


def entry_signal(closes: list[float]) -> dict:
    """Diagnostics dict with an `entry` bool. Never raises — bad/short
    history reads as "no signal", not an error, so a caller in a real
    decision loop degrades to HOLD rather than crashing."""
    if not closes or len(closes) < SMA_WINDOW + RSI_WINDOW:
        return {"entry": False, "reason": "INSUFFICIENT_HISTORY"}
    z, sma = zscore_vs_sma(closes)
    r = rsi(closes)
    if z is None or r is None:
        return {"entry": False, "reason": "INSUFFICIENT_HISTORY", "z": z, "rsi": r, "sma20": sma}
    entry = z <= Z_ENTRY_THRESHOLD and r <= RSI_OVERSOLD
    return {"entry": entry, "z": round(z, 3), "rsi": round(r, 2), "sma20": round(sma, 4) if sma else sma}


def exit_signal(*, current_price: float, sma20: float, entry_price: float, days_held: int) -> dict:
    """Mirrors the backtested exit rule exactly: revert to the mean, hit
    the flat stop-loss, or time out at MAX_HOLD_DAYS — in that priority
    order (matches tae_meanreversion_backtest.simulate_ticker)."""
    pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price else 0.0
    if sma20 is not None and current_price >= sma20:
        return {"exit": True, "reason": "REVERTED", "pnl_pct": round(pnl_pct, 4)}
    if pnl_pct <= STOP_LOSS_PCT:
        return {"exit": True, "reason": "STOP_LOSS", "pnl_pct": round(pnl_pct, 4)}
    if days_held >= MAX_HOLD_DAYS:
        return {"exit": True, "reason": "TIMED_OUT", "pnl_pct": round(pnl_pct, 4)}
    return {"exit": False, "reason": "HOLD", "pnl_pct": round(pnl_pct, 4)}
