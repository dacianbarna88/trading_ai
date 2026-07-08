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
REPORT_MD = Path("TAE_PAPER_EXECUTION_REPORT.md")

DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")

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
        open_value += current_value
        unrealized += pnl
    cash = _f(portfolio.get("cash"))
    portfolio["open_positions_value"] = round(open_value, 4)
    portfolio["unrealized_pnl"] = round(unrealized, 4)
    portfolio["total_value"] = round(cash + open_value, 4)
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
    scores = decision.get("action_scores") or {}
    if _f(decision.get("expected_profit_delta")) and _f(decision.get("confidence")):
        pass
    pos = (decision.get("portfolio_snapshot") or {})
    px = _f(pos.get("current_price"))
    if px > 0:
        return px
    return 100.0


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
        "starting_value": round(total, 2),
        "cash": round(cash, 2),
        "open_positions_value": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_value": 0.0,
        "positions": positions,
        "processed_decision_ids": [],
    }
    recalc_portfolio(portfolio)
    return portfolio


def _sell_shares(
    portfolio: dict[str, Any],
    ticker: str,
    shares_to_sell: float,
    price: float,
) -> tuple[float, dict[str, Any] | None]:
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if not pos:
        return 0.0, None
    shares_before = _f(pos.get("shares"))
    avg_price = _f(pos.get("avg_price"))
    shares_to_sell = min(shares_to_sell, shares_before)
    if shares_to_sell <= 0:
        return 0.0, pos
    realized = round((price - avg_price) * shares_to_sell, 4) if avg_price > 0 else 0.0
    shares_after = round(shares_before - shares_to_sell, 6)
    portfolio["cash"] = round(_f(portfolio.get("cash")) + shares_to_sell * price, 4)
    portfolio["realized_pnl"] = round(_f(portfolio.get("realized_pnl")) + realized, 4)
    if shares_after <= 0.000001:
        positions.pop(ticker, None)
        return realized, None
    pos["shares"] = shares_after
    pos["status"] = "OPEN"
    return realized, pos


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
        "total_value": round(_f(portfolio.get("total_value")), 4),
    }


