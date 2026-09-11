"""V2 relative-weakness trim — exits positions lagging the broad market
benchmark (SPY), independent of position count.

Motivation (2026-09-09): on a day the broad market was flat (SPY -0.02%,
QQQ +0.10%, DIA +0.74%), V2 still lost -$259.87 in unrealized PnL,
concentrated in a handful of names (CDNS -$118, INTU -$99, BLK -$66,
LMT -$46, HD -$42, SNPS -$34) that badly lagged the market -- pure
stock-selection weakness, not a market-wide selloff. The existing
concentration trim (tae_strategy_v2_concentration.py) only fires when
position COUNT exceeds a target; it would never touch these names on a day
V2 is already at or under its target count. This adds a second,
independent trigger based on relative underperformance vs SPY over a
fixed lookback window -- not tied to entry price/timestamp, so it applies
immediately to positions opened long before this mechanism existed.

Deliberately mirrors tae_strategy_v2_concentration.py's conservatism:
- Never touches a position with trailing_armed=True (a winner already
  running its course — this is not a second stop-loss).
- Never judges a position younger than RELATIVE_WEAKNESS_MIN_AGE_HOURS
  (same reasoning as the concentration module's age guard).
- Rate-limited to at most one trim per RELATIVE_WEAKNESS_MIN_GAP_MINUTES,
  checked against the real trades journal, filtered to this reason only
  (reuses tae_strategy_v2_concentration._last_trim_timestamp's
  now-parameterized `reason` argument).
- Fails safe: any missing/unfetchable price history means "don't trim",
  never "assume the worst".

Wired in as a fallback ONLY after the existing exit_policy AND the
concentration trim have both had nothing to say for this position.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_strategy_v2_concentration import _f, _last_trim_timestamp, _position_age_hours

BENCHMARK_TICKER = "SPY"
RELATIVE_WEAKNESS_LOOKBACK_DAYS = 10
RELATIVE_WEAKNESS_THRESHOLD_PCT = -8.0
RELATIVE_WEAKNESS_MIN_AGE_HOURS = 24.0
RELATIVE_WEAKNESS_MIN_GAP_MINUTES = 50.0
V2_RELATIVE_WEAKNESS_REASON = "V2_RELATIVE_WEAKNESS_TRIM"

# Cheap per-cycle cache for the benchmark's own return -- computing it once
# per lookback window per cycle instead of once per position avoids
# re-fetching SPY's history ~15-50x per V2 pass (the same class of
# redundant-network-call cost found and fixed 2026-09-09 elsewhere).
_benchmark_cache: dict[int, dict[str, Any]] = {}
BENCHMARK_CACHE_TTL_SECONDS = 1800.0


def _pct_return(closes: list[float] | None, lookback_days: int) -> float | None:
    if not closes or len(closes) < 2:
        return None
    n = min(lookback_days, len(closes) - 1)
    start = closes[-(n + 1)]
    end = closes[-1]
    if not start:
        return None
    return (end - start) / start * 100.0


def _cached_benchmark_return_pct(
    *, now: datetime, lookback_days: int = RELATIVE_WEAKNESS_LOOKBACK_DAYS
) -> float | None:
    cached = _benchmark_cache.get(lookback_days)
    if cached is not None and (now - cached["fetched_at"]).total_seconds() < BENCHMARK_CACHE_TTL_SECONDS:
        return cached["return_pct"]
    from tae_strategy_v1_vol_stop import fetch_recent_closes

    closes = fetch_recent_closes(BENCHMARK_TICKER, period="2mo")
    ret = _pct_return(closes, lookback_days)
    if ret is not None:
        _benchmark_cache[lookback_days] = {"fetched_at": now, "return_pct": ret}
        return ret
    return cached["return_pct"] if cached is not None else None


def relative_underperformance_pct(
    ticker: str, *, now: datetime | None = None, lookback_days: int = RELATIVE_WEAKNESS_LOOKBACK_DAYS
) -> float | None:
    """ticker's own % return over lookback_days minus the benchmark's %
    return over the same window. None if either series is unavailable —
    callers must treat that as "no signal", never as "worst case"."""
    moment = now or datetime.now(timezone.utc)
    from tae_strategy_v1_vol_stop import fetch_recent_closes

    ticker_closes = fetch_recent_closes(ticker, period="2mo")
    ticker_ret = _pct_return(ticker_closes, lookback_days)
    bench_ret = _cached_benchmark_return_pct(now=moment, lookback_days=lookback_days)
    if ticker_ret is None or bench_ret is None:
        return None
    return ticker_ret - bench_ret


def should_relative_weakness_trim(
    *,
    pos: dict[str, Any] | None,
    cycle: dict[str, Any] | None,
    ticker: str,
    trades_path: Path | str,
    current_price: float | None = None,
    threshold_pct: float = RELATIVE_WEAKNESS_THRESHOLD_PCT,
    min_age_hours: float = RELATIVE_WEAKNESS_MIN_AGE_HOURS,
    min_gap_minutes: float = RELATIVE_WEAKNESS_MIN_GAP_MINUTES,
    now: datetime | None = None,
) -> str | None:
    """Returns V2_RELATIVE_WEAKNESS_REASON if this position should be
    force-closed for lagging the market, else None. Pure decision
    function — callers are responsible for actually executing the close."""
    if not pos or _f(pos.get("shares")) <= 0:
        return None
    if bool((cycle or {}).get("trailing_armed") or pos.get("trailing_armed")):
        return None
    moment = now or datetime.now(timezone.utc)
    age_hours = _position_age_hours(pos, now=moment)
    if age_hours is None or age_hours < min_age_hours:
        return None
    # Cheap pre-filter before the network fetch below: a position that's
    # already up on its own price can't plausibly be lagging the market by
    # threshold_pct (a large negative number) -- skip the fetch entirely.
    # Avoids ~1 extra yfinance call per in-profit V2 position per cycle.
    avg = _f(pos.get("avg_price"))
    mark = _f(current_price) if current_price is not None else _f(pos.get("current_price"))
    if avg > 0 and mark > 0:
        own_pnl_pct = (mark - avg) / avg * 100.0
        if own_pnl_pct > 0:
            return None
    rel = relative_underperformance_pct(ticker, now=moment)
    if rel is None:
        return None
    if rel > threshold_pct:
        return None
    last_trim = _last_trim_timestamp(trades_path, reason=V2_RELATIVE_WEAKNESS_REASON)
    if last_trim is not None:
        age_minutes = (moment - last_trim).total_seconds() / 60.0
        if age_minutes < min_gap_minutes:
            return None
    return V2_RELATIVE_WEAKNESS_REASON
