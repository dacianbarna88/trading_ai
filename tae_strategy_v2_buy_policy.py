#!/usr/bin/env python3
"""
Strategy V2 BUY Policy — PAPER / isolated replay only.

Produces deterministic OPEN_CYCLE | ADD_TRANCHE | HOLD | STOP_ACCUMULATION.

Economic policy (buy_policy.v2_price_driven):
  - OPEN_CYCLE: company quality gate (score/thesis/PDE) unchanged.
  - ADD_TRANCHE: after OPEN, price/budget/cash/state only — current score,
    thesis WATCH, or absent BUY PDE must not veto planned tranches.
  - ACCUMULATION_STOPPED: structural reasons only (max tranches, budget,
    hard-risk critical, invalid mark/state) — not score/thesis deterioration.

Does not auto-activate (STRATEGY_V2_ENABLED default false).
Does not implement SELL V2 / CLOSE_CYCLE automation / live_bot changes.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tae_strategy_v2_config import (
    is_strategy_v2_enabled,
    load_strategy_v2_config,
)
from tae_strategy_v2_foundation import (
    ADD_ALLOWED,
    STRATEGY_VERSION,
    build_cycle,
    build_tranche,
    build_v2_decision_payload,
    evaluate_accumulation_reactivation,
    find_open_cycle_for_ticker,
    is_finite_positive,
    new_execution_id,
)

POLICY_VERSION = "buy_policy.v2_price_driven"

# Explicit ADD_TRANCHE profit-context gate outcomes (tranche 2+ only).
V2_TRANCHE_ALLOWED = "V2_TRANCHE_ALLOWED"
V2_TRANCHE_BLOCKED_MARKET = "V2_TRANCHE_BLOCKED_MARKET"
V2_TRANCHE_BLOCKED_RELATIVE_STRENGTH = "V2_TRANCHE_BLOCKED_RELATIVE_STRENGTH"
V2_TRANCHE_BLOCKED_COMPANY_RISK = "V2_TRANCHE_BLOCKED_COMPANY_RISK"
V2_TRANCHE_BLOCKED_FALLING_KNIFE = "V2_TRANCHE_BLOCKED_FALLING_KNIFE"
V2_TRANCHE_BLOCKED_CAPITAL = "V2_TRANCHE_BLOCKED_CAPITAL"

PCE_JSON = Path("tae_profit_context_engine.json")
_TRANCHE_GATE_CODES = frozenset(
    {
        V2_TRANCHE_ALLOWED,
        V2_TRANCHE_BLOCKED_MARKET,
        V2_TRANCHE_BLOCKED_RELATIVE_STRENGTH,
        V2_TRANCHE_BLOCKED_COMPANY_RISK,
        V2_TRANCHE_BLOCKED_FALLING_KNIFE,
        V2_TRANCHE_BLOCKED_CAPITAL,
    }
)

FAVORABLE_PDE_ACTIONS = frozenset({"BUY_PAPER", "BUY", "STRONG BUY", "STRONG_BUY"})
EXIT_REQUIRED_ACTIONS = frozenset({"SELL_PAPER", "SELL"})

REASON_OPEN = "OPEN_VALID_CANDIDATE"
REASON_ADD = "ADD_PRICE_STEP_REACHED"
REASON_HOLD_STEP = "HOLD_PRICE_STEP_NOT_REACHED"
REASON_HOLD_SIGNAL = "HOLD_SIGNAL_NOT_CONFIRMED"
REASON_HOLD_WATCH = "HOLD_THESIS_WATCH"
REASON_BLOCK_UNKNOWN = "BLOCKED_THESIS_UNKNOWN"
REASON_BLOCK_MARK = "BLOCKED_INVALID_MARK"
REASON_BLOCK_BUDGET = "BLOCKED_INSUFFICIENT_BUDGET"
REASON_BLOCK_DUP = "BLOCKED_DUPLICATE_DECISION"
REASON_STOP_THESIS = "STOP_THESIS_INVALID"
REASON_STOP_HR = "STOP_HARD_RISK"
REASON_STOP_FULL = "STOP_FULLY_ALLOCATED"
REASON_STOP_MAX = "STOP_MAX_TRANCHES"
REASON_STOP_DATA = "STOP_INVALID_DATA"
REASON_STOP_STATE = "STOP_CYCLE_STATE"
REASON_DISABLED = "BLOCKED_STRATEGY_V2_DISABLED"
REASON_SKIP = "SKIP_NO_CYCLE_NO_ENTRY"
REASON_BLOCK_DECISION_BRAIN_SKIP = "BLOCKED_DECISION_BRAIN_SKIP"


def _s(v: Any) -> str:
    return str(v or "").strip()


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        out = float(v)
        if math.isnan(out) or math.isinf(out):
            return float("nan")
        return out
    except (TypeError, ValueError):
        return float(default)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


@dataclass
class BuyPolicyInput:
    """Canonical ex-ante snapshot. Missing fields must be explicit UNKNOWN/False."""

    ticker: str
    timestamp: str
    mark_price: float
    mark_freshness: str = "UNKNOWN"
    mark_age_seconds: float = float("nan")
    score: float | None = None
    confidence: float | None = None
    pde_action: str = "UNKNOWN"
    hard_risk_active: bool = False
    hard_risk_status: str = "UNKNOWN"
    session_valid: bool = True
    data_fresh: bool = False
    candidate_eligible: bool | None = None  # None → UNKNOWN eligibility
    held: bool = False
    quantity: float = 0.0
    average_cost: float = 0.0
    currency: str = "USD"
    fx_rate: float = 1.0
    company_budget: float | None = None  # None → derive from cash/config
    allocation_hint: float | None = None
    cash: float = 0.0
    cycle: dict[str, Any] | None = None
    decision_id: str | None = None
    seen_decision_ids: list[str] = field(default_factory=list)
    max_tranches_override: int | None = None
    # Existing PCE / hard-risk context for ADD_TRANCHE profit gate (optional; UNKNOWN = missing).
    market_regime: str = "UNKNOWN"
    market_context: str = "UNKNOWN"
    trend_context: str = "UNKNOWN"
    momentum_context: str = "UNKNOWN"
    sector_context: str = "UNKNOWN"
    volatility_context: str = "UNKNOWN"
    relative_strength_state: str = "UNKNOWN"
    decline_class: str = "UNCLASSIFIED"
    context_verdict: str = "UNKNOWN"
    company_risk_blocked: bool = False
    quarantined: bool = False
    position_drawdown_pct: float | None = None
    profit_context_score: float | None = None
    hard_risk_class: str = "SAFE"
    allow_position_growth: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_company_budget(
    *,
    cash: float,
    cfg: dict[str, Any],
    company_budget: float | None = None,
    allocation_hint: float | None = None,
) -> float:
    """Configurable budget. Does not hardcode a universal notional as the budget itself."""
    lo = float(cfg["minimum_company_budget"])
    hi = float(cfg["maximum_company_budget"])
    reserve = float(cfg["MIN_CASH_RESERVE_USD"])
    if company_budget is not None and is_finite_positive(float(company_budget)):
        return round(_clamp(float(company_budget), lo, hi), 6)
    if allocation_hint is not None and is_finite_positive(float(allocation_hint)):
        return round(_clamp(float(allocation_hint), lo, hi), 6)
    investable = max(0.0, float(cash) - reserve)
    # Minimal documented rule: up to 50% of investable cash, clamped to [min, max].
    derived = investable * 0.5
    return round(_clamp(derived, lo, hi), 6)


def proposed_tranche_value_usd(
    *,
    company_budget: float,
    budget_remaining: float,
    cfg: dict[str, Any],
) -> float:
    frac = float(cfg["tranche_fraction"])
    raw = float(company_budget) * frac
    capped = min(raw, float(budget_remaining), float(cfg["max_order_value_usd"]))
    # Never round up past remaining
    if capped + 1e-9 < float(cfg["min_order_value_usd"]):
        # If remaining cannot fund min order, return remaining (caller may block)
        return round(max(0.0, min(capped, float(budget_remaining))), 6)
    return round(min(capped, float(budget_remaining)), 6)


def price_drop_reached(
    *,
    mark_price: float,
    last_tranche_price: float,
    drop_pct: float,
) -> bool:
    if not is_finite_positive(mark_price) or not is_finite_positive(last_tranche_price):
        return False
    threshold = float(last_tranche_price) * (1.0 - float(drop_pct))
    return float(mark_price) <= threshold + 1e-12


def next_tranche_reference_price(last_tranche_price: float | None, drop_pct: float) -> float | None:
    if last_tranche_price is None or not is_finite_positive(float(last_tranche_price)):
        return None
    return round(float(last_tranche_price) * (1.0 - float(drop_pct)), 6)


def load_profit_context_document(path: Path | None = None) -> dict[str, Any] | None:
    """Read existing PCE SSOT (no new engine)."""
    p = Path(path) if path is not None else PCE_JSON
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def extract_profit_context_for_ticker(
    pce: dict[str, Any] | None,
    ticker: str,
) -> dict[str, Any]:
    """Map existing PCE market_snapshot + ticker row → BuyPolicyInput context fields."""
    ticker_u = _s(ticker).upper()
    snap = (pce or {}).get("market_snapshot") or {}
    regime = _s(((snap.get("regime") or {}).get("regime"))).upper() or "UNKNOWN"
    row = None
    for item in (pce or {}).get("tickers") or []:
        if _s((item or {}).get("ticker")).upper() == ticker_u:
            row = item
            break
    factors = (row or {}).get("context_factors") or {}
    return {
        "market_regime": regime,
        "market_context": _s(factors.get("market_context") or "UNKNOWN").upper() or "UNKNOWN",
        "trend_context": _s(factors.get("trend_context") or "UNKNOWN").upper() or "UNKNOWN",
        "momentum_context": _s(factors.get("momentum_context") or "UNKNOWN").upper() or "UNKNOWN",
        "sector_context": _s(factors.get("sector_context") or "UNKNOWN").upper() or "UNKNOWN",
        "volatility_context": _s(factors.get("volatility_context") or "UNKNOWN").upper() or "UNKNOWN",
        "context_verdict": _s((row or {}).get("context_verdict") or "UNKNOWN").upper() or "UNKNOWN",
        "profit_context_score": (
            float(row["profit_context_score"])
            if row is not None and row.get("profit_context_score") is not None
            else None
        ),
        "position_drawdown_pct": (
            float(row["drawdown"]) if row is not None and row.get("drawdown") is not None else None
        ),
        # Derive RS state from existing PCE factors (stock weak while market supportive).
        "relative_strength_state": _derive_relative_strength_state(factors, regime),
        "decline_class": _derive_decline_class(factors, row),
        "quarantined": _s((row or {}).get("context_verdict")).upper() == "PROTECT_NOW"
        and _s(factors.get("volatility_context")).upper() == "VOLATILITY_HIGH",
        "company_risk_blocked": _s((row or {}).get("context_verdict")).upper() == "PROTECT_NOW",
    }


def _derive_relative_strength_state(factors: dict[str, Any], regime: str) -> str:
    mom = _s(factors.get("momentum_context")).upper()
    trend = _s(factors.get("trend_context")).upper()
    mkt = _s(factors.get("market_context")).upper()
    regime_u = _s(regime).upper()
    if mom == "MOMENTUM_WEAK" and trend == "TREND_WEAK" and (
        mkt == "MARKET_SUPPORTIVE" or regime_u == "BULL"
    ):
        return "SEVERE_DETERIORATION"
    if mom == "MOMENTUM_WEAK" and mkt == "MARKET_SUPPORTIVE":
        return "DETERIORATING"
    if mom == "MOMENTUM_STRONG":
        return "STABLE"
    return "UNKNOWN"


def _derive_decline_class(factors: dict[str, Any], row: dict[str, Any] | None) -> str:
    """Map PCE labels → research decline classes without importing research engine."""
    vol = _s(factors.get("volatility_context")).upper()
    mom = _s(factors.get("momentum_context")).upper()
    trend = _s(factors.get("trend_context")).upper()
    verdict = _s((row or {}).get("context_verdict")).upper()
    dd = abs(_f((row or {}).get("drawdown"))) if row else 0.0
    if vol == "VOLATILITY_HIGH" and mom == "MOMENTUM_WEAK" and (trend == "TREND_WEAK" or dd >= 5.0):
        return "FALLING_KNIFE"
    if verdict == "PROTECT_NOW" and trend == "TREND_WEAK" and mom == "MOMENTUM_WEAK":
        return "COMPANY_SPECIFIC_DECLINE"
    if trend == "TREND_WEAK" and vol in {"VOLATILITY_HIGH", "VOLATILITY_ELEVATED"} and dd >= 5.0:
        return "STRUCTURAL_DECLINE"
    return "UNCLASSIFIED"


def apply_profit_context_to_input(inp: BuyPolicyInput, fields: dict[str, Any] | None) -> BuyPolicyInput:
    """Mutate BuyPolicyInput with PCE-derived fields (existing signals only)."""
    if not fields:
        return inp
    for key in (
        "market_regime",
        "market_context",
        "trend_context",
        "momentum_context",
        "sector_context",
        "volatility_context",
        "relative_strength_state",
        "decline_class",
        "context_verdict",
    ):
        if key in fields and fields[key] is not None:
            setattr(inp, key, fields[key])
    if "profit_context_score" in fields:
        inp.profit_context_score = fields.get("profit_context_score")
    if "position_drawdown_pct" in fields:
        inp.position_drawdown_pct = fields.get("position_drawdown_pct")
    if "quarantined" in fields:
        inp.quarantined = bool(fields.get("quarantined"))
    if "company_risk_blocked" in fields:
        inp.company_risk_blocked = bool(fields.get("company_risk_blocked"))
    return inp


def evaluate_v2_tranche_profit_gate(
    inp: BuyPolicyInput,
    *,
    cfg: dict[str, Any] | None = None,
    proposed_value: float | None = None,
) -> dict[str, Any]:
    """
    Profit-first gate for ADD_TRANCHE (after first fill only).

    Uses existing PCE / hard-risk fields on BuyPolicyInput — no new scoring engine.
    """
    cfg = cfg or load_strategy_v2_config()
    tol = float(cfg["MONEY_TOLERANCE_USD"])
    detail: list[str] = []

    regime = _s(inp.market_regime).upper()
    if not regime or regime in {"UNKNOWN", "N/A", "NONE"}:
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_MARKET, "detail": "market_regime_unavailable"}
    if "BEAR" in regime or regime in {"RISK_OFF", "GLOBAL_RISK_OFF"}:
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_MARKET, "detail": f"market_regime={regime}"}

    decline = _s(inp.decline_class).upper()
    if inp.quarantined or decline == "FALLING_KNIFE":
        return {
            "ok": False,
            "code": V2_TRANCHE_BLOCKED_FALLING_KNIFE,
            "detail": "quarantined" if inp.quarantined else decline,
        }

    if inp.company_risk_blocked or decline in {"COMPANY_SPECIFIC_DECLINE", "STRUCTURAL_DECLINE"}:
        return {
            "ok": False,
            "code": V2_TRANCHE_BLOCKED_COMPANY_RISK,
            "detail": decline if decline != "UNCLASSIFIED" else "company_risk_blocked",
        }

    trend = _s(inp.trend_context).upper()
    if trend in {"TREND_WEAK", "TREND_BROKEN", "TREND_RUPTURED"}:
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_COMPANY_RISK, "detail": f"trend={trend}"}

    sector = _s(inp.sector_context).upper()
    if sector and sector not in {"UNKNOWN", "UNKNOWN_SECTOR", ""} and sector == "SECTOR_LAGGING":
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_COMPANY_RISK, "detail": "sector_severe_deterioration"}

    rs = _s(inp.relative_strength_state).upper()
    if rs in {"SEVERE_DETERIORATION", "RELATIVE_STRENGTH_DECLINE"}:
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_RELATIVE_STRENGTH, "detail": f"rs={rs}"}
    # Severe RS: weak momentum while market still supportive/bull (stock lagging benchmark).
    mom = _s(inp.momentum_context).upper()
    mkt_ctx = _s(inp.market_context).upper()
    if mom == "MOMENTUM_WEAK" and (mkt_ctx == "MARKET_SUPPORTIVE" or regime == "BULL") and trend in {
        "TREND_WEAK",
        "TREND_NEUTRAL",
    }:
        # Only block when RS explicitly severe OR (weak mom + supportive market + weak/neutral trend)
        # TREND_WEAK already blocked above; TREND_NEUTRAL + MOMENTUM_WEAK + BULL = RS lag
        if trend == "TREND_NEUTRAL":
            return {
                "ok": False,
                "code": V2_TRANCHE_BLOCKED_RELATIVE_STRENGTH,
                "detail": "momentum_weak_vs_supportive_market",
            }

    hr_cls = _s(inp.hard_risk_class).upper()
    if not inp.allow_position_growth or hr_cls in {"CRITICAL_HARD_RISK", "DATA_SAFETY_BLOCK"}:
        return {
            "ok": False,
            "code": V2_TRANCHE_BLOCKED_COMPANY_RISK,
            "detail": f"hard_risk_blocks_growth class={hr_cls or 'n/a'}",
        }
    if inp.hard_risk_active and _s(inp.hard_risk_status).upper() not in {
        "OK",
        "STRATEGY_STOP_V1_ONLY",
        "UNKNOWN",
        "",
    }:
        return {
            "ok": False,
            "code": V2_TRANCHE_BLOCKED_COMPANY_RISK,
            "detail": f"hard_risk_status={inp.hard_risk_status}",
        }

    # Capital: company budget remaining + cash reserve (same rules as buy policy).
    cycle = inp.cycle or {}
    rem = _f(cycle.get("budget_remaining"))
    prop = proposed_value
    if prop is None:
        prop = proposed_tranche_value_usd(
            company_budget=_f(cycle.get("company_budget") or inp.company_budget),
            budget_remaining=rem if rem or rem == 0.0 else _f(inp.company_budget),
            cfg=cfg,
        )
    if prop <= 0 or prop + tol < float(cfg["min_order_value_usd"]):
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_CAPITAL, "detail": "budget_or_min_order"}
    if inp.cash - float(prop) < float(cfg["MIN_CASH_RESERVE_USD"]) - tol:
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_CAPITAL, "detail": "cash_reserve"}
    budget_max = _f(cycle.get("company_budget") or inp.company_budget)
    used = _f(cycle.get("budget_used"))
    if budget_max > 0 and used + float(prop) > budget_max + tol:
        return {"ok": False, "code": V2_TRANCHE_BLOCKED_CAPITAL, "detail": "company_budget_cap"}

    detail.append(f"regime={regime}")
    return {"ok": True, "code": V2_TRANCHE_ALLOWED, "detail": ";".join(detail) or "pass"}


def classify_thesis(inp: BuyPolicyInput, cfg: dict[str, Any]) -> tuple[str, str]:
    """Map existing signals → VALID | WATCH | INVALID | UNKNOWN. No new fundamentals."""
    mark_ok = (
        is_finite_positive(inp.mark_price)
        and _s(inp.mark_freshness).upper() == "FRESH"
        and inp.data_fresh
        and (not math.isnan(inp.mark_age_seconds))
        and float(inp.mark_age_seconds) <= float(cfg["MARK_MAX_AGE_SECONDS"])
    )
    # Price −3%/−5% statuses are informational for V2; only non-price hard_risk_active
    # (exposure/gap) forces INVALID thesis.
    hr_status_u = _s(inp.hard_risk_status).upper()
    price_dd_status = hr_status_u in {
        "STOP_LOSS_BREACHED",
        "CRITICAL_LOSS",
        "HARD_CRITICAL_STOP_-5",
        "HARD_STOP_LOSS_-3",
        "PRICE_DRAWDOWN_INFORMATIONAL",
        "STRATEGY_STOP_V1_ONLY",
    }
    hr_critical = bool(inp.hard_risk_active) and not price_dd_status
    pde = _s(inp.pde_action).upper()
    exit_required = pde in EXIT_REQUIRED_ACTIONS or "HARD RISK" in pde

    if hr_critical or exit_required:
        return "INVALID", REASON_STOP_HR if hr_critical else REASON_STOP_THESIS
    if not inp.session_valid:
        return "INVALID", REASON_STOP_DATA
    if not mark_ok:
        # Stale/invalid marks: cannot evaluate → UNKNOWN (or INVALID if held and persistent)
        if inp.held or inp.cycle:
            return "INVALID", REASON_STOP_DATA
        return "UNKNOWN", REASON_BLOCK_MARK

    eligible = inp.candidate_eligible
    if eligible is None and inp.score is None and pde in {"UNKNOWN", ""}:
        return "UNKNOWN", REASON_BLOCK_UNKNOWN

    favorable = pde in FAVORABLE_PDE_ACTIONS or (
        inp.score is not None and is_finite_positive(float(inp.score)) and float(inp.score) >= 80.0
    )
    if eligible is False and not inp.cycle:
        return "INVALID", REASON_STOP_THESIS
    if favorable and eligible is not False and mark_ok and not hr_critical:
        return "VALID", REASON_OPEN if not inp.cycle else REASON_ADD
    if (eligible is True or inp.held or inp.cycle) and not hr_critical and mark_ok:
        return "WATCH", REASON_HOLD_WATCH
    return "UNKNOWN", REASON_BLOCK_UNKNOWN


def _base_payload(
    *,
    action: str,
    reason_code: str,
    thesis: str,
    inp: BuyPolicyInput,
    cfg: dict[str, Any],
    cycle: dict[str, Any] | None,
    proposed_value: float | None = None,
    source_note: str = "",
) -> dict[str, Any]:
    cyc = cycle or {}
    last_px = cyc.get("last_tranche_price")
    drop = float(cfg["add_tranche_drop_pct"])
    next_ref = next_tranche_reference_price(
        float(last_px) if last_px is not None else None,
        drop,
    )
    budget = _f(cyc.get("company_budget"), inp.company_budget or 0.0)
    used = _f(cyc.get("budget_used"))
    rem = _f(cyc.get("budget_remaining"), budget - used if budget else 0.0)
    return {
        "strategy_version": STRATEGY_VERSION,
        "policy_version": str(cfg.get("policy_version") or POLICY_VERSION),
        "cycle_id": cyc.get("cycle_id"),
        "ticker": _s(inp.ticker).upper(),
        "action": action,
        "thesis_state": thesis,
        "reason_code": reason_code,
        "decision_id": inp.decision_id or f"V2POL-{_s(inp.ticker).upper()}-{uuid.uuid4().hex[:10].upper()}",
        "timestamp": inp.timestamp,
        "mark_price": inp.mark_price,
        "company_budget": budget,
        "budget_used": used,
        "budget_remaining": rem,
        "tranche_count": int(cyc.get("tranche_count") or 0),
        "max_tranches": int(cyc.get("max_tranches") or cfg["max_tranches"]),
        "proposed_tranche_value": proposed_value,
        "last_tranche_price": last_px,
        "next_tranche_reference_price": next_ref,
        "source_pde_action": inp.pde_action,
        "source_score": inp.score,
        "source_confidence": inp.confidence,
        "hard_risk_state": inp.hard_risk_status,
        "candidate_eligible": inp.candidate_eligible,
        "data_freshness_state": inp.mark_freshness,
        "note": source_note,
        "tranche_gate_code": None,
        "active": action in {"OPEN_CYCLE", "ADD_TRANCHE", "HOLD", "STOP_ACCUMULATION"},
        "capital_mutating": action in {"OPEN_CYCLE", "ADD_TRANCHE"},
    }


def evaluate_buy_policy(
    inp: BuyPolicyInput,
    *,
    cfg: dict[str, Any] | None = None,
    enabled: bool | None = None,
    store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Deterministic V2 BUY policy decision.
    When enabled is False (default via config), returns inactive blocked payload.
    """
    cfg = cfg or load_strategy_v2_config()
    flag = is_strategy_v2_enabled(override=enabled) if enabled is not None else is_strategy_v2_enabled()
    ticker = _s(inp.ticker).upper()
    decision_id = inp.decision_id or f"V2POL-{ticker}-{uuid.uuid4().hex[:10].upper()}"
    inp.decision_id = decision_id

    if not flag:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_DISABLED,
            thesis="UNKNOWN",
            inp=inp,
            cfg=cfg,
            cycle=inp.cycle,
        )
        out["active"] = False
        out["capital_mutating"] = False
        return out

    if decision_id in set(inp.seen_decision_ids or []):
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_BLOCK_DUP,
            thesis="UNKNOWN",
            inp=inp,
            cfg=cfg,
            cycle=inp.cycle,
        )
        out["active"] = False
        return out

    cycle = inp.cycle
    if store and not cycle:
        cycle = find_open_cycle_for_ticker(store, ticker)

    thesis, thesis_reason = classify_thesis(inp, cfg)

    # Mark validity for entry
    mark_ok = (
        is_finite_positive(inp.mark_price)
        and _s(inp.mark_freshness).upper() == "FRESH"
        and inp.data_fresh
        and (not math.isnan(_f(inp.mark_age_seconds)))
        and _f(inp.mark_age_seconds) <= float(cfg["MARK_MAX_AGE_SECONDS"])
    )

    # Active cycle → structural stops + price-driven ADD (signal reevaluation is audit-only)
    if cycle:
        status = _s(cycle.get("status"))
        tc = int(cycle.get("tranche_count") or 0)
        mx = int(cycle.get("max_tranches") or cfg["max_tranches"])
        rem = _f(cycle.get("budget_remaining"))
        tol = float(cfg["MONEY_TOLERANCE_USD"])
        open_thesis_snapshot = cycle.get("open_thesis_state") or cycle.get("thesis_state")

        # Structural integrity only — score/WATCH/PDE/price% hard-risk must not STOP after OPEN.
        # Price −5%/−3% is audit-only; hard_risk_active is reserved for non-price critical.
        if inp.hard_risk_active and _s(inp.hard_risk_status).upper() not in {
            "CRITICAL_LOSS",
            "HARD_CRITICAL_STOP_-5",
            "PRICE_DRAWDOWN_INFORMATIONAL",
            "STRATEGY_STOP_V1_ONLY",
            "STOP_LOSS_BREACHED",
            "HARD_STOP_LOSS_-3",
            "OK",
            "",
        }:
            return _base_payload(
                action="STOP_ACCUMULATION",
                reason_code=REASON_STOP_HR,
                thesis="INVALID",
                inp=inp,
                cfg=cfg,
                cycle=cycle,
                source_note=(
                    f"non_price_hard_risk status={inp.hard_risk_status}; "
                    f"open_thesis_snapshot={open_thesis_snapshot}"
                ),
            )
        if not mark_ok:
            return _base_payload(
                action="STOP_ACCUMULATION",
                reason_code=REASON_STOP_DATA,
                thesis="INVALID",
                inp=inp,
                cfg=cfg,
                cycle=cycle,
                source_note=f"open_thesis_snapshot={open_thesis_snapshot}",
            )
        if rem <= tol or status == "FULLY_ALLOCATED":
            return _base_payload(
                action="STOP_ACCUMULATION",
                reason_code=REASON_STOP_FULL,
                thesis=thesis if thesis != "INVALID" else "WATCH",
                inp=inp,
                cfg=cfg,
                cycle=cycle,
            )
        if tc >= mx:
            return _base_payload(
                action="STOP_ACCUMULATION",
                reason_code=REASON_STOP_MAX,
                thesis=thesis if thesis != "INVALID" else "WATCH",
                inp=inp,
                cfg=cfg,
                cycle=cycle,
            )
        if status == "ACCUMULATION_STOPPED":
            reactivation = evaluate_accumulation_reactivation(cycle, mark_ok=mark_ok)
            if reactivation.get("action") == "STOP":
                return _base_payload(
                    action="STOP_ACCUMULATION",
                    reason_code=_s(reactivation.get("reason_code")) or REASON_STOP_STATE,
                    thesis=thesis,
                    inp=inp,
                    cfg=cfg,
                    cycle=reactivation.get("cycle") or cycle,
                )
            if reactivation.get("action") == "REACTIVATED":
                cycle = reactivation["cycle"]
                status = _s(cycle.get("status"))
        if status in {"ACCUMULATION_STOPPED", "CLOSED", "BLOCKED", "CLOSING"}:
            return _base_payload(
                action="STOP_ACCUMULATION",
                reason_code=REASON_STOP_STATE,
                thesis=thesis,
                inp=inp,
                cfg=cfg,
                cycle=cycle,
            )
        if status not in ADD_ALLOWED:
            return _base_payload(
                action="HOLD",
                reason_code=REASON_STOP_STATE,
                thesis=thesis,
                inp=inp,
                cfg=cfg,
                cycle=cycle,
            )

        # Price-driven ADD: log current thesis/score/PDE but do not veto.
        last_px = _f(cycle.get("last_tranche_price"))
        drop = float(cfg["add_tranche_drop_pct"])
        if not price_drop_reached(mark_price=inp.mark_price, last_tranche_price=last_px, drop_pct=drop):
            out = _base_payload(
                action="HOLD",
                reason_code=REASON_HOLD_STEP,
                thesis=thesis,
                inp=inp,
                cfg=cfg,
                cycle=cycle,
                source_note=(
                    f"price_driven_add; signal_observation thesis={thesis} "
                    f"score={inp.score} pde={inp.pde_action}; "
                    f"open_thesis_snapshot={open_thesis_snapshot}"
                ),
            )
            return out

        prop = proposed_tranche_value_usd(
            company_budget=_f(cycle.get("company_budget")),
            budget_remaining=rem,
            cfg=cfg,
        )
        if prop <= 0 or prop + tol < float(cfg["min_order_value_usd"]):
            out = _base_payload(
                action="STOP_ACCUMULATION" if rem <= tol else "HOLD",
                reason_code=REASON_STOP_FULL if rem <= tol else V2_TRANCHE_BLOCKED_CAPITAL,
                thesis=thesis,
                inp=inp,
                cfg=cfg,
                cycle=cycle,
                proposed_value=prop,
            )
            out["tranche_gate_code"] = V2_TRANCHE_BLOCKED_CAPITAL
            return out
        if inp.cash - prop < float(cfg["MIN_CASH_RESERVE_USD"]) - tol:
            out = _base_payload(
                action="HOLD",
                reason_code=V2_TRANCHE_BLOCKED_CAPITAL,
                thesis=thesis,
                inp=inp,
                cfg=cfg,
                cycle=cycle,
                proposed_value=prop,
            )
            out["tranche_gate_code"] = V2_TRANCHE_BLOCKED_CAPITAL
            return out

        # Profit-context gate is observational only under price-driven accumulation.
        # Temporary market/signal deterioration must not block or stop ADD.
        out = _base_payload(
            action="ADD_TRANCHE",
            reason_code=REASON_ADD,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=cycle,
            proposed_value=prop,
            source_note=(
                f"price_driven_add; signal_observation thesis={thesis} "
                f"score={inp.score} pde={inp.pde_action}; "
                f"open_thesis_snapshot={open_thesis_snapshot}; "
                f"thesis_reason={thesis_reason}"
            ),
        )
        out["tranche_gate_code"] = REASON_ADD
        out["add_authority"] = "PRICE_BUDGET_STATE"
        out["signal_reevaluation_blocks_add"] = False
        return out

    # No active cycle → OPEN or skip
    if inp.hard_risk_active:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_STOP_HR,
            thesis="INVALID",
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    if not mark_ok:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_BLOCK_MARK,
            thesis=thesis if thesis in {"UNKNOWN", "INVALID"} else "UNKNOWN",
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    if thesis == "UNKNOWN" and cfg.get("thesis_unknown_blocks_entry", True):
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_BLOCK_UNKNOWN,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    if thesis == "INVALID":
        out = _base_payload(
            action="SKIP",
            reason_code=thesis_reason if thesis_reason in {
                REASON_STOP_HR, REASON_STOP_THESIS, REASON_STOP_DATA
            } else REASON_STOP_THESIS,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    if thesis != "VALID":
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_HOLD_SIGNAL,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    if inp.candidate_eligible is False:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_STOP_THESIS,
            thesis="INVALID",
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    favorable = _s(inp.pde_action).upper() in FAVORABLE_PDE_ACTIONS or (
        inp.score is not None and float(inp.score) >= 80.0
    )
    if not favorable:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_HOLD_SIGNAL,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out
    if store and find_open_cycle_for_ticker(store, ticker):
        # Should have been caught via cycle load; safety
        cyc = find_open_cycle_for_ticker(store, ticker)
        return _base_payload(
            action="HOLD",
            reason_code=REASON_STOP_STATE,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=cyc,
        )

    budget = resolve_company_budget(
        cash=inp.cash,
        cfg=cfg,
        company_budget=inp.company_budget,
        allocation_hint=inp.allocation_hint,
    )
    if not is_finite_positive(budget):
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_BLOCK_BUDGET,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
        )
        out["active"] = False
        return out

    prop = proposed_tranche_value_usd(
        company_budget=budget,
        budget_remaining=budget,
        cfg=cfg,
    )
    if prop < float(cfg["min_order_value_usd"]) - 1e-9:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_BLOCK_BUDGET,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
            proposed_value=prop,
        )
        out["active"] = False
        return out
    if inp.cash - prop < float(cfg["MIN_CASH_RESERVE_USD"]) - 1e-9:
        out = _base_payload(
            action="SKIP",
            reason_code=REASON_BLOCK_BUDGET,
            thesis=thesis,
            inp=inp,
            cfg=cfg,
            cycle=None,
            proposed_value=prop,
        )
        out["active"] = False
        return out

    # Binding Decision Brain SKIP gate — OPEN only (ADD path never reaches here).
    try:
        from tae_paper_execution import (
            BLOCK_REASON_DECISION_BRAIN_SKIP,
            append_decision_brain_skip_block_event,
            build_decision_brain_skip_attribution,
            evaluate_decision_brain_skip_new_entry_gate,
        )

        db_gate = evaluate_decision_brain_skip_new_entry_gate(
            action="OPEN_CYCLE",
            is_new_position=True,
            ticker=ticker,
            decision={
                "decision_id": decision_id,
                "ticker": ticker,
                "action": "OPEN_CYCLE",
                "strategy_id": "V2",
                "decision_brain_verdict": inp.pde_action,
                "source_pde_action": inp.pde_action,
                "score": inp.score,
                "confidence": inp.confidence,
                "timestamp": inp.timestamp,
            },
            explicit_verdict=inp.pde_action,
            entry_kind="OPEN",
            strategy_id="V2",
        )
        if db_gate.get("blocked"):
            out = _base_payload(
                action="SKIP",
                reason_code=REASON_BLOCK_DECISION_BRAIN_SKIP,
                thesis=thesis,
                inp=inp,
                cfg=cfg,
                cycle=None,
                proposed_value=prop,
            )
            out["active"] = False
            out["capital_mutating"] = False
            out["decision_brain_skip_gate"] = db_gate
            out["block_reason"] = BLOCK_REASON_DECISION_BRAIN_SKIP
            out["economic_class"] = "ENTRY_BLOCKED_BY_DECISION_BRAIN_SKIP"
            out["final_action"] = "BLOCKED_DECISION_BRAIN_SKIP"
            attr = build_decision_brain_skip_attribution(
                gate=db_gate,
                decision={
                    "decision_id": decision_id,
                    "ticker": ticker,
                    "action": "OPEN_CYCLE",
                    "strategy_id": "V2",
                    "score": inp.score,
                    "confidence": inp.confidence,
                    "source_pde_action": inp.pde_action,
                    "timestamp": inp.timestamp,
                },
                strategy_id="V2",
                mark_price=inp.mark_price if inp.mark_price and inp.mark_price > 0 else None,
                capital_not_deployed=prop,
            )
            # V2 cohort journal under parallel paper path when available; else canonical.
            append_decision_brain_skip_block_event(attr)
            return out
    except Exception:
        # Fail-open on import/runtime errors — never invent a SKIP block from exceptions.
        pass

    max_tr = int(inp.max_tranches_override or cfg["max_tranches"])
    cycle_new = build_cycle(
        ticker=ticker,
        currency=inp.currency,
        company_budget=budget,
        max_tranches=max_tr,
        thesis_state="VALID",
        status="PROPOSED",
    )
    return _base_payload(
        action="OPEN_CYCLE",
        reason_code=REASON_OPEN,
        thesis="VALID",
        inp=inp,
        cfg=cfg,
        cycle=cycle_new,
        proposed_value=prop,
    )


