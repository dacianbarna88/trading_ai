#!/usr/bin/env python3
"""
TAE Sprint X.10A-1 — Rolling Actionable Signal Audit

MODE: OBSERVABILITY ONLY | NO_EXECUTION | NO_BROKER | NO_PORTFOLIO_CHANGE
Does NOT modify live_bot.py, watchlist.txt, or execute trades.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import live_bot
from config import settings as config_settings
from markets.market_hours import (
    get_market_statuses,
    get_ticker_market,
    is_ticker_market_open,
)
from research_core.governance.live_advisory_runtime import (
    load_live_advisory,
    should_block_new_buy,
)

AUDIT_MODE = "OBSERVABILITY_ONLY"
NO_EXECUTION = True

ROOT = Path(".")
LIVE_SIGNALS_PATH = ROOT / config_settings.LIVE_SIGNALS_FILE
PORTFOLIO_PATH = ROOT / config_settings.PORTFOLIO_FILE
WATCHLIST_PATH = ROOT / config_settings.WATCHLIST_FILE
ADVISORY_PATH = ROOT / "tae_live_advisory.json"
SHADOW_EVENTS_PATH = ROOT / "tae_shadow_validation_events.csv"

OUTPUT_JSON = ROOT / "tae_actionable_signal_audit.json"
OUTPUT_MD = ROOT / "tae_actionable_signal_audit.md"
OUTPUT_CSV = ROOT / "tae_actionable_signal_audit.csv"

CLASSIFICATIONS = (
    "STRONG_BUY_ALREADY_HELD",
    "STRONG_BUY_ACTIONABLE_MARKET_OPEN",
    "STRONG_BUY_MARKET_CLOSED",
    "BLOCKED_BY_TAE",
    "BLOCKED_BY_CASH",
    "BLOCKED_BY_MAX_POSITIONS",
    "WAIT",
    "TAKE_PROFIT",
    "OTHER",
)


@dataclass
class SignalAuditRow:
    time: str
    ticker: str
    price: float | None
    score: float | None
    signal: str
    market: str
    market_open: bool
    in_watchlist: bool
    already_held: bool
    classification: str
    reason: str
    shadow_event_type: str | None = None
    shadow_block_reason: str | None = None
    shadow_timestamp: str | None = None


@dataclass
class AuditSummary:
    total_signals: int = 0
    strong_buy_total: int = 0
    strong_buy_already_held: int = 0
    strong_buy_actionable_new: int = 0
    strong_buy_market_open: int = 0
    strong_buy_market_closed: int = 0
    blocked_by_tae: int = 0
    blocked_by_cash: int = 0
    blocked_by_max_positions: int = 0
    actionable_by_market: int = 0
    wait_count: int = 0
    take_profit_count: int = 0
    other_count: int = 0
    already_held_tickers: list[str] = field(default_factory=list)
    actionable_tickers: list[str] = field(default_factory=list)
    market_closed_tickers: list[str] = field(default_factory=list)
    blocked_tae_tickers: list[str] = field(default_factory=list)
    blocked_cash_tickers: list[str] = field(default_factory=list)
    blocked_max_positions_tickers: list[str] = field(default_factory=list)
    recommendation: str = ""
    verdict: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_advisory_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_watchlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tickers: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        ticker = line.strip().upper()
        if ticker and not ticker.startswith("#"):
            tickers.add(ticker)
    return tickers


def _load_shadow_latest_by_ticker(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    latest: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ticker = str(row.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            ts = str(row.get("timestamp", ""))
            prev = latest.get(ticker)
            if prev is None or ts >= prev.get("timestamp", ""):
                latest[ticker] = {
                    "timestamp": ts,
                    "event_type": str(row.get("event_type", "")),
                    "block_reason": str(row.get("block_reason", "") or ""),
                }
    return latest


def _normalize_signal(value: Any) -> str:
    return str(value or "").strip().upper()


def _eligible_strong_buy_mask(
    signals_df: pd.DataFrame,
    open_tickers: set[str],
    market_regime: str,
) -> pd.Series:
    scores = pd.to_numeric(signals_df["Score"], errors="coerce")
    return (
        (signals_df["Signal"].astype(str).str.upper() == "STRONG BUY")
        & (scores >= live_bot.MIN_SCORE_TO_BUY)
        & (~signals_df["Ticker"].astype(str).str.upper().isin(open_tickers))
        & (market_regime != "BEAR")
    )


def _resolve_market_regime() -> str:
    try:
        return str(live_bot.get_market_regime())
    except Exception:
        return "UNKNOWN"


def classify_signals(
    signals_df: pd.DataFrame,
    open_positions: dict[str, Any],
    watchlist: set[str],
    block_new_buy: bool,
    tae_block_reason: str,
    market_regime: str,
    trade_size: float,
    cash_available: float,
    shadow_by_ticker: dict[str, dict[str, str]],
) -> list[SignalAuditRow]:
    open_tickers = {str(k).upper() for k in open_positions.keys()}
    open_count = len(open_positions)
    slots_available = max(live_bot.MAX_POSITIONS - open_count, 0)
    eligible_mask = _eligible_strong_buy_mask(signals_df, open_tickers, market_regime)
    eligible_open_market = []
    for _, row in signals_df[eligible_mask].iterrows():
        ticker = str(row["Ticker"]).upper()
        if is_ticker_market_open(ticker) or live_bot.ALLOW_BUY_WHEN_MARKET_CLOSED:
            eligible_open_market.append(ticker)

    cash_blocked_globally = (
        trade_size <= 0 or trade_size < live_bot.MIN_TRADE_USD or cash_available < live_bot.MIN_TRADE_USD
    )
    max_positions_reached = open_count >= live_bot.MAX_POSITIONS

    rows: list[SignalAuditRow] = []

    for _, row in signals_df.iterrows():
        ticker = str(row["Ticker"]).upper()
        signal = _normalize_signal(row.get("Signal"))
        score = pd.to_numeric(row.get("Score"), errors="coerce")
        price = pd.to_numeric(row.get("Price"), errors="coerce")
        signal_time = str(row.get("Time", ""))
        market = get_ticker_market(ticker)
        market_open = is_ticker_market_open(ticker)
        already_held = ticker in open_tickers
        shadow = shadow_by_ticker.get(ticker, {})

        classification = "OTHER"
        reason = ""

        if signal == "WAIT":
            classification = "WAIT"
            reason = "Signal is WAIT — no BUY intent"
        elif signal == "TAKE PROFIT":
            classification = "TAKE_PROFIT"
            reason = "Signal is TAKE PROFIT — exit review, not a new BUY"
        elif signal == "STRONG BUY":
            if pd.isna(score) or float(score) < live_bot.MIN_SCORE_TO_BUY:
                classification = "OTHER"
                reason = f"STRONG BUY score {score} below MIN_SCORE_TO_BUY ({live_bot.MIN_SCORE_TO_BUY})"
            elif already_held:
                classification = "STRONG_BUY_ALREADY_HELD"
                reason = "Ticker already in open portfolio positions"
            elif not market_open and not live_bot.ALLOW_BUY_WHEN_MARKET_CLOSED:
                classification = "STRONG_BUY_MARKET_CLOSED"
                reason = f"{market} market session closed for {ticker}"
            elif market_regime != "BULL":
                classification = "OTHER"
                reason = f"Market regime {market_regime} — live_bot requires BULL for new BUY"
            elif block_new_buy:
                classification = "BLOCKED_BY_TAE"
                reason = tae_block_reason or "TAE block_new_buy=True"
            elif max_positions_reached:
                classification = "BLOCKED_BY_MAX_POSITIONS"
                reason = (
                    f"Open positions {open_count} >= MAX_POSITIONS ({live_bot.MAX_POSITIONS})"
                )
            elif cash_blocked_globally:
                classification = "BLOCKED_BY_CASH"
                reason = (
                    f"Insufficient cash for MIN_TRADE_USD ${live_bot.MIN_TRADE_USD:.2f} "
                    f"(cash=${cash_available:.2f}, trade_size=${trade_size:.2f})"
                )
            elif ticker in eligible_open_market:
                classification = "STRONG_BUY_ACTIONABLE_MARKET_OPEN"
                reason = (
                    f"New STRONG BUY, {market} open, TAE clear, "
                    f"{slots_available} slot(s), est trade ${trade_size:.2f}"
                )
            else:
                classification = "OTHER"
                reason = "STRONG BUY did not pass actionable gate checks"
        else:
            classification = "OTHER"
            reason = f"Unhandled signal type: {signal or 'EMPTY'}"

        rows.append(
            SignalAuditRow(
                time=signal_time,
                ticker=ticker,
                price=float(price) if pd.notna(price) else None,
                score=float(score) if pd.notna(score) else None,
                signal=signal,
                market=market,
                market_open=market_open,
                in_watchlist=ticker in watchlist,
                already_held=already_held,
                classification=classification,
                reason=reason,
                shadow_event_type=shadow.get("event_type") or None,
                shadow_block_reason=shadow.get("block_reason") or None,
                shadow_timestamp=shadow.get("timestamp") or None,
            )
        )

    return rows


def build_summary(rows: list[SignalAuditRow]) -> AuditSummary:
    summary = AuditSummary(total_signals=len(rows))

    strong_buy_rows = [r for r in rows if r.signal == "STRONG BUY"]
    summary.strong_buy_total = len(strong_buy_rows)

    for row in rows:
        if row.classification == "STRONG_BUY_ALREADY_HELD":
            summary.strong_buy_already_held += 1
            if row.ticker not in summary.already_held_tickers:
                summary.already_held_tickers.append(row.ticker)
        elif row.classification == "STRONG_BUY_ACTIONABLE_MARKET_OPEN":
            summary.strong_buy_actionable_new += 1
            summary.strong_buy_market_open += 1
            summary.actionable_by_market += 1
            if row.ticker not in summary.actionable_tickers:
                summary.actionable_tickers.append(row.ticker)
        elif row.classification == "STRONG_BUY_MARKET_CLOSED":
            summary.strong_buy_market_closed += 1
            if row.ticker not in summary.market_closed_tickers:
                summary.market_closed_tickers.append(row.ticker)
        elif row.classification == "BLOCKED_BY_TAE":
            summary.blocked_by_tae += 1
            if row.ticker not in summary.blocked_tae_tickers:
                summary.blocked_tae_tickers.append(row.ticker)
        elif row.classification == "BLOCKED_BY_CASH":
            summary.blocked_by_cash += 1
            if row.ticker not in summary.blocked_cash_tickers:
                summary.blocked_cash_tickers.append(row.ticker)
        elif row.classification == "BLOCKED_BY_MAX_POSITIONS":
            summary.blocked_by_max_positions += 1
            if row.ticker not in summary.blocked_max_positions_tickers:
                summary.blocked_max_positions_tickers.append(row.ticker)
        elif row.classification == "WAIT":
            summary.wait_count += 1
        elif row.classification == "TAKE_PROFIT":
            summary.take_profit_count += 1
        elif row.classification == "OTHER":
            summary.other_count += 1

    if summary.strong_buy_actionable_new > 0:
        summary.verdict = "ACTIONABLE_STRONG_BUY_PRESENT"
        names = ", ".join(summary.actionable_tickers)
        summary.recommendation = (
            f"{summary.strong_buy_actionable_new} new STRONG BUY candidate(s) are actionable now "
            f"({names}). Monitor live_bot cycle — no manual intervention required."
        )
    elif summary.strong_buy_market_closed > 0 and summary.blocked_by_tae == 0:
        names = ", ".join(summary.market_closed_tickers)
        summary.verdict = "STRONG_BUY_WAITING_SESSION"
        summary.recommendation = (
            f"STRONG BUY signal(s) blocked by market session ({names}). "
            "Re-run audit after the relevant exchange opens."
        )
    elif summary.blocked_by_tae > 0:
        summary.verdict = "TAE_BLOCKING_NEW_BUY"
        summary.recommendation = (
            "TAE RISK_ADVISORY is blocking new BUY orders. Resolve advisory blockers before expecting auto-BUY."
        )
    elif summary.blocked_by_max_positions > 0:
        summary.verdict = "MAX_POSITIONS_REACHED"
        summary.recommendation = (
            f"Portfolio at MAX_POSITIONS ({live_bot.MAX_POSITIONS}). "
            "Close or trim positions before new STRONG BUY entries."
        )
    elif summary.blocked_by_cash > 0:
        summary.verdict = "INSUFFICIENT_CASH"
        summary.recommendation = "Cash below trade minimum — deposit or free capital before new BUY."
    elif summary.strong_buy_already_held > 0 and summary.strong_buy_actionable_new == 0:
        summary.verdict = "HELD_ONLY"
        summary.recommendation = (
            "STRONG BUY signals exist only for tickers already held — no new entry candidates."
        )
    else:
        summary.verdict = "NO_ACTIONABLE_STRONG_BUY"
        summary.recommendation = "No eligible STRONG BUY new-entry candidates at audit time."

    return summary


def _runtime_context(
    portfolio: pd.DataFrame,
    advisory_payload: dict[str, Any],
    block_new_buy: bool,
    tae_block_reason: str,
    market_regime: str,
    trade_size: float,
    cash_available: float,
) -> dict[str, Any]:
    runtime = advisory_payload.get("runtime_snapshot") or {}
    return {
        "audit_mode": AUDIT_MODE,
        "no_execution": NO_EXECUTION,
        "generated_at": _utc_now_iso(),
        "live_bot_constants": {
            "MIN_SCORE_TO_BUY": live_bot.MIN_SCORE_TO_BUY,
            "MAX_POSITIONS": live_bot.MAX_POSITIONS,
            "MIN_TRADE_USD": live_bot.MIN_TRADE_USD,
            "MAX_TRADE_USD": live_bot.MAX_TRADE_USD,
            "STARTING_CAPITAL": live_bot.STARTING_CAPITAL,
            "ALLOW_BUY_WHEN_MARKET_CLOSED": live_bot.ALLOW_BUY_WHEN_MARKET_CLOSED,
            "MARKET_REGIME_FILTER": live_bot.MARKET_REGIME_FILTER,
        },
        "config_settings_note": {
            "STARTING_CAPITAL": config_settings.STARTING_CAPITAL,
            "MIN_SCORE_TO_BUY": config_settings.MIN_SCORE_TO_BUY,
            "MIN_CASH_RESERVE": getattr(config_settings, "MIN_CASH_RESERVE", None),
            "canonical_runtime_source": "live_bot.py",
        },
        "inputs": {
            "live_signals": str(LIVE_SIGNALS_PATH),
            "portfolio": str(PORTFOLIO_PATH),
            "watchlist": str(WATCHLIST_PATH),
            "advisory": str(ADVISORY_PATH),
            "shadow_events": str(SHADOW_EVENTS_PATH) if SHADOW_EVENTS_PATH.exists() else None,
        },
        "market_statuses": get_market_statuses(),
        "market_regime": market_regime,
        "open_positions_count": len(live_bot.get_open_positions(portfolio)),
        "cash_available_usd": round(cash_available, 2),
        "dynamic_trade_size_usd": round(trade_size, 2),
        "advisory_action": advisory_payload.get("action") or (advisory_payload.get("advisory") or {}).get("action"),
        "block_new_buy": block_new_buy,
        "tae_block_reason": tae_block_reason,
        "advisory_generated_at": advisory_payload.get("generated_at"),
        "runtime_snapshot": runtime,
        "watchlist_count": None,
    }


def render_markdown(
    rows: list[SignalAuditRow],
    summary: AuditSummary,
    context: dict[str, Any],
) -> str:
    lines = [
        "# TAE Actionable Signal Audit",
        "",
        f"**Mode:** {AUDIT_MODE} | **Generated:** {context['generated_at']}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| total_signals | {summary.total_signals} |",
        f"| strong_buy_total | {summary.strong_buy_total} |",
        f"| strong_buy_already_held | {summary.strong_buy_already_held} |",
        f"| strong_buy_actionable_new | {summary.strong_buy_actionable_new} |",
        f"| strong_buy_market_open | {summary.strong_buy_market_open} |",
        f"| strong_buy_market_closed | {summary.strong_buy_market_closed} |",
        f"| blocked_by_tae | {summary.blocked_by_tae} |",
        f"| blocked_by_cash | {summary.blocked_by_cash} |",
        f"| blocked_by_max_positions | {summary.blocked_by_max_positions} |",
        f"| actionable_by_market | {summary.actionable_by_market} |",
        f"| **Verdict** | **{summary.verdict}** |",
        "",
        f"**Recommendation:** {summary.recommendation}",
        "",
        "## Runtime",
        "",
        f"- Market regime: `{context['market_regime']}`",
        f"- Market statuses: `{context['market_statuses']}`",
        f"- Open positions: `{context['open_positions_count']}` / `{live_bot.MAX_POSITIONS}`",
        f"- Cash available: `${context['cash_available_usd']}`",
        f"- Dynamic trade size: `${context['dynamic_trade_size_usd']}`",
        f"- TAE action: `{context['advisory_action']}` | block_new_buy: `{context['block_new_buy']}`",
        "",
        "## Ticker lists",
        "",
        f"- Already held STRONG BUY: {', '.join(summary.already_held_tickers) or '—'}",
        f"- Actionable new: {', '.join(summary.actionable_tickers) or '—'}",
        f"- Market closed STRONG BUY: {', '.join(summary.market_closed_tickers) or '—'}",
        "",
        "## Per-signal classification",
        "",
        "| Time | Ticker | Signal | Score | Market | Open | Class | Reason | Shadow |",
        "|------|--------|--------|-------|--------|------|-------|--------|--------|",
    ]

    for row in rows:
        shadow = row.shadow_block_reason or row.shadow_event_type or "—"
        lines.append(
            f"| {row.time} | {row.ticker} | {row.signal} | {row.score} | {row.market} | "
            f"{row.market_open} | {row.classification} | {row.reason} | {shadow} |"
        )

    lines.extend(["", "---", f"*Canonical runtime constants from live_bot.py; config/settings.py noted in JSON.*"])
    return "\n".join(lines) + "\n"


def print_terminal(summary: AuditSummary) -> None:
    print("===== TAE ACTIONABLE SIGNAL AUDIT =====")
    print(f"Strong BUY total: {summary.strong_buy_total}")
    print(f"Already held: {summary.strong_buy_already_held} ({', '.join(summary.already_held_tickers) or '—'})")
    print(f"Actionable new: {summary.strong_buy_actionable_new} ({', '.join(summary.actionable_tickers) or '—'})")
    print(f"Market closed: {summary.strong_buy_market_closed} ({', '.join(summary.market_closed_tickers) or '—'})")
    print(f"Blocked by TAE: {summary.blocked_by_tae}")
    print(f"Blocked by cash: {summary.blocked_by_cash}")
    print(f"Blocked by max positions: {summary.blocked_by_max_positions}")
    print(f"Verdict: {summary.verdict}")
    print(f"Recommendation: {summary.recommendation}")


def run_audit(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT

    signals_path = base / config_settings.LIVE_SIGNALS_FILE
    portfolio_path = base / config_settings.PORTFOLIO_FILE
    watchlist_path = base / config_settings.WATCHLIST_FILE
    advisory_path = base / "tae_live_advisory.json"
    shadow_path = base / "tae_shadow_validation_events.csv"

    if not signals_path.exists():
        raise FileNotFoundError(f"Missing {signals_path}")

    signals_df = pd.read_csv(signals_path)
    portfolio = pd.read_csv(portfolio_path) if portfolio_path.exists() else pd.DataFrame()
    watchlist = _load_watchlist(watchlist_path)
    advisory_payload = _parse_advisory_payload(advisory_path)
    shadow_by_ticker = _load_shadow_latest_by_ticker(shadow_path)

    advisory_state = load_live_advisory(advisory_path)
    block_new_buy, tae_block_reason = should_block_new_buy(advisory_state)
    parsed_block = advisory_payload.get("block_new_buy")
    if parsed_block is not None:
        block_new_buy = bool(parsed_block)

    open_positions = live_bot.get_open_positions(portfolio)
    cash_available = float(live_bot.get_cash_available(portfolio))
    market_regime = _resolve_market_regime()
    trade_size = float(live_bot.get_dynamic_trade_size(signals_df, portfolio, market_regime))

    rows = classify_signals(
        signals_df=signals_df,
        open_positions=open_positions,
        watchlist=watchlist,
        block_new_buy=block_new_buy,
        tae_block_reason=tae_block_reason,
        market_regime=market_regime,
        trade_size=trade_size,
        cash_available=cash_available,
        shadow_by_ticker=shadow_by_ticker,
    )
    summary = build_summary(rows)
    context = _runtime_context(
        portfolio=portfolio,
        advisory_payload=advisory_payload,
        block_new_buy=block_new_buy,
        tae_block_reason=tae_block_reason,
        market_regime=market_regime,
        trade_size=trade_size,
        cash_available=cash_available,
    )
    context["watchlist_count"] = len(watchlist)

    payload = {
        **context,
        "summary": asdict(summary),
        "classifications": list(CLASSIFICATIONS),
        "signals": [asdict(r) for r in rows],
    }

    out_json = base / "tae_actionable_signal_audit.json"
    out_md = base / "tae_actionable_signal_audit.md"
    out_csv = base / "tae_actionable_signal_audit.csv"

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(rows, summary, context), encoding="utf-8")

    fieldnames = list(asdict(rows[0]).keys()) if rows else list(SignalAuditRow.__dataclass_fields__.keys())
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    print_terminal(summary)
    return payload


def main() -> int:
    try:
        run_audit()
        return 0
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
