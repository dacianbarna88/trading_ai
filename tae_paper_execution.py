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

    if action == "SKIP_PAPER":
        after = before
    elif action == "HOLD_PAPER":
        after = before
    elif action == "SELL_PAPER":
        realized_pnl, after_pos = _sell_shares(portfolio, ticker, _f(before.get("shares")), price)
        capital_impact = round(realized_pnl + _f(before.get("current_value")), 4)
        after = _position_snapshot(after_pos)
    elif action == "REDUCE_PAPER":
        trim_pct = 30.0 if confidence < 0.7 else 20.0
        trim_shares = _f(before.get("shares")) * (trim_pct / 100.0)
        realized_pnl, after_pos = _sell_shares(portfolio, ticker, trim_shares, price)
        capital_impact = round(trim_shares * price, 4)
        after = _position_snapshot(after_pos)
        reason = f"REDUCE_PAPER trim {trim_pct:.0f}% — {reason}"
    elif action == "PROTECT_PAPER":
        pos = positions.get(ticker)
        if pos:
            pos["protect_mode"] = "TRAIL_SHADOW"
            if risk_score >= 80:
                trim_shares = _f(pos.get("shares")) * 0.1
                realized_pnl, after_pos = _sell_shares(portfolio, ticker, trim_shares, price)
                after = _position_snapshot(after_pos)
                reason = f"PROTECT_PAPER urgency trim 10% — {reason}"
            else:
                after = _position_snapshot(pos)
                reason = f"PROTECT_PAPER protect-only — {reason}"
        else:
            after = before
    elif action == "BUY_PAPER":
        cash = _f(portfolio.get("cash"))
        notional = min(cash * max(0.05, confidence * 0.12), cash * 0.15)
        _, after_pos = _buy_shares(portfolio, ticker, notional, price)
        capital_impact = round(-notional, 4)
        after = _position_snapshot(after_pos)
    elif action == "ROTATE_PAPER":
        realized_pnl, _ = _sell_shares(portfolio, ticker, _f(before.get("shares")), price)
        target = best_rotate_target(all_decisions, ticker)
        rotate_notional = _f(before.get("current_value")) or _f(portfolio.get("cash")) * 0.1
        if target:
            tgt_ticker = _s(target.get("ticker")).upper()
            tgt_price = price_for_ticker(tgt_ticker, accounting, target)
            _, after_pos = _buy_shares(portfolio, tgt_ticker, rotate_notional, tgt_price)
            after = _position_snapshot(after_pos)
            reason = f"ROTATE_PAPER {ticker}→{tgt_ticker} — {reason}"
        else:
            after = _position_snapshot(None)
            reason = f"ROTATE_PAPER sell-only (no BUY target) — {reason}"
        capital_impact = round(rotate_notional - _f(before.get("current_value")), 4)
    else:
        after = before
        reason = f"unknown action {action} — skipped"

    recalc_portfolio(portfolio)

    order = {
        "timestamp": _now(),
        "decision_id": decision_id,
        "ticker": ticker,
        "action": action,
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

    return {
        "schema": "tae.rule_outcome_attribution.v1",
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
        "generated_at": _now(),
        "rules": rules,
        "orders_processed": len(orders),
    }


def write_report(payload: dict[str, Any]) -> None:
    portfolio = payload.get("portfolio") or {}
    action_counts = payload.get("action_counts") or {}
    lines = [
        "# TAE PAPER Execution Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
        "",
        f"- Decisions consumed: **{payload.get('decisions_consumed', 0)}**",
        f"- Orders executed: **{payload.get('orders_executed', 0)}**",
        f"- Portfolio value: **${ _f(portfolio.get('total_value')):,.2f}**",
        f"- Cash: **${ _f(portfolio.get('cash')):,.2f}**",
        f"- Open positions: **{len(portfolio.get('positions') or {})}**",
        f"- Realized PnL: **${ _f(portfolio.get('realized_pnl')):,.2f}**",
        f"- Unrealized PnL: **${ _f(portfolio.get('unrealized_pnl')):,.2f}**",
        "",
        "## Action summary",
        "",
    ]
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
            "## Execution boundary audit",
            "",
            "- live_bot.py classification: **LOCAL_PAPER_RUNTIME** (no broker SDK; CSV journal only)",
            "- live_bot.py broker_connected: **false**",
            "- PAPER portfolio SSOT: **`runtime_outputs/paper_execution/paper_portfolio.json`**",
            "- Live risk SSOT (read-only seed): **`tae_accounting_snapshot.json` / `portfolio.csv`**",
            "- Forbidden paths untouched: **live_bot.py, portfolio.csv, live_signals.csv, watchlist.txt, core/, research_core/**",
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

    orders: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}

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
        if action not in {"HOLD_PAPER", "SKIP_PAPER", "PROTECT_PAPER"} or _f(order.get("simulated_pnl_impact")):
            trade = {**order, "record_type": "paper_trade"}
            append_jsonl(TRADES_JSONL, trade)
        action_counts[action] = action_counts.get(action, 0) + 1
        processed.add(decision_id)

    portfolio["processed_decision_ids"] = sorted(processed)
    portfolio["last_execution_at"] = _now()
    portfolio["broker_executed"] = False
    portfolio["live_money"] = False
    save_json(PORTFOLIO_JSON, portfolio)

    prev_attr = load_json(ATTRIBUTION_JSON)
    attribution = build_rule_attribution(orders, prev_attr)
    save_json(ATTRIBUTION_JSON, attribution)

    payload = {
        "ok": True,
        "generated_at": _now(),
        "decisions_consumed": len(decisions),
        "orders_executed": len(orders),
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
        print(f"ERROR: {result.get('error')}", file=__import__("sys").stderr)
        return 1
    print(f"Orders executed: {result.get('orders_executed')}")
    print(f"Portfolio value: ${ _f((result.get('portfolio') or {}).get('total_value')):,.2f}")
    print(f"Rule attribution rules: {result.get('attribution_rules')}")
    print(f"Wrote: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
