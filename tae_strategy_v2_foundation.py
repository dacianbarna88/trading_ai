#!/usr/bin/env python3
"""
Strategy V2 PAPER investment-cycle foundation.

PAPER_ONLY | flag default OFF | does not own V1 BUY/SELL | does not weaken hard-risk.

SSOT:
  cycle state  → runtime_outputs/strategy_v2/cycle_state.json
  tranche journal → runtime_outputs/strategy_v2/tranche_events.jsonl

Capital mutation reuses tae_paper_execution._buy_shares / _sell_shares.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tae_strategy_v2_config import (
    feature_flag_owner,
    is_strategy_v2_enabled,
    load_strategy_v2_config,
)

CYCLE_SCHEMA = "tae.strategy_v2.cycle.v1"
TRANCHE_SCHEMA = "tae.strategy_v2.tranche.v1"
STRATEGY_VERSION = "V2"

RUNTIME_DIR = Path("runtime_outputs/strategy_v2")
CYCLE_STATE_PATH = RUNTIME_DIR / "cycle_state.json"
TRANCHE_JOURNAL_PATH = RUNTIME_DIR / "tranche_events.jsonl"

CYCLE_STATUSES = frozenset(
    {
        "PROPOSED",
        "OPEN",
        "ACCUMULATING",
        "FULLY_ALLOCATED",
        "ACCUMULATION_STOPPED",
        "CLOSING",
        "CLOSED",
        "BLOCKED",
    }
)
THESIS_STATES = frozenset({"VALID", "WATCH", "INVALID", "UNKNOWN"})
TRANCHE_STATUSES = frozenset(
    {"PROPOSED", "AUTHORIZED", "FILLED", "BLOCKED", "SKIPPED", "REJECTED"}
)
V2_ACTIONS = frozenset(
    {"OPEN_CYCLE", "ADD_TRANCHE", "HOLD", "STOP_ACCUMULATION", "CLOSE_CYCLE"}
)
OPEN_LIKE = frozenset({"OPEN", "ACCUMULATING", "FULLY_ALLOCATED", "ACCUMULATION_STOPPED", "CLOSING"})
ADD_ALLOWED = frozenset({"OPEN", "ACCUMULATING"})

STOP_ACCUMULATION_COOLDOWN_SECONDS = 3600
STRUCTURAL_ACCUMULATION_STOP_REASONS = frozenset(
    {
        "STOP_FULLY_ALLOCATED",
        "STOP_MAX_TRANCHES",
        "STOP_HARD_RISK",
        "STOP_THESIS_INVALID",
    }
)

BLOCK_DISABLED = "BLOCKED_STRATEGY_V2_DISABLED"
BLOCK_INVALID_CYCLE = "BLOCKED_INVALID_CYCLE_STATE"
BLOCK_INVALID_THESIS = "BLOCKED_INVALID_THESIS"
BLOCK_MAX_BUDGET = "BLOCKED_MAX_BUDGET"
BLOCK_MAX_TRANCHES = "BLOCKED_MAX_TRANCHES"
BLOCK_DUP_DECISION = "BLOCKED_DUPLICATE_DECISION"
BLOCK_DUP_EXECUTION = "BLOCKED_DUPLICATE_EXECUTION"
BLOCK_HARD_RISK = "BLOCKED_HARD_RISK_AT_FILL"
BLOCK_INVALID_MARK = "BLOCKED_INVALID_MARK_PRICE"
BLOCK_INSUFFICIENT_CASH = "BLOCKED_INSUFFICIENT_CASH"
BLOCK_SCHEMA = "BLOCKED_INVALID_SCHEMA"
BLOCK_TICKER = "BLOCKED_TICKER_MISMATCH"
BLOCK_OPEN_DUP = "BLOCKED_OPEN_CYCLE_EXISTS"
BLOCK_FX = "BLOCKED_INVALID_FX"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return float("nan")
        return out
    except (TypeError, ValueError):
        return float(default)


def _s(value: Any) -> str:
    return str(value or "").strip()


def money_eq(a: float, b: float, tol: float) -> bool:
    return abs(float(a) - float(b)) <= float(tol)


def is_finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def is_finite_non_negative(value: float) -> bool:
    return math.isfinite(value) and value >= 0.0


def filled_value_usd(*, quantity: float, price: float, fx_rate: float) -> float:
    """Local notional × FX → USD accounting unit for budget."""
    return round(float(quantity) * float(price) * float(fx_rate), 6)


def compute_average_cost(old_qty: float, old_avg: float, new_qty: float, fill_price: float) -> float:
    total_qty = float(old_qty) + float(new_qty)
    if total_qty <= 0:
        return 0.0
    return round(((float(old_qty) * float(old_avg)) + (float(new_qty) * float(fill_price))) / total_qty, 6)


def new_cycle_id(ticker: str) -> str:
    return f"V2CYC-{_s(ticker).upper()}-{uuid.uuid4().hex[:12].upper()}"


def new_tranche_id(cycle_id: str, sequence: int) -> str:
    return f"V2TR-{cycle_id}-{int(sequence):03d}"


def new_execution_id() -> str:
    return f"V2EX-{uuid.uuid4().hex[:16].upper()}"


# ── persistence ──────────────────────────────────────────────────────────────


def empty_cycle_store() -> dict[str, Any]:
    return {
        "schema": CYCLE_SCHEMA,
        "strategy_version": STRATEGY_VERSION,
        "updated_at": _now(),
        "cycles": {},
        "decision_ids_seen": [],
        "execution_ids_seen": [],
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def load_cycle_store(path: Path | None = None) -> dict[str, Any]:
    store_path = Path(path) if path is not None else CYCLE_STATE_PATH
    if not store_path.is_file():
        return empty_cycle_store()
    try:
        raw = json.loads(store_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_cycle_store()
    if not isinstance(raw, dict):
        return empty_cycle_store()
    store = empty_cycle_store()
    store.update(raw)
    store.setdefault("cycles", {})
    store.setdefault("decision_ids_seen", [])
    store.setdefault("execution_ids_seen", [])
    return store


def save_cycle_store(store: dict[str, Any], path: Path | None = None) -> None:
    store_path = Path(path) if path is not None else CYCLE_STATE_PATH
    store = dict(store)
    store["schema"] = CYCLE_SCHEMA
    store["strategy_version"] = STRATEGY_VERSION
    store["updated_at"] = _now()
    atomic_write_json(store_path, store)


def append_tranche_event(event: dict[str, Any], path: Path | None = None) -> None:
    journal = Path(path) if path is not None else TRANCHE_JOURNAL_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True) + "\n"
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def cycle_state_owner() -> str:
    return "tae_strategy_v2_foundation.py → runtime_outputs/strategy_v2/cycle_state.json"


def tranche_journal_owner() -> str:
    return "tae_strategy_v2_foundation.py → runtime_outputs/strategy_v2/tranche_events.jsonl"


# ── schema builders ──────────────────────────────────────────────────────────


def build_cycle(
    *,
    ticker: str,
    currency: str,
    company_budget: float,
    max_tranches: int,
    thesis_state: str = "VALID",
    cycle_id: str | None = None,
    status: str = "PROPOSED",
) -> dict[str, Any]:
    budget = float(company_budget)
    now = _now()
    return {
        "schema_version": CYCLE_SCHEMA,
        "strategy_version": STRATEGY_VERSION,
        "cycle_id": cycle_id or new_cycle_id(ticker),
        "ticker": _s(ticker).upper(),
        "currency": _s(currency).upper(),
        "status": status,
        "thesis_state": thesis_state,
        "opened_at": now,
        "updated_at": now,
        "closed_at": None,
        "company_budget": round(budget, 6),
        "budget_used": 0.0,
        "budget_remaining": round(budget, 6),
        "tranche_count": 0,
        "max_tranches": int(max_tranches),
        "total_quantity": 0.0,
        "average_cost": 0.0,
        "last_tranche_price": None,
        "next_tranche_reference_price": None,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "decision_ids": [],
        "execution_ids": [],
        "close_reason": None,
    }


def build_tranche(
    *,
    cycle_id: str,
    ticker: str,
    sequence: int,
    decision_id: str,
    execution_id: str,
    requested_value: float,
    quantity: float,
    price: float,
    currency: str,
    fx_rate: float,
    reason: str,
    status: str = "PROPOSED",
    filled_value: float | None = None,
) -> dict[str, Any]:
    now = _now()
    qty = float(quantity)
    px = float(price)
    fx = float(fx_rate)
    filled = filled_value if filled_value is not None else filled_value_usd(quantity=qty, price=px, fx_rate=fx)
    return {
        "schema_version": TRANCHE_SCHEMA,
        "tranche_id": new_tranche_id(cycle_id, sequence),
        "cycle_id": cycle_id,
        "ticker": _s(ticker).upper(),
        "sequence": int(sequence),
        "decision_id": decision_id,
        "execution_id": execution_id,
        "requested_at": now,
        "filled_at": None,
        "requested_value": round(float(requested_value), 6),
        "filled_value": round(float(filled), 6),
        "quantity": round(qty, 6),
        "price": round(px, 6),
        "currency": _s(currency).upper(),
        "fx_rate": round(fx, 8),
        "status": status,
        "reason": reason,
        "pre_fill_budget_used": None,
        "post_fill_budget_used": None,
        "pre_fill_quantity": None,
        "post_fill_quantity": None,
        "pre_fill_average_cost": None,
        "post_fill_average_cost": None,
    }


def build_v2_decision_payload(
    *,
    action: str,
    ticker: str,
    cycle: dict[str, Any] | None = None,
    tranche: dict[str, Any] | None = None,
    mark_price: float | None = None,
    mark_freshness: str = "FRESH",
    mark_age_seconds: float = 0.0,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Structural PDE-compatible decision stub (not auto-emitted by scoring)."""
    act = _s(action).upper()
    if act not in V2_ACTIONS:
        raise ValueError(f"unsupported V2 action: {act}")
    ticker_u = _s(ticker).upper()
    did = decision_id or f"V2DEC-{ticker_u}-{uuid.uuid4().hex[:10].upper()}"
    return {
        "decision_id": did,
        "ticker": ticker_u,
        "action": "BUY_PAPER" if act in {"OPEN_CYCLE", "ADD_TRANCHE"} else (
            "SELL_PAPER" if act == "CLOSE_CYCLE" else "HOLD_PAPER"
        ),
        "strategy_v2": {
            "enabled_request": True,
            "v2_action": act,
            "cycle": cycle,
            "tranche": tranche,
            "mark_price": mark_price,
            "mark_freshness": mark_freshness,
            "mark_age_seconds": mark_age_seconds,
        },
        "confidence": 0.5,
        "evidence": f"Strategy V2 structural {act}",
        "mode": "PAPER_ONLY",
    }


