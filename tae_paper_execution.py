#!/usr/bin/env python3
"""
TAE PAPER Execution — apply validated PDE decisions to isolated PAPER portfolio.

PAPER_ONLY | NO_BROKER | NO_LIVE_EXECUTION | NO_LIVE_PROMOTION
Writes only to runtime_outputs/paper_execution/ — never touches live_bot.py or portfolio.csv.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae.paper_portfolio.v1"
MODE = "PAPER_ONLY"

OUTPUT_DIR = Path("runtime_outputs/paper_execution")
PORTFOLIO_JSON = OUTPUT_DIR / "paper_portfolio.json"
ORDERS_JSONL = OUTPUT_DIR / "paper_orders.jsonl"
TRADES_JSONL = OUTPUT_DIR / "paper_trades.jsonl"
ATTRIBUTION_JSON = OUTPUT_DIR / "rule_outcome_attribution.json"
MTM_JSON = OUTPUT_DIR / "mark_to_market.json"
REPORT_MD = Path("TAE_PAPER_EXECUTION_REPORT.md")
MTM_REPORT_MD = Path("TAE_PAPER_MARK_TO_MARKET_REPORT.md")
CANONICAL_VS_PAPER_MD = Path("TAE_CANONICAL_VS_PAPER_REPORT.md")

DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")

INFLUENCE_DELTA_CAP = 0.008

FORBIDDEN_WRITE_PREFIXES = (
    "live_bot.py",
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "core/",
    "research_core/",
)

PAPER_ACTIONS = frozenset(
    {
        "BUY_PAPER",
        "SELL_PAPER",
        "PROTECT_PAPER",
        "REDUCE_PAPER",
        "ROTATE_PAPER",
        "HOLD_PAPER",
        "SKIP_PAPER",
    }
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


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def assert_safe_path(path: Path) -> None:
    resolved = str(path.resolve())
    out_root = OUTPUT_DIR.resolve()
    if out_root not in path.resolve().parents and path.resolve() != out_root:
        if path.suffix == ".md" and path.parent.resolve() == Path(".").resolve():
            return
        raise RuntimeError(f"Unsafe output path outside {OUTPUT_DIR}: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def save_json(path: Path, payload: dict[str, Any]) -> None:
    assert_safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    assert_safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")


RECONCILE_EPS = 0.02


def recalc_portfolio(portfolio: dict[str, Any]) -> None:
    positions = portfolio.get("positions") or {}
    open_value = 0.0
    unrealized = 0.0
    for pos in positions.values():
        shares = _f(pos.get("shares"))
        avg_price = _f(pos.get("avg_price"))
        current_price = _f(pos.get("current_price")) or avg_price
        current_value = shares * current_price
        pnl = (current_price - avg_price) * shares if avg_price > 0 else 0.0
        pos["current_price"] = round(current_price, 6)
        pos["current_value"] = round(current_value, 4)
        pos["pnl"] = round(pnl, 4)
        if avg_price > 0:
            pos["current_pct"] = round(((current_price - avg_price) / avg_price) * 100, 4)
            pos["unrealized_pct"] = pos["current_pct"]
            price_high = max(_f(pos.get("price_high")), current_price)
            pos["price_high"] = round(price_high, 6)
            if price_high > 0:
                pos["drawdown_pct"] = round(((price_high - current_price) / price_high) * 100, 4)
        open_value += current_value
        unrealized += pnl
    cash = _f(portfolio.get("cash"))
    realized = _f(portfolio.get("realized_pnl"))
    portfolio["open_positions_value"] = round(open_value, 4)
    portfolio["unrealized_pnl"] = round(unrealized, 4)
    portfolio["total_pnl"] = round(realized + unrealized, 4)
    portfolio["total_value"] = round(cash + open_value, 4)
    starting = _f(portfolio.get("starting_value"))
    if starting > 0:
        portfolio["value_delta"] = round(_f(portfolio.get("total_value")) - starting, 4)
    portfolio["updated_at"] = _now()


def _position_snapshot(pos: dict[str, Any] | None) -> dict[str, Any]:
    if not pos:
        return {"shares": 0.0, "avg_price": 0.0, "current_price": 0.0, "current_value": 0.0, "pnl": 0.0}
    return {
        "shares": _f(pos.get("shares")),
        "avg_price": _f(pos.get("avg_price")),
        "current_price": _f(pos.get("current_price")),
        "current_value": _f(pos.get("current_value")),
        "pnl": _f(pos.get("pnl")),
        "protect_mode": pos.get("protect_mode"),
        "status": pos.get("status", "CLOSED"),
    }


def price_for_ticker(ticker: str, accounting: dict[str, Any] | None, decision: dict[str, Any]) -> float:
    for row in (accounting or {}).get("open_positions") or []:
        if _s(row.get("ticker")).upper() == ticker:
            px = _f(row.get("current_price"))
            if px > 0:
                return px
    pos = (decision.get("portfolio_snapshot") or {})
    px = _f(pos.get("current_price"))
    if px > 0:
        return px
    return 0.0


def fill_price_for_position(
    pos: dict[str, Any] | None,
    ticker: str,
    accounting: dict[str, Any] | None,
    decision: dict[str, Any],
) -> float:
    """MTM/current price for fills — never use avg_price or synthetic defaults as fill."""
    if pos:
        px = _f(pos.get("current_price"))
        if px > 0:
            return px
    px = price_for_ticker(ticker, accounting, decision)
    if px > 0 and pos:
        avg = _f(pos.get("avg_price"))
        if avg > 0 and abs(px - avg) < 0.0001:
            px = 0.0
    if px > 0:
        return px
    return 0.0


def _canonical_account_value(accounting: dict[str, Any] | None) -> float:
    acct = accounting or {}
    for key in ("account_value_corrected", "account_value_cash_based", "total_account_value"):
        value = _f(acct.get(key))
        if value > 0:
            return value
    cash = _f(acct.get("cash_available"))
    open_val = _f(acct.get("open_positions_value"))
    if cash + open_val > 0:
        return cash + open_val
    return _f(acct.get("effective_contributed_capital"), 30000.0)


def _validation_capital_base(accounting: dict[str, Any] | None) -> float:
    acct = accounting or {}
    contributed = _f(acct.get("effective_contributed_capital"))
    if contributed > 0:
        return contributed
    return _canonical_account_value(acct)


def paper_portfolio_has_synthetic_fill_corruption(
    portfolio: dict[str, Any],
    accounting: dict[str, Any] | None = None,
) -> bool:
    """Detect inflated PAPER state from legacy $100 synthetic fill fallback."""
    canon = _canonical_account_value(accounting)
    paper_val = _f(portfolio.get("total_value"))
    if canon > 0 and paper_val - canon > 1000:
        return True
    for pos in (portfolio.get("positions") or {}).values():
        avg = _f(pos.get("avg_price"))
        current = _f(pos.get("current_price"))
        if abs(avg - 100.0) < 0.01 and current > 150:
            return True
    if TRADES_JSONL.is_file():
        buy_at_100 = 0
        for line in TRADES_JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                trade = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _s(trade.get("action")).upper() != "BUY_PAPER":
                continue
            if abs(_f(trade.get("fill_price")) - 100.0) < 0.01:
                buy_at_100 += 1
        if buy_at_100 >= 3:
            return True
    return False


def reset_paper_portfolio_from_accounting(
    accounting: dict[str, Any] | None = None,
    *,
    archive_ledger: bool = True,
) -> dict[str, Any]:
    """Rebuild PAPER portfolio from canonical accounting; archive corrupt ledger."""
    acct = accounting or load_json(ACCOUNTING_JSON) or {}
    archive_dir = OUTPUT_DIR / "archive" / "capital_base_defect_reset"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now().replace(":", "").replace("+", "")
    if archive_ledger:
        for path in (PORTFOLIO_JSON, ORDERS_JSONL, TRADES_JSONL):
            if not path.is_file():
                continue
            dest = archive_dir / f"{path.name}.{stamp}"
            dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            if path.suffix == ".jsonl":
                path.write_text("", encoding="utf-8")
    portfolio = bootstrap_portfolio(acct, None)
    recalc_portfolio(portfolio)
    portfolio["validation_capital_base"] = round(_validation_capital_base(acct), 2)
    portfolio["starting_value"] = round(_f(portfolio.get("total_value")), 2)
    portfolio["baseline_unrealized_pnl"] = round(_f(portfolio.get("unrealized_pnl")), 4)
    portfolio["realized_pnl_at_baseline"] = 0.0
    portfolio["realized_pnl"] = 0.0
    portfolio["processed_decision_ids"] = []
    portfolio.pop("accounting_baseline_v1", None)
    portfolio["capital_base_reset_at"] = _now()
    portfolio["capital_base_reset_reason"] = "SYNTHETIC_100_FILL_DEFECT"
    recalc_portfolio(portfolio)
    save_json(PORTFOLIO_JSON, portfolio)
    return portfolio


def extract_rule_sources(decision: dict[str, Any]) -> list[str]:
    rules: list[str] = []
    for hyp in decision.get("hypothesis_rules_applied") or []:
        rid = _s(hyp.get("hypothesis_id"))
        if rid:
            rules.append(rid)
    ke = decision.get("knowledge_evidence") or {}
    for rid in ke.get("rules_applied") or []:
        if rid:
            rules.append(str(rid))
    for rid in ke.get("named_confidence_rules") or []:
        if rid and rid not in rules:
            rules.append(str(rid))
    lk = decision.get("longitudinal_knowledge_evidence") or {}
    for rid in lk.get("rules_applied") or lk.get("rule_ids") or []:
        if rid:
            rules.append(str(rid))
    return list(dict.fromkeys(rules))[:8]


def bootstrap_portfolio(accounting: dict[str, Any] | None, existing: dict[str, Any] | None) -> dict[str, Any]:
    if existing and existing.get("schema") == SCHEMA:
        return existing

    acct = accounting or {}
    cash = _f(acct.get("cash_available"))
    total = _f(acct.get("account_value_corrected") or acct.get("total_account_value"))
    if total <= 0:
        total = _f(acct.get("effective_contributed_capital"), 30000.0)
    if cash <= 0 and total > 0:
        cash = total * 0.08

    positions: dict[str, dict[str, Any]] = {}
    for row in acct.get("open_positions") or []:
        ticker = _s(row.get("ticker")).upper()
        shares = _f(row.get("shares"))
        if not ticker or shares <= 0:
            continue
        current_price = _f(row.get("current_price"))
        avg_price = current_price
        if avg_price <= 0:
            continue
        positions[ticker] = {
            "ticker": ticker,
            "shares": round(shares, 6),
            "avg_price": round(avg_price, 6),
            "current_price": round(current_price, 6),
            "current_value": round(shares * current_price, 4),
            "pnl": round(_f(row.get("pnl")), 4),
            "current_pct": round(_f(row.get("pnl_pct")), 4),
            "status": "OPEN",
            "protect_mode": None,
        }

    portfolio = {
        "schema": SCHEMA,
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
        "source": str(ACCOUNTING_JSON),
        "created_at": _now(),
        "updated_at": _now(),
        "starting_value": 0.0,
        "baseline_unrealized_pnl": 0.0,
        "cash": round(cash, 2),
        "open_positions_value": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_pnl": 0.0,
        "total_value": 0.0,
        "positions": positions,
        "processed_decision_ids": [],
    }
    recalc_portfolio(portfolio)
    portfolio["validation_capital_base"] = round(_validation_capital_base(acct), 2)
    portfolio["starting_value"] = round(_f(portfolio.get("total_value")), 2)
    portfolio["baseline_unrealized_pnl"] = round(_f(portfolio.get("unrealized_pnl")), 4)
    portfolio["realized_pnl_at_baseline"] = round(_f(portfolio.get("realized_pnl")), 4)
    return portfolio


def _sell_shares(
    portfolio: dict[str, Any],
    ticker: str,
    shares_to_sell: float,
    fill_price: float,
) -> tuple[float, float, dict[str, Any] | None]:
    """Returns (realized_pnl, gross_proceeds, after_position_or_none)."""
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if not pos:
        return 0.0, 0.0, None
    shares_before = _f(pos.get("shares"))
    avg_price = _f(pos.get("avg_price"))
    shares_to_sell = min(shares_to_sell, shares_before)
    if shares_to_sell <= 0:
        return 0.0, 0.0, pos
    cost_basis = round(avg_price * shares_to_sell, 4) if avg_price > 0 else 0.0
    gross_proceeds = round(shares_to_sell * fill_price, 4)
    realized = round(gross_proceeds - cost_basis, 4) if avg_price > 0 else 0.0
    shares_after = round(shares_before - shares_to_sell, 6)
    portfolio["cash"] = round(_f(portfolio.get("cash")) + gross_proceeds, 4)
    portfolio["realized_pnl"] = round(_f(portfolio.get("realized_pnl")) + realized, 4)
    if shares_after <= 0.000001:
        positions.pop(ticker, None)
        return realized, gross_proceeds, None
    pos["shares"] = shares_after
    pos["status"] = "OPEN"
    return realized, gross_proceeds, pos


def _buy_shares(
    portfolio: dict[str, Any],
    ticker: str,
    notional: float,
    price: float,
) -> tuple[float, dict[str, Any]]:
    if price <= 0 or notional <= 0:
        return 0.0, portfolio.get("positions", {}).get(ticker) or {}
    cash = _f(portfolio.get("cash"))
    notional = min(notional, cash)
    if notional <= 0:
        return 0.0, portfolio.get("positions", {}).get(ticker) or {}
    shares = round(notional / price, 6)
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker) or {
        "ticker": ticker,
        "shares": 0.0,
        "avg_price": 0.0,
        "current_price": price,
        "status": "OPEN",
        "protect_mode": None,
    }
    prev_shares = _f(pos.get("shares"))
    prev_avg = _f(pos.get("avg_price"))
    new_shares = prev_shares + shares
    if new_shares > 0:
        pos["avg_price"] = round(
            ((prev_shares * prev_avg) + (shares * price)) / new_shares,
            6,
        )
    pos["shares"] = round(new_shares, 6)
    pos["current_price"] = round(price, 6)
    pos["status"] = "OPEN"
    positions[ticker] = pos
    portfolio["cash"] = round(cash - notional, 4)
    return shares, pos


def best_rotate_target(decisions: list[dict[str, Any]], source_ticker: str) -> dict[str, Any] | None:
    candidates = [
        d
        for d in decisions
        if _s(d.get("action")).upper() == "BUY_PAPER"
        and _s(d.get("ticker")).upper() != source_ticker
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: _f(d.get("confidence")) * _f(d.get("expected_profit_delta"), 1.0))


def _has_open_position(before: dict[str, Any]) -> bool:
    return _f(before.get("shares")) > 0


def _portfolio_snapshot(portfolio: dict[str, Any]) -> dict[str, Any]:
    positions = portfolio.get("positions") or {}
    return {
        "cash": round(_f(portfolio.get("cash")), 4),
        "positions_count": len(positions),
        "realized_pnl": round(_f(portfolio.get("realized_pnl")), 4),
        "unrealized_pnl": round(_f(portfolio.get("unrealized_pnl")), 4),
        "total_pnl": round(_f(portfolio.get("total_pnl")), 4),
        "total_value": round(_f(portfolio.get("total_value")), 4),
        "open_positions_value": round(_f(portfolio.get("open_positions_value")), 4),
    }


def _action_changed_flag(execution_reason: str) -> bool:
    return execution_reason.startswith("action_changed:")


def execute_decision(
    decision: dict[str, Any],
    portfolio: dict[str, Any],
    *,
    accounting: dict[str, Any] | None,
    all_decisions: list[dict[str, Any]],
    execution_reason: str = "new_decision",
) -> dict[str, Any]:
    action = _s(decision.get("action")).upper()
    ticker = _s(decision.get("ticker")).upper()
    decision_id = _s(decision.get("decision_id"))
    confidence = _f(decision.get("confidence"), 0.5)
    risk_score = _f(decision.get("risk_score"))
    expected_delta = _f(decision.get("expected_profit_delta"))
    rule_sources = extract_rule_sources(decision)

    positions = portfolio.setdefault("positions", {})
    pos_ref = positions.get(ticker)
    fill_price = fill_price_for_position(pos_ref, ticker, accounting, decision)
    price = fill_price
    if fill_price <= 0 and _has_open_position(_position_snapshot(pos_ref)):
        fallback = _f((_position_snapshot(pos_ref)).get("current_price"))
        if fallback > 0:
            fill_price = fallback
            price = fallback

    cash_before = round(_f(portfolio.get("cash")), 4)
    before = _position_snapshot(positions.get(ticker))
    realized_pnl = 0.0
    cost_basis = 0.0
    gross_value = 0.0
    capital_impact = 0.0
    risk_impact = _f(decision.get("expected_risk_delta"))
    reason = _s(decision.get("evidence"))[:240] or action
    fill_shares = 0.0
    status = "NO_CHANGE"
    executed = False
    is_trade = False
    after = before

    requires_position = action in {"SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER"}
    if requires_position and not _has_open_position(before):
        status = "SKIPPED_NO_POSITION"
        reason = f"{action} skipped — no open paper position for {ticker}"
    elif action == "SKIP_PAPER":
        status = "NO_CHANGE"
    elif action == "HOLD_PAPER":
        status = "NO_CHANGE"
    elif action == "SELL_PAPER":
        sell_shares = _f(before.get("shares"))
        avg = _f(before.get("avg_price"))
        cost_basis = round(avg * sell_shares, 4) if avg > 0 else 0.0
        realized_pnl, gross_value, after_pos = _sell_shares(portfolio, ticker, sell_shares, fill_price)
        fill_shares = sell_shares
        capital_impact = round(gross_value, 4)
        after = _position_snapshot(after_pos)
        status = "EXECUTED"
        executed = True
        is_trade = fill_shares > 0
    elif action == "REDUCE_PAPER":
        trim_pct = 30.0 if confidence < 0.7 else 20.0
        trim_shares = _f(before.get("shares")) * (trim_pct / 100.0)
        avg = _f(before.get("avg_price"))
        cost_basis = round(avg * trim_shares, 4) if avg > 0 else 0.0
        realized_pnl, gross_value, after_pos = _sell_shares(portfolio, ticker, trim_shares, fill_price)
        fill_shares = trim_shares
        capital_impact = round(gross_value, 4)
        after = _position_snapshot(after_pos)
        reason = f"REDUCE_PAPER trim {trim_pct:.0f}% — {reason}"
        status = "EXECUTED"
        executed = True
        is_trade = fill_shares > 0
    elif action == "PROTECT_PAPER":
        pos = positions.get(ticker)
        prev_protect = before.get("protect_mode")
        pos["protect_mode"] = "TRAIL_SHADOW"
        if risk_score >= 80 and _f(pos.get("shares")) > 0:
            trim_shares = _f(pos.get("shares")) * 0.1
            avg = _f(before.get("avg_price"))
            cost_basis = round(avg * trim_shares, 4) if avg > 0 else 0.0
            realized_pnl, gross_value, after_pos = _sell_shares(portfolio, ticker, trim_shares, fill_price)
            fill_shares = trim_shares
            after = _position_snapshot(after_pos)
            reason = f"PROTECT_PAPER urgency trim 10% — {reason}"
            is_trade = fill_shares > 0
        else:
            after = _position_snapshot(pos)
            reason = f"PROTECT_PAPER protect-only — {reason}"
        if prev_protect != "TRAIL_SHADOW" or is_trade:
            status = "EXECUTED"
            executed = True
        else:
            status = "NO_CHANGE"
    elif action == "BUY_PAPER":
        if fill_price <= 0:
            status = "SKIPPED_NO_MARK_PRICE"
            reason = f"BUY_PAPER skipped — no mark price for {ticker}"
        else:
            cash = _f(portfolio.get("cash"))
            notional = min(cash * max(0.05, confidence * 0.12), cash * 0.15)
            bought, after_pos = _buy_shares(portfolio, ticker, notional, fill_price)
            fill_shares = bought
            if fill_shares > 0:
                gross_value = round(notional, 4)
                capital_impact = round(-notional, 4)
                after = _position_snapshot(after_pos)
                status = "EXECUTED"
                executed = True
                is_trade = True
            else:
                status = "SKIPPED_NO_CASH"
                reason = f"BUY_PAPER skipped — insufficient cash for {ticker}"
    elif action == "ROTATE_PAPER":
        sell_shares = _f(before.get("shares"))
        avg = _f(before.get("avg_price"))
        cost_basis = round(avg * sell_shares, 4) if avg > 0 else 0.0
        realized_pnl, gross_value, _ = _sell_shares(portfolio, ticker, sell_shares, fill_price)
        rotate_notional = gross_value or _f(before.get("current_value")) or _f(portfolio.get("cash")) * 0.1
        target = best_rotate_target(all_decisions, ticker)
        buy_fill = 0.0
        if target and rotate_notional > 0:
            tgt_ticker = _s(target.get("ticker")).upper()
            tgt_price = fill_price_for_position(
                (portfolio.get("positions") or {}).get(tgt_ticker),
                tgt_ticker,
                accounting,
                target,
            )
            buy_fill, after_pos = _buy_shares(portfolio, tgt_ticker, rotate_notional, tgt_price)
            after = _position_snapshot(after_pos)
            reason = f"ROTATE_PAPER {ticker}→{tgt_ticker} — {reason}"
        else:
            after = _position_snapshot(None)
            reason = f"ROTATE_PAPER sell-only (no BUY target) — {reason}"
        fill_shares = sell_shares if sell_shares > 0 else buy_fill
        capital_impact = round(rotate_notional - gross_value, 4)
        status = "EXECUTED"
        executed = sell_shares > 0 or buy_fill > 0
        is_trade = sell_shares > 0 or buy_fill > 0
    else:
        reason = f"unknown action {action} — skipped"

    if status != "SKIPPED_NO_POSITION":
        recalc_portfolio(portfolio)

    cash_after = round(_f(portfolio.get("cash")), 4)

    order = {
        "timestamp": _now(),
        "decision_id": decision_id,
        "ticker": ticker,
        "action": action,
        "status": status,
        "executed": executed,
        "is_trade": is_trade,
        "fill_shares": round(fill_shares, 6),
        "fill_price": round(fill_price, 6),
        "gross_value": round(gross_value, 4),
        "cost_basis": round(cost_basis, 4),
        "realized_pnl": round(realized_pnl, 4),
        "cash_before": cash_before,
        "cash_after": cash_after,
        "position_before": before,
        "position_after": after,
        "action_changed": _action_changed_flag(execution_reason),
        "execution_reason": execution_reason,
        "rule_sources": rule_sources,
        "before_position": before,
        "after_position": after,
        "simulated_pnl_impact": round(realized_pnl, 4),
        "expected_profit_delta": expected_delta,
        "capital_impact": capital_impact,
        "risk_impact": risk_impact,
        "price": round(fill_price, 6),
        "confidence": confidence,
        "reason": reason,
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
    }
    return order


def build_rule_attribution(
    orders: list[dict[str, Any]],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = dict((previous or {}).get("rules") or {})
    for order in orders:
        if not order.get("executed"):
            continue
        pnl = _f(order.get("realized_pnl")) or _f(order.get("simulated_pnl_impact"))
        expected = _f(order.get("expected_profit_delta"))
        outcome = pnl if pnl != 0 else (expected * 0.1)
        positive = outcome >= 0
        for rule_id in order.get("rule_sources") or []:
            entry = rules.setdefault(
                rule_id,
                {
                    "rule_id": rule_id,
                    "executions": 0,
                    "positive_outcomes": 0,
                    "negative_outcomes": 0,
                    "net_pnl_impact": 0.0,
                    "weight_delta": 0.0,
                },
            )
            entry["executions"] += 1
            entry["net_pnl_impact"] = round(_f(entry.get("net_pnl_impact")) + outcome, 4)
            if positive:
                entry["positive_outcomes"] += 1
                entry["weight_delta"] = round(_f(entry.get("weight_delta")) + 0.008, 4)
            else:
                entry["negative_outcomes"] += 1
                entry["weight_delta"] = round(_f(entry.get("weight_delta")) - 0.008, 4)
            entry["last_action"] = order.get("action")
            entry["last_ticker"] = order.get("ticker")
            entry["last_outcome"] = "positive" if positive else "negative"

    executed_orders = sum(1 for o in orders if o.get("executed"))
    return {
        "schema": "tae.rule_outcome_attribution.v1",
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
        "generated_at": _now(),
        "rules": rules,
        "orders_processed": executed_orders,
    }


def _count_jsonl_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def sanitize_trades_file(path: Path) -> int:
    """Remove invalid zero-position or zero-share trade rows from prior runs."""
    if not path.is_file():
        return 0
    kept: list[str] = []
    removed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            removed += 1
            continue
        shares = _f(row.get("fill_shares") or row.get("shares"))
        action = _s(row.get("action")).upper()
        before = row.get("before_position") or {}
        if shares <= 0 and action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"}:
            shares = _f(before.get("shares"))
        if shares <= 0:
            removed += 1
            continue
        if action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"} and _f(before.get("shares")) <= 0:
            removed += 1
            continue
        kept.append(line)
    if removed:
        assert_safe_path(path)
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed


def validate_trades_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return errors
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid jsonl line: {exc}")
            continue
        if row.get("is_trade") or row.get("record_type") == "paper_trade":
            enrich_trade_record(row)
        errors.extend(validate_trade_record(row))
    return errors


def trade_realized_from_record(trade: dict[str, Any]) -> float:
    if trade.get("realized_pnl") is not None and _f(trade.get("realized_pnl")) != 0:
        return _f(trade.get("realized_pnl"))
    before = trade.get("before_position") or trade.get("position_before") or {}
    shares = _f(trade.get("fill_shares") or trade.get("shares"))
    avg = _f(before.get("avg_price"))
    fill = _f(trade.get("fill_price"))
    legacy_price = _f(trade.get("price"))
    current = _f(before.get("current_price"))
    if fill <= 0:
        fill = legacy_price
    if current > 0 and (fill <= 0 or (avg > 0 and abs(fill - avg) < 0.0001 and abs(current - avg) > 0.0001)):
        fill = current
    if fill <= 0:
        fill = avg
    if shares > 0 and avg > 0 and fill > 0:
        return round((fill - avg) * shares, 4)
    simulated = _f(trade.get("simulated_pnl_impact"))
    if simulated != 0:
        return simulated
    return 0.0


def enrich_trade_record(trade: dict[str, Any]) -> dict[str, Any]:
    """Backfill ledger fields on legacy trade rows."""
    before = trade.get("before_position") or trade.get("position_before") or {}
    after = trade.get("after_position") or trade.get("position_after") or {}
    shares = _f(trade.get("fill_shares") or trade.get("shares"))
    avg = _f(before.get("avg_price"))
    fill = _f(trade.get("fill_price"))
    legacy_price = _f(trade.get("price"))
    current = _f(before.get("current_price"))
    if fill <= 0:
        fill = legacy_price
    if current > 0 and (fill <= 0 or (avg > 0 and abs(fill - avg) < 0.0001 and abs(current - avg) > 0.0001)):
        fill = current
    if fill <= 0:
        fill = avg
    gross = _f(trade.get("gross_value"))
    if gross <= 0 and shares > 0 and fill > 0:
        gross = round(shares * fill, 4)
    cost = _f(trade.get("cost_basis"))
    if cost <= 0 and shares > 0 and avg > 0:
        cost = round(shares * avg, 4)
    trade.setdefault("fill_price", round(fill, 6) if fill > 0 else 0.0)
    trade.setdefault("gross_value", gross)
    trade.setdefault("cost_basis", cost)
    trade.setdefault("position_before", before)
    trade.setdefault("position_after", after)
    trade.setdefault("before_position", before)
    trade.setdefault("after_position", after)
    trade.setdefault("action_changed", bool(trade.get("action_changed") or _action_changed_flag(_s(trade.get("execution_reason")))))
    trade.setdefault("broker_executed", False)
    trade.setdefault("live_money", False)
    realized = round((fill - avg) * shares, 4) if shares > 0 and avg > 0 and fill > 0 else trade_realized_from_record(trade)
    if trade.get("realized_pnl") is None or (
        _f(trade.get("realized_pnl")) == 0 and realized != 0
    ):
        trade["realized_pnl"] = realized
    trade["simulated_pnl_impact"] = round(_f(trade.get("realized_pnl")), 4)
    return trade


def ensure_accounting_baseline(portfolio: dict[str, Any]) -> bool:
    """One-time baseline for value_delta reconciliation after accounting hardening."""
    if portfolio.get("accounting_baseline_v1"):
        return False
    recalc_portfolio(portfolio)
    accounting = load_json(ACCOUNTING_JSON) or {}
    if portfolio.get("validation_capital_base") is None:
        portfolio["validation_capital_base"] = round(_validation_capital_base(accounting), 2)
    portfolio["starting_value"] = round(_f(portfolio.get("total_value")), 2)
    portfolio["baseline_unrealized_pnl"] = round(_f(portfolio.get("unrealized_pnl")), 4)
    portfolio["realized_pnl_at_baseline"] = round(_f(portfolio.get("realized_pnl")), 4)
    portfolio["accounting_baseline_v1"] = _now()
    return True


def backfill_portfolio_realized_from_trades(portfolio: dict[str, Any], trades_path: Path | None = None) -> bool:
    """Recompute cumulative realized_pnl and cash from trade ledger if stale."""
    path = trades_path or TRADES_JSONL
    trades = load_jsonl(path)
    if not trades:
        return False
    total_realized = 0.0
    cash_delta = 0.0
    changed_trades = False
    enriched: list[str] = []
    sell_actions = {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER", "PROTECT_PAPER"}

    for trade in trades:
        is_trade = trade.get("record_type") == "paper_trade" or trade.get("is_trade")
        if not is_trade:
            enriched.append(json.dumps(trade, separators=(",", ":"), ensure_ascii=False))
            continue
        action = _s(trade.get("action")).upper()
        before = trade.get("before_position") or trade.get("position_before") or {}
        old_fill = _f(trade.get("fill_price") or trade.get("price"))
        old_gross = _f(trade.get("gross_value"))
        if old_gross <= 0 and _f(trade.get("fill_shares")) > 0 and old_fill > 0:
            old_gross = round(_f(trade.get("fill_shares")) * old_fill, 4)
        prior_realized = trade.get("realized_pnl")
        enrich_trade_record(trade)
        if (
            prior_realized != trade.get("realized_pnl")
            or abs(old_fill - _f(trade.get("fill_price"))) > RECONCILE_EPS
            or abs(old_gross - _f(trade.get("gross_value"))) > RECONCILE_EPS
        ):
            changed_trades = True
        if action in sell_actions:
            rp = trade_realized_from_record(trade)
            if action == "PROTECT_PAPER" and rp == 0:
                enriched.append(json.dumps(trade, separators=(",", ":"), ensure_ascii=False))
                continue
            new_gross = _f(trade.get("gross_value"))
            if old_gross > 0 and new_gross > 0:
                cash_delta += new_gross - old_gross
            total_realized += rp
        enriched.append(json.dumps(trade, separators=(",", ":"), ensure_ascii=False))

    current = _f(portfolio.get("realized_pnl"))
    needs_update = abs(current - total_realized) > RECONCILE_EPS or abs(cash_delta) > RECONCILE_EPS
    if needs_update or changed_trades:
        if abs(cash_delta) > RECONCILE_EPS:
            portfolio["cash"] = round(_f(portfolio.get("cash")) + cash_delta, 4)
        portfolio["realized_pnl"] = round(total_realized, 4)
        recalc_portfolio(portfolio)
        if changed_trades or needs_update:
            if path.resolve() == TRADES_JSONL.resolve() or TRADES_JSONL.resolve() in path.resolve().parents:
                assert_safe_path(path)
            path.write_text("\n".join(enriched) + ("\n" if enriched else ""), encoding="utf-8")
        return True
    return changed_trades


def validate_portfolio_reconciliation(portfolio: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    cash = _f(portfolio.get("cash"))
    open_val = _f(portfolio.get("open_positions_value"))
    total_val = _f(portfolio.get("total_value"))
    realized = _f(portfolio.get("realized_pnl"))
    unrealized = _f(portfolio.get("unrealized_pnl"))
    total_pnl = _f(portfolio.get("total_pnl"))
    starting = _f(portfolio.get("starting_value"))

    positions = portfolio.get("positions") or {}
    computed_open = sum(_f(p.get("current_value")) for p in positions.values())
    computed_unrealized = sum(_f(p.get("pnl")) for p in positions.values())

    def add_check(name: str, expected: float, actual: float, formula: str) -> None:
        ok = abs(expected - actual) <= RECONCILE_EPS
        checks.append({"name": name, "expected": round(expected, 4), "actual": round(actual, 4), "ok": ok, "formula": formula})
        if not ok:
            errors.append(f"{name}: expected {expected:.4f} actual {actual:.4f} ({formula})")

    add_check("total_value", cash + open_val, total_val, "cash + open_positions_value")
    add_check("open_positions_value", computed_open, open_val, "sum(position.current_value)")
    add_check("unrealized_pnl", computed_unrealized, unrealized, "sum(position.pnl)")
    add_check("total_pnl", realized + unrealized, total_pnl, "realized_pnl + unrealized_pnl")
    # value_delta vs total_pnl only when bootstrap baseline is consistent
    if starting > 0 and portfolio.get("baseline_unrealized_pnl") is not None:
        baseline_unreal = _f(portfolio.get("baseline_unrealized_pnl"))
        realized_at_baseline = _f(portfolio.get("realized_pnl_at_baseline"))
        expected_delta = (realized - realized_at_baseline) + (unrealized - baseline_unreal)
        value_delta = _f(portfolio.get("value_delta"))
        add_check(
            "value_delta",
            expected_delta,
            value_delta,
            "(realized_pnl - realized_at_baseline) + (unrealized_pnl - baseline_unrealized_pnl)",
        )

    return {
        "ok": not errors,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "checks": checks,
        "cash": cash,
        "open_positions_value": open_val,
        "total_value": total_val,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_pnl": total_pnl,
        "positions_count": len(positions),
    }


def validate_trade_record(trade: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    is_trade_row = trade.get("record_type") == "paper_trade" or trade.get("is_trade") is True
    if not is_trade_row:
        return errors
    shares = _f(trade.get("fill_shares") or trade.get("shares"))
    action = _s(trade.get("action")).upper()
    before = trade.get("before_position") or trade.get("position_before") or {}
    if shares <= 0:
        errors.append(f"{trade.get('decision_id')}: trade fill_shares must be > 0")
    if action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"} and _f(before.get("shares")) <= 0:
        errors.append(f"{trade.get('decision_id')}: {action} trade requires existing position")
    if action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"}:
        rp = trade.get("realized_pnl")
        if rp is None:
            errors.append(f"{trade.get('decision_id')}: {action} trade missing realized_pnl")
        cash_before = trade.get("cash_before")
        cash_after = trade.get("cash_after")
        gross = _f(trade.get("gross_value"))
        if cash_before is not None and cash_after is not None and gross > 0 and action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"}:
            expected_cash = round(_f(cash_before) + gross, 4)
            if abs(expected_cash - _f(cash_after)) > RECONCILE_EPS:
                errors.append(
                    f"{trade.get('decision_id')}: cash_after {cash_after} != cash_before + gross_value ({expected_cash})"
                )
    return errors


def validate_execution_run(
    orders: list[dict[str, Any]],
    *,
    trades_written: int,
    trades_file_lines: int,
    portfolio: dict[str, Any],
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    trade_orders = [o for o in orders if o.get("is_trade")]
    if len(trade_orders) != trades_written:
        errors.append(
            f"trades_written mismatch: is_trade orders={len(trade_orders)} trades_written={trades_written}"
        )
    for order in trade_orders:
        errors.extend(validate_trade_record(order))
    skipped = [o for o in orders if o.get("status") == "SKIPPED_NO_POSITION"]
    for order in skipped:
        if order.get("is_trade"):
            errors.append(f"{order.get('decision_id')}: skipped order must not be a trade")
        before = order.get("before_position") or {}
        if _f(before.get("shares")) > 0:
            errors.append(f"{order.get('decision_id')}: SKIPPED_NO_POSITION but before shares > 0")

    positions = portfolio.get("positions") or {}
    if len(positions) != after_snapshot.get("positions_count"):
        errors.append("positions count does not reconcile with portfolio state")

    reconciliation = validate_portfolio_reconciliation(portfolio)
    if not reconciliation.get("ok"):
        errors.extend(reconciliation.get("errors") or [])

    return {
        "ok": not errors,
        "errors": errors,
        "reconciliation": reconciliation,
        "orders_created": len(orders),
        "orders_executed": sum(1 for o in orders if o.get("executed")),
        "orders_skipped": sum(1 for o in orders if str(o.get("status", "")).startswith("SKIPPED")),
        "trades_written": trades_written,
        "trades_file_lines": trades_file_lines,
        "positions_before": before_snapshot.get("positions_count"),
        "positions_after": after_snapshot.get("positions_count"),
        "cash_before": before_snapshot.get("cash"),
        "cash_after": after_snapshot.get("cash"),
        "realized_pnl": after_snapshot.get("realized_pnl"),
        "unrealized_pnl": after_snapshot.get("unrealized_pnl"),
        "total_pnl": after_snapshot.get("total_pnl"),
        "total_value": after_snapshot.get("total_value"),
    }


def write_report(payload: dict[str, Any]) -> None:
    portfolio = payload.get("portfolio") or {}
    stats = payload.get("stats") or {}
    validation = payload.get("validation") or {}
    reconciliation = validation.get("reconciliation") or {}
    action_counts = payload.get("action_counts") or {}
    lines = [
        "# TAE PAPER Execution Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
        "",
        "## Run summary",
        "",
        f"- Decisions consumed: **{payload.get('decisions_consumed', 0)}**",
        f"- Orders created (this run): **{stats.get('orders_created', 0)}**",
        f"- Orders executed (this run): **{stats.get('orders_executed', 0)}**",
        f"- Orders skipped (this run): **{stats.get('orders_skipped', 0)}**",
        f"- Skipped same action: **{stats.get('skipped_same_action', 0)}**",
        f"- Skipped unauthorized switch: **{stats.get('skipped_switch_not_authorized', 0)}**",
        f"- Accepted action switches: **{stats.get('accepted_action_switches', 0)}**",
        f"- Re-executed on action change: **{stats.get('reexecuted_on_action_change', 0)}**",
        f"- Trades written (this run): **{stats.get('trades_written', 0)}**",
        f"- Trades file total lines: **{stats.get('trades_file_lines', 0)}**",
        "",
        "## Portfolio delta (this run)",
        "",
        f"- Positions before: **{stats.get('positions_before', 0)}**",
        f"- Positions after: **{stats.get('positions_after', 0)}**",
        f"- Cash before: **${ _f(stats.get('cash_before')):,.2f}**",
        f"- Cash after: **${ _f(stats.get('cash_after')):,.2f}**",
        f"- Total value: **${ _f(portfolio.get('total_value')):,.2f}**",
        "",
        "## PnL accounting",
        "",
        f"- Realized PnL: **${ _f(portfolio.get('realized_pnl')):,.2f}**",
        f"- Unrealized PnL: **${ _f(portfolio.get('unrealized_pnl')):,.2f}**",
        f"- Total PnL: **${ _f(portfolio.get('total_pnl')):,.2f}**",
        f"- Value delta vs starting: **${ _f(portfolio.get('value_delta')):,.2f}**",
        "",
        "## Reconciliation",
        "",
        f"- Status: **{reconciliation.get('status', 'UNKNOWN')}**",
        f"- Formula: `total_value = cash + open_positions_value`",
        f"- Formula: `total_pnl = realized_pnl + unrealized_pnl`",
        f"- Formula: `value_delta = total_value - starting_value`",
    ]
    for check in reconciliation.get("checks") or []:
        mark = "PASS" if check.get("ok") else "FAIL"
        lines.append(
            f"- {check.get('name')}: **{mark}** expected={check.get('expected')} actual={check.get('actual')}"
        )
    lines.extend(["", "## Validation", "", f"- Validation OK: **{validation.get('ok', False)}**"])
    for err in validation.get("errors") or []:
        lines.append(f"- Error: {err}")
    if not validation.get("errors"):
        lines.append("- No validation errors")
    lines.extend(["", "## Action summary (this run)", ""])
    for action, count in sorted(action_counts.items()):
        lines.append(f"- {action}: **{count}**")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- broker_executed: **false**",
            "- live_money: **false**",
            "- live_bot.py / portfolio.csv: **untouched**",
            "",
            "## Outputs",
            "",
            f"- `{PORTFOLIO_JSON}`",
            f"- `{ORDERS_JSONL}`",
            f"- `{TRADES_JSONL}`",
            f"- `{ATTRIBUTION_JSON}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_orders_by_decision(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or ORDERS_JSONL
    by_id: dict[str, dict[str, Any]] = {}
    for order in load_jsonl(path):
        did = _s(order.get("decision_id"))
        if did:
            by_id[did] = order
    return by_id


def should_execute_decision(
    decision_id: str,
    action: str,
    *,
    processed: set[str],
    last_orders: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    if not decision_id:
        return False, "missing decision_id"
    if decision_id not in processed:
        return True, "new_decision"
    prior_action = _s((last_orders.get(decision_id) or {}).get("action")).upper()
    if prior_action and prior_action != action:
        return True, f"action_changed:{prior_action}->{action}"
    return False, "already_processed_same_action"


def run_paper_execution(*, write_report_flag: bool = True) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    decisions_doc = load_json(DECISIONS_JSON)
    if not decisions_doc:
        return {"ok": False, "error": f"missing {DECISIONS_JSON}"}

    decisions = list(decisions_doc.get("decisions") or [])
    accounting = load_json(ACCOUNTING_JSON)
    existing = load_json(PORTFOLIO_JSON)
    if existing and paper_portfolio_has_synthetic_fill_corruption(existing, accounting):
        portfolio = reset_paper_portfolio_from_accounting(accounting, archive_ledger=True)
        existing = portfolio
    else:
        portfolio = bootstrap_portfolio(accounting, existing)
    if portfolio.get("baseline_unrealized_pnl") is None:
        portfolio["baseline_unrealized_pnl"] = round(_f(portfolio.get("unrealized_pnl")), 4)
    if portfolio.get("realized_pnl_at_baseline") is None:
        portfolio["realized_pnl_at_baseline"] = round(_f(portfolio.get("realized_pnl")), 4)
    if _f(portfolio.get("starting_value")) <= 0:
        recalc_portfolio(portfolio)
        portfolio["starting_value"] = round(_f(portfolio.get("total_value")), 2)
    if portfolio.get("validation_capital_base") is None:
        portfolio["validation_capital_base"] = round(_validation_capital_base(accounting), 2)
    backfill_portfolio_realized_from_trades(portfolio, TRADES_JSONL)
    baseline_reset = ensure_accounting_baseline(portfolio) if existing else False
    if not baseline_reset:
        recalc_portfolio(portfolio)
    processed = set(portfolio.get("processed_decision_ids") or [])
    last_orders = load_orders_by_decision(ORDERS_JSONL)

    removed_legacy_trades = sanitize_trades_file(TRADES_JSONL)
    before_snapshot = _portfolio_snapshot(portfolio)

    orders: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}
    trades_written = 0
    reexecuted = 0
    skipped_same_action = 0
    skipped_switch = 0
    accepted_switch = 0

    for decision in decisions:
        decision_id = _s(decision.get("decision_id"))
        action = _s(decision.get("action")).upper()
        ok, reason = should_execute_decision(
            decision_id, action, processed=processed, last_orders=last_orders
        )
        if not ok:
            skipped_same_action += 1
            continue
        if action not in PAPER_ACTIONS:
            continue
        if reason.startswith("action_changed"):
            hard_override = bool((decision.get("hard_risk_discipline") or {}).get("override"))
            switch_ok = bool(decision.get("decision_switch_authorized"))
            if not hard_override and not switch_ok:
                skipped_switch += 1
                order = {
                    "timestamp": _now(),
                    "decision_id": decision_id,
                    "ticker": _s(decision.get("ticker")).upper(),
                    "action": action,
                    "status": "SKIPPED_SWITCH_NOT_AUTHORIZED",
                    "executed": False,
                    "is_trade": False,
                    "execution_reason": reason,
                    "switch_reason": _s(decision.get("switch_reason")),
                    "decision_switch_authorized": False,
                    "hard_rule_override": hard_override,
                    "ev_margin_actual": decision.get("ev_margin_actual"),
                    "ev_margin_required": decision.get("ev_margin_required"),
                    "previous_action": decision.get("previous_action"),
                    "mode": MODE,
                    "broker_executed": False,
                    "live_money": False,
                }
                orders.append(order)
                append_jsonl(ORDERS_JSONL, order)
                continue
            reexecuted += 1
            accepted_switch += 1
        order = execute_decision(
            decision,
            portfolio,
            accounting=accounting,
            all_decisions=decisions,
            execution_reason=reason,
        )
        order["execution_reason"] = reason
        orders.append(order)
        append_jsonl(ORDERS_JSONL, order)
        if order.get("is_trade"):
            trade = {**order, "record_type": "paper_trade", "shares": order.get("fill_shares")}
            append_jsonl(TRADES_JSONL, trade)
            trades_written += 1
        action_counts[action] = action_counts.get(action, 0) + 1
        processed.add(decision_id)
        last_orders[decision_id] = order

    after_snapshot = _portfolio_snapshot(portfolio)
    trades_file_lines = _count_jsonl_lines(TRADES_JSONL)
    validation = validate_execution_run(
        orders,
        trades_written=trades_written,
        trades_file_lines=trades_file_lines,
        portfolio=portfolio,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    file_errors = validate_trades_file(TRADES_JSONL)
    if file_errors:
        validation["errors"].extend(file_errors)
        validation["ok"] = False

    portfolio["processed_decision_ids"] = sorted(processed)
    portfolio["last_execution_at"] = _now()
    portfolio["broker_executed"] = False
    portfolio["live_money"] = False
    save_json(PORTFOLIO_JSON, portfolio)

    prev_attr = load_json(ATTRIBUTION_JSON)
    attribution = build_rule_attribution(orders, prev_attr)
    save_json(ATTRIBUTION_JSON, attribution)

    stats = {
        "orders_created": validation["orders_created"],
        "orders_executed": validation["orders_executed"],
        "orders_skipped": validation["orders_skipped"],
        "trades_written": validation["trades_written"],
        "trades_file_lines": validation["trades_file_lines"],
        "positions_before": validation["positions_before"],
        "positions_after": validation["positions_after"],
        "cash_before": validation["cash_before"],
        "cash_after": validation["cash_after"],
        "realized_pnl": validation["realized_pnl"],
        "unrealized_pnl": validation["unrealized_pnl"],
        "total_pnl": validation["total_pnl"],
        "total_value": validation["total_value"],
        "reconciliation_status": (validation.get("reconciliation") or {}).get("status"),
        "legacy_trades_removed": removed_legacy_trades,
        "reexecuted_on_action_change": reexecuted,
        "skipped_same_action": skipped_same_action,
        "skipped_switch_not_authorized": skipped_switch,
        "accepted_action_switches": accepted_switch,
    }

    payload = {
        "ok": validation["ok"],
        "generated_at": _now(),
        "decisions_consumed": len(decisions),
        "stats": stats,
        "validation": validation,
        "action_counts": action_counts,
        "portfolio": portfolio,
        "attribution_rules": len(attribution.get("rules") or {}),
    }
    if write_report_flag:
        write_report(payload)
    return payload


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


def _fetch_ticker_price(ticker: str) -> tuple[float | None, str, str]:
    try:
        from core.market_data_layer import get_market_price

        result = get_market_price(ticker, purpose="risk")
        if result.price is not None and result.price > 0:
            return result.price, result.source or "yfinance", result.status
    except Exception:
        pass
    return None, "UNAVAILABLE", "STALE"


def _outcome_label(actual: float, expected: float, verdict: str | None) -> str:
    if verdict in {"NEEDS_MORE_DATA"}:
        return "needs_more_data"
    if actual > 0 or (expected > 0 and actual >= expected * 0.5):
        return "success"
    if actual < 0 or (expected > 0 and actual < 0):
        return "failure"
    return "needs_more_data"


def _order_counts_for_attribution(order: dict[str, Any]) -> bool:
    explicit = order.get("executed")
    if explicit is False:
        return False
    if explicit is True:
        return True
    status = _s(order.get("status")).upper()
    if status in {"SKIPPED_NO_POSITION", "SKIPPED_NO_CASH"}:
        return False
    if status in {"EXECUTED", "NO_CHANGE"}:
        return True
    action = _s(order.get("action")).upper()
    before = order.get("before_position") or {}
    after = order.get("after_position") or {}
    if action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"} and _f(before.get("shares")) <= 0:
        return False
    if action == "BUY_PAPER" and _f(after.get("shares")) <= _f(before.get("shares")):
        return False
    return bool(_s(order.get("decision_id")))


def _actual_pnl_for_order(order: dict[str, Any], portfolio: dict[str, Any]) -> float:
    ticker = _s(order.get("ticker")).upper()
    pos = (portfolio.get("positions") or {}).get(ticker) or {}
    if _f(pos.get("shares")) > 0:
        return _f(pos.get("pnl"))
    simulated = _f(order.get("realized_pnl")) or _f(order.get("simulated_pnl_impact"))
    if simulated != 0:
        return simulated
    before = order.get("before_position") or {}
    after = order.get("after_position") or {}
    price = _f(order.get("price")) or _f(before.get("current_price"))
    sold = _f(before.get("shares")) - _f(after.get("shares"))
    if sold > 0 and price > 0:
        avg = _f(before.get("avg_price"))
        if avg > 0:
            return round((price - avg) * sold, 4)
    return simulated


def refresh_rule_attribution_from_actual(
    portfolio: dict[str, Any],
    *,
    orders: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del previous  # rebuild from actual outcomes; do not incrementally merge v1 rows
    orders = orders if orders is not None else load_jsonl(ORDERS_JSONL)
    validation = validation if validation is not None else load_json(VALIDATION_JSON)
    val_by = {
        _s(r.get("decision_id")): r
        for r in (validation or {}).get("results") or []
        if r.get("decision_id")
    }
    by_decision: dict[str, dict[str, Any]] = {}
    for order in orders:
        did = _s(order.get("decision_id"))
        if did:
            by_decision[did] = order

    rules: dict[str, dict[str, Any]] = {}
    processed = 0
    for order in by_decision.values():
        if not _order_counts_for_attribution(order):
            continue
        processed += 1
        did = _s(order.get("decision_id"))
        ticker = _s(order.get("ticker")).upper()
        action = _s(order.get("action"))
        val = val_by.get(did) or {}
        verdict = _s(val.get("verdict"))
        expected = _f(order.get("expected_profit_delta"))
        pos = (portfolio.get("positions") or {}).get(ticker) or {}
        actual = _actual_pnl_for_order(order, portfolio)
        drawdown = _f(pos.get("drawdown_pct"))
        outcome = _outcome_label(actual, expected, verdict)
        positive = outcome == "success"
        influence = INFLUENCE_DELTA_CAP if positive else -INFLUENCE_DELTA_CAP
        if outcome == "needs_more_data":
            influence = 0.0

        for rule_id in order.get("rule_sources") or []:
            entry = rules.setdefault(
                rule_id,
                {
                    "rule_id": rule_id,
                    "total_decisions": 0,
                    "executions": 0,
                    "wins": 0,
                    "losses": 0,
                    "positive_outcomes": 0,
                    "negative_outcomes": 0,
                    "avg_actual_pnl": 0.0,
                    "avg_drawdown": 0.0,
                    "win_rate": 0.0,
                    "net_pnl_impact": 0.0,
                    "weight_delta": 0.0,
                    "recommended_influence_delta": 0.0,
                    "confidence_impact": 0.0,
                    "last_action": None,
                    "last_ticker": None,
                    "last_outcome": None,
                    "last_updated": None,
                    "associated_action": None,
                },
            )
            n = int(_f(entry.get("total_decisions"))) + 1
            entry["total_decisions"] = n
            entry["executions"] = n
            entry["avg_actual_pnl"] = round(
                (_f(entry.get("avg_actual_pnl")) * (n - 1) + actual) / n,
                4,
            )
            entry["avg_drawdown"] = round(
                (_f(entry.get("avg_drawdown")) * (n - 1) + drawdown) / n,
                4,
            )
            entry["net_pnl_impact"] = round(_f(entry.get("net_pnl_impact")) + actual, 4)
            if positive:
                entry["wins"] = int(_f(entry.get("wins")) + 1)
                entry["positive_outcomes"] = int(_f(entry.get("positive_outcomes")) + 1)
            elif outcome == "failure":
                entry["losses"] = int(_f(entry.get("losses")) + 1)
                entry["negative_outcomes"] = int(_f(entry.get("negative_outcomes")) + 1)
            wins = _f(entry.get("wins"))
            entry["win_rate"] = round(wins / n, 4) if n else 0.0
            entry["weight_delta"] = round(
                max(-0.2, min(0.2, _f(entry.get("weight_delta")) + influence)),
                4,
            )
            entry["recommended_influence_delta"] = round(
                max(-INFLUENCE_DELTA_CAP, min(INFLUENCE_DELTA_CAP, influence)),
                4,
            )
            entry["confidence_impact"] = round(entry["win_rate"] - 0.5, 4)
            entry["last_action"] = action
            entry["last_ticker"] = ticker
            entry["last_outcome"] = outcome
            entry["last_updated"] = _now()
            entry["associated_action"] = action

    return {
        "schema": "tae.rule_outcome_attribution.v2",
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
        "generated_at": _now(),
        "rules": rules,
        "orders_processed": processed,
        "source": "actual_mtm_outcomes",
    }


def run_paper_mark_to_market(*, write_report_flag: bool = True) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    portfolio = load_json(PORTFOLIO_JSON)
    if not portfolio:
        return {"ok": False, "error": f"missing {PORTFOLIO_JSON}"}

    peak_value = _f(portfolio.get("peak_value") or portfolio.get("starting_value") or portfolio.get("total_value"))
    position_rows: list[dict[str, Any]] = []
    stale_count = 0
    live_count = 0

    for ticker, pos in sorted((portfolio.get("positions") or {}).items()):
        price, source, status = _fetch_ticker_price(ticker)
        avg_price = _f(pos.get("avg_price"))
        if price is None or price <= 0:
            price = _f(pos.get("current_price"))
            if price <= 0 and avg_price > 0:
                price = avg_price
            source = "FALLBACK_STALE"
            status = "STALE"
            stale_count += 1
        else:
            live_count += 1

        shares = _f(pos.get("shares"))
        price_high = max(_f(pos.get("price_high")), price)
        pos["current_price"] = round(price, 6)
        pos["price_high"] = round(price_high, 6)
        pos["mark_source"] = source
        pos["mark_status"] = status
        if avg_price > 0:
            pos["unrealized_pct"] = round(((price - avg_price) / avg_price) * 100, 4)
            pos["run_up_pct"] = round(((price_high - avg_price) / avg_price) * 100, 4)
        else:
            pos["unrealized_pct"] = 0.0
            pos["run_up_pct"] = 0.0

        position_rows.append(
            {
                "ticker": ticker,
                "shares": shares,
                "avg_price": avg_price,
                "current_price": price,
                "current_value": round(shares * price, 4),
                "unrealized_pnl": round((price - avg_price) * shares, 4) if avg_price > 0 else 0.0,
                "unrealized_pct": pos["unrealized_pct"],
                "run_up_pct": pos["run_up_pct"],
                "mark_source": source,
                "mark_status": status,
            }
        )

    recalc_portfolio(portfolio)
    total_value = _f(portfolio.get("total_value"))
    reconciliation = validate_portfolio_reconciliation(portfolio)
    peak_value = max(peak_value, total_value)
    portfolio["peak_value"] = round(peak_value, 4)
    drawdown_pct = round(((peak_value - total_value) / peak_value) * 100, 4) if peak_value > 0 else 0.0
    portfolio["drawdown_pct"] = drawdown_pct
    open_value = _f(portfolio.get("open_positions_value"))
    portfolio["capital_efficiency"] = round(
        _f(portfolio.get("unrealized_pnl")) / open_value if open_value > 0 else 0.0,
        4,
    )
    portfolio["last_mark_to_market_at"] = _now()
    save_json(PORTFOLIO_JSON, portfolio)

    attribution = refresh_rule_attribution_from_actual(portfolio, orders=load_jsonl(ORDERS_JSONL))
    save_json(ATTRIBUTION_JSON, attribution)

    mtm_doc = {
        "schema": "tae.paper_mark_to_market.v1",
        "mode": MODE,
        "generated_at": _now(),
        "positions_marked": len(position_rows),
        "live_price_count": live_count,
        "stale_price_count": stale_count,
        "total_value": total_value,
        "cash": _f(portfolio.get("cash")),
        "realized_pnl": _f(portfolio.get("realized_pnl")),
        "unrealized_pnl": _f(portfolio.get("unrealized_pnl")),
        "total_pnl": _f(portfolio.get("total_pnl")),
        "drawdown_pct": drawdown_pct,
        "capital_efficiency": portfolio.get("capital_efficiency"),
        "reconciliation_status": reconciliation.get("status"),
        "positions": position_rows,
    }
    save_json(MTM_JSON, mtm_doc)

    if write_report_flag:
        lines = [
            "# TAE PAPER Mark-to-Market Report",
            "",
            f"**Generated:** {mtm_doc['generated_at']}",
            f"**Mode:** {MODE} — NO_BROKER",
            "",
            f"- Positions marked: **{len(position_rows)}**",
            f"- Live prices: **{live_count}**",
            f"- Stale/fallback prices: **{stale_count}**",
            f"- Total value: **${total_value:,.2f}**",
            f"- Cash: **${_f(portfolio.get('cash')):,.2f}**",
            f"- Open positions value: **${_f(portfolio.get('open_positions_value')):,.2f}**",
            "",
            "## PnL accounting",
            "",
            f"- Realized PnL: **${_f(portfolio.get('realized_pnl')):,.2f}**",
            f"- Unrealized PnL: **${_f(portfolio.get('unrealized_pnl')):,.2f}**",
            f"- Total PnL: **${_f(portfolio.get('total_pnl')):,.2f}**",
            f"- Drawdown: **{drawdown_pct}%**",
            f"- Capital efficiency: **{portfolio.get('capital_efficiency')}**",
            "",
            "## Reconciliation",
            "",
            f"- Status: **{reconciliation.get('status', 'UNKNOWN')}**",
            f"- Formula: `total_value = cash + open_positions_value`",
            f"- Formula: `total_pnl = realized_pnl + unrealized_pnl`",
        ]
        for check in reconciliation.get("checks") or []:
            mark = "PASS" if check.get("ok") else "FAIL"
            lines.append(
                f"- {check.get('name')}: **{mark}** expected={check.get('expected')} actual={check.get('actual')}"
            )
        lines.extend(
            [
                "",
                "## Positions",
                "",
                "| ticker | price | source | unrealized | run-up |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in position_rows[:30]:
            lines.append(
                f"| {row['ticker']} | {row['current_price']} | {row['mark_source']} | "
                f"${row['unrealized_pnl']:,.2f} | {row['run_up_pct']}% |"
            )
        MTM_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "ok": reconciliation.get("ok", True),
        "mtm": mtm_doc,
        "portfolio": portfolio,
        "attribution_rules": len(attribution.get("rules") or {}),
        "stale_price_count": stale_count,
        "live_price_count": live_count,
        "reconciliation": reconciliation,
    }


def compare_canonical_vs_paper(*, write_report_flag: bool = True) -> dict[str, Any]:
    accounting = load_json(ACCOUNTING_JSON) or {}
    paper = load_json(PORTFOLIO_JSON) or {}
    mtm = load_json(MTM_JSON) or {}

    canonical_value = _f(accounting.get("account_value_corrected") or accounting.get("total_account_value"))
    canonical_cash = _f(accounting.get("cash_available"))
    canonical_positions = accounting.get("open_positions_count") or len(accounting.get("open_positions") or [])
    canonical_realized = _f(accounting.get("realized_pnl"))
    canonical_unrealized = _f(accounting.get("unrealized_pnl"))
    canonical_total_pnl = _f(accounting.get("total_pnl")) or canonical_realized + canonical_unrealized

    paper_value = _f(paper.get("total_value"))
    paper_cash = _f(paper.get("cash"))
    paper_positions = len(paper.get("positions") or {})
    paper_realized = _f(paper.get("realized_pnl"))
    paper_unrealized = _f(paper.get("unrealized_pnl"))
    paper_total_pnl = paper_realized + paper_unrealized
    reconciliation = validate_portfolio_reconciliation(paper)

    delta_value = round(paper_value - canonical_value, 4)
    delta_cash = round(paper_cash - canonical_cash, 4)
    delta_positions = paper_positions - int(canonical_positions)
    delta_pnl = round(paper_total_pnl - canonical_total_pnl, 4)
    delta_realized = round(paper_realized - canonical_realized, 4)
    delta_unrealized = round(paper_unrealized - canonical_unrealized, 4)

    explanation = (
        f"PAPER portfolio diverges by ${delta_value:,.2f} total value "
        f"({delta_positions:+d} positions, ${delta_cash:,.2f} cash delta, "
        f"${delta_realized:,.2f} realized delta, ${delta_unrealized:,.2f} unrealized delta) "
        f"after isolated PAPER execution and mark-to-market."
    )

    payload = {
        "schema": "tae.canonical_vs_paper.v1",
        "mode": MODE,
        "generated_at": _now(),
        "canonical": {
            "total_value": canonical_value,
            "cash": canonical_cash,
            "open_positions": canonical_positions,
            "realized_pnl": canonical_realized,
            "unrealized_pnl": canonical_unrealized,
            "total_pnl": canonical_total_pnl,
        },
        "paper": {
            "total_value": paper_value,
            "cash": paper_cash,
            "open_positions": paper_positions,
            "realized_pnl": paper_realized,
            "unrealized_pnl": paper_unrealized,
            "total_pnl": paper_total_pnl,
            "drawdown_pct": paper.get("drawdown_pct"),
            "mark_to_market_stale_count": mtm.get("stale_price_count"),
            "reconciliation_status": reconciliation.get("status"),
        },
        "delta": {
            "total_value": delta_value,
            "cash": delta_cash,
            "open_positions": delta_positions,
            "total_pnl": delta_pnl,
            "realized_pnl": delta_realized,
            "unrealized_pnl": delta_unrealized,
        },
        "reconciliation": reconciliation,
        "explanation": explanation,
    }

    if write_report_flag:
        lines = [
            "# TAE Canonical vs PAPER Portfolio Report",
            "",
            f"**Generated:** {payload['generated_at']}",
            f"**Mode:** {MODE} — READ_ONLY comparison",
            "",
            "| metric | canonical | PAPER | delta |",
            "| --- | --- | --- | --- |",
            f"| total value | ${canonical_value:,.2f} | ${paper_value:,.2f} | ${delta_value:,.2f} |",
            f"| cash | ${canonical_cash:,.2f} | ${paper_cash:,.2f} | ${delta_cash:,.2f} |",
            f"| open positions | {canonical_positions} | {paper_positions} | {delta_positions:+d} |",
            f"| realized PnL | ${canonical_realized:,.2f} | ${paper_realized:,.2f} | ${delta_realized:,.2f} |",
            f"| unrealized PnL | ${canonical_unrealized:,.2f} | ${paper_unrealized:,.2f} | ${delta_unrealized:,.2f} |",
            f"| total PnL | ${canonical_total_pnl:,.2f} | ${paper_total_pnl:,.2f} | ${delta_pnl:,.2f} |",
            "",
            "## PAPER reconciliation",
            "",
            f"- Status: **{reconciliation.get('status', 'UNKNOWN')}**",
        ]
        for check in reconciliation.get("checks") or []:
            mark = "PASS" if check.get("ok") else "FAIL"
            lines.append(
                f"- {check.get('name')}: **{mark}** expected={check.get('expected')} actual={check.get('actual')}"
            )
        lines.extend(["", f"**Explanation:** {explanation}"])
        CANONICAL_VS_PAPER_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"ok": reconciliation.get("ok", True), **payload}


def run_rule_outcome_attribution(*, write_report_flag: bool = False) -> dict[str, Any]:
    portfolio = load_json(PORTFOLIO_JSON)
    if not portfolio:
        return {"ok": False, "error": f"missing {PORTFOLIO_JSON}"}
    attribution = refresh_rule_attribution_from_actual(portfolio, orders=load_jsonl(ORDERS_JSONL))
    save_json(ATTRIBUTION_JSON, attribution)
    strengthened = [
        rid for rid, row in (attribution.get("rules") or {}).items()
        if _f(row.get("recommended_influence_delta")) > 0
    ]
    weakened = [
        rid for rid, row in (attribution.get("rules") or {}).items()
        if _f(row.get("recommended_influence_delta")) < 0
    ]
    return {
        "ok": True,
        "rules": len(attribution.get("rules") or {}),
        "strengthened": strengthened[:5],
        "weakened": weakened[:5],
        "attribution": attribution,
    }


def main() -> int:
    print("===== TAE PAPER EXECUTION =====")
    print(f"Mode: {MODE} | NO_BROKER | NO_LIVE_EXECUTION | isolated portfolio")
    result = run_paper_execution()
    if not result.get("ok"):
        err = result.get("error") or "; ".join((result.get("validation") or {}).get("errors") or ["validation failed"])
        print(f"ERROR: {err}", file=__import__("sys").stderr)
        return 1
    stats = result.get("stats") or {}
    print(f"Orders created: {stats.get('orders_created', 0)}")
    print(f"Orders executed: {stats.get('orders_executed', 0)}")
    print(f"Orders skipped: {stats.get('orders_skipped', 0)}")
    print(f"Trades written: {stats.get('trades_written', 0)}")
    print(f"Portfolio value: ${ _f((result.get('portfolio') or {}).get('total_value')):,.2f}")
    print(f"Rule attribution rules: {result.get('attribution_rules')}")
    print(f"Wrote: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
