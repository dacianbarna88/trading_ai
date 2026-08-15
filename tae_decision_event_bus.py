#!/usr/bin/env python3
"""
TAE DPE-1 — Decision Event Bus — SHADOW_ONLY / READ_ONLY.

Captures immutable decision-relevant snapshots as JSONL events.
Does NOT alter decisions, execute trades, or modify live behavior.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dpe.decision_event.v1"
MODE = "SHADOW_ONLY"
SOURCE = "tae_decision_event_bus"

ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
GII_JSON = Path("tae_growth_intelligence.json")
TARGET_JSON = Path("tae_profit_target_adapter.json")
PHILOSOPHY_JSON = Path("tae_market_philosophy_lab.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
LIVE_SIGNALS_CSV = Path("live_signals.csv")
PORTFOLIO_CSV = Path("portfolio.csv")
BOT_LOG = Path("bot_output.log")

DPE_DIR = Path("runtime_outputs/dpe")
EVENT_LOG = DPE_DIR / "decision_events.jsonl"
OUTPUT_MD = Path("tae_decision_event_bus.md")

UPSTREAM_REUSE = [
    "tae_accounting_snapshot.json — account_snapshot",
    "tae_growth_intelligence.json — growth_snapshot per ticker",
    "tae_profit_target_adapter.json — target_snapshot per ticker",
    "tae_market_philosophy_lab.json — philosophy_snapshot",
    "tae_portfolio_profit_governor.json — portfolio_policy_snapshot",
    "tae_adaptive_profit_policy_engine.json — policy_state",
    "tae_profit_context_engine.json — risk pce enrichment",
    "tae_profit_decision_governor.json — governor in risk_snapshot",
    "live_signals.csv — signal_snapshot",
    "portfolio.csv — position_snapshot",
    "bot_output.log — market_session_state hint",
]

NOT_DUPLICATED = (
    "Does not recompute GII, targets, philosophy scores, accounting, or protection logic. "
    "Normalizes existing artifacts into immutable event records for DPE-2 splitter."
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def stable_event_id(timestamp: str, ticker: str, event_type: str) -> str:
    batch_day = timestamp[:10] if timestamp else "unknown"
    raw = f"{batch_day}|{ticker.upper()}|{event_type}|{SCHEMA_VERSION}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{batch_day.replace('-', '')}_{ticker.upper()}_{event_type}_{digest}"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def open_positions_from_portfolio(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Net open shares per ticker from portfolio.csv trade history."""
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _s(row.get("Ticker"))
        if not ticker:
            continue
        action = (_s(row.get("Action")) or "").upper()
        shares = _f(row.get("Shares")) or 0.0
        price = _f(row.get("Price"))
        current_price = _f(row.get("Current_Price"))
        pnl = _f(row.get("PnL"))
        pnl_pct = _f(row.get("PnL_%")) or _f(row.get("PnL%"))
        current_value = _f(row.get("Current_Value"))
        invested = _f(row.get("Invested"))

        entry = by_ticker.setdefault(
            ticker.upper(),
            {
                "shares": 0.0,
                "cost_basis": 0.0,
                "avg_price": None,
                "current_price": current_price,
                "pnl": pnl,
                "current_pct": pnl_pct,
                "current_value": current_value,
                "status": "FLAT",
            },
        )
        if action == "BUY":
            entry["cost_basis"] = (entry["cost_basis"] or 0.0) + shares * (price or 0.0)
            entry["shares"] = (entry["shares"] or 0.0) + shares
        elif action == "SELL":
            entry["shares"] = (entry["shares"] or 0.0) - shares
        if current_price is not None:
            entry["current_price"] = current_price
        if pnl is not None:
            entry["pnl"] = pnl
        if pnl_pct is not None:
            entry["current_pct"] = pnl_pct
        if current_value is not None:
            entry["current_value"] = current_value
        if invested is not None and entry["shares"] and entry["shares"] > 0:
            entry["avg_price"] = invested / entry["shares"] if invested else price

    result: dict[str, dict[str, Any]] = {}
    for ticker, entry in by_ticker.items():
        shares = round(entry["shares"] or 0.0, 6)
        if shares <= 1e-9:
            continue
        avg = entry["avg_price"]
        if avg is None and entry["cost_basis"] and shares:
            avg = entry["cost_basis"] / shares
        result[ticker] = {
            "shares": shares,
            "avg_price": round(avg, 4) if avg is not None else None,
            "current_price": entry["current_price"],
            "current_pct": entry["current_pct"],
            "current_value": entry["current_value"],
            "pnl": entry["pnl"],
            "status": "OPEN",
        }
    return result


