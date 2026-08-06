#!/usr/bin/env python3
"""
Canonical PAPER profit trailing SSOT (+5% activate / −2% from peak).

PAPER_ONLY — does not import LIVE portfolio, does not flip LIVE_PROFIT_TRAILING_5_2_ENABLED.
State lives on paper positions inside paper_portfolio.json.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- SSOT thresholds (fractions, not percent points) ---
PAPER_PROFIT_TRAILING_ACTIVATION_PCT = 0.05
PAPER_PROFIT_TRAILING_DRAWDOWN_PCT = 0.02

REASON_ACTIVATED = "PROFIT_TRAILING_ACTIVATED_5_PERCENT"
REASON_BOOTSTRAP = "PROFIT_TRAILING_PROSPECTIVE_BOOTSTRAP_ACTIVATED"
REASON_PEAK_UPDATED = "PROFIT_TRAILING_PEAK_UPDATED"
REASON_HOLD = "PROFIT_TRAILING_HOLD"
REASON_EXIT = "PROFIT_TRAILING_EXIT_DRAWDOWN_2_PERCENT"
REASON_SOFT_SUPPRESSED = "PDE_SOFT_EXIT_SUPPRESSED_BY_ACTIVE_PROFIT_TRAILING"
REASON_BUY_BLOCKED = "BUY_BLOCKED_ACTIVE_PROFIT_TRAILING"
REASON_PCE_PROTECTION_WIRED = "PCE_PROFIT_PROTECTION_WIRED"
STATUS_SKIP_EXIT_INVALID = "SKIPPED_TRAILING_EXIT_NO_LONGER_VALID"
STATUS_SKIP_NO_MARK = "SKIPPED_NO_VALID_TRAILING_MARK"

SOFT_EXIT_ACTIONS = frozenset({"SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER"})

PCE_JSON = Path("tae_profit_context_engine.json")
PCE_PROTECTION_VERDICTS = frozenset({"PROTECT_NOW", "CONTEXT_WEAKENING"})
GII_TIGHTEN_GOVERNOR = frozenset(
    {"PARTIAL_PROTECT_SHADOW", "TRAIL_PROTECT_SHADOW", "PROTECT_SHADOW", "TRAIL_SHADOW"}
)
GII_TIGHTEN_STRATEGIES = frozenset(
    {"TIGHTEN_TRAIL_SHADOW", "PROTECT_PROFIT_SHADOW", "REDUCE_EXPOSURE_SHADOW"}
)

_STALE = frozenset(
    {"STALE", "MARK_STALE", "UNAVAILABLE", "MARK_UNAVAILABLE", "INVALID", "MARK_INVALID", "EXPIRED"}
)

TRAILING_POS_FIELDS = (
    "position_cycle_id",
    "profit_trailing_active",
    "profit_trailing_activation_threshold_pct",
    "profit_trailing_drawdown_pct",
    "profit_trailing_activation_timestamp",
    "profit_trailing_activation_mark",
    "profit_trailing_peak_price",
    "profit_trailing_peak_timestamp",
    "profit_trailing_last_valid_mark",
    "profit_trailing_state_version",
    "profit_trailing_bootstrap_completed",
    "profit_trailing_pce_verdict",
    "profit_trailing_pce_wired",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return out


def assert_trailing_thresholds(
    activation: float = PAPER_PROFIT_TRAILING_ACTIVATION_PCT,
    drawdown: float = PAPER_PROFIT_TRAILING_DRAWDOWN_PCT,
) -> tuple[float, float]:
    for name, value in (("activation", activation), ("drawdown", drawdown)):
        try:
            v = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"trailing {name} must be numeric") from exc
        if not math.isfinite(v) or v <= 0.0 or v >= 1.0:
            raise ValueError(f"trailing {name} must be in (0, 1)")
    return float(activation), float(drawdown)


assert_trailing_thresholds()


def is_valid_trailing_mark(mark: Any, *, pos: dict[str, Any] | None = None) -> bool:
    try:
        x = float(mark)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(x) or x <= 0.0:
        return False
    if pos is not None:
        status = str(pos.get("mark_status") or "").strip().upper()
        if status in _STALE:
            return False
        freshness = str(pos.get("mark_freshness") or pos.get("freshness") or "FRESH").strip().upper()
        if freshness in _STALE or freshness in {"STALE", "EXPIRED"}:
            return False
    return True


def compute_profit_pct(mark: float, average_cost: float) -> float | None:
    if not is_valid_trailing_mark(mark) or not is_valid_trailing_mark(average_cost):
        return None
    if float(average_cost) <= 0.0:
        return None
    return (float(mark) / float(average_cost)) - 1.0


def compute_drawdown_from_peak(mark: float, peak: float) -> float | None:
    if not is_valid_trailing_mark(mark) or not is_valid_trailing_mark(peak):
        return None
    return (float(mark) / float(peak)) - 1.0


def trailing_exit_triggered(mark: float, peak: float) -> bool:
    """True when mark is at or below peak × (1 − drawdown).

    Uses a tiny relative epsilon so contractual edges like 127.40 on peak 130
    (exactly −2%) are not lost to binary float noise. Does not round for display.
    """
    if not is_valid_trailing_mark(mark) or not is_valid_trailing_mark(peak):
        return False
    ratio = float(mark) / float(peak)
    return ratio <= (1.0 - PAPER_PROFIT_TRAILING_DRAWDOWN_PCT) + 1e-12


def mint_position_cycle_id(ticker: str, *, now_iso: str | None = None) -> str:
    stamp = (now_iso or _now_iso()).replace(":", "").replace("-", "")[:15]
    return f"PPC-{str(ticker or '').strip().upper()}-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def ensure_position_cycle_id(pos: dict[str, Any], ticker: str, *, now_iso: str | None = None) -> str:
    existing = str(pos.get("position_cycle_id") or "").strip()
    if existing:
        return existing
    cid = mint_position_cycle_id(ticker, now_iso=now_iso)
    pos["position_cycle_id"] = cid
    return cid


def clear_profit_trailing_fields(pos: dict[str, Any]) -> None:
    for key in TRAILING_POS_FIELDS:
        if key == "position_cycle_id":
            continue
        pos.pop(key, None)
    pos["profit_trailing_active"] = False
    pos["profit_trailing_bootstrap_completed"] = False


def trailing_active_on_position(pos: dict[str, Any] | None) -> bool:
    if not pos:
        return False
    return bool(pos.get("profit_trailing_active"))


def is_trailing_exit_decision(decision: dict[str, Any] | None) -> bool:
    if not decision:
        return False
    code = str(decision.get("reason_code") or "").strip().upper()
    if code == REASON_EXIT:
        return True
    evidence = str(decision.get("evidence") or "")
    return REASON_EXIT in evidence


def apply_profit_trailing_transition(
    pos: dict[str, Any],
    *,
    ticker: str,
    mark: float,
    average_cost: float | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """
    Mutate position trailing state prospectively (no price_high).

    Returns event describing activation / peak / exit_ready / hold.
    Does not sell; exit_ready=True means decision layer should emit SELL_PAPER.
    """
    stamp = now_iso or _now_iso()
    avg = _f(average_cost if average_cost is not None else pos.get("avg_price"))
    event: dict[str, Any] = {
        "ticker": str(ticker).upper(),
        "changed": False,
        "exit_ready": False,
        "trailing_active": bool(pos.get("profit_trailing_active")),
        "reason_code": None,
        "suppressed_price_high": True,
    }
    if _f(pos.get("shares")) <= 0:
        event["reject_reason"] = "no_shares"
        return event
    if not is_valid_trailing_mark(mark, pos=pos):
        event["reject_reason"] = "invalid_or_stale_mark"
        return event
    if avg <= 0.0:
        event["reject_reason"] = "invalid_average_cost"
        return event

    cid = ensure_position_cycle_id(pos, ticker, now_iso=stamp)
    event["position_cycle_id"] = cid
    profit_pct = compute_profit_pct(mark, avg)
    event["profit_pct"] = None if profit_pct is None else round(profit_pct, 10)
    event["mark"] = float(mark)
    event["average_cost"] = avg

    pos["profit_trailing_activation_threshold_pct"] = PAPER_PROFIT_TRAILING_ACTIVATION_PCT
    pos["profit_trailing_drawdown_pct"] = PAPER_PROFIT_TRAILING_DRAWDOWN_PCT
    pos["profit_trailing_last_valid_mark"] = float(mark)

    active = bool(pos.get("profit_trailing_active"))
    bootstrap_done = bool(pos.get("profit_trailing_bootstrap_completed"))

    # Prospective activation / one-shot bootstrap for already-profitable opens.
    if not active and profit_pct is not None and profit_pct >= PAPER_PROFIT_TRAILING_ACTIVATION_PCT:
        pos["profit_trailing_active"] = True
        pos["profit_trailing_activation_mark"] = float(mark)
        pos["profit_trailing_activation_timestamp"] = stamp
        pos["profit_trailing_peak_price"] = float(mark)
        pos["profit_trailing_peak_timestamp"] = stamp
        pos["profit_trailing_state_version"] = int(_f(pos.get("profit_trailing_state_version"))) + 1
        if not bootstrap_done:
            pos["profit_trailing_bootstrap_completed"] = True
            event["reason_code"] = REASON_BOOTSTRAP
            event["bootstrap"] = True
        else:
            event["reason_code"] = REASON_ACTIVATED
            event["bootstrap"] = False
        event["changed"] = True
        event["trailing_active"] = True
        event["peak_price"] = float(mark)
        event["exit_ready"] = False  # never sell on activation/bootstrap cycle
        return event

    if not active:
        event["reason_code"] = None
        event["trailing_active"] = False
        return event

    # Active: ratchet peak (monotonic), then evaluate exit.
    prev_peak = _f(pos.get("profit_trailing_peak_price"))
    if prev_peak <= 0.0:
        prev_peak = float(mark)
    new_peak = max(prev_peak, float(mark))
    if new_peak > prev_peak + 1e-15:
        pos["profit_trailing_peak_price"] = new_peak
        pos["profit_trailing_peak_timestamp"] = stamp
        pos["profit_trailing_state_version"] = int(_f(pos.get("profit_trailing_state_version"))) + 1
        event["changed"] = True
        event["reason_code"] = REASON_PEAK_UPDATED
    else:
        pos["profit_trailing_peak_price"] = new_peak
        event["reason_code"] = REASON_HOLD

    event["peak_price"] = new_peak
    event["trailing_active"] = True
    dd = compute_drawdown_from_peak(float(mark), new_peak)
    event["drawdown_from_peak"] = None if dd is None else round(dd, 10)
    if trailing_exit_triggered(float(mark), new_peak):
        event["exit_ready"] = True
        event["reason_code"] = REASON_EXIT
    return event


def sync_portfolio_profit_trailing(
    portfolio: dict[str, Any],
    *,
    now_iso: str | None = None,
) -> list[dict[str, Any]]:
    """Apply prospective trailing transitions for all open paper positions (in-memory)."""
    positions = portfolio.get("positions") or {}
    events: list[dict[str, Any]] = []
    if not isinstance(positions, dict):
        return events
    stamp = now_iso or _now_iso()
    for ticker, pos in list(positions.items()):
        if not isinstance(pos, dict):
            continue
        mark = pos.get("current_price") or pos.get("mark_price")
        if not is_valid_trailing_mark(mark, pos=pos):
            # Still ensure cycle id exists for open qty.
            if _f(pos.get("shares")) > 0 and not str(pos.get("position_cycle_id") or "").strip():
                ensure_position_cycle_id(pos, str(ticker), now_iso=stamp)
                events.append(
                    {
                        "ticker": str(ticker).upper(),
                        "changed": True,
                        "reason_code": None,
                        "cycle_id_only": True,
                    }
                )
            continue
        ev = apply_profit_trailing_transition(
            pos,
            ticker=str(ticker),
            mark=float(mark),
            average_cost=_f(pos.get("avg_price")),
            now_iso=stamp,
        )
        events.append(ev)
    return events


def revalidate_trailing_exit_at_fill(
    *,
    fill_mark: float,
    peak_price: float,
    trailing_active: bool,
    shares: float,
    position_cycle_id: str | None,
    decision_cycle_id: str | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "ok": False,
        "status": STATUS_SKIP_EXIT_INVALID,
        "reason_code": REASON_EXIT,
        "fill_mark": _f(fill_mark),
        "peak_price": _f(peak_price),
        "shares": _f(shares),
    }
    if _f(shares) <= 0:
        out["status"] = "SKIPPED_NO_POSITION"
        out["reject_reason"] = "no_open_quantity"
        return out
    if decision_cycle_id and position_cycle_id and str(decision_cycle_id) != str(position_cycle_id):
        out["reject_reason"] = "position_cycle_id_mismatch"
        return out
    if not trailing_active:
        out["reject_reason"] = "trailing_inactive"
        return out
    if not is_valid_trailing_mark(fill_mark):
        out["status"] = STATUS_SKIP_NO_MARK
        out["reject_reason"] = "invalid_fill_mark"
        return out
    if not is_valid_trailing_mark(peak_price):
        out["reject_reason"] = "invalid_peak"
        return out
    dd = compute_drawdown_from_peak(float(fill_mark), float(peak_price))
    out["drawdown_from_peak"] = dd
    if not trailing_exit_triggered(float(fill_mark), float(peak_price)):
        out["status"] = STATUS_SKIP_EXIT_INVALID
        out["reject_reason"] = "drawdown_no_longer_valid"
        return out
    out["ok"] = True
    out["status"] = "AUTHORIZED"
    return out


def suppress_soft_exit_if_trailing_active(
    action: str,
    *,
    trailing_active: bool,
    exit_ready: bool,
) -> tuple[str, str | None]:
    """When trailing owns profit exit, soft exits become HOLD (observability reason)."""
    if exit_ready:
        return action, None
    if trailing_active and action in SOFT_EXIT_ACTIONS:
        return "HOLD_PAPER", REASON_SOFT_SUPPRESSED
    return action, None


def load_pce_by_ticker(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Index PCE ticker rows for executable PAPER profit-protection wiring."""
    path = path or PCE_JSON
    if not path.is_file():
        return {}
    try:
        import json

        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in (doc or {}).get("tickers") or []:
        if isinstance(row, dict):
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                out[ticker] = row
    return out


