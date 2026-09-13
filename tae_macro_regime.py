"""Shared macro-regime signal math — VIX tercile, market trend (SPY vs its
own SMA), and yield-curve slope. Used identically by the backtest
(tae_macro_regime_backtest.py) and, once reviewed, by the live wiring into
V3's existing RegimeGrid (tae_strategy_v3_learning_policy.py:119-127),
which already has trend/vol_tercile slots but has them hard-coded
"UNKNOWN" in production (_run_v3_arm, tae_parallel_paper_runtime.py:
3476/3911) — this fills those slots with real data rather than adding new
plumbing.

Trend rule deliberately mirrors live_bot.py's own get_market_regime()
(SPY close vs its MARKET_REGIME_SMA-day mean, config.settings.
MARKET_REGIME_TICKER/MARKET_REGIME_SMA) rather than inventing a different
rule — but get_market_regime() only ever answers "as of right now" (a live
yfinance fetch), so it cannot be called day-by-day for a historical
backtest. classify_trend() here is the same rule, computable from a plain
closes list at any historical point.

Sprint 3 context (2026-09-13): built to test whether the existing
technical score's win rate/profit factor actually differs across VIX/
yield-curve regimes, BEFORE wiring any of this into a live decision (same
discipline as tae_mean_reversion_signal.py / tae_score_decile_backtest.py).
"""

from __future__ import annotations

VIX_FETCH_PERIOD = "1y"
VIX_FETCH_TIMEOUT_SECONDS = 20.0

VIX_TICKER = "^VIX"
TNX_TICKER = "^TNX"
IRX_TICKER = "^IRX"

VIX_TERCILE_HISTORY_WINDOW = 252


def classify_trend(closes: list[float], window: int) -> str:
    """BULL/BEAR from the latest close vs. its trailing `window`-bar mean —
    mirrors live_bot.py's get_market_regime() (SPY vs SMA200 by default)."""
    if len(closes) < window:
        return "UNKNOWN"
    sma = sum(closes[-window:]) / window
    return "BULL" if closes[-1] > sma else "BEAR"


def vix_tercile(vix_closes: list[float], window: int = VIX_TERCILE_HISTORY_WINDOW) -> str:
    """LOW/MED/HIGH tercile of the latest VIX close against its own
    trailing history — same tercile-against-own-history spirit as
    tae_strategy_v3_learning_policy.classify_vol_tercile, reimplemented
    here on a plain closes list (that function takes a precomputed
    realized-vol history, not raw VIX levels)."""
    if len(vix_closes) < 30:
        return "UNKNOWN"
    current = vix_closes[-1]
    hist = vix_closes[-(window + 1):-1] if len(vix_closes) > window else vix_closes[:-1]
    if not hist:
        return "UNKNOWN"
    sorted_hist = sorted(hist)
    lo = sorted_hist[len(sorted_hist) // 3]
    hi = sorted_hist[(2 * len(sorted_hist)) // 3]
    if current <= lo:
        return "LOW"
    if current >= hi:
        return "HIGH"
    return "MED"


def yield_curve_slope(tnx_close: float | None, irx_close: float | None) -> float | None:
    """10y minus 13-week yield. Negative = inverted curve (recession-risk
    signal); positive = normal curve."""
    if tnx_close is None or irx_close is None:
        return None
    return tnx_close - irx_close


def curve_regime(slope: float | None) -> str:
    if slope is None:
        return "UNKNOWN"
    return "INVERTED" if slope < 0 else "NORMAL"


def fetch_current_vix_tercile() -> str:
    """Live, once-per-cycle fetch: today's VIX tercile against its own
    trailing 1y history. Fail-soft — any fetch/data problem returns
    "UNKNOWN" rather than raising, same convention as every other network
    call in this codebase (tae_network_hard_timeout.py). Backtested
    2026-09-13 (tae_macro_regime_backtest.py) on real V1/V2 trade history:
    LOW-VIX entries win_rate=39.3%/PF=0.77 vs MED/HIGH win_rate~20%/
    PF~0.25 — a real, if modest-sample, split. Trend (BULL/BEAR) and
    yield-curve regime were NOT validated (zero regime variation in the
    observed window) and are deliberately not wired live yet."""
    try:
        import yfinance as yf

        from tae_network_hard_timeout import hard_timeout

        with hard_timeout(VIX_FETCH_TIMEOUT_SECONDS):
            data = yf.download(VIX_TICKER, period=VIX_FETCH_PERIOD, interval="1d", progress=False)
        if data is None or data.empty:
            return "UNKNOWN"
        closes = [float(c) for c in data["Close"].dropna().to_numpy().ravel()]
        return vix_tercile(closes)
    except Exception:
        return "UNKNOWN"
