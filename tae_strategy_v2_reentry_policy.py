#!/usr/bin/env python3
"""
Strategy V2 PAPER — validated reentry after V2_PROFIT_TRAILING_5_2.

PAPER / parallel only. Does not enable STRATEGY_V2_ENABLED.
Does not touch LIVE, V1, or PDE.

Lifecycle:
  OPEN/ADD → trailing arm +5% → SELL −2% from peak → PROFIT_CAPTURED
  → REENTRY_WATCH → validated pullback|breakout → normal V2 BUY OPEN → new cycle
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tae_strategy_v2_config import load_strategy_v2_config
from tae_strategy_v2_foundation import STRATEGY_VERSION, is_finite_positive

POLICY_VERSION = "reentry_policy.v1"
REENTRY_SCHEMA = "tae.strategy_v2.reentry.v1"

# Explicit result codes (SSOT)
V2_REENTRY_WATCH = "V2_REENTRY_WATCH"
V2_REENTRY_ALLOWED_PULLBACK = "V2_REENTRY_ALLOWED_PULLBACK"
V2_REENTRY_ALLOWED_BREAKOUT = "V2_REENTRY_ALLOWED_BREAKOUT"
V2_REENTRY_BLOCKED_MARKET = "V2_REENTRY_BLOCKED_MARKET"
V2_REENTRY_BLOCKED_COMPANY_RISK = "V2_REENTRY_BLOCKED_COMPANY_RISK"
V2_REENTRY_BLOCKED_RELATIVE_STRENGTH = "V2_REENTRY_BLOCKED_RELATIVE_STRENGTH"
V2_REENTRY_BLOCKED_FALLING_KNIFE = "V2_REENTRY_BLOCKED_FALLING_KNIFE"
V2_REENTRY_BLOCKED_CAPITAL = "V2_REENTRY_BLOCKED_CAPITAL"
V2_REENTRY_BLOCKED_TOO_SOON = "V2_REENTRY_BLOCKED_TOO_SOON"
V2_REENTRY_BLOCKED_DUPLICATE = "V2_REENTRY_BLOCKED_DUPLICATE"
V2_REENTRY_BLOCKED_SAME_TS = "V2_REENTRY_BLOCKED_SAME_TS"
V2_REENTRY_BLOCKED_IDLE = "V2_REENTRY_BLOCKED_IDLE"
V2_REENTRY_BLOCKED_PATH = "V2_REENTRY_BLOCKED_PATH"
V2_REENTRY_BLOCKED_HARD_RISK = "V2_REENTRY_BLOCKED_HARD_RISK"
V2_REENTRY_BLOCKED_STALE_PRICE = "V2_REENTRY_BLOCKED_STALE_PRICE"

DEFAULT_REENTRY_PATH = Path("runtime_outputs/strategy_v2/reentry_state.json")

# Config keys (single source — values live in tae_strategy_v2_config.json)
CFG_PULLBACK = "REENTRY_PULLBACK_PCT"
CFG_BREAKOUT = "REENTRY_BREAKOUT_PCT"
CFG_COOLDOWN = "REENTRY_COOLDOWN_SECONDS"
CFG_SLIPPAGE = "REENTRY_SLIPPAGE_BPS"
CFG_COMMISSION = "REENTRY_COMMISSION_USD"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _s(v: Any) -> str:
    return str(v or "").strip()


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        out = float(v)
        if math.isnan(out) or math.isinf(out):
            return float(default)
        return out
    except (TypeError, ValueError):
        return float(default)


def _parse_ts(ts: Any) -> datetime | None:
    if ts is None or ts == "":
        return None
    try:
        t = pd_timestamp(ts)
        if t is None:
            return None
        if t.tzinfo is None:
            return t.replace(tzinfo=timezone.utc)
        return t
    except Exception:
        return None


def pd_timestamp(ts: Any) -> datetime | None:
    s = _s(ts)
    if not s:
        return None
    try:
        # Prefer stdlib for ISO; fall back to fromisoformat variants
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def empty_reentry_store() -> dict[str, Any]:
    return {
        "schema": REENTRY_SCHEMA,
        "strategy_version": STRATEGY_VERSION,
        "policy_version": POLICY_VERSION,
        "updated_at": _now(),
        "by_ticker": {},
    }


def load_reentry_store(path: Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else DEFAULT_REENTRY_PATH
    if not p.is_file():
        return empty_reentry_store()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_reentry_store()
    if not isinstance(raw, dict):
        return empty_reentry_store()
    store = empty_reentry_store()
    store.update({k: raw.get(k, store.get(k)) for k in store})
    by = raw.get("by_ticker") if isinstance(raw.get("by_ticker"), dict) else {}
    store["by_ticker"] = {str(k).upper(): dict(v) for k, v in by.items() if isinstance(v, dict)}
    return store


def save_reentry_store(store: dict[str, Any], path: Path | None = None) -> None:
    p = Path(path) if path is not None else DEFAULT_REENTRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    out = dict(store)
    out["updated_at"] = _now()
    out["schema"] = REENTRY_SCHEMA
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def get_ticker_reentry(store: dict[str, Any], ticker: str) -> dict[str, Any]:
    t = _s(ticker).upper()
    row = (store.get("by_ticker") or {}).get(t)
    if isinstance(row, dict):
        return dict(row)
    return {
        "ticker": t,
        "reentry_state": "IDLE",
        "last_profit_exit_price": None,
        "last_profit_exit_at": None,
        "last_cycle_realized_pnl": 0.0,
        "completed_profit_cycles": 0,
        "reentry_reference_peak": None,
        "reentry_reference_exit": None,
        "last_cycle_id": None,
        "last_reentry_signal_id": None,
        "cooldown_until": None,
        "pending_reentry_consumed": False,
    }


def apply_transaction_costs(
    notional: float,
    *,
    cfg: dict[str, Any] | None = None,
) -> float:
    """Delegate to canonical PAPER tx-cost SSOT (deterministic, no broker).

    Maps legacy REENTRY_SLIPPAGE_BPS / REENTRY_COMMISSION_USD into the unified model.
    """
    from tae_paper_transaction_costs import apply_transaction_costs as _ssot

    cfg = cfg or load_strategy_v2_config()
    return float(_ssot(notional, cfg=cfg))


@dataclass
class ReentryDecision:
    code: str
    ok: bool
    path: str | None = None  # PULLBACK | BREAKOUT | None
    detail: str = ""
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def mark_profit_captured(
    store: dict[str, Any],
    *,
    ticker: str,
    exit_price: float,
    exit_at: str,
    realized_pnl: float,
    peak_price: float | None,
    cycle_id: str | None,
    cfg: dict[str, Any] | None = None,
    persist_path: Path | None = None,
    released_capital: float | None = None,
) -> dict[str, Any]:
    """After V2_PROFIT_TRAILING_5_2 — move ticker to REENTRY_WATCH and compound accounting fields."""
    cfg = cfg or load_strategy_v2_config()
    t = _s(ticker).upper()
    row = get_ticker_reentry(store, t)
    cooldown_s = int(_f(cfg.get(CFG_COOLDOWN), 3600.0))
    exit_dt = _parse_ts(exit_at) or datetime.now(timezone.utc)
    cooldown_until = (exit_dt + timedelta(seconds=cooldown_s)).isoformat()
    peak = _f(peak_price, exit_price)
    if not is_finite_positive(peak):
        peak = float(exit_price)
    released = _f(released_capital)
    row.update(
        {
            "ticker": t,
            "reentry_state": "WATCH",
            "last_profit_exit_price": round(float(exit_price), 6),
            "last_profit_exit_at": exit_at,
            "last_cycle_realized_pnl": round(float(realized_pnl), 6),
            "completed_profit_cycles": int(row.get("completed_profit_cycles") or 0) + 1,
            "reentry_reference_peak": round(float(peak), 6),
            "reentry_reference_exit": round(float(exit_price), 6),
            "released_capital": round(released, 6) if released > 0 else round(float(released_capital or 0.0), 6),
            "last_cycle_id": cycle_id,
            "cooldown_until": cooldown_until,
            "pending_reentry_consumed": False,
            "last_reentry_signal_id": None,
            "updated_at": _now(),
            "status_label": "PROFIT_CAPTURED",
        }
    )
    store.setdefault("by_ticker", {})[t] = row
    if persist_path is not None:
        save_reentry_store(store, persist_path)
    return row


def consume_reentry(
    store: dict[str, Any],
    *,
    ticker: str,
    signal_id: str,
    new_cycle_id: str | None,
    persist_path: Path | None = None,
) -> dict[str, Any]:
    """After successful OPEN following ALLOWED reentry — one reentry per signal/cycle."""
    t = _s(ticker).upper()
    row = get_ticker_reentry(store, t)
    row["reentry_state"] = "IN_CYCLE"
    row["pending_reentry_consumed"] = True
    row["last_reentry_signal_id"] = _s(signal_id)
    row["active_cycle_id"] = new_cycle_id
    row["updated_at"] = _now()
    store.setdefault("by_ticker", {})[t] = row
    if persist_path is not None:
        save_reentry_store(store, persist_path)
    return row


def evaluate_reentry_policy(
    *,
    ticker: str,
    mark_price: float,
    timestamp: str,
    cash: float,
    reentry_row: dict[str, Any] | None,
    market_regime: str = "UNKNOWN",
    decline_class: str = "UNCLASSIFIED",
    relative_strength_state: str = "UNKNOWN",
    quarantined: bool = False,
    company_risk_blocked: bool = False,
    hard_risk_allows: bool = True,
    momentum_context: str = "UNKNOWN",
    trend_context: str = "UNKNOWN",
    atr_pct: float | None = None,
    signal_id: str | None = None,
    cfg: dict[str, Any] | None = None,
    min_order_usd: float | None = None,
) -> ReentryDecision:
    """
    Authorize at most one validated reentry while reentry_state=WATCH.

    Paths:
      1) Pullback: mark <= reference * (1 - pullback_pct) [ATR-aware if atr_pct provided]
      2) Breakout: mark > peak * (1 + breakout_pct) with momentum/RS validation
    """
    cfg = cfg or load_strategy_v2_config()
    row = dict(reentry_row or {})
    state = get_ticker_reentry({"by_ticker": { _s(ticker).upper(): row }}, ticker) if row else row
    # normalize
    if not state:
        state = get_ticker_reentry({"by_ticker": {}}, ticker)

    if _s(state.get("reentry_state")).upper() != "WATCH":
        return ReentryDecision(code=V2_REENTRY_BLOCKED_IDLE, ok=False, detail="not_in_watch", state=state)

    if bool(state.get("pending_reentry_consumed")):
        return ReentryDecision(code=V2_REENTRY_BLOCKED_DUPLICATE, ok=False, detail="already_consumed", state=state)

    sid = _s(signal_id)
    if sid and sid == _s(state.get("last_reentry_signal_id")):
        return ReentryDecision(code=V2_REENTRY_BLOCKED_DUPLICATE, ok=False, detail="duplicate_signal", state=state)

    exit_at = _s(state.get("last_profit_exit_at"))
    if exit_at and _s(timestamp) and _s(timestamp)[:19] == exit_at[:19]:
        return ReentryDecision(code=V2_REENTRY_BLOCKED_SAME_TS, ok=False, detail="same_timestamp_as_sell", state=state)

    # Cooldown
    cd = _parse_ts(state.get("cooldown_until"))
    now = _parse_ts(timestamp) or datetime.now(timezone.utc)
    if cd is not None and now < cd:
        return ReentryDecision(code=V2_REENTRY_BLOCKED_TOO_SOON, ok=False, detail=f"cooldown_until={cd.isoformat()}", state=state)

    if not is_finite_positive(mark_price):
        return ReentryDecision(code=V2_REENTRY_BLOCKED_STALE_PRICE, ok=False, detail="invalid_mark", state=state)

    regime = _s(market_regime).upper()
    if not regime or regime in {"UNKNOWN", "N/A", "NONE"}:
        return ReentryDecision(code=V2_REENTRY_BLOCKED_MARKET, ok=False, detail="regime_unavailable", state=state)
    if "BEAR" in regime or regime in {"RISK_OFF", "GLOBAL_RISK_OFF"}:
        return ReentryDecision(code=V2_REENTRY_BLOCKED_MARKET, ok=False, detail=f"regime={regime}", state=state)

    decline = _s(decline_class).upper()
    if quarantined or decline == "FALLING_KNIFE":
        return ReentryDecision(
            code=V2_REENTRY_BLOCKED_FALLING_KNIFE,
            ok=False,
            detail="quarantined" if quarantined else decline,
            state=state,
        )

    if company_risk_blocked or decline in {"COMPANY_SPECIFIC_DECLINE", "STRUCTURAL_DECLINE"}:
        return ReentryDecision(
            code=V2_REENTRY_BLOCKED_COMPANY_RISK,
            ok=False,
            detail=decline or "company_risk",
            state=state,
        )

    if not hard_risk_allows:
        return ReentryDecision(code=V2_REENTRY_BLOCKED_HARD_RISK, ok=False, detail="hard_risk", state=state)

    rs = _s(relative_strength_state).upper()
    if rs in {"SEVERE_DETERIORATION", "RELATIVE_STRENGTH_DECLINE"}:
        return ReentryDecision(code=V2_REENTRY_BLOCKED_RELATIVE_STRENGTH, ok=False, detail=f"rs={rs}", state=state)

    reserve = _f(cfg.get("MIN_CASH_RESERVE_USD"), 500.0)
    min_order = _f(min_order_usd, cfg.get("min_order_value_usd") or 250.0)
    deployable = float(cash) - reserve
    if deployable + 1e-9 < min_order:
        return ReentryDecision(
            code=V2_REENTRY_BLOCKED_CAPITAL,
            ok=False,
            detail=f"deployable={deployable:.2f}<min_order={min_order:.2f}",
            state=state,
        )

    pullback_pct = _f(cfg.get(CFG_PULLBACK), 3.0)
    breakout_pct = _f(cfg.get(CFG_BREAKOUT), 1.0)
    # ATR-aware: widen pullback when ATR% is larger than configured pullback
    if atr_pct is not None and is_finite_positive(atr_pct):
        pullback_pct = max(pullback_pct, float(atr_pct))

    peak = _f(state.get("reentry_reference_peak"), state.get("last_profit_exit_price"))
    exit_px = _f(state.get("reentry_reference_exit"), state.get("last_profit_exit_price"))
    if not is_finite_positive(peak) or not is_finite_positive(exit_px):
        return ReentryDecision(code=V2_REENTRY_BLOCKED_PATH, ok=False, detail="missing_reference", state=state)

    mark = float(mark_price)
    pullback_level = min(peak, exit_px) * (1.0 - pullback_pct / 100.0)
    breakout_level = peak * (1.0 + breakout_pct / 100.0)

    mom = _s(momentum_context).upper()
    trend = _s(trend_context).upper()

    # Path 1: validated pullback (not merely below sell — must clear pullback distance)
    if mark <= pullback_level + 1e-12:
        # Reject "just below sell" without enough distance: already encoded by pullback_level
        return ReentryDecision(
            code=V2_REENTRY_ALLOWED_PULLBACK,
            ok=True,
            path="PULLBACK",
            detail=f"mark={mark:.4f}<=pullback_level={pullback_level:.4f} pct={pullback_pct}",
            state=state,
        )

    # Path 2: new breakout above prior peak with momentum/RS (not merely > sell)
    if mark >= breakout_level - 1e-12:
        # Must be above peak, not only above exit
        if mark <= exit_px + 1e-12:
            return ReentryDecision(
                code=V2_REENTRY_BLOCKED_PATH,
                ok=False,
                detail="above_exit_but_not_breakout",
                state=state,
            )
        mom_ok = mom in {"MOMENTUM_STRONG", "MOMENTUM_IMPROVING", "UNKNOWN", ""}
        trend_ok = trend not in {"TREND_WEAK", "TREND_BROKEN", "TREND_RUPTURED"}
        rs_ok = rs not in {"DETERIORATING", "SEVERE_DETERIORATION"}
        if mom_ok and trend_ok and rs_ok:
            return ReentryDecision(
                code=V2_REENTRY_ALLOWED_BREAKOUT,
                ok=True,
                path="BREAKOUT",
                detail=f"mark={mark:.4f}>=breakout_level={breakout_level:.4f}",
                state=state,
            )
        return ReentryDecision(
            code=V2_REENTRY_BLOCKED_RELATIVE_STRENGTH,
            ok=False,
            detail=f"breakout_without_momentum mom={mom} trend={trend} rs={rs}",
            state=state,
        )

    # Still watching — insufficient pullback / no breakout
    return ReentryDecision(
        code=V2_REENTRY_WATCH,
        ok=False,
        detail=f"waiting mark={mark:.4f} pullback_level={pullback_level:.4f} breakout_level={breakout_level:.4f}",
        state=state,
    )


__all__ = [
    "POLICY_VERSION",
    "V2_REENTRY_WATCH",
    "V2_REENTRY_ALLOWED_PULLBACK",
    "V2_REENTRY_ALLOWED_BREAKOUT",
    "V2_REENTRY_BLOCKED_MARKET",
    "V2_REENTRY_BLOCKED_COMPANY_RISK",
    "V2_REENTRY_BLOCKED_RELATIVE_STRENGTH",
    "V2_REENTRY_BLOCKED_FALLING_KNIFE",
    "V2_REENTRY_BLOCKED_CAPITAL",
    "V2_REENTRY_BLOCKED_TOO_SOON",
    "V2_REENTRY_BLOCKED_DUPLICATE",
    "V2_REENTRY_BLOCKED_SAME_TS",
    "V2_REENTRY_BLOCKED_HARD_RISK",
    "V2_REENTRY_BLOCKED_STALE_PRICE",
    "apply_transaction_costs",
    "consume_reentry",
    "evaluate_reentry_policy",
    "get_ticker_reentry",
    "load_reentry_store",
    "mark_profit_captured",
    "save_reentry_store",
    "empty_reentry_store",
]