def resolve_pce_protection_verdict(
    *,
    pce_row: dict[str, Any] | None,
    gii_row: dict[str, Any] | None,
) -> str | None:
    """Map PCE/GII protection observations to an executable PAPER verdict."""
    for source in (pce_row, gii_row):
        if not source:
            continue
        verdict = str(source.get("context_verdict") or source.get("pce_verdict") or "").strip().upper()
        if verdict in PCE_PROTECTION_VERDICTS:
            return verdict
    gii_row = gii_row or {}
    if str(gii_row.get("governor_recommendation") or "").strip().upper() in GII_TIGHTEN_GOVERNOR:
        return "CONTEXT_WEAKENING"
    if str(gii_row.get("recommended_shadow_strategy") or "").strip().upper() in GII_TIGHTEN_STRATEGIES:
        return "CONTEXT_WEAKENING"
    return None


def pce_protection_execution_eligible(
    *,
    pce_row: dict[str, Any] | None,
    gii_row: dict[str, Any] | None,
) -> bool:
    """True when existing PCE/GII protection should arm canonical PAPER trailing."""
    return resolve_pce_protection_verdict(pce_row=pce_row, gii_row=gii_row) is not None


def _effective_peak_price(
    pos: dict[str, Any],
    *,
    gii_row: dict[str, Any] | None,
    mark: float,
) -> float:
    avg = _f(pos.get("avg_price"))
    price_high = _f(pos.get("price_high"))
    high_pct = _f((gii_row or {}).get("high_pct"))
    gii_peak = avg * (1.0 + high_pct / 100.0) if avg > 0 and high_pct > 0 else 0.0
    candidates = [x for x in (mark, price_high, gii_peak) if is_finite_positive(x)]
    return max(candidates) if candidates else mark


