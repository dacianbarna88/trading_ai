#!/usr/bin/env python3
"""
TAE Decision State — thin active-decision view from existing execution artifacts.

PAPER_ONLY | READ_ONLY builder | NO_BROKER | NO_LIVE_PROMOTION
Does NOT decide trades — aggregates state and switch-authorization helpers for PDE/execution.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae.decision_state.v1"
MODE = "PAPER_ONLY"

OUTPUT_DIR = Path("runtime_outputs/decision_state")
ACTIVE_JSON = OUTPUT_DIR / "active_decisions.json"
REPORT_MD = Path("TAE_DECISION_STATE_REPORT.md")

ORDERS_JSONL = Path("runtime_outputs/paper_execution/paper_orders.jsonl")
TRADES_JSONL = Path("runtime_outputs/paper_execution/paper_trades.jsonl")
PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
HARD_RISK_JSON = Path("runtime_outputs/governance/hard_risk.json")
COOLDOWN_AUDIT_JSON = Path("tae_stop_reentry_cooldown_audit.json")

EV_MARGIN_REQUIRED = 0.15
STRONG_EV_MULTIPLIER = 2.0
COOLDOWN_MINUTES_DEFAULT = 30
RECENT_CHAIN_LIMIT = 8

EXECUTED_STATUSES = frozenset({"EXECUTED", "FILLED", "PARTIAL"})
TRADE_ACTIONS = frozenset({"BUY_PAPER", "SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"})

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
    "research_core/",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if path.resolve() != REPORT_MD.resolve() and output_root not in path.resolve().parents:
        raise RuntimeError(f"Unsafe output path outside decision_state/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def cooldown_minutes_from_audit() -> int:
    audit = load_json(COOLDOWN_AUDIT_JSON) or {}
    best = _s(audit.get("summary", {}).get("best_cooldown") if isinstance(audit.get("summary"), dict) else "")
    mapping = {"cooldown_15m": 15, "cooldown_30m": 30, "cooldown_60m": 60}
    return mapping.get(best, COOLDOWN_MINUTES_DEFAULT)


def ev_margin_actual(proposed_raev: float, baseline_raev: float) -> float:
    denom = max(abs(baseline_raev), 1.0)
    return round((proposed_raev - baseline_raev) / denom, 4)


def _is_executed_order(order: dict[str, Any]) -> bool:
    status = _s(order.get("status")).upper()
    if status in EXECUTED_STATUSES:
        return True
    if order.get("is_trade") or order.get("executed"):
        return True
    if status == "NO_CHANGE":
        return False
    return status not in {"SKIPPED_NO_POSITION", "SKIPPED_SWITCH_NOT_AUTHORIZED", ""}


def _orders_by_ticker(orders: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for order in orders:
        ticker = _s(order.get("ticker")).upper()
        if ticker:
            by.setdefault(ticker, []).append(order)
    for ticker in by:
        by[ticker].sort(key=lambda o: _s(o.get("timestamp")))
    return by


def _hard_risk_by_ticker() -> dict[str, dict[str, Any]]:
    doc = load_json(HARD_RISK_JSON) or {}
    out: dict[str, dict[str, Any]] = {}
    for row in (doc.get("positions") or []) + (doc.get("breaches") or []):
        if isinstance(row, dict):
            t = _s(row.get("ticker")).upper()
            if t:
                out[t] = row
    return out


def _cooldown_status(last_sell_at: str | None, *, cooldown_minutes: int) -> dict[str, Any]:
    if not last_sell_at:
        return {"active": False, "reason": "no_prior_sell", "minutes_remaining": 0}
    sell_ts = _parse_ts(last_sell_at)
    if not sell_ts:
        return {"active": False, "reason": "unparseable_sell_ts", "minutes_remaining": 0}
    elapsed = (datetime.now(timezone.utc) - sell_ts).total_seconds() / 60.0
    remaining = max(0.0, cooldown_minutes - elapsed)
    active = remaining > 0
    return {
        "active": active,
        "reason": "STOP_REENTRY_CHURN_ENFORCED" if active else "cooldown_expired",
        "minutes_remaining": round(remaining, 1),
        "cooldown_minutes": cooldown_minutes,
        "last_sell_at": last_sell_at,
    }


def _churn_risk(action_change_count: int, recent_chain: list[str]) -> str:
    if action_change_count >= 4:
        return "HIGH"
    if len(recent_chain) >= 3:
        flips = sum(
            1
            for i in range(1, len(recent_chain))
            if recent_chain[i] != recent_chain[i - 1]
            and recent_chain[i] in TRADE_ACTIONS
            and recent_chain[i - 1] in TRADE_ACTIONS
        )
        if flips >= 2:
            return "HIGH"
    if action_change_count >= 2:
        return "MEDIUM"
    return "LOW"


def build_ticker_state(
    ticker: str,
    orders: list[dict[str, Any]],
    portfolio: dict[str, Any] | None,
    hard_risk: dict[str, Any] | None,
    *,
    cooldown_minutes: int,
) -> dict[str, Any]:
    ticker = ticker.upper()
    pos = ((portfolio or {}).get("positions") or {}).get(ticker) or {}
    shares = _f(pos.get("shares"))
    status = "OPEN" if shares > 0 else "FLAT"

    last_action = ""
    last_executed = ""
    last_action_at = None
    last_execution_at = None
    last_decision_id = ""
    last_buy_at = None
    last_sell_at = None
    last_protect_at = None
    last_hard_rule_action = None
    recent_chain: list[str] = []
    action_change_count = 0
    prev_action = ""

    for order in orders:
        action = _s(order.get("action")).upper()
        ts = _s(order.get("timestamp"))
        if action:
            recent_chain.append(action)
            if prev_action and action != prev_action:
                action_change_count += 1
            prev_action = action
            last_action = action
            last_action_at = ts or last_action_at
            last_decision_id = _s(order.get("decision_id")) or last_decision_id
        if _is_executed_order(order) and action in TRADE_ACTIONS:
            last_executed = action
            last_execution_at = ts or last_execution_at
            if action == "BUY_PAPER":
                last_buy_at = ts
            elif action == "SELL_PAPER":
                last_sell_at = ts
            elif action == "PROTECT_PAPER":
                last_protect_at = ts

    recent_chain = recent_chain[-RECENT_CHAIN_LIMIT:]

    hr = hard_risk or {}
    if _s(hr.get("status")) in {"STOP_LOSS_BREACHED", "CRITICAL_LOSS"}:
        last_hard_rule_action = "SELL_PAPER"

    cooldown = _cooldown_status(last_sell_at, cooldown_minutes=cooldown_minutes)
    churn = _churn_risk(action_change_count, recent_chain)

    return {
        "ticker": ticker,
        "last_action": last_action or None,
        "last_executed_action": last_executed or None,
        "last_action_at": last_action_at,
        "last_execution_at": last_execution_at,
        "last_decision_id": last_decision_id or None,
        "current_position_shares": round(shares, 6),
        "current_position_status": status,
        "last_buy_at": last_buy_at,
        "last_sell_at": last_sell_at,
        "last_protect_at": last_protect_at,
        "action_change_count": action_change_count,
        "recent_action_chain": recent_chain,
        "cooldown_status": cooldown,
        "churn_risk": churn,
        "last_hard_rule_action": last_hard_rule_action,
        "source_artifacts": [
            str(ORDERS_JSONL),
            str(PORTFOLIO_JSON),
            str(HARD_RISK_JSON),
            str(COOLDOWN_AUDIT_JSON),
        ],
    }


def build_active_decisions() -> dict[str, Any]:
    orders = load_jsonl(ORDERS_JSONL)
    portfolio = load_json(PORTFOLIO_JSON)
    hard_map = _hard_risk_by_ticker()
    cooldown_minutes = cooldown_minutes_from_audit()
    by_ticker = _orders_by_ticker(orders)

    tickers = set(by_ticker.keys())
    tickers.update(_s(t).upper() for t in ((portfolio or {}).get("positions") or {}).keys())
    tickers.update(hard_map.keys())

    states = {
        t: build_ticker_state(
            t,
            by_ticker.get(t, []),
            portfolio,
            hard_map.get(t),
            cooldown_minutes=cooldown_minutes,
        )
        for t in sorted(tickers)
    }

    return {
        "schema": SCHEMA,
        "mode": MODE,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "cooldown_minutes_default": cooldown_minutes,
        "ev_margin_required_default": EV_MARGIN_REQUIRED,
        "ticker_count": len(states),
        "tickers": states,
        "sources_loaded": {
            "paper_orders": ORDERS_JSONL.is_file(),
            "paper_portfolio": PORTFOLIO_JSON.is_file(),
            "hard_risk": HARD_RISK_JSON.is_file(),
            "cooldown_audit": COOLDOWN_AUDIT_JSON.is_file(),
        },
    }


def load_active_by_ticker(path: Path | None = None) -> dict[str, dict[str, Any]]:
    doc = load_json(path or ACTIVE_JSON) or {}
    return dict((doc.get("tickers") or {}))


def scenario_raev_map(scenario_ev_table: list[dict[str, Any]] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in scenario_ev_table or []:
        action = _s(row.get("action")).upper()
        if action:
            out[action] = _f(row.get("risk_adjusted_EV"))
    return out


def evaluate_action_switch(
    ticker: str,
    proposed_action: str,
    *,
    state: dict[str, Any] | None,
    hard_rule_override: bool,
    scenario_raev: dict[str, float] | None = None,
    loss_context: dict[str, Any] | None = None,
    held: bool = False,
    ev_margin_required: float = EV_MARGIN_REQUIRED,
) -> dict[str, Any]:
    """Return switch authorization metadata; may suggest fallback action."""
    proposed_action = _s(proposed_action).upper()
    state = state or {}
    prev = _s(state.get("last_executed_action")) or _s(state.get("last_action"))
    prev_at = state.get("last_action_at")
    raev = scenario_raev or {}
    cooldown = state.get("cooldown_status") or {}
    churn_risk = _s(state.get("churn_risk"), "LOW")

    proposed_raev = _f(raev.get(proposed_action))
    baseline_action = prev if prev in raev else ("HOLD_PAPER" if held else "SKIP_PAPER")
    baseline_raev = _f(raev.get(baseline_action))
    margin_act = ev_margin_actual(proposed_raev, baseline_raev)

    base = {
        "ticker": ticker.upper(),
        "previous_action": prev or None,
        "previous_action_at": prev_at,
        "proposed_action": proposed_action,
        "ev_margin_actual": margin_act,
        "ev_margin_required": ev_margin_required,
        "cooldown_status": cooldown,
        "churn_risk": churn_risk,
        "hard_rule_bypass": bool(hard_rule_override),
    }

    if not prev or proposed_action == prev:
        return {
            **base,
            "decision_switch_authorized": True,
            "switch_authorized": True,
            "switch_reason": "same_action_or_no_prior",
            "final_action": proposed_action,
        }

    if hard_rule_override:
        return {
            **base,
            "decision_switch_authorized": True,
            "switch_authorized": True,
            "switch_reason": "hard_rule_bypass",
            "final_action": proposed_action,
        }

    current_pct = _f((loss_context or {}).get("current_pct"))
    loss_breach = current_pct <= -5.0
    risk_deterioration = current_pct <= -3.0 or bool((loss_context or {}).get("weak_rule_evidence"))

    # BUY -> SELL
    if prev == "BUY_PAPER" and proposed_action == "SELL_PAPER":
        if loss_breach or risk_deterioration:
            return {
                **base,
                "decision_switch_authorized": True,
                "switch_authorized": True,
                "switch_reason": "loss_breach_or_risk_deterioration",
                "final_action": proposed_action,
            }
        if margin_act >= ev_margin_required:
            return {
                **base,
                "decision_switch_authorized": True,
                "switch_authorized": True,
                "switch_reason": "ev_margin_met",
                "final_action": proposed_action,
            }
        return {
            **base,
            "decision_switch_authorized": False,
            "switch_authorized": False,
            "switch_reason": "insufficient_ev_margin_hold",
            "final_action": "HOLD_PAPER",
        }

    # SELL -> BUY (STOP_REENTRY_CHURN)
    if prev == "SELL_PAPER" and proposed_action == "BUY_PAPER":
        if cooldown.get("active"):
            strong = margin_act >= ev_margin_required * STRONG_EV_MULTIPLIER and not state.get("last_hard_rule_action")
            if strong:
                return {
                    **base,
                    "decision_switch_authorized": True,
                    "switch_authorized": True,
                    "switch_reason": "strong_ev_cooldown_exception",
                    "final_action": proposed_action,
                }
            return {
                **base,
                "decision_switch_authorized": False,
                "switch_authorized": False,
                "switch_reason": "STOP_REENTRY_CHURN_ENFORCED",
                "final_action": "SKIP_PAPER",
            }
        if margin_act >= ev_margin_required:
            return {
                **base,
                "decision_switch_authorized": True,
                "switch_authorized": True,
                "switch_reason": "ev_margin_met_post_cooldown",
                "final_action": proposed_action,
            }
        return {
            **base,
            "decision_switch_authorized": False,
            "switch_authorized": False,
            "switch_reason": "insufficient_ev_margin_skip",
            "final_action": "SKIP_PAPER",
        }

    # PROTECT -> SELL
    if prev == "PROTECT_PAPER" and proposed_action == "SELL_PAPER":
        if loss_breach or risk_deterioration or margin_act >= ev_margin_required:
            return {
                **base,
                "decision_switch_authorized": True,
                "switch_authorized": True,
                "switch_reason": "protect_exit_authorized",
                "final_action": proposed_action,
            }
        return {
            **base,
            "decision_switch_authorized": False,
            "switch_authorized": False,
            "switch_reason": "protect_hold_insufficient_ev",
            "final_action": "HOLD_PAPER",
        }

    # Generic opposite trade switch
    if prev in TRADE_ACTIONS and proposed_action in TRADE_ACTIONS and proposed_action != prev:
        if margin_act >= ev_margin_required:
            return {
                **base,
                "decision_switch_authorized": True,
                "switch_authorized": True,
                "switch_reason": "generic_ev_margin_met",
                "final_action": proposed_action,
            }
        fallback = "HOLD_PAPER" if held else "SKIP_PAPER"
        return {
            **base,
            "decision_switch_authorized": False,
            "switch_authorized": False,
            "switch_reason": "generic_insufficient_ev_margin",
            "final_action": fallback,
        }

    return {
        **base,
        "decision_switch_authorized": True,
        "switch_authorized": True,
        "switch_reason": "non_trade_or_allowed",
        "final_action": proposed_action,
    }


def apply_decision_state_gate(
    ticker: str,
    proposed_action: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    hard_risk_discipline: dict[str, Any],
    loss_discipline: dict[str, Any],
    scenario_ev_table: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gate PDE action against active decision state — hard rules bypass."""
    held = bool((ctx.get("paper_positions") or {}).get(ticker.upper()))
    state = (ctx.get("active_decisions_by_ticker") or {}).get(ticker.upper()) or {}
    raev = scenario_raev_map(scenario_ev_table or (ctx.get("conflict_resolution_by_ticker") or {}).get(ticker.upper(), {}).get("scenario_ev_table"))
    hard_override = bool(hard_risk_discipline.get("override"))

    switch = evaluate_action_switch(
        ticker,
        proposed_action,
        state=state,
        hard_rule_override=hard_override,
        scenario_raev=raev,
        loss_context=loss_discipline if isinstance(loss_discipline, dict) else {},
        held=held,
    )

    final_action = _s(switch.get("final_action"), proposed_action)
    if final_action != proposed_action and not hard_override:
        scores[final_action] = max(scores.get(final_action, 0.0), scores.get(proposed_action, 0.0) + 25.0)
        scores[proposed_action] = max(0.0, scores.get(proposed_action, 0.0) - 20.0)
        evidence.append(
            f"decision state gate: {proposed_action}->{final_action} ({switch.get('switch_reason')}) "
            f"margin={switch.get('ev_margin_actual')}/{switch.get('ev_margin_required')}"
        )

    return {
        "source": str(ACTIVE_JSON),
        "decision_state_evidence": switch,
        "decision_switch_authorized": bool(switch.get("decision_switch_authorized")),
        "switch_reason": switch.get("switch_reason"),
        "previous_action": switch.get("previous_action"),
        "previous_action_at": switch.get("previous_action_at"),
        "cooldown_status": switch.get("cooldown_status"),
        "churn_risk": switch.get("churn_risk"),
        "ev_margin_actual": switch.get("ev_margin_actual"),
        "ev_margin_required": switch.get("ev_margin_required"),
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def write_decision_state_report(payload: dict[str, Any]) -> None:
    lines = [
        "# TAE Decision State Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        "**Mode:** PAPER_ONLY — active decision view — NO_BROKER",
        f"**Tickers tracked:** {payload.get('ticker_count', 0)}",
        f"**Cooldown window:** {payload.get('cooldown_minutes_default')} minutes",
        f"**EV switch margin required:** {payload.get('ev_margin_required_default')}",
        "",
        "| ticker | last executed | position | cooldown | churn | changes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for ticker, row in sorted((payload.get("tickers") or {}).items()):
        cd = row.get("cooldown_status") or {}
        lines.append(
            f"| {ticker} | {row.get('last_executed_action') or '-'} | {row.get('current_position_status')} | "
            f"{'active' if cd.get('active') else 'no'} | {row.get('churn_risk')} | {row.get('action_change_count')} |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| live_promotion_allowed | **false** |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    assert_safe_output_path(ACTIVE_JSON)
    assert_safe_output_path(REPORT_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    from tae_learning_persistence import atomic_write_json

    atomic_write_json(ACTIVE_JSON, payload)
    write_decision_state_report(payload)
    return ACTIVE_JSON, REPORT_MD


def run_decision_state_refresh(*, write_outputs_flag: bool = True) -> dict[str, Any]:
    payload = build_active_decisions()
    if write_outputs_flag:
        paths = write_outputs(payload)
        print("===== TAE DECISION STATE =====")
        print(f"Tickers: {payload.get('ticker_count', 0)}")
        print("Wrote:", *paths)
    return payload


def main() -> int:
    run_decision_state_refresh(write_outputs_flag=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
