"""V2 active concentration trim — gradually shrinks V2's position count.

Context: raising V2_MAX_POSITIONS (tae_parallel_paper_runtime.py) only caps
future growth — it does nothing for a book that's already over-diversified
(49 positions at ~$500-1000 each, diluting the proven per-trade edge that
motivated Kelly sizing in the first place). This module adds the missing
piece: an ACTIVE trim that closes the weakest, going-nowhere positions
(flat or slightly losing, not yet a real stop-loss, not a working trailing
winner) so capital frees up for Kelly-sized, higher-conviction entries.

Deliberately conservative and self-rate-limiting:
- Only trims while position count is above V2_CONCENTRATION_TARGET.
- Never touches a position with trailing_armed=True (a winner already
  running its course is left alone — this is capital reallocation, not a
  second stop-loss).
- Only targets positions below V2_TRIM_MAX_PNL_PCT unrealized gain (i.e.
  "not clearly working" — a real winner or a real stop-loss candidate are
  both left to the existing exit logic).
- Rate-limited to at most one trim per V2_TRIM_MIN_GAP_MINUTES, checked
  against the real trades journal (a durable signal, not an in-memory
  counter) so it stays correct regardless of how many separate callers
  (tae_parallel_paper_runtime.run_cycle, tae_canonical_dual_strategy) touch
  the same V2 book in the same hour.
- Never trims a position younger than V2_TRIM_MIN_AGE_HOURS. A freshly
  opened position necessarily starts near 0% pnl, which otherwise looks
  identical to a "flat, going-nowhere" position — without this guard, a
  brand-new entry gets immediately re-trimmed, producing an open/trim/open
  churn loop with no economic purpose (found live on SAP.DE 2026-09-08).
  Age is read from position_cycle_id's embedded open timestamp
  ("PPC-<ticker>-<UTC timestamp>-<hash>").

Wired in as a fallback ONLY when the existing exit_policy (trailing stop,
stop-loss, thesis-invalid close, ATR profit target) has nothing to say —
this never overrides a higher-priority real exit signal.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

V2_CONCENTRATION_TARGET = 15
V2_TRIM_MAX_PNL_PCT = 1.0
V2_TRIM_MIN_GAP_MINUTES = 50.0
V2_TRIM_MIN_AGE_HOURS = 4.0
V2_CONCENTRATION_TRIM_REASON = "V2_CONCENTRATION_TRIM"

_CYCLE_ID_TS_RE = re.compile(r"-(\d{8}T\d{6})-")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if x == x else default  # filters NaN


def _open_position_count(portfolio: dict[str, Any]) -> int:
    return sum(
        1 for pos in (portfolio.get("positions") or {}).values() if _f(pos.get("shares")) > 0
    )


def _position_age_hours(pos: dict[str, Any], *, now: datetime) -> float | None:
    """Reads the open timestamp embedded in position_cycle_id
    ("PPC-<ticker>-<UTC timestamp>-<hash>"). Returns None if it can't be
    parsed — callers should then decline to trim (fail safe, not open)."""
    cycle_id = pos.get("position_cycle_id")
    if not cycle_id:
        return None
    m = _CYCLE_ID_TS_RE.search(str(cycle_id))
    if not m:
        return None
    try:
        opened_at = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (now - opened_at).total_seconds() / 3600.0


def _last_trim_timestamp(
    trades_path: Path | str, *, reason: str = V2_CONCENTRATION_TRIM_REASON
) -> datetime | None:
    path = Path(trades_path)
    if not path.exists():
        return None
    last_ts: datetime | None = None
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("reason") != reason:
                continue
            ts = rec.get("ts")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except ValueError:
                continue
            if last_ts is None or dt > last_ts:
                last_ts = dt
    return last_ts


def should_concentration_trim(
    *,
    portfolio: dict[str, Any],
    pos: dict[str, Any] | None,
    cycle: dict[str, Any] | None,
    current_price: float,
    trades_path: Path | str,
    target: int = V2_CONCENTRATION_TARGET,
    max_pnl_pct: float = V2_TRIM_MAX_PNL_PCT,
    min_gap_minutes: float = V2_TRIM_MIN_GAP_MINUTES,
    min_age_hours: float = V2_TRIM_MIN_AGE_HOURS,
    now: datetime | None = None,
) -> str | None:
    """Returns V2_CONCENTRATION_TRIM_REASON if this position should be
    force-closed for concentration, else None. Pure decision function —
    callers are responsible for actually executing the close."""
    if not pos or _f(pos.get("shares")) <= 0:
        return None
    if _open_position_count(portfolio) <= target:
        return None
    if bool((cycle or {}).get("trailing_armed") or pos.get("trailing_armed")):
        return None
    moment = now or datetime.now(timezone.utc)
    age_hours = _position_age_hours(pos, now=moment)
    if age_hours is None or age_hours < min_age_hours:
        return None
    avg = _f(pos.get("avg_price"))
    if avg <= 0 or current_price <= 0:
        return None
    pnl_pct = (current_price - avg) / avg * 100.0
    if pnl_pct >= max_pnl_pct:
        return None
    last_trim = _last_trim_timestamp(trades_path)
    if last_trim is not None:
        age_minutes = (moment - last_trim).total_seconds() / 60.0
        if age_minutes < min_gap_minutes:
            return None
    return V2_CONCENTRATION_TRIM_REASON