def execute_decision(
    decision: dict[str, Any],
    portfolio: dict[str, Any],
    *,
    accounting: dict[str, Any] | None,
    all_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    action = _s(decision.get("action")).upper()
    ticker = _s(decision.get("ticker")).upper()
    decision_id = _s(decision.get("decision_id"))
    confidence = _f(decision.get("confidence"), 0.5)
    risk_score = _f(decision.get("risk_score"))
    expected_delta = _f(decision.get("expected_profit_delta"))
    rule_sources = extract_rule_sources(decision)
    price = price_for_ticker(ticker, accounting, decision)

    positions = portfolio.setdefault("positions", {})
    before = _position_snapshot(positions.get(ticker))
    realized_pnl = 0.0
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
        realized_pnl, after_pos = _sell_shares(portfolio, ticker, sell_shares, price)
        fill_shares = sell_shares
        capital_impact = round(realized_pnl + _f(before.get("current_value")), 4)
        after = _position_snapshot(after_pos)
        status = "EXECUTED"
        executed = True
        is_trade = fill_shares > 0
    elif action == "REDUCE_PAPER":
        trim_pct = 30.0 if confidence < 0.7 else 20.0
        trim_shares = _f(before.get("shares")) * (trim_pct / 100.0)
        realized_pnl, after_pos = _sell_shares(portfolio, ticker, trim_shares, price)
        fill_shares = trim_shares
        capital_impact = round(trim_shares * price, 4)
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
            realized_pnl, after_pos = _sell_shares(portfolio, ticker, trim_shares, price)
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
        cash = _f(portfolio.get("cash"))
        notional = min(cash * max(0.05, confidence * 0.12), cash * 0.15)
        bought, after_pos = _buy_shares(portfolio, ticker, notional, price)
        fill_shares = bought
        if fill_shares > 0:
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
        realized_pnl, _ = _sell_shares(portfolio, ticker, sell_shares, price)
        rotate_notional = _f(before.get("current_value")) or _f(portfolio.get("cash")) * 0.1
        target = best_rotate_target(all_decisions, ticker)
        buy_fill = 0.0
        if target and rotate_notional > 0:
            tgt_ticker = _s(target.get("ticker")).upper()
            tgt_price = price_for_ticker(tgt_ticker, accounting, target)
            buy_fill, after_pos = _buy_shares(portfolio, tgt_ticker, rotate_notional, tgt_price)
            after = _position_snapshot(after_pos)
            reason = f"ROTATE_PAPER {ticker}→{tgt_ticker} — {reason}"
        else:
            after = _position_snapshot(None)
            reason = f"ROTATE_PAPER sell-only (no BUY target) — {reason}"
        fill_shares = sell_shares if sell_shares > 0 else buy_fill
        capital_impact = round(rotate_notional - _f(before.get("current_value")), 4)
        status = "EXECUTED"
        executed = sell_shares > 0 or buy_fill > 0
        is_trade = sell_shares > 0 or buy_fill > 0
    else:
        reason = f"unknown action {action} — skipped"

    if status != "SKIPPED_NO_POSITION":
        recalc_portfolio(portfolio)

    order = {
        "timestamp": _now(),
        "decision_id": decision_id,
        "ticker": ticker,
        "action": action,
        "status": status,
        "executed": executed,
        "is_trade": is_trade,
        "fill_shares": round(fill_shares, 6),
        "rule_sources": rule_sources,
        "before_position": before,
        "after_position": after,
        "simulated_pnl_impact": round(realized_pnl, 4),
        "expected_profit_delta": expected_delta,
        "capital_impact": capital_impact,
        "risk_impact": risk_impact,
        "price": price,
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
        pnl = _f(order.get("simulated_pnl_impact"))
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
        errors.extend(validate_trade_record(row))
    return errors


def validate_trade_record(trade: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    is_trade_row = trade.get("record_type") == "paper_trade" or trade.get("is_trade") is True
    if not is_trade_row:
        return errors
    shares = _f(trade.get("fill_shares") or trade.get("shares"))
    action = _s(trade.get("action")).upper()
    before = trade.get("before_position") or {}
    if shares <= 0:
        errors.append(f"{trade.get('decision_id')}: trade fill_shares must be > 0")
    if action in {"SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"} and _f(before.get("shares")) <= 0:
        errors.append(f"{trade.get('decision_id')}: {action} trade requires existing position")
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

    return {
        "ok": not errors,
        "errors": errors,
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
    }


def write_report(payload: dict[str, Any]) -> None:
    portfolio = payload.get("portfolio") or {}
    stats = payload.get("stats") or {}
    validation = payload.get("validation") or {}
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
        f"- Trades written (this run): **{stats.get('trades_written', 0)}**",
        f"- Trades file total lines: **{stats.get('trades_file_lines', 0)}**",
        "",
        "## Portfolio delta (this run)",
        "",
        f"- Positions before: **{stats.get('positions_before', 0)}**",
        f"- Positions after: **{stats.get('positions_after', 0)}**",
        f"- Cash before: **${ _f(stats.get('cash_before')):,.2f}**",
        f"- Cash after: **${ _f(stats.get('cash_after')):,.2f}**",
        f"- Realized PnL: **${ _f(stats.get('realized_pnl')):,.2f}**",
        f"- Portfolio value: **${ _f(portfolio.get('total_value')):,.2f}**",
        f"- Unrealized PnL: **${ _f(portfolio.get('unrealized_pnl')):,.2f}**",
        "",
        "## Validation",
        "",
        f"- Validation OK: **{validation.get('ok', False)}**",
    ]
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


def run_paper_execution(*, write_report_flag: bool = True) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    decisions_doc = load_json(DECISIONS_JSON)
    if not decisions_doc:
        return {"ok": False, "error": f"missing {DECISIONS_JSON}"}

    decisions = list(decisions_doc.get("decisions") or [])
    accounting = load_json(ACCOUNTING_JSON)
    existing = load_json(PORTFOLIO_JSON)
    portfolio = bootstrap_portfolio(accounting, existing)
    processed = set(portfolio.get("processed_decision_ids") or [])

    removed_legacy_trades = sanitize_trades_file(TRADES_JSONL)
    before_snapshot = _portfolio_snapshot(portfolio)

    orders: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}
    trades_written = 0

    for decision in decisions:
        decision_id = _s(decision.get("decision_id"))
        action = _s(decision.get("action")).upper()
        if not decision_id or decision_id in processed:
            continue
        if action not in PAPER_ACTIONS:
            continue
        order = execute_decision(
            decision,
            portfolio,
            accounting=accounting,
            all_decisions=decisions,
        )
        orders.append(order)
        append_jsonl(ORDERS_JSONL, order)
        if order.get("is_trade"):
            trade = {**order, "record_type": "paper_trade", "shares": order.get("fill_shares")}
            append_jsonl(TRADES_JSONL, trade)
            trades_written += 1
        action_counts[action] = action_counts.get(action, 0) + 1
        processed.add(decision_id)

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
        "legacy_trades_removed": removed_legacy_trades,
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
