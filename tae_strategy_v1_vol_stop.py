"""Volatility-adjusted entry stop-loss for V1 (isolated parallel-paper arm).

V1's entry stop was a flat -3% applied identically to every ticker
regardless of how volatile that name actually is — a quiet stock and a
name that routinely swings 2%+/day get the exact same stop distance, so
the flat stop is likely tripped by ordinary noise on volatile names while
being needlessly loose on calm ones. This computes a per-ticker stop
distance from that ticker's own trailing realized volatility instead.

Reuses tae_strategy_v3_learning_policy.realized_vol_annualized() (a pure
function on a closes series, no V3-specific state) rather than
reimplementing volatility math. Only fetches history for tickers V1
actually holds a position in (bounded by V1's open-position count, not the
full watchlist), since that's the only place a stop-loss decision is made.
"""

from __future__ import annotations

import math
from typing import Any

import yfinance as yf

from tae_strategy_v3_learning_policy import realized_vol_annualized

VOL_STOP_K = 2.0
VOL_STOP_MIN_PCT = 2.0
VOL_STOP_MAX_PCT = 6.0
CLOSES_WINDOW_DAYS = 25
DEFAULT_STOP_LOSS_PCT = -3.0  # fallback when volatility can't be computed


def fetch_recent_closes(ticker: str, *, period: str = "2mo") -> list[float] | None:
    """Trailing daily closes for one ticker, NaN-filtered (mirrors live_bot.py's
    own generate_signals() NaN-Close handling for the same yfinance quirk)."""
    try:
        data = yf.download(ticker, period=period, auto_adjust=False, progress=False)
    except Exception:
        return None
    if data is None or data.empty:
        return None
    if len(data.columns.names) > 1:
        data.columns = data.columns.droplevel(1)
    data = data[data["Close"].notna()]
    if data.empty:
        return None
    return [float(x) for x in data["Close"].tolist()]


def vol_adjusted_stop_pct(
    closes: list[float] | None,
    *,
    k: float = VOL_STOP_K,
    min_pct: float = VOL_STOP_MIN_PCT,
    max_pct: float = VOL_STOP_MAX_PCT,
    window: int = 20,
) -> tuple[float, dict[str, Any]]:
    """Returns (stop_loss_pct, diagnostics). stop_loss_pct is negative
    (e.g. -3.5), matching evaluate_position_exit's stop_loss_pct convention.

    Formula: k standard deviations of the ticker's own daily-equivalent
    volatility, clamped to [-max_pct, -min_pct] so it can never become
    degenerately tight or loose.
    """
    if not closes:
        return DEFAULT_STOP_LOSS_PCT, {
            "source": "DEFAULT_NO_CLOSES",
            "realized_vol_annualized": None,
        }
    vol = realized_vol_annualized(closes, window=window)
    if vol is None:
        return DEFAULT_STOP_LOSS_PCT, {
            "source": "DEFAULT_INSUFFICIENT_HISTORY",
            "realized_vol_annualized": None,
        }
    daily_vol_pct = (vol / math.sqrt(252.0)) * 100.0
    magnitude = max(min_pct, min(max_pct, k * daily_vol_pct))
    return -magnitude, {
        "source": "VOLATILITY_ADJUSTED",
        "realized_vol_annualized": round(vol, 6),
        "daily_vol_pct": round(daily_vol_pct, 4),
    }