def materialize_v2_execution_decision(
    policy_decision: dict[str, Any],
    inp: BuyPolicyInput,
    *,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build foundation-compatible strategy_v2 decision for OPEN/ADD only."""
    cfg = cfg or load_strategy_v2_config()
    action = _s(policy_decision.get("action")).upper()
    if action not in {"OPEN_CYCLE", "ADD_TRANCHE", "HOLD", "STOP_ACCUMULATION"}:
        return None
    ticker = _s(policy_decision.get("ticker")).upper()
    decision_id = _s(policy_decision.get("decision_id"))
    cycle = None
    tranche = None
    if action in {"OPEN_CYCLE", "ADD_TRANCHE"}:
        # Reconstruct cycle from policy fields
        from tae_strategy_v2_foundation import build_cycle as _bc

        budget = _f(policy_decision.get("company_budget"))
        cycle = inp.cycle
        if action == "OPEN_CYCLE" or not cycle:
            cycle = _bc(
                ticker=ticker,
                currency=inp.currency,
                company_budget=budget,
                max_tranches=int(policy_decision.get("max_tranches") or cfg["max_tranches"]),
                thesis_state="VALID",
                cycle_id=_s(policy_decision.get("cycle_id")) or None,
                status="PROPOSED",
            )
            if policy_decision.get("cycle_id"):
                cycle["cycle_id"] = policy_decision["cycle_id"]
        prop = _f(policy_decision.get("proposed_tranche_value"))
        px = _f(inp.mark_price)
        fx = _f(inp.fx_rate, 1.0)
        # quantity from USD notional / (price*fx)
        local_px_usd = px * fx
        qty = round(prop / local_px_usd, 6) if local_px_usd > 0 else 0.0
        seq = int(cycle.get("tranche_count") or 0) + 1
        tranche = build_tranche(
            cycle_id=cycle["cycle_id"],
            ticker=ticker,
            sequence=seq,
            decision_id=decision_id,
            execution_id=new_execution_id(),
            requested_value=prop,
            quantity=qty,
            price=px,
            currency=inp.currency,
            fx_rate=fx,
            reason=action,
        )
    elif action in {"HOLD", "STOP_ACCUMULATION"}:
        cycle = inp.cycle
        if not cycle and policy_decision.get("cycle_id"):
            cycle = {
                "cycle_id": policy_decision["cycle_id"],
                "ticker": ticker,
                "status": "OPEN",
                "thesis_state": policy_decision.get("thesis_state"),
                "company_budget": policy_decision.get("company_budget"),
                "budget_used": policy_decision.get("budget_used"),
                "budget_remaining": policy_decision.get("budget_remaining"),
                "tranche_count": policy_decision.get("tranche_count"),
                "max_tranches": policy_decision.get("max_tranches"),
                "last_tranche_price": policy_decision.get("last_tranche_price"),
            }

    return build_v2_decision_payload(
        action=action,
        ticker=ticker,
        cycle=cycle,
        tranche=tranche,
        mark_price=inp.mark_price,
        mark_freshness=inp.mark_freshness,
        mark_age_seconds=_f(inp.mark_age_seconds),
        decision_id=decision_id,
    )


def pde_maybe_v2_buy_policy(
    *,
    ticker: str,
    pde_decision: dict[str, Any],
    ctx: dict[str, Any],
    enabled_override: bool | None = None,
) -> dict[str, Any] | None:
    """
    PDE hook: returns V2 policy decision only when flag enabled.
    Default false → None (V1 path unchanged).
    """
    if not is_strategy_v2_enabled(override=enabled_override):
        return None
    paper_pos = (ctx.get("paper_positions") or {}).get(ticker.upper()) or {}
    signal = (ctx.get("signals") or {}).get(ticker.upper()) or {}
    hard = (ctx.get("hard_risk_by") or {}).get(ticker.upper()) or {}
    hr_status = _s(hard.get("status") or "OK")
    mark = _f(pde_decision.get("mark_price") or signal.get("price") or paper_pos.get("current_price"))
    inp = BuyPolicyInput(
        ticker=ticker,
        timestamp=_s(pde_decision.get("timestamp")),
        mark_price=mark,
        mark_freshness="FRESH" if mark > 0 else "UNKNOWN",
        mark_age_seconds=0.0 if mark > 0 else float("nan"),
        score=_f(signal.get("score")) if signal.get("score") is not None else None,
        confidence=pde_decision.get("confidence"),
        pde_action=_s(pde_decision.get("action")),
        hard_risk_active=hr_status in {"STOP_LOSS_BREACHED", "CRITICAL_LOSS"},
        hard_risk_status=hr_status or "OK",
        session_valid=True,
        data_fresh=mark > 0,
        candidate_eligible=_s(pde_decision.get("capital_candidate_status"))
        in {"ACTIONABLE_CAPITAL_CANDIDATE", "PORTFOLIO_POLICY_CANDIDATE", ""}
        or _s(pde_decision.get("action")).upper() == "BUY_PAPER",
        held=_f(paper_pos.get("shares")) > 0,
        quantity=_f(paper_pos.get("shares")),
        average_cost=_f(paper_pos.get("avg_price")),
        cash=_f((ctx.get("paper_portfolio") or {}).get("cash")),
        decision_id=None,  # fresh V2 id
    )
    return evaluate_buy_policy(inp, enabled=True)