# ── invariants ───────────────────────────────────────────────────────────────


def validate_cycle_invariants(
    cycle: dict[str, Any],
    *,
    tol: float | None = None,
) -> list[str]:
    cfg = load_strategy_v2_config()
    money_tol = float(tol if tol is not None else cfg["MONEY_TOLERANCE_USD"])
    errors: list[str] = []
    if _s(cycle.get("schema_version")) != CYCLE_SCHEMA:
        errors.append("bad_schema_version")
    if _s(cycle.get("status")) not in CYCLE_STATUSES:
        errors.append("bad_status")
    if _s(cycle.get("thesis_state")) not in THESIS_STATES:
        errors.append("bad_thesis_state")
    budget = _f(cycle.get("company_budget"))
    used = _f(cycle.get("budget_used"))
    rem = _f(cycle.get("budget_remaining"))
    if not is_finite_positive(budget):
        errors.append("company_budget_must_be_positive")
    if not is_finite_non_negative(used):
        errors.append("budget_used_negative_or_nonfinite")
    if not is_finite_non_negative(rem):
        errors.append("budget_remaining_negative_or_nonfinite")
    if not money_eq(used + rem, budget, money_tol):
        errors.append("budget_identity_broken")
    tc = int(cycle.get("tranche_count") or 0)
    mx = int(cycle.get("max_tranches") or 0)
    if tc < 0 or mx < 0 or tc > mx:
        errors.append("tranche_count_out_of_range")
    qty = _f(cycle.get("total_quantity"))
    avg = _f(cycle.get("average_cost"))
    if not is_finite_non_negative(qty):
        errors.append("total_quantity_invalid")
    if not is_finite_non_negative(avg):
        errors.append("average_cost_invalid")
    return errors