def is_finite_positive(value: Any) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and x > 0.0


def apply_pce_profit_protection_wiring(
    pos: dict[str, Any],
    *,
    ticker: str,
    pce_row: dict[str, Any] | None,
    gii_row: dict[str, Any] | None,
    mark: float | None = None,
    now_iso: str | None = None,
) -> dict[str, Any]:
    """
    Arm canonical profit trailing when PCE/GII requests winner protection.

    Uses existing +5% activation / −2% drawdown thresholds. Peak is inferred from
    the best available causal mark (position price_high, current mark, GII high_pct).
    """
    stamp = now_iso or _now_iso()
    ticker = str(ticker).upper()
    event: dict[str, Any] = {
        "ticker": ticker,
        "applied": False,
        "pce_execution_eligible": False,
        "reason_code": None,
    }
    if _f(pos.get("shares")) <= 0:
        event["reject_reason"] = "flat_position"
        return event

    verdict = resolve_pce_protection_verdict(pce_row=pce_row, gii_row=gii_row)
    if not verdict:
        event["reject_reason"] = "no_pce_protection_verdict"
        return event
    event["pce_execution_eligible"] = True
    event["pce_verdict"] = verdict

    px = _f(mark if mark is not None else pos.get("current_price") or pos.get("mark_price"))
    if not is_valid_trailing_mark(px, pos=pos):
        event["reject_reason"] = "invalid_or_stale_mark"
        return event

    avg = _f(pos.get("avg_price"))
    if avg <= 0:
        event["reject_reason"] = "invalid_average_cost"
        return event

    peak_px = _effective_peak_price(pos, gii_row=gii_row, mark=px)
    peak_profit_pct = compute_profit_pct(peak_px, avg)
    if peak_profit_pct is None or peak_profit_pct < PAPER_PROFIT_TRAILING_ACTIVATION_PCT:
        event["reject_reason"] = "peak_below_activation_threshold"
        event["peak_profit_pct"] = peak_profit_pct
        return event

    cid = ensure_position_cycle_id(pos, ticker, now_iso=stamp)
    pos["profit_trailing_active"] = True
    pos["profit_trailing_activation_threshold_pct"] = PAPER_PROFIT_TRAILING_ACTIVATION_PCT
    pos["profit_trailing_drawdown_pct"] = PAPER_PROFIT_TRAILING_DRAWDOWN_PCT
    pos["profit_trailing_activation_mark"] = float(peak_px)
    pos["profit_trailing_activation_timestamp"] = stamp
    pos["profit_trailing_peak_price"] = float(peak_px)
    pos["profit_trailing_peak_timestamp"] = stamp
    pos["profit_trailing_last_valid_mark"] = float(px)
    pos["profit_trailing_bootstrap_completed"] = True
    pos["profit_trailing_pce_verdict"] = verdict
    pos["profit_trailing_state_version"] = int(_f(pos.get("profit_trailing_state_version"))) + 1
    pos["profit_trailing_pce_wired"] = True

    event.update(
        {
            "applied": True,
            "reason_code": REASON_PCE_PROTECTION_WIRED,
            "position_cycle_id": cid,
            "peak_price": float(peak_px),
            "mark": float(px),
            "peak_profit_pct": round(float(peak_profit_pct), 10),
            "trailing_active": True,
        }
    )
    return event


def wire_paper_profit_protection(
    portfolio: dict[str, Any],
    *,
    pce_by: dict[str, dict[str, Any]] | None = None,
    gii_by: dict[str, dict[str, Any]] | None = None,
    now_iso: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Connect PCE/GII winner-protection signals to canonical trailing state.

    Returns (events, portfolio_changed).
    """
    pce_by = pce_by if pce_by is not None else load_pce_by_ticker()
    gii_by = gii_by or {}
    positions = portfolio.get("positions") or {}
    events: list[dict[str, Any]] = []
    changed = False
    if not isinstance(positions, dict):
        return events, False

    for ticker, pos in list(positions.items()):
        if not isinstance(pos, dict):
            continue
        ticker_u = str(ticker).upper()
        ev = apply_pce_profit_protection_wiring(
            pos,
            ticker=ticker_u,
            pce_row=pce_by.get(ticker_u),
            gii_row=gii_by.get(ticker_u),
            now_iso=now_iso,
        )
        events.append(ev)
        if ev.get("applied"):
            changed = True

    if changed:
        sync_portfolio_profit_trailing(portfolio, now_iso=now_iso)
    return events, changed
