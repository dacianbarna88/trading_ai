#!/usr/bin/env python3
"""
Strategy V2 Exit Policy V1 — PAPER / isolated replay only.

Actions: HOLD | STOP_ACCUMULATION | CLOSE_CYCLE
Does not implement EXIT_PARTIAL. Does not auto-enable STRATEGY_V2_ENABLED.
Does not apply V1 mechanical −3% / +5% strategy stops to V2 cycles.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from tae_strategy_v2_config import is_strategy_v2_enabled, load_strategy_v2_config
from tae_strategy_v2_foundation import STRATEGY_VERSION, is_finite_positive
from tae_strategy_v2_hard_risk_adapter import (
    CLASS_CRITICAL,
    CLASS_DATA_SAFETY,
    CLASS_PRICE_DRAWDOWN_INFO,
    classify_hard_risk_for_v2,
    requires_close as hard_risk_requires_close,
)

POLICY_VERSION = "exit_policy.v1"

REASON_HOLD_VALID = "HOLD_THESIS_VALID"
REASON_HOLD_WATCH = "HOLD_THESIS_WATCH"
REASON_HOLD_PROFIT = "HOLD_PROFIT_TARGET_NOT_REACHED"
REASON_STOP_THESIS = "STOP_THESIS_INVALID"
REASON_STOP_FULL = "STOP_FULLY_ALLOCATED"
REASON_STOP_MAX = "STOP_MAX_TRANCHES"
REASON_CLOSE_PROFIT = "CLOSE_PROFIT_TARGET_REACHED"
REASON_CLOSE_THESIS = "CLOSE_THESIS_INVALID"
REASON_CLOSE_HR = "CLOSE_HARD_RISK_CRITICAL"
REASON_CLOSE_DATA = "CLOSE_DATA_SAFETY"
REASON_CLOSE_GOV = "MANUAL_OR_GOVERNANCE_CLOSE"
REASON_CLOSE_TRAILING = "V2_PROFIT_TRAILING_5_2"
REASON_CLOSE_STOP = "V2_STOP_LOSS_UNARMED"
REASON_BLOCK_MARK = "BLOCKED_EXIT_INVALID_MARK"
REASON_BLOCK_ACCT = "BLOCKED_EXIT_ACCOUNTING_MISMATCH"
REASON_BLOCK_DUP = "BLOCKED_DUPLICATE_CLOSE"
REASON_DISABLED = "BLOCKED_STRATEGY_V2_DISABLED"
REASON_HOLD_CLOSED = "HOLD_CYCLE_ALREADY_CLOSED"


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


@dataclass
class ExitPolicyInput:
    ticker: str
    timestamp: str
    mark_price: float
    mark_freshness: str = "UNKNOWN"
    mark_age_seconds: float = float("nan")
    average_cost: float = 0.0
    quantity: float = 0.0
    first_tranche_price: float | None = None
    score: float | None = None
    pde_action: str = "UNKNOWN"
    candidate_eligible: bool | None = None
    structural_invalid: bool = False
    data_fresh: bool = False
    session_valid: bool = True
    accounting_valid: bool = True
    cycle: dict[str, Any] | None = None
    hard_risk_class: str | None = None
    hard_risk_payload: dict[str, Any] | None = None
    decision_id: str | None = None
    seen_close_execution_ids: list[str] = field(default_factory=list)
    governance_close: bool = False
    governance_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_exit_thesis(inp: ExitPolicyInput) -> tuple[str, str]:
    """
    Exit-side thesis. Lost BUY confirmation alone → WATCH (not INVALID).
    Score-derived candidate_eligible=False is NOT structural INVALID.
    INVALID only for explicit session failure or governance/structural flags.
    """
    if not inp.session_valid:
        return "INVALID", REASON_STOP_THESIS
    # Optional explicit structural flag on cycle / input (not mere score eligibility)
    if bool(getattr(inp, "structural_invalid", False)):
        return "INVALID", REASON_STOP_THESIS
    cycle = inp.cycle or {}
    if _s(cycle.get("structural_invalid")).upper() in {"TRUE", "1", "YES"} or cycle.get("structural_invalid") is True:
        return "INVALID", REASON_STOP_THESIS

    mark_ok = (
        is_finite_positive(inp.mark_price)
        and _s(inp.mark_freshness).upper() == "FRESH"
        and inp.data_fresh
    )
    if not mark_ok:
        return "WATCH", REASON_HOLD_WATCH

    favorable = _s(inp.pde_action).upper() in {"BUY_PAPER", "BUY", "STRONG BUY", "STRONG_BUY"} or (
        inp.score is not None and is_finite_positive(float(inp.score)) and float(inp.score) >= 80.0
    )
    if favorable and inp.candidate_eligible is not False:
        return "VALID", REASON_HOLD_VALID
    # Signal lost / eligibility soft-false → WATCH, do not auto-close
    return "WATCH", REASON_HOLD_WATCH


def profit_target_reached(
    *,
    mark_price: float,
    average_cost: float,
    minimum_cycle_profit_pct: float,
) -> bool:
    if not is_finite_positive(mark_price) or not is_finite_positive(average_cost):
        return False
    return float(mark_price) >= float(average_cost) * (1.0 + float(minimum_cycle_profit_pct)) - 1e-12


def evaluate_exit_policy(
    inp: ExitPolicyInput,
    *,
    cfg: dict[str, Any] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    cfg = dict(cfg or load_strategy_v2_config())
    try:
        from tae_paper_execution import _fetch_atr_pct_for_sizing

        atr_pct = _fetch_atr_pct_for_sizing(inp.ticker)
    except Exception:
        atr_pct = None
    factor = 1.0 if atr_pct is None else max(0.4, min(1.6, atr_pct / 2.0))
    min_profit = float(cfg.get("minimum_cycle_profit_pct", 0.10)) * factor
    thesis_invalid_exit = bool(cfg.get("thesis_invalid_exit", True))
    hard_risk_exit = bool(cfg.get("hard_risk_exit", True))
    close_fraction = float(cfg.get("close_fraction", 1.0))

    flag = is_strategy_v2_enabled(override=enabled) if enabled is not None else is_strategy_v2_enabled()
    cycle = inp.cycle or {}
    ticker = _s(inp.ticker).upper()
    decision_id = inp.decision_id or f"V2EXPOL-{ticker}-{uuid.uuid4().hex[:10].upper()}"

    def _base(action: str, reason: str, thesis: str, **extra: Any) -> dict[str, Any]:
        return {
            "strategy_version": STRATEGY_VERSION,
            "policy_version": POLICY_VERSION,
            "exit_policy_version": POLICY_VERSION,
            "cycle_id": cycle.get("cycle_id"),
            "ticker": ticker,
            "action": action,
            "thesis_state": thesis,
            "reason_code": reason,
            "decision_id": decision_id,
            "timestamp": inp.timestamp,
            "mark_price": inp.mark_price,
            "average_cost": inp.average_cost,
            "profit_reference": "aggregate_average_cost",
            "minimum_cycle_profit_pct": min_profit,
            "close_fraction": close_fraction,
            "hard_risk_class": inp.hard_risk_class,
            "capital_mutating": action == "CLOSE_CYCLE",
            "active": action in {"HOLD", "STOP_ACCUMULATION", "CLOSE_CYCLE"},
            **extra,
        }

    if not flag:
        return _base("SKIP", REASON_DISABLED, "UNKNOWN", active=False, capital_mutating=False)

    status = _s(cycle.get("status")).upper()
    if not cycle:
        return _base("HOLD", REASON_HOLD_WATCH, "WATCH", capital_mutating=False)
    if status == "CLOSED":
        return _base("HOLD", REASON_HOLD_CLOSED, "WATCH", capital_mutating=False)

    prior_close = _s(cycle.get("close_execution_id"))
    if prior_close and prior_close in set(inp.seen_close_execution_ids or []):
        return _base("HOLD", REASON_BLOCK_DUP, _s(cycle.get("thesis_state") or "WATCH"), capital_mutating=False)

    hr = inp.hard_risk_payload
    if hr is None:
        hr = classify_hard_risk_for_v2(
            ticker=ticker,
            avg_price=inp.average_cost,
            current_price=inp.mark_price,
            shares=inp.quantity or _f(cycle.get("total_quantity"), 1.0),
            mark_freshness=inp.mark_freshness,
            mark_age_seconds=_f(inp.mark_age_seconds),
            mark_max_age_seconds=float(cfg.get("MARK_MAX_AGE_SECONDS", 3600.0)),
            accounting_valid=inp.accounting_valid,
        )
    hr_class = _s(inp.hard_risk_class or hr.get("class")).upper()
    thesis, _thesis_reason = classify_exit_thesis(inp)

    if hr_class == CLASS_DATA_SAFETY:
        reason = REASON_BLOCK_MARK if _s(hr.get("reason")) != "ACCOUNTING_CORRUPTION" else REASON_BLOCK_ACCT
        return _base(
            "HOLD",
            reason,
            thesis,
            hard_risk_class=hr_class,
            capital_mutating=False,
            note="DATA_SAFETY_BLOCK — no CLOSE at unsafe mark",
        )

    if not inp.accounting_valid:
        return _base("HOLD", REASON_BLOCK_ACCT, thesis, hard_risk_class=hr_class, capital_mutating=False)

    if inp.governance_close:
        return _base(
            "CLOSE_CYCLE",
            REASON_CLOSE_GOV,
            thesis,
            hard_risk_class=hr_class,
            close_reason=inp.governance_reason or REASON_CLOSE_GOV,
        )

    # Price −5% is informational for V2 — never CLOSE on percentage drawdown alone.
    # Non-price critical (exposure / extreme gap) may still require CLOSE.
    hr_for_close = hr if isinstance(hr, dict) else {"class": hr_class, "reason": ""}
    if isinstance(hr_for_close, dict) and not hr_for_close.get("reason") and hr_class == CLASS_CRITICAL:
        # Legacy callers may pass CLASS_CRITICAL for −5% without reason → treat as price DD.
        hr_for_close = {
            **hr_for_close,
            "class": CLASS_PRICE_DRAWDOWN_INFO,
            "reason": "HARD_CRITICAL_STOP_-5",
        }
    if hard_risk_exit and hard_risk_requires_close(hr_for_close):
        return _base(
            "CLOSE_CYCLE",
            REASON_CLOSE_HR,
            "INVALID",
            hard_risk_class=hr_class,
            close_reason=REASON_CLOSE_HR,
        )

    # --- Profit trailing +5% / −2% from peak (V2 PAPER active) ---
    from tae_strategy_v2_trailing import (
        TRAILING_ACTIVATE_PCT,
        TRAILING_DISTANCE_PCT,
        V2_PROFIT_TRAILING_REASON,
        V2_STOP_LOSS_REASON,
        evaluate_position_exit,
        persist_fields_from_decision,
        trailing_state_from_mapping,
    )

    activate_pct = float(cfg.get("TRAILING_ACTIVATE_PCT", TRAILING_ACTIVATE_PCT))
    trail_distance_pct = float(cfg.get("TRAILING_DISTANCE_PCT", TRAILING_DISTANCE_PCT))
    v2_stop_pct = float(cfg.get("V2_STOP_LOSS_PCT", -3.0))
    prior_trail = trailing_state_from_mapping(cycle, inp.average_cost)
    trail_decision = evaluate_position_exit(
        inp.average_cost,
        inp.mark_price,
        prior_trail,
        stop_loss_pct=v2_stop_pct,
        activate_pct=activate_pct,
        trail_distance_pct=trail_distance_pct,
        sell_reason=V2_PROFIT_TRAILING_REASON,
        now_iso=inp.timestamp,
    )
    trail_fields = persist_fields_from_decision(
        prior_trail, trail_decision, now_iso=inp.timestamp
    )

    def _with_trail(payload: dict[str, Any]) -> dict[str, Any]:
        out = dict(payload)
        out.update(trail_fields)
        out["trailing_state"] = dict(trail_fields)
        return out

    # Priority: trailing sell if armed+hit.
    if trail_decision.action == "SELL_TRAILING":
        return _with_trail(
            _base(
                "CLOSE_CYCLE",
                REASON_CLOSE_TRAILING,
                thesis,
                hard_risk_class=hr_class,
                close_reason=V2_PROFIT_TRAILING_REASON,
            )
        )

    # Unarmed entry stop: only when accumulation is finished (preserve −3% ADD path).
    rem_pre = _f(cycle.get("budget_remaining"))
    tol_pre = float(cfg.get("MONEY_TOLERANCE_USD", 0.01))
    tc_pre = int(cycle.get("tranche_count") or 0)
    mx_pre = int(cycle.get("max_tranches") or cfg.get("max_tranches") or 5)
    accumulation_done = (
        rem_pre <= tol_pre or status == "FULLY_ALLOCATED" or tc_pre >= mx_pre
    )
    if trail_decision.action == "SELL_STOP_LOSS" and accumulation_done:
        return _with_trail(
            _base(
                "CLOSE_CYCLE",
                REASON_CLOSE_STOP,
                thesis,
                hard_risk_class=hr_class,
                close_reason=V2_STOP_LOSS_REASON,
            )
        )

    # STRATEGY_STOP_V1_ONLY: continue — do not close on soft −3% while accumulating

    if thesis == "INVALID":
        if thesis_invalid_exit:
            return _with_trail(
                _base(
                    "CLOSE_CYCLE",
                    REASON_CLOSE_THESIS,
                    "INVALID",
                    hard_risk_class=hr_class,
                    close_reason=REASON_CLOSE_THESIS,
                    also_stop_accumulation=True,
                )
            )
        return _with_trail(
            _base("STOP_ACCUMULATION", REASON_STOP_THESIS, "INVALID", hard_risk_class=hr_class)
        )

    rem = rem_pre
    tol = tol_pre
    tc = tc_pre
    mx = mx_pre
    if rem <= tol or status == "FULLY_ALLOCATED":
        return _with_trail(
            _base("STOP_ACCUMULATION", REASON_STOP_FULL, thesis, hard_risk_class=hr_class)
        )
    if tc >= mx:
        return _with_trail(
            _base("STOP_ACCUMULATION", REASON_STOP_MAX, thesis, hard_risk_class=hr_class)
        )

    if profit_target_reached(
        mark_price=inp.mark_price,
        average_cost=inp.average_cost,
        minimum_cycle_profit_pct=min_profit,
    ):
        mark_ok = is_finite_positive(inp.mark_price) and _s(inp.mark_freshness).upper() == "FRESH" and inp.data_fresh
        if mark_ok and inp.accounting_valid:
            return _with_trail(
                _base(
                    "CLOSE_CYCLE",
                    REASON_CLOSE_PROFIT,
                    thesis,
                    hard_risk_class=hr_class,
                    close_reason=REASON_CLOSE_PROFIT,
                )
            )

    if inp.first_tranche_price and is_finite_positive(float(inp.first_tranche_price)):
        first_hit = float(inp.mark_price) >= float(inp.first_tranche_price) * (1.0 + min_profit) - 1e-12
        avg_hit = profit_target_reached(
            mark_price=inp.mark_price,
            average_cost=inp.average_cost,
            minimum_cycle_profit_pct=min_profit,
        )
        if first_hit and not avg_hit:
            return _with_trail(
                _base(
                    "HOLD",
                    REASON_HOLD_PROFIT,
                    thesis,
                    hard_risk_class=hr_class,
                    note="first_tranche_profit_without_avg_cost_target",
                )
            )

    if thesis == "WATCH":
        return _with_trail(_base("HOLD", REASON_HOLD_WATCH, thesis, hard_risk_class=hr_class))

    if thesis == "VALID":
        hit = profit_target_reached(
            mark_price=inp.mark_price,
            average_cost=inp.average_cost,
            minimum_cycle_profit_pct=min_profit,
        )
        return _with_trail(
            _base(
                "HOLD",
                REASON_HOLD_PROFIT if not hit else REASON_HOLD_VALID,
                thesis,
                hard_risk_class=hr_class,
            )
        )

    return _with_trail(_base("HOLD", REASON_HOLD_WATCH, thesis, hard_risk_class=hr_class))


def materialize_close_decision(
    exit_decision: dict[str, Any],
    inp: ExitPolicyInput,
    *,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if _s(exit_decision.get("action")).upper() != "CLOSE_CYCLE":
        return None
    if not inp.cycle:
        return None
    cycle = dict(inp.cycle)
    execution_id = f"V2EX-CLOSE-{_s(cycle.get('cycle_id'))}-{uuid.uuid4().hex[:8].upper()}"
    return {
        "decision_id": exit_decision.get("decision_id"),
        "ticker": _s(inp.ticker).upper(),
        "action": "SELL_PAPER",
        "timestamp": inp.timestamp,
        "strategy_v2": {
            "v2_action": "CLOSE_CYCLE",
            "strategy_version": STRATEGY_VERSION,
            "exit_policy_version": POLICY_VERSION,
            "cycle": cycle,
            "mark_price": inp.mark_price,
            "mark_freshness": inp.mark_freshness,
            "mark_age_seconds": inp.mark_age_seconds,
            "close_reason": exit_decision.get("close_reason") or exit_decision.get("reason_code"),
            "close_execution_id": execution_id,
            "hard_risk_class": exit_decision.get("hard_risk_class"),
        },
        "strategy_version": STRATEGY_VERSION,
        "strategy_v2_cycle_id": cycle.get("cycle_id"),
    }