def find_open_cycle_for_ticker(store: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    ticker_u = _s(ticker).upper()
    for cycle in (store.get("cycles") or {}).values():
        if _s(cycle.get("ticker")).upper() != ticker_u:
            continue
        if _s(cycle.get("status")) in OPEN_LIKE and _s(cycle.get("status")) != "CLOSED":
            return cycle
    return None


def validate_price_fx(price: float, fx_rate: float, currency: str) -> str | None:
    if not is_finite_positive(price):
        return BLOCK_INVALID_MARK
    if not is_finite_positive(fx_rate):
        return BLOCK_FX
    cur = _s(currency).upper()
    if cur not in {"USD", "EUR", "GBP", "GBX"}:
        return BLOCK_FX
    if cur == "USD" and not money_eq(fx_rate, 1.0, 1e-6):
        return BLOCK_FX
    return None


# ── pre-mutation gates ───────────────────────────────────────────────────────


def preflight_v2(
    *,
    v2_action: str,
    store: dict[str, Any],
    cycle: dict[str, Any] | None,
    tranche: dict[str, Any] | None,
    portfolio: dict[str, Any],
    mark_price: float,
    mark_freshness: str,
    mark_age_seconds: float,
    decision_id: str,
    execution_id: str,
    enabled: bool,
    hard_risk_eval: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    cfg = load_strategy_v2_config()
    if not enabled:
        return False, BLOCK_DISABLED

    act = _s(v2_action).upper()
    if act not in V2_ACTIONS:
        return False, BLOCK_SCHEMA

    if decision_id and decision_id in set(store.get("decision_ids_seen") or []):
        return False, BLOCK_DUP_DECISION
    if execution_id and execution_id in set(store.get("execution_ids_seen") or []):
        return False, BLOCK_DUP_EXECUTION

    if act in {"HOLD", "STOP_ACCUMULATION", "CLOSE_CYCLE", "ADD_TRANCHE"}:
        if not cycle:
            return False, BLOCK_INVALID_CYCLE
        errs = validate_cycle_invariants(cycle)
        if errs:
            return False, BLOCK_INVALID_CYCLE

    if act == "HOLD":
        return True, None

    if act == "STOP_ACCUMULATION":
        if _s(cycle.get("status")) not in ADD_ALLOWED | {"FULLY_ALLOCATED"}:
            return False, BLOCK_INVALID_CYCLE
        return True, None

    if act == "CLOSE_CYCLE":
        if _s(cycle.get("status")) == "CLOSED":
            return False, BLOCK_INVALID_CYCLE
        return True, None

    # OPEN / ADD need mark + money checks
    age_max = float(cfg["MARK_MAX_AGE_SECONDS"])
    if _s(mark_freshness).upper() != "FRESH" or float(mark_age_seconds) > age_max:
        return False, BLOCK_INVALID_MARK
    if not is_finite_positive(mark_price):
        return False, BLOCK_INVALID_MARK

    if act == "OPEN_CYCLE":
        if not cycle:
            return False, BLOCK_SCHEMA
        errs = validate_cycle_invariants(cycle)
        if errs:
            return False, BLOCK_SCHEMA
        if _s(cycle.get("thesis_state")) == "INVALID":
            return False, BLOCK_INVALID_THESIS
        existing = find_open_cycle_for_ticker(store, cycle["ticker"])
        if existing and _s(existing.get("cycle_id")) != _s(cycle.get("cycle_id")):
            return False, BLOCK_OPEN_DUP
        if not tranche:
            return False, BLOCK_SCHEMA
        return _preflight_tranche_money(
            cycle=cycle,
            tranche=tranche,
            portfolio=portfolio,
            mark_price=mark_price,
            hard_risk_eval=hard_risk_eval,
            require_add_status=False,
        )

    if act == "ADD_TRANCHE":
        assert cycle is not None
        if _s(cycle.get("thesis_state")) == "INVALID":
            return False, BLOCK_INVALID_THESIS
        if _s(cycle.get("status")) == "CLOSED":
            return False, BLOCK_INVALID_CYCLE
        if int(cycle.get("tranche_count") or 0) >= int(cycle.get("max_tranches") or 0):
            return False, BLOCK_MAX_TRANCHES
        if _s(cycle.get("status")) == "ACCUMULATION_STOPPED":
            return False, BLOCK_INVALID_CYCLE
        if _s(cycle.get("status")) not in ADD_ALLOWED:
            return False, BLOCK_INVALID_CYCLE
        if not tranche:
            return False, BLOCK_SCHEMA
        if _v2_fill_hard_risk_blocks(hard_risk_eval):
            return False, BLOCK_HARD_RISK
        return _preflight_tranche_money(
            cycle=cycle,
            tranche=tranche,
            portfolio=portfolio,
            mark_price=mark_price,
            hard_risk_eval=hard_risk_eval,
            require_add_status=True,
        )

    return False, BLOCK_SCHEMA


def _preflight_tranche_money(
    *,
    cycle: dict[str, Any],
    tranche: dict[str, Any],
    portfolio: dict[str, Any],
    mark_price: float,
    hard_risk_eval: dict[str, Any] | None,
    require_add_status: bool,
) -> tuple[bool, str | None]:
    cfg = load_strategy_v2_config()
    tol = float(cfg["MONEY_TOLERANCE_USD"])
    reserve = float(cfg["MIN_CASH_RESERVE_USD"])

    price = _f(tranche.get("price"))
    fx = _f(tranche.get("fx_rate"), 1.0)
    qty = _f(tranche.get("quantity"))
    currency = _s(tranche.get("currency") or cycle.get("currency"))
    fx_err = validate_price_fx(price, fx, currency)
    if fx_err:
        return False, fx_err
    if not is_finite_positive(qty):
        return False, BLOCK_INVALID_MARK
    # Prefer explicit mark coherence
    if not money_eq(price, mark_price, max(tol, mark_price * 1e-6 + 1e-9)):
        # allow tranche price to be the fill price; mark must still be finite positive
        if not is_finite_positive(mark_price):
            return False, BLOCK_INVALID_MARK

    filled = filled_value_usd(quantity=qty, price=price, fx_rate=fx)
    # budget based on filled value
    remaining = _f(cycle.get("budget_remaining"))
    if filled > remaining + tol:
        return False, BLOCK_MAX_BUDGET
    if int(cycle.get("tranche_count") or 0) >= int(cycle.get("max_tranches") or 0):
        return False, BLOCK_MAX_TRANCHES

    cash = _f(portfolio.get("cash"))
    if filled > cash + tol:
        return False, BLOCK_INSUFFICIENT_CASH
    if cash - filled + tol < reserve:
        return False, BLOCK_INSUFFICIENT_CASH

    if _v2_fill_hard_risk_blocks(hard_risk_eval):
        return False, BLOCK_HARD_RISK

    if require_add_status and _s(cycle.get("status")) not in ADD_ALLOWED:
        return False, BLOCK_INVALID_CYCLE
    return True, None


def _v2_fill_hard_risk_blocks(hard_risk_eval: dict[str, Any] | None) -> bool:
    """
    V2 fill gate: DATA_SAFETY and non-price CRITICAL block ADD.
    Price −3%/−5% drawdown is informational — never blocks ADD fills.
    """
    if not hard_risk_eval:
        return False
    try:
        from tae_strategy_v2_hard_risk_adapter import fill_time_blocks_add

        adapted = hard_risk_eval.get("v2_adapter")
        if isinstance(adapted, dict):
            return fill_time_blocks_add(adapted)
        # Synthesize from annotated class/reason on the eval dict
        return fill_time_blocks_add(
            {
                "class": hard_risk_eval.get("class") or hard_risk_eval.get("v2_hard_risk_class"),
                "reason": (adapted or {}).get("reason")
                if isinstance(adapted, dict)
                else hard_risk_eval.get("reason") or hard_risk_eval.get("hard_rule"),
            }
        )
    except Exception:
        pass
    cls = _s(hard_risk_eval.get("class") or hard_risk_eval.get("v2_hard_risk_class")).upper()
    if cls in {"PRICE_DRAWDOWN_INFORMATIONAL", "STRATEGY_STOP_V1_ONLY", "SAFE"}:
        return False
    if cls == "DATA_SAFETY_BLOCK":
        return True
    if cls == "CRITICAL_HARD_RISK":
        reason = _s(hard_risk_eval.get("reason") or hard_risk_eval.get("hard_rule")).upper()
        return reason in {"EXPOSURE_BREACH", "GAP_EXTREME"}
    status = _s(hard_risk_eval.get("status") or hard_risk_eval.get("hard_rule")).upper()
    # Legacy CRITICAL_LOSS / −5% price rule: do not block V2 ADD
    if status in {"CRITICAL_LOSS", "HARD_CRITICAL_STOP_-5", "STOP_LOSS_BREACHED", "HARD_STOP_LOSS_-3"}:
        return False
    return False


# ── apply / simulate ─────────────────────────────────────────────────────────


def _snapshot_money(portfolio: dict[str, Any], ticker: str) -> dict[str, float]:
    pos = (portfolio.get("positions") or {}).get(ticker) or {}
    return {
        "cash": _f(portfolio.get("cash")),
        "shares": _f(pos.get("shares")),
        "avg_price": _f(pos.get("avg_price")),
        "realized_pnl": _f(portfolio.get("realized_pnl")),
    }


def apply_open_or_add_tranche(
    *,
    store: dict[str, Any],
    cycle: dict[str, Any],
    tranche: dict[str, Any],
    portfolio: dict[str, Any],
    v2_action: str,
    buy_fn: Callable[..., tuple[float, dict[str, Any]]] | None = None,
    cycle_path: Path | None = None,
    journal_path: Path | None = None,
    persist: bool = True,
    apply_paper_tx_costs: bool = False,
    paper_tx_cost_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate portfolio via existing buy helper; update cycle + journal."""
    import tae_paper_execution as pe

    buy = buy_fn or pe._buy_shares
    ticker = _s(cycle.get("ticker")).upper()
    pre = _snapshot_money(portfolio, ticker)
    pre_budget_used = _f(cycle.get("budget_used"))
    pre_qty = _f(cycle.get("total_quantity"))
    pre_avg = _f(cycle.get("average_cost"))

    price = _f(tranche.get("price"))
    qty_req = _f(tranche.get("quantity"))
    fx = _f(tranche.get("fx_rate"), 1.0)
    # Convert USD budget spend into local notional for _buy_shares (price local).
    # filled_value is USD; local notional = qty * price.
    local_notional = round(qty_req * price, 6)
    buy_kwargs: dict[str, Any] = {}
    if apply_paper_tx_costs:
        buy_kwargs["apply_paper_tx_costs"] = True
        buy_kwargs["paper_tx_cost_cfg"] = paper_tx_cost_cfg
    shares, pos = buy(portfolio, ticker, local_notional, price, **buy_kwargs)
    if shares <= 0:
        tranche = dict(tranche)
        tranche["status"] = "BLOCKED"
        tranche["reason"] = BLOCK_INSUFFICIENT_CASH
        eco = portfolio.get("_last_paper_fill_economics")
        if isinstance(eco, dict):
            tranche["transaction_costs"] = eco
        if persist:
            append_tranche_event(tranche, journal_path)
        return {
            "ok": False,
            "block_reason": BLOCK_INSUFFICIENT_CASH,
            "cycle": cycle,
            "tranche": tranche,
            "portfolio": portfolio,
        }

    # Actual filled from executed shares (partial fill support)
    filled_local = round(shares * price, 6)
    filled_usd = round(filled_local * fx, 6)
    # Prefer portfolio avg (includes BUY tx costs when explicitly enabled).
    new_avg = _f((pos or {}).get("avg_price")) if pos else 0.0
    if new_avg <= 0:
        new_avg = compute_average_cost(pre_qty, pre_avg, shares, price)
    new_qty = round(pre_qty + shares, 6)
    new_used = round(pre_budget_used + filled_usd, 6)
    new_rem = round(_f(cycle.get("company_budget")) - new_used, 6)

    cycle = dict(cycle)
    cycle["budget_used"] = new_used
    cycle["budget_remaining"] = max(0.0, new_rem)
    cycle["tranche_count"] = int(cycle.get("tranche_count") or 0) + 1
    cycle["total_quantity"] = new_qty
    cycle["average_cost"] = new_avg
    cycle["last_tranche_price"] = price
    cycle["next_tranche_reference_price"] = price
    cycle["updated_at"] = _now()
    cycle["status"] = (
        "FULLY_ALLOCATED"
        if cycle["budget_remaining"] <= load_strategy_v2_config()["MONEY_TOLERANCE_USD"]
        or cycle["tranche_count"] >= int(cycle["max_tranches"])
        else ("ACCUMULATING" if v2_action == "ADD_TRANCHE" or cycle["tranche_count"] > 1 else "OPEN")
    )
    did = _s(tranche.get("decision_id"))
    eid = _s(tranche.get("execution_id"))
    if did and did not in cycle["decision_ids"]:
        cycle["decision_ids"] = list(cycle.get("decision_ids") or []) + [did]
    if eid and eid not in cycle["execution_ids"]:
        cycle["execution_ids"] = list(cycle.get("execution_ids") or []) + [eid]

    # unrealized vs last mark (= fill price here)
    cycle["unrealized_pnl"] = round((price - new_avg) * new_qty * fx, 6)

    tranche = dict(tranche)
    tranche["status"] = "FILLED"
    tranche["filled_at"] = _now()
    tranche["quantity"] = round(shares, 6)
    tranche["filled_value"] = filled_usd
    tranche["pre_fill_budget_used"] = pre_budget_used
    tranche["post_fill_budget_used"] = new_used
    tranche["pre_fill_quantity"] = pre_qty
    tranche["post_fill_quantity"] = new_qty
    tranche["pre_fill_average_cost"] = pre_avg
    tranche["post_fill_average_cost"] = new_avg
    eco = portfolio.get("_last_paper_fill_economics")
    if isinstance(eco, dict):
        tranche["gross_notional"] = eco.get("gross_notional", filled_usd)
        tranche["commission_cost"] = eco.get("commission_cost", 0.0)
        tranche["spread_cost"] = eco.get("spread_cost", 0.0)
        tranche["slippage_cost"] = eco.get("slippage_cost", 0.0)
        tranche["total_transaction_cost"] = eco.get("total_transaction_cost", 0.0)
        tranche["net_cash_movement"] = eco.get("net_cash_movement")
        tranche["cost_model_version"] = eco.get("cost_model_version")
        tranche["cost_configuration"] = eco.get("cost_configuration")

    inv = validate_cycle_invariants(cycle)
    if inv:
        # rollback portfolio cash/qty to pre snapshot
        portfolio["cash"] = pre["cash"]
        positions = portfolio.setdefault("positions", {})
        if pre["shares"] <= 0:
            positions.pop(ticker, None)
        else:
            positions[ticker] = {
                "ticker": ticker,
                "shares": pre["shares"],
                "avg_price": pre["avg_price"],
                "current_price": price,
                "status": "OPEN",
            }
        portfolio["realized_pnl"] = pre["realized_pnl"]
        tranche["status"] = "REJECTED"
        tranche["reason"] = BLOCK_INVALID_CYCLE
        if persist:
            append_tranche_event(tranche, journal_path)
        return {
            "ok": False,
            "block_reason": BLOCK_INVALID_CYCLE,
            "invariant_errors": inv,
            "cycle": cycle,
            "tranche": tranche,
            "portfolio": portfolio,
        }

    store = dict(store)
    cycles = dict(store.get("cycles") or {})
    cycles[cycle["cycle_id"]] = cycle
    store["cycles"] = cycles
    seen_d = list(store.get("decision_ids_seen") or [])
    seen_e = list(store.get("execution_ids_seen") or [])
    if did and did not in seen_d:
        seen_d.append(did)
    if eid and eid not in seen_e:
        seen_e.append(eid)
    store["decision_ids_seen"] = seen_d
    store["execution_ids_seen"] = seen_e

    if persist:
        save_cycle_store(store, cycle_path)
        append_tranche_event(tranche, journal_path)

    return {
        "ok": True,
        "block_reason": None,
        "cycle": cycle,
        "tranche": tranche,
        "store": store,
        "portfolio": portfolio,
        "filled_shares": shares,
        "filled_value_usd": filled_usd,
        "fill_economics": eco if isinstance(eco, dict) else None,
    }


def apply_stop_accumulation(
    cycle: dict[str, Any],
    store: dict[str, Any],
    *,
    reason_code: str | None = None,
    cooldown_seconds: float | None = None,
    persist: bool = True,
    cycle_path: Path | None = None,
) -> dict[str, Any]:
    from datetime import timedelta

    cycle = dict(cycle)
    cycle["status"] = "ACCUMULATION_STOPPED"
    cycle["updated_at"] = _now()
    if reason_code:
        cycle["accumulation_stop_reason"] = str(reason_code)
    cd = float(cooldown_seconds if cooldown_seconds is not None else STOP_ACCUMULATION_COOLDOWN_SECONDS)
    if cd > 0 and _s(reason_code) not in STRUCTURAL_ACCUMULATION_STOP_REASONS:
        stop_dt = datetime.now(timezone.utc) + timedelta(seconds=cd)
        cycle["accumulation_stop_until"] = stop_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    store = dict(store)
    cycles = dict(store.get("cycles") or {})
    cycles[cycle["cycle_id"]] = cycle
    store["cycles"] = cycles
    if persist:
        save_cycle_store(store, cycle_path)
    return {"ok": True, "cycle": cycle, "store": store}


def accumulation_stop_cooldown_elapsed(cycle: dict[str, Any]) -> bool:
    until = cycle.get("accumulation_stop_until")
    if not until:
        return True
    try:
        raw = str(until).replace("Z", "+00:00")
        stop_dt = datetime.fromisoformat(raw)
        if stop_dt.tzinfo is None:
            stop_dt = stop_dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return True
    return datetime.now(timezone.utc) >= stop_dt


def evaluate_accumulation_reactivation(
    cycle: dict[str, Any],
    *,
    mark_ok: bool,
) -> dict[str, Any]:
    """Finite cooldown then re-evaluate soft STOP_ACCUMULATION — keeps tranche discipline."""
    cycle = dict(cycle)
    if _s(cycle.get("status")) != "ACCUMULATION_STOPPED":
        return {"action": "CONTINUE", "cycle": cycle}
    reason = _s(cycle.get("accumulation_stop_reason"))
    if reason in STRUCTURAL_ACCUMULATION_STOP_REASONS:
        return {"action": "STOP", "reason_code": "STOP_ACCUMULATION_STRUCTURAL", "cycle": cycle}
    if not accumulation_stop_cooldown_elapsed(cycle):
        return {"action": "STOP", "reason_code": "STOP_ACCUMULATION_COOLDOWN", "cycle": cycle}
    if not mark_ok:
        return {"action": "STOP", "reason_code": "STOP_INVALID_DATA", "cycle": cycle}
    cycle["status"] = "ACCUMULATING"
    cycle.pop("accumulation_stop_until", None)
    cycle.pop("accumulation_stop_reason", None)
    cycle["updated_at"] = _now()
    return {"action": "REACTIVATED", "cycle": cycle}


def apply_close_cycle(
    *,
    cycle: dict[str, Any],
    store: dict[str, Any],
    portfolio: dict[str, Any],
    mark_price: float,
    fx_rate: float = 1.0,
    close_reason: str = "CLOSE_CYCLE",
    close_execution_id: str | None = None,
    sell_fn: Callable[..., tuple[float, float, dict[str, Any] | None]] | None = None,
    persist: bool = True,
    cycle_path: Path | None = None,
    apply_paper_tx_costs: bool = False,
    paper_tx_cost_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full close via existing paper sell helper — no parallel accounting.

    Status path: OPEN/ACCUMULATING/… → CLOSING → CLOSED.
    Duplicate close (already CLOSED or same close_execution_id) does not mutate capital.
    """
    import tae_paper_execution as pe

    sell = sell_fn or pe._sell_shares
    ticker = _s(cycle.get("ticker")).upper()
    cycle = dict(cycle)
    store = dict(store)
    eid = _s(close_execution_id) or new_execution_id()

    if _s(cycle.get("status")) == "CLOSED":
        return {
            "ok": False,
            "block_reason": BLOCK_DUP_EXECUTION,
            "cycle": cycle,
            "store": store,
            "realized_pnl": 0.0,
            "portfolio": portfolio,
            "duplicate_close": True,
        }
    if _s(cycle.get("close_execution_id")) and _s(cycle.get("close_execution_id")) == eid:
        return {
            "ok": False,
            "block_reason": BLOCK_DUP_EXECUTION,
            "cycle": cycle,
            "store": store,
            "realized_pnl": 0.0,
            "portfolio": portfolio,
            "duplicate_close": True,
        }

    # CLOSING marker before sell
    cycle["status"] = "CLOSING"
    cycle["updated_at"] = _now()
    cycle["close_reason"] = close_reason
    cycle["close_execution_id"] = eid
    store.setdefault("cycles", {})[cycle["cycle_id"]] = cycle
    if persist:
        save_cycle_store(store, cycle_path)

    pos = (portfolio.get("positions") or {}).get(ticker) or {}
    shares = _f(pos.get("shares"))
    if shares <= 0:
        cycle["status"] = "CLOSED"
        cycle["closed_at"] = _now()
        cycle["updated_at"] = _now()
        store.setdefault("cycles", {})[cycle["cycle_id"]] = cycle
        if persist:
            save_cycle_store(store, cycle_path)
        return {"ok": True, "cycle": cycle, "store": store, "realized_pnl": 0.0, "portfolio": portfolio}

    sell_kwargs: dict[str, Any] = {}
    if apply_paper_tx_costs:
        sell_kwargs["apply_paper_tx_costs"] = True
        sell_kwargs["paper_tx_cost_cfg"] = paper_tx_cost_cfg
    realized, gross, _after = sell(portfolio, ticker, shares, float(mark_price), **sell_kwargs)
    realized_usd = round(float(realized) * float(fx_rate), 6)
    eco = portfolio.get("_last_paper_fill_economics")
    cycle["status"] = "CLOSED"
    cycle["closed_at"] = _now()
    cycle["close_reason"] = close_reason
    cycle["close_execution_id"] = eid
    cycle["updated_at"] = _now()
    cycle["realized_pnl"] = round(_f(cycle.get("realized_pnl")) + realized_usd, 6)
    cycle["unrealized_pnl"] = 0.0
    cycle["total_quantity"] = 0.0
    # Clear trailing persistence on full close
    cycle["trailing_armed"] = False
    cycle["highest_price"] = None
    cycle["trailing_stop"] = None
    cycle["armed_at"] = None
    store.setdefault("cycles", {})[cycle["cycle_id"]] = cycle
    seen_e = list(store.get("execution_ids_seen") or [])
    if eid and eid not in seen_e:
        seen_e.append(eid)
    store["execution_ids_seen"] = seen_e
    if persist:
        save_cycle_store(store, cycle_path)
    return {
        "ok": True,
        "cycle": cycle,
        "store": store,
        "realized_pnl": realized_usd,
        "portfolio": portfolio,
        "close_execution_id": eid,
        "gross_proceeds": gross,
        "fill_economics": eco if isinstance(eco, dict) else None,
    }


def execute_strategy_v2_decision(
    decision: dict[str, Any],
    portfolio: dict[str, Any],
    *,
    accounting: dict[str, Any] | None = None,
    enabled_override: bool | None = None,
    cycle_path: Path | None = None,
    journal_path: Path | None = None,
    persist: bool = True,
    hard_risk_fn: Callable[..., dict[str, Any]] | None = None,
    apply_paper_tx_costs: bool = False,
    paper_tx_cost_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Entry from paper_execution when decision carries strategy_v2 payload.
    Never mutates capital when STRATEGY_V2_ENABLED is false.
    Paper tx costs apply only when explicitly activated by the caller.
    """
    import tae_paper_execution as pe

    v2 = decision.get("strategy_v2") or {}
    enabled = is_strategy_v2_enabled(override=enabled_override)
    action = _s(v2.get("v2_action")).upper()
    ticker = _s(decision.get("ticker") or (v2.get("cycle") or {}).get("ticker")).upper()
    decision_id = _s(decision.get("decision_id"))
    cycle = v2.get("cycle")
    tranche = v2.get("tranche")
    if isinstance(cycle, dict):
        cycle = dict(cycle)
    if isinstance(tranche, dict):
        tranche = dict(tranche)

    execution_id = _s(v2.get("close_execution_id")) or _s((tranche or {}).get("execution_id")) or new_execution_id()
    if tranche is not None and not _s(tranche.get("execution_id")):
        tranche["execution_id"] = execution_id

    mark_price = _f(v2.get("mark_price"))
    mark_freshness = _s(v2.get("mark_freshness") or "FRESH")
    mark_age = _f(v2.get("mark_age_seconds"))

    store = load_cycle_store(cycle_path)
    # Prefer persisted cycle if id present
    if cycle and _s(cycle.get("cycle_id")) in (store.get("cycles") or {}):
        cycle = dict(store["cycles"][cycle["cycle_id"]])

    hard_risk = None
    pos = (portfolio.get("positions") or {}).get(ticker) or {}
    if _f(pos.get("shares")) > 0 and action == "ADD_TRANCHE":
        eval_fn = hard_risk_fn or pe.evaluate_fill_time_hard_risk
        raw_hr = eval_fn(
            ticker,
            avg_price=_f(pos.get("avg_price")),
            current_price=mark_price if is_finite_positive(mark_price) else _f(pos.get("current_price")),
            shares=_f(pos.get("shares")),
        )
        # Annotate with V2 adapter class so −3% V1 stop does not block ADD
        try:
            from tae_strategy_v2_hard_risk_adapter import classify_hard_risk_for_v2

            adapted = classify_hard_risk_for_v2(
                ticker=ticker,
                avg_price=_f(pos.get("avg_price")),
                current_price=mark_price if is_finite_positive(mark_price) else _f(pos.get("current_price")),
                shares=_f(pos.get("shares")),
                mark_freshness=mark_freshness,
                mark_age_seconds=mark_age,
                guardian_result=raw_hr,
            )
            hard_risk = dict(raw_hr or {})
            hard_risk["class"] = adapted.get("class")
            hard_risk["v2_hard_risk_class"] = adapted.get("class")
            hard_risk["v2_adapter"] = adapted
        except Exception:
            hard_risk = raw_hr

    ok, reason = preflight_v2(
        v2_action=action,
        store=store,
        cycle=cycle,
        tranche=tranche,
        portfolio=portfolio,
        mark_price=mark_price,
        mark_freshness=mark_freshness,
        mark_age_seconds=mark_age,
        decision_id=decision_id,
        execution_id=execution_id,
        enabled=enabled,
        hard_risk_eval=hard_risk,
    )

    base_order = {
        "schema": "tae.strategy_v2.order.v1",
        "decision_id": decision_id,
        "execution_id": execution_id,
        "ticker": ticker,
        "action": _s(decision.get("action")),
        "v2_action": action,
        "strategy_v2": True,
        "executed": False,
        "is_trade": False,
        "broker_executed": False,
        "live_money": False,
        "mode": "PAPER_ONLY",
        "status": "BLOCKED",
        "reason": reason,
        "cash_before": _f(portfolio.get("cash")),
        "cash_after": _f(portfolio.get("cash")),
        "fill_shares": 0.0,
        "fill_price": mark_price if is_finite_positive(mark_price) else None,
        "fill_time_hard_risk": hard_risk,
        "cycle_id": _s((cycle or {}).get("cycle_id")) or None,
    }

    if not ok:
        # Explicit blocked journal for attempted tranche
        if tranche and persist and action in {"OPEN_CYCLE", "ADD_TRANCHE"}:
            blocked = dict(tranche)
            blocked["status"] = "BLOCKED"
            blocked["reason"] = reason
            append_tranche_event(blocked, journal_path)
        base_order["status"] = reason or BLOCK_DISABLED
        return base_order

    if action == "HOLD":
        base_order["status"] = "NO_CHANGE"
        base_order["reason"] = "HOLD"
        base_order["executed"] = False
        return base_order

    if action == "STOP_ACCUMULATION":
        result = apply_stop_accumulation(cycle, store, persist=persist, cycle_path=cycle_path)
        base_order["status"] = "EXECUTED"
        base_order["executed"] = True
        base_order["reason"] = "STOP_ACCUMULATION"
        base_order["cycle"] = result["cycle"]
        base_order["cash_after"] = _f(portfolio.get("cash"))
        return base_order

    if action == "CLOSE_CYCLE":
        fx = _f(v2.get("fx_rate"), 1.0)
        if cycle and _s(cycle.get("currency")).upper() == "USD":
            fx = 1.0
        close_reason = _s(v2.get("close_reason")) or "CLOSE_CYCLE"
        close_eid = _s(v2.get("close_execution_id")) or execution_id
        result = apply_close_cycle(
            cycle=cycle,
            store=store,
            portfolio=portfolio,
            mark_price=mark_price,
            fx_rate=fx,
            close_reason=close_reason,
            close_execution_id=close_eid,
            persist=persist,
            cycle_path=cycle_path,
            apply_paper_tx_costs=apply_paper_tx_costs,
            paper_tx_cost_cfg=paper_tx_cost_cfg,
        )
        if result.get("duplicate_close") or not result.get("ok"):
            base_order["status"] = result.get("block_reason") or BLOCK_DUP_EXECUTION
            base_order["reason"] = base_order["status"]
            base_order["duplicate_close"] = True
            base_order["cycle"] = result.get("cycle")
            return base_order
        store2 = result["store"]
        seen_d = list(store2.get("decision_ids_seen") or [])
        seen_e = list(store2.get("execution_ids_seen") or [])
        if decision_id and decision_id not in seen_d:
            seen_d.append(decision_id)
        if close_eid and close_eid not in seen_e:
            seen_e.append(close_eid)
        store2["decision_ids_seen"] = seen_d
        store2["execution_ids_seen"] = seen_e
        if persist:
            save_cycle_store(store2, cycle_path)
        base_order["status"] = "EXECUTED"
        base_order["executed"] = True
        base_order["is_trade"] = True
        base_order["reason"] = close_reason
        base_order["execution_id"] = close_eid
        base_order["realized_pnl"] = result.get("realized_pnl")
        base_order["cycle"] = result["cycle"]
        base_order["cash_after"] = _f(portfolio.get("cash"))
        base_order["filled_value_usd"] = result.get("gross_proceeds")
        eco = result.get("fill_economics")
        if isinstance(eco, dict):
            base_order["fill_economics"] = eco
            base_order["total_transaction_cost"] = eco.get("total_transaction_cost")
            base_order["net_cash_movement"] = eco.get("net_cash_movement")
            base_order["realized_pnl_gross"] = eco.get("realized_pnl_gross")
            base_order["realized_pnl_net"] = eco.get("realized_pnl_net", result.get("realized_pnl"))
            base_order["cost_model_version"] = eco.get("cost_model_version")
            base_order["cost_configuration"] = eco.get("cost_configuration")
        return base_order

    # OPEN_CYCLE / ADD_TRANCHE
    if action == "OPEN_CYCLE":
        # register cycle before fill
        store = dict(store)
        store.setdefault("cycles", {})[cycle["cycle_id"]] = cycle
        if persist:
            save_cycle_store(store, cycle_path)

    result = apply_open_or_add_tranche(
        store=store,
        cycle=cycle,
        tranche=tranche,
        portfolio=portfolio,
        v2_action=action,
        cycle_path=cycle_path,
        journal_path=journal_path,
        persist=persist,
        apply_paper_tx_costs=apply_paper_tx_costs,
        paper_tx_cost_cfg=paper_tx_cost_cfg,
    )
    if not result.get("ok"):
        base_order["status"] = result.get("block_reason") or BLOCK_INVALID_CYCLE
        base_order["reason"] = base_order["status"]
        base_order["cash_after"] = _f(portfolio.get("cash"))
        base_order["cycle"] = result.get("cycle")
        base_order["tranche"] = result.get("tranche")
        return base_order

    base_order["status"] = "EXECUTED"
    base_order["executed"] = True
    base_order["is_trade"] = True
    base_order["reason"] = action
    base_order["fill_shares"] = result.get("filled_shares")
    base_order["filled_value_usd"] = result.get("filled_value_usd")
    base_order["cycle"] = result.get("cycle")
    base_order["tranche"] = result.get("tranche")
    base_order["cash_after"] = _f(portfolio.get("cash"))
    eco = result.get("fill_economics")
    if isinstance(eco, dict):
        base_order["fill_economics"] = eco
        base_order["total_transaction_cost"] = eco.get("total_transaction_cost")
        base_order["net_cash_movement"] = eco.get("net_cash_movement")
        base_order["cost_model_version"] = eco.get("cost_model_version")
        base_order["cost_configuration"] = eco.get("cost_configuration")
    # attribution metadata on position (no parallel ledger)
    pos_after = (portfolio.get("positions") or {}).get(ticker)
    if isinstance(pos_after, dict):
        pos_after["strategy_v2_cycle_id"] = result["cycle"]["cycle_id"]
        pos_after["strategy_version"] = STRATEGY_VERSION
    return base_order


def decision_has_strategy_v2(decision: dict[str, Any] | None) -> bool:
    if not isinstance(decision, dict):
        return False
    return isinstance(decision.get("strategy_v2"), dict)


__all__ = [
    "CYCLE_SCHEMA",
    "TRANCHE_SCHEMA",
    "STRATEGY_VERSION",
    "feature_flag_owner",
    "cycle_state_owner",
    "tranche_journal_owner",
    "is_strategy_v2_enabled",
    "load_strategy_v2_config",
    "build_cycle",
    "build_tranche",
    "build_v2_decision_payload",
    "validate_cycle_invariants",
    "compute_average_cost",
    "filled_value_usd",
    "execute_strategy_v2_decision",
    "decision_has_strategy_v2",
    "preflight_v2",
    "load_cycle_store",
    "save_cycle_store",
    "apply_open_or_add_tranche",
    "apply_stop_accumulation",
    "apply_close_cycle",
    "BLOCK_DISABLED",
    "BLOCK_MAX_BUDGET",
    "BLOCK_MAX_TRANCHES",
    "BLOCK_INVALID_THESIS",
    "BLOCK_INVALID_CYCLE",
    "BLOCK_DUP_DECISION",
    "BLOCK_DUP_EXECUTION",
    "BLOCK_HARD_RISK",
    "BLOCK_INVALID_MARK",
    "BLOCK_INSUFFICIENT_CASH",
    "BLOCK_OPEN_DUP",
]