def signals_by_ticker(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _s(row.get("Ticker"))
        if not ticker:
            continue
        latest[ticker.upper()] = {
            "score": _f(row.get("Score")),
            "signal": _s(row.get("Signal")),
            "rsi": _f(row.get("RSI")),
            "sma50": _f(row.get("SMA50")),
            "price": _f(row.get("Price")),
            "time": _s(row.get("Time")),
        }
    return latest


def market_session_state(bot_log: Path, signals: dict[str, dict[str, Any]]) -> str:
    if bot_log.is_file():
        try:
            tail = bot_log.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
            text = "\n".join(tail).upper()
            if "CLOSED" in text or "MARKET CLOSED" in text:
                return "CLOSED"
            if "OPEN" in text or "SESSION" in text:
                return "OPEN"
        except OSError:
            pass
    if signals:
        return "SIGNALS_ACTIVE"
    return "UNKNOWN"


def account_snapshot(accounting: dict[str, Any] | None) -> dict[str, Any]:
    if not accounting:
        return {
            "account_value_corrected": None,
            "corrected_total_trading_pnl": None,
            "corrected_realized_pnl": None,
            "corrected_unrealized_pnl": None,
            "cash_available": None,
            "data_quality": None,
        }
    return {
        "account_value_corrected": _f(accounting.get("account_value_corrected")),
        "corrected_total_trading_pnl": _f(accounting.get("corrected_total_trading_pnl")),
        "corrected_realized_pnl": _f(accounting.get("corrected_realized_pnl")),
        "corrected_unrealized_pnl": _f(accounting.get("corrected_unrealized_pnl")),
        "cash_available": _f(accounting.get("cash_available")),
        "data_quality": _s(accounting.get("data_quality_status")),
    }


def portfolio_policy_snapshot(
    gii: dict[str, Any] | None,
    ppg: dict[str, Any] | None,
    appe: dict[str, Any] | None,
    targets: dict[str, Any] | None,
) -> dict[str, Any]:
    gii_p = (gii or {}).get("portfolio") or {}
    latest = (appe or {}).get("latest_observation") or {}
    target_p = (targets or {}).get("portfolio") or {}
    return {
        "portfolio_verdict": _s(gii_p.get("portfolio_verdict") or (ppg or {}).get("portfolio_verdict")),
        "policy_state": _s(gii_p.get("policy_state") or latest.get("policy_state")),
        "suggested_shadow_policy": _s(
            gii_p.get("suggested_shadow_policy") or latest.get("suggested_shadow_policy")
        ),
        "portfolio_target_policy": _s(target_p.get("portfolio_target_policy")),
    }


def philosophy_portfolio(philosophy: dict[str, Any] | None) -> dict[str, Any]:
    comp = (philosophy or {}).get("comparative") or {}
    return {
        "competitive_bias_score": None,
        "collaborative_bias_score": None,
        "philosophy_preference": None,
        "competitive_score": _f(comp.get("competitive_score")),
        "collaborative_score": _f(comp.get("collaborative_score")),
        "market_harmony_score": _f(comp.get("market_harmony_score")),
        "current_winning_philosophy": _s(comp.get("current_winning_philosophy")),
        "recommended_experiment_mode": _s(comp.get("recommended_experiment_mode")),
    }


def philosophy_ticker(philosophy: dict[str, Any] | None, ticker: str) -> dict[str, Any]:
    base = philosophy_portfolio(philosophy)
    row = next(
        (t for t in (philosophy or {}).get("tickers") or [] if _s(t.get("ticker")).upper() == ticker.upper()),
        None,
    )
    if row:
        base.update(
            {
                "competitive_bias_score": _f(row.get("competitive_bias_score")),
                "collaborative_bias_score": _f(row.get("collaborative_bias_score")),
                "philosophy_preference": _s(row.get("philosophy_preference")),
            }
        )
    return base


def growth_snapshot(gii_row: dict[str, Any] | None) -> dict[str, Any]:
    if not gii_row:
        return {
            "growth_score": None,
            "winner_quality": None,
            "opportunity_score": None,
            "lifecycle_stage": None,
            "collapse_probability": None,
            "survival_probability": None,
            "recommended_shadow_strategy": None,
        }
    return {
        "growth_score": _f(gii_row.get("growth_score")),
        "winner_quality": _f(gii_row.get("winner_quality")),
        "opportunity_score": _f(gii_row.get("opportunity_score")),
        "lifecycle_stage": _s(gii_row.get("lifecycle_stage")),
        "collapse_probability": _f(gii_row.get("collapse_probability")),
        "survival_probability": _f(gii_row.get("survival_probability")),
        "recommended_shadow_strategy": _s(gii_row.get("recommended_shadow_strategy")),
    }


def target_snapshot(target_row: dict[str, Any] | None) -> dict[str, Any]:
    if not target_row:
        return {
            "dynamic_partial_tp_pct": None,
            "dynamic_trailing_pct": None,
            "dynamic_profit_lock_pct": None,
            "hold_ceiling_pct": None,
            "min_capture_pct": None,
            "exit_window_urgency": None,
            "suggested_partial_size_pct": None,
        }
    return {
        "dynamic_partial_tp_pct": _f(target_row.get("dynamic_partial_tp_pct")),
        "dynamic_trailing_pct": _f(target_row.get("dynamic_trailing_pct")),
        "dynamic_profit_lock_pct": _f(target_row.get("dynamic_profit_lock_pct")),
        "hold_ceiling_pct": _f(target_row.get("hold_ceiling_pct")),
        "min_capture_pct": _f(target_row.get("min_capture_pct")),
        "exit_window_urgency": _s(target_row.get("exit_window_urgency")),
        "suggested_partial_size_pct": _f(target_row.get("suggested_partial_size_pct")),
    }


def position_snapshot_for(
    ticker: str,
    portfolio_positions: dict[str, dict[str, Any]],
    accounting: dict[str, Any] | None,
    gii_row: dict[str, Any] | None,
) -> dict[str, Any]:
    pos = portfolio_positions.get(ticker.upper())
    if pos:
        return pos
    acct_pos = {
        _s(p.get("ticker")).upper(): p
        for p in (accounting or {}).get("open_positions") or []
        if p.get("ticker")
    }.get(ticker.upper())
    if acct_pos:
        return {
            "shares": _f(acct_pos.get("shares")),
            "avg_price": None,
            "current_price": _f(acct_pos.get("current_price")),
            "current_pct": _f(acct_pos.get("pnl_pct")),
            "current_value": None,
            "pnl": _f(acct_pos.get("pnl")),
            "status": "OPEN",
        }
    if gii_row:
        return {
            "shares": None,
            "avg_price": None,
            "current_price": None,
            "current_pct": _f(gii_row.get("current_pct")),
            "current_value": None,
            "pnl": None,
            "status": "INTELLIGENCE_ONLY",
        }
    return {
        "shares": None,
        "avg_price": None,
        "current_price": None,
        "current_pct": None,
        "current_value": None,
        "pnl": None,
        "status": "UNKNOWN",
    }


def build_events() -> tuple[list[dict[str, Any]], dict[str, bool], list[str]]:
    source_paths = {
        "tae_accounting_snapshot.json": ACCOUNTING_JSON,
        "tae_growth_intelligence.json": GII_JSON,
        "tae_profit_target_adapter.json": TARGET_JSON,
        "tae_market_philosophy_lab.json": PHILOSOPHY_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "live_signals.csv": LIVE_SIGNALS_CSV,
        "portfolio.csv": PORTFOLIO_CSV,
        "bot_output.log": BOT_LOG,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, Any] = {}
    missing: list[str] = []

    for key, path in source_paths.items():
        if key.endswith(".csv") or key.endswith(".log"):
            ok = path.is_file()
            sources_loaded[key] = ok
            payloads[key] = None
            if not ok:
                missing.append(key)
            continue
        if key == "tae_accounting_snapshot.json":
            # Always rebuild live economic SSOT — never use stale JSON as truth.
            from research_core.accounting.accounting_snapshot import build_accounting_snapshot

            payloads[key] = build_accounting_snapshot(".")
            sources_loaded[key] = True
            continue
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data
        if not ok:
            missing.append(key)

    accounting = payloads["tae_accounting_snapshot.json"]
    gii = payloads["tae_growth_intelligence.json"]
    targets = payloads["tae_profit_target_adapter.json"]
    philosophy = payloads["tae_market_philosophy_lab.json"]
    ppg = payloads["tae_portfolio_profit_governor.json"]
    appe = payloads["tae_adaptive_profit_policy_engine.json"]
    pdg = payloads["tae_profit_decision_governor.json"]

    portfolio_rows = read_csv_rows(PORTFOLIO_CSV) if sources_loaded["portfolio.csv"] else []
    signal_rows = read_csv_rows(LIVE_SIGNALS_CSV) if sources_loaded["live_signals.csv"] else []
    portfolio_positions = open_positions_from_portfolio(portfolio_rows)
    signals = signals_by_ticker(signal_rows)
    session_state = market_session_state(BOT_LOG, signals)

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    acct_snap = account_snapshot(accounting)
    policy_snap = portfolio_policy_snapshot(gii, ppg, appe, targets)
    phil_port = philosophy_portfolio(philosophy)

    gii_by = {
        _s(t.get("ticker")).upper(): t for t in (gii or {}).get("tickers") or [] if t.get("ticker")
    }
    target_by = {
        _s(t.get("ticker")).upper(): t for t in (targets or {}).get("tickers") or [] if t.get("ticker")
    }
    pdg_by = {
        _s(r.get("ticker")).upper(): r
        for r in (pdg or {}).get("ticker_postures") or []
        if r.get("ticker")
    }

    gii_portfolio = (gii or {}).get("portfolio") or {}
    events: list[dict[str, Any]] = []

    portfolio_event = {
        "event_id": stable_event_id(timestamp, "PORTFOLIO", "PORTFOLIO_SNAPSHOT"),
        "timestamp": timestamp,
        "event_type": "PORTFOLIO_SNAPSHOT",
        "source": SOURCE,
        "mode": MODE,
        "ticker": "PORTFOLIO",
        "market_session_state": session_state,
        "price_snapshot": {
            "current_price": None,
            "high_pct": None,
            "drawdown_pct": None,
        },
        "position_snapshot": {
            "shares": None,
            "avg_price": None,
            "current_price": None,
            "current_pct": None,
            "current_value": _f((accounting or {}).get("open_positions_value")),
            "pnl": acct_snap.get("corrected_total_trading_pnl"),
            "status": "PORTFOLIO_AGGREGATE",
        },
        "account_snapshot": acct_snap,
        "signal_snapshot": {
            "score": None,
            "signal": None,
            "rsi": None,
            "sma50": None,
            "price": None,
            "active_signal_count": len(signals),
        },
        "growth_snapshot": {
            "growth_score": _f(gii_portfolio.get("global_growth_score")),
            "winner_quality": _f(gii_portfolio.get("portfolio_growth_quality")),
            "opportunity_score": _f(gii_portfolio.get("opportunity_index")),
            "lifecycle_stage": None,
            "collapse_probability": None,
            "survival_probability": None,
            "recommended_shadow_strategy": _s(gii_portfolio.get("recommended_portfolio_shadow_strategy")),
        },
        "target_snapshot": target_snapshot(None),
        "philosophy_snapshot": phil_port,
        "portfolio_policy_snapshot": policy_snap,
        "risk_snapshot": {
            "portfolio_verdict": policy_snap.get("portfolio_verdict"),
            "policy_state": policy_snap.get("policy_state"),
            "opportunity_cost_total": _f(gii_portfolio.get("opportunity_cost_total")),
            "profit_capture_rate": _f(gii_portfolio.get("profit_capture_rate")),
            "governor_recommendation": None,
            "pce_verdict": None,
        },
        "raw_sources": sources_loaded,
        "schema_version": SCHEMA_VERSION,
    }
    events.append(portfolio_event)

    tickers = sorted(gii_by.keys()) if gii_by else sorted(set(portfolio_positions) | set(signals))
    for ticker in tickers:
        gii_row = gii_by.get(ticker)
        target_row = target_by.get(ticker)
        gov = pdg_by.get(ticker) or {}
        sig = signals.get(ticker) or {}
        pos = position_snapshot_for(ticker, portfolio_positions, accounting, gii_row)

        events.append(
            {
                "event_id": stable_event_id(timestamp, ticker, "TICKER_DECISION_SNAPSHOT"),
                "timestamp": timestamp,
                "event_type": "TICKER_DECISION_SNAPSHOT",
                "source": SOURCE,
                "mode": MODE,
                "ticker": ticker,
                "market_session_state": session_state,
                "price_snapshot": {
                    "current_price": sig.get("price") or pos.get("current_price"),
                    "high_pct": _f((gii_row or {}).get("high_pct")),
                    "drawdown_pct": _f((gii_row or {}).get("drawdown")),
                },
                "position_snapshot": pos,
                "account_snapshot": acct_snap,
                "signal_snapshot": {
                    "score": sig.get("score"),
                    "signal": sig.get("signal"),
                    "rsi": sig.get("rsi"),
                    "sma50": sig.get("sma50"),
                    "price": sig.get("price"),
                },
                "growth_snapshot": growth_snapshot(gii_row),
                "target_snapshot": target_snapshot(target_row),
                "philosophy_snapshot": philosophy_ticker(philosophy, ticker),
                "portfolio_policy_snapshot": policy_snap,
                "risk_snapshot": {
                    "portfolio_verdict": policy_snap.get("portfolio_verdict"),
                    "policy_state": policy_snap.get("policy_state"),
                    "opportunity_cost_total": _f((gii_row or {}).get("missed_usd")),
                    "profit_capture_rate": _f(gii_portfolio.get("profit_capture_rate")),
                    "governor_recommendation": _s(
                        (gii_row or {}).get("governor_recommendation") or gov.get("final_shadow_recommendation")
                    ),
                    "pce_verdict": _s((gii_row or {}).get("pce_verdict")),
                },
                "raw_sources": sources_loaded,
                "schema_version": SCHEMA_VERSION,
            }
        )

    return events, sources_loaded, missing


def append_events(events: list[dict[str, Any]]) -> tuple[int, int, set[str]]:
    DPE_DIR.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if EVENT_LOG.is_file():
        try:
            for line in EVENT_LOG.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                eid = _s(row.get("event_id"))
                if eid:
                    existing.add(eid)
        except (json.JSONDecodeError, OSError):
            pass
    seen: set[str] = set()
    written = 0
    skipped = 0
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        for event in events:
            eid = event["event_id"]
            if eid in seen or eid in existing:
                skipped += 1
                continue
            seen.add(eid)
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
            written += 1
    return written, skipped, seen


def write_report(
    *,
    written: int,
    skipped: int,
    event_count: int,
    sources_loaded: dict[str, bool],
    missing: list[str],
    events: list[dict[str, Any]],
) -> None:
    portfolio_events = [e for e in events if e["event_type"] == "PORTFOLIO_SNAPSHOT"]
    ticker_events = [e for e in events if e["event_type"] == "TICKER_DECISION_SNAPSHOT"]

    lines = [
        "# TAE Decision Event Bus (DPE-1)",
        "",
        f"**Generated:** {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"**Mode:** {MODE} — READ_ONLY",
        f"**Schema version:** {SCHEMA_VERSION}",
        "",
        "> **Immutable decision events — no execution, no live behavior change**",
        "",
        "## Executive summary",
        "",
        f"- Events built this run: **{event_count}**",
        f"- Events appended: **{written}** (skipped duplicates in run: **{skipped}**)",
        f"- Event log: `{EVENT_LOG}`",
        f"- Portfolio snapshots: **{len(portfolio_events)}**",
        f"- Ticker decision snapshots: **{len(ticker_events)}**",
        "",
        "## Schema version",
        "",
        f"`{SCHEMA_VERSION}` — see `tae_decision_event_bus_schema.json`",
        "",
        "## Events generated",
        "",
        "| event_type | count |",
        "| --- | --- |",
        f"| PORTFOLIO_SNAPSHOT | {len(portfolio_events)} |",
        f"| TICKER_DECISION_SNAPSHOT | {len(ticker_events)} |",
        "",
        "## Source status",
        "",
        "| source | loaded |",
        "| --- | --- |",
    ]
    for key, loaded in sorted(sources_loaded.items()):
        mark = "✅" if loaded else "❌"
        lines.append(f"| {key} | {mark} |")

    if missing:
        lines.extend(["", "**Missing sources:**", ""])
        for m in missing:
            lines.append(f"- {m}")

    lines.extend(["", "## Portfolio event summary", ""])
    if portfolio_events:
        pe = portfolio_events[0]
        lines.append(f"- Event ID: `{pe['event_id']}`")
        lines.append(f"- Account value: **{pe['account_snapshot'].get('account_value_corrected')}**")
        lines.append(f"- Winning philosophy: **{pe['philosophy_snapshot'].get('current_winning_philosophy')}**")
        lines.append(f"- Portfolio verdict: **{pe['portfolio_policy_snapshot'].get('portfolio_verdict')}**")

    lines.extend(["", "## Ticker event summary", "", "| ticker | growth | strategy | philosophy pref |", "| --- | --- | --- | --- |"])
    for row in ticker_events[:20]:
        gs = row["growth_snapshot"]
        ps = row["philosophy_snapshot"]
        lines.append(
            f"| {row['ticker']} | {gs.get('growth_score')} | {gs.get('recommended_shadow_strategy')} | "
            f"{ps.get('philosophy_preference')} |"
        )
    if len(ticker_events) > 20:
        lines.append(f"| … | +{len(ticker_events) - 20} more | | |")

    lines.extend(
        [
            "",
            "## Event log path",
            "",
            f"`{EVENT_LOG}`",
            "",
            "## How this feeds DPE-2",
            "",
            "DPE-2 Execution Splitter will read `decision_events.jsonl`, fan out each "
            "`TICKER_DECISION_SNAPSHOT` into competitive and collaborative decision packets "
            "without modifying live execution.",
            "",
            "## What this reuses",
            "",
        ]
    )
    for item in UPSTREAM_REUSE:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## What this does not duplicate",
            "",
            f"- {NOT_DUPLICATED}",
            "",
            "## Safety confirmation",
            "",
            "- READ_ONLY: **true**",
            "- SHADOW_ONLY: **true**",
            "- NO_BROKER: **true**",
            "- NO_EXECUTION: **true**",
            "- NO_LIVE_BOT_CHANGE: **true**",
            "- NO_ADVISORY_CHANGE: **true**",
            "- portfolio.csv modified: **false**",
            "",
            "## Recommended next sprint",
            "",
            "**TAE DPE-2 — Execution Splitter**",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(written: int, event_count: int, missing: list[str]) -> None:
    print("===== TAE DECISION EVENT BUS (DPE-1) =====")
    print("Mode: SHADOW_ONLY — read-only capture")
    print("Schema:", SCHEMA_VERSION)
    print("Events built:", event_count)
    print("Events appended:", written)
    print("Event log:", EVENT_LOG)
    if missing:
        print("Missing sources:", ", ".join(missing))


def main() -> int:
    events, sources_loaded, missing = build_events()
    written, skipped, _ = append_events(events)
    write_report(
        written=written,
        skipped=skipped,
        event_count=len(events),
        sources_loaded=sources_loaded,
        missing=missing,
        events=events,
    )
    print_summary(written, len(events), missing)
    print("Wrote:", OUTPUT_MD, EVENT_LOG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
