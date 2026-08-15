#!/usr/bin/env python3
"""
TAE Executive Review — three-part READ_ONLY consolidator.

PAPER_ONLY | READ_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_MUTATION

Aggregates existing canonical artifacts into economic, architecture, and operations
analyses. Does not start/stop bot, execute trades, or mutate portfolio.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae.executive_review.v1"
MODE = "READ_ONLY"
CAPITAL_BASE = 30000.0
OUTPUT_JSON = "tae_executive_review.json"
OUTPUT_MD = "TAE_EXECUTIVE_REVIEW.md"

REQUIRED_SOURCES = (
    "tae_quick_health_check.json",
    "tae_live_advisory.json",
    "portfolio.csv",
)

OPTIONAL_SOURCES = (
    "tae_accounting_snapshot.json",
    "tae_profit_pipeline.json",
    "tae_profit_optimization_audit.json",
    "tae_baseline_vs_challengers.json",
    "tae_30_day_paper_profit_validation.json",
    "tae_decision_state_ownership_audit.json",
    "tae_decision_governor.json",
    "bot_output.log",
    "alerts_log.csv",
    "live_signals.csv",
)

# Explicit SSOT map for executive metrics (runtime rebuild preferred over on-disk cache).
SSOT = {
    "capital_base": "research_core.accounting.accounting_snapshot.build_accounting_snapshot.starting_capital",
    "cash_available": "build_accounting_snapshot.cash_available",
    "account_value": "build_accounting_snapshot.account_value_corrected",
    "realized_pnl": "build_accounting_snapshot.corrected_realized_pnl",
    "unrealized_pnl": "build_accounting_snapshot.corrected_unrealized_pnl",
    "total_trading_pnl": "build_accounting_snapshot.corrected_total_trading_pnl",
    "open_positions_count": "build_accounting_snapshot.open_positions_count",
    "open_positions": "build_accounting_snapshot.open_positions",
    "open_positions_value": "build_accounting_snapshot.open_positions_value",
    "latest_execution": "portfolio.csv last BUY/SELL (+ bot_output.log / alerts_log.csv cross-check)",
    "buy_gate": "tae_live_advisory.json block_new_buy",
    "process_status": "tae_quick_health_check.json (LIVE BOT status; may be cached)",
}

STALE_LIVE_REJECT = (
    "tae_unified_runtime.json",
)

PERMITTED_VERDICTS = (
    "OPERATIONALLY_CONNECTED_ECONOMICALLY_UNPROVEN",
    "READY_FOR_DISCIPLINED_PAPER_VALIDATION",
    "PAPER_VALIDATION_BLOCKED",
    "ARCHITECTURALLY_INCOMPLETE",
    "INSTITUTIONALLY_NOT_READY",
)

FRESH_HOURS_OK = 24.0
FRESH_HOURS_WARN = 72.0

TIMESTAMP_KEYS = ("generated_at", "timestamp", "updated_at", "generatedAt")


def project_root() -> Path:
    return Path(__file__).resolve().parent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _extract_ts(payload: dict[str, Any] | None, path: Path) -> str | None:
    if payload:
        for key in TIMESTAMP_KEYS:
            if payload.get(key):
                return str(payload[key])
    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return None


def _freshness_label(age_hours: float | None) -> str:
    if age_hours is None:
        return "unknown"
    if age_hours <= FRESH_HOURS_OK:
        return "fresh"
    if age_hours <= FRESH_HOURS_WARN:
        return "aging"
    return "stale"


@dataclass
class SourceRecord:
    path: str
    exists: bool
    generated_at: str | None = None
    mtime: str | None = None
    age_hours: float | None = None
    freshness: str = "missing"
    canonical: bool = True
    used: bool = False
    rejected: bool = False
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "generated_at": self.generated_at,
            "mtime": self.mtime,
            "age_hours": self.age_hours,
            "freshness": self.freshness,
            "canonical": self.canonical,
            "used": self.used,
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
        }


def _inspect_source(root: Path, name: str, *, canonical: bool = True) -> SourceRecord:
    path = root / name
    exists = path.is_file()
    rec = SourceRecord(path=name, exists=exists, canonical=canonical)
    if not exists:
        rec.freshness = "missing"
        return rec
    mtime_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    rec.mtime = mtime_dt.isoformat()
    payload = _load_json(path) if name.endswith(".json") else None
    rec.generated_at = _extract_ts(payload, path)
    ref = _parse_ts(rec.generated_at) or mtime_dt
    rec.age_hours = round((_now() - ref).total_seconds() / 3600.0, 2)
    rec.freshness = _freshness_label(rec.age_hours)
    if name in STALE_LIVE_REJECT:
        rec.rejected = True
        rec.used = False
        rec.rejection_reason = "stale historical artifact — not live SSOT"
    return rec


def _mark_used(sources: dict[str, SourceRecord], name: str) -> None:
    if name in sources:
        sources[name].used = True
        sources[name].rejected = False
        sources[name].rejection_reason = None


def _require_payload(
    sources: dict[str, SourceRecord],
    payloads: dict[str, dict[str, Any] | None],
    name: str,
) -> dict[str, Any]:
    rec = sources[name]
    payload = payloads.get(name)
    if not rec.exists or payload is None:
        raise RuntimeError(f"Required canonical source missing or invalid: {name}")
    _mark_used(sources, name)
    return payload


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unavailable(reason: str) -> dict[str, Any]:
    return {"value": "UNAVAILABLE", "reason": reason}


def load_fresh_accounting(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Rebuild canonical accounting from portfolio.csv. Never trust a stale on-disk snapshot for money metrics."""
    portfolio = root / "portfolio.csv"
    if not portfolio.is_file():
        return None, "portfolio.csv missing"
    try:
        from research_core.accounting.accounting_snapshot import (
            build_accounting_snapshot,
            persist_accounting_snapshot,
        )

        snapshot = build_accounting_snapshot(root)
        if not snapshot.get("portfolio_readable", True) and snapshot.get("data_quality_status") == "NO_DATA":
            return None, "portfolio.csv empty or unreadable"
        # Keep on-disk SSOT aligned with this run (generated artifact only).
        persist_accounting_snapshot(snapshot, root)
        return snapshot, None
    except Exception as exc:  # noqa: BLE001 — surface as UNAVAILABLE, no stale fallback
        return None, f"build_accounting_snapshot failed: {exc}"


def resolve_latest_execution(root: Path) -> dict[str, Any]:
    """Resolve latest LIVE BOT fill from portfolio, then cross-check logs."""
    portfolio = root / "portfolio.csv"
    result: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": None,
        "source": None,
        "action": None,
        "ticker": None,
        "timestamp": None,
        "price": None,
        "shares": None,
        "display": "UNAVAILABLE",
        "log_cross_check": None,
    }
    if not portfolio.is_file():
        result["reason"] = "portfolio.csv missing"
        return result

    try:
        import csv

        with portfolio.open(encoding="utf-8", errors="replace", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        result["reason"] = f"portfolio.csv unreadable: {exc}"
        return result

    latest = None
    for row in reversed(rows):
        action = str(row.get("Action", "")).strip().upper()
        ticker = str(row.get("Ticker", "")).strip().upper()
        if action not in {"BUY", "SELL"} or not ticker or ticker == "CASH":
            continue
        latest = row
        break

    if latest is None:
        result["reason"] = "no BUY/SELL rows in portfolio.csv"
        return result

    action = str(latest.get("Action", "")).strip().upper()
    ticker = str(latest.get("Ticker", "")).strip().upper()
    ts = str(latest.get("Date", "")).strip()
    price = _safe_float(latest.get("Price"))
    shares = _safe_float(latest.get("Shares"))
    notional = None
    if price is not None and shares is not None:
        notional = round(price * shares, 2)
    display = f"[{ts}] {action} {ticker}"
    if notional is not None and shares is not None and price is not None:
        display = f"[{ts}] {action} executat: {ticker} | ${notional} | {shares} shares @ {price}"

    log_hit = None
    for log_name in ("bot_output.log", "alerts_log.csv", "live_signals.csv"):
        path = root / log_name
        if not path.is_file():
            continue
        try:
            # Tail scan for ticker+action evidence
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()[-400:]
        except OSError:
            continue
        for line in reversed(lines):
            if ticker in line.upper() and (action in line.upper() or "executat" in line.lower()):
                log_hit = {"file": log_name, "line": line.strip()[:240]}
                break
        if log_hit:
            break

    result.update(
        {
            "status": "OK",
            "reason": None,
            "source": "portfolio.csv",
            "action": action,
            "ticker": ticker,
            "timestamp": ts,
            "price": price,
            "shares": shares,
            "notional": notional,
            "display": display,
            "log_cross_check": log_hit,
            "lane": "LIVE_BOT",
        }
    )
    return result


def _build_economic(
    *,
    accounting: dict[str, Any] | None,
    accounting_error: str | None,
    profit_pipeline: dict[str, Any] | None,
    profit_opt: dict[str, Any] | None,
    baseline: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    sources: dict[str, SourceRecord],
) -> dict[str, Any]:
    if accounting is None:
        return {
            "ssot": "UNAVAILABLE",
            "ssot_source": SSOT,
            "unavailable_reason": accounting_error or "accounting rebuild failed",
            "capital_base": "UNAVAILABLE",
            "cash_available": "UNAVAILABLE",
            "account_value": "UNAVAILABLE",
            "market_value_open": "UNAVAILABLE",
            "profit_vs_base": "UNAVAILABLE",
            "return_pct": "UNAVAILABLE",
            "realized_pnl": "UNAVAILABLE",
            "unrealized_pnl": "UNAVAILABLE",
            "total_trading_pnl": "UNAVAILABLE",
            "open_positions_count": "UNAVAILABLE",
            "open_positions": [],
            "win_rate": None,
            "profit_factor": None,
            "max_drawdown_pct": None,
            "top_winners": [],
            "top_losers": [],
            "profit_loss_drivers": {},
            "paper_pipeline_summary": None,
            "validation_day": None,
            "edge_demonstrated": False,
            "verdict": "ECONOMICALLY_UNPROVEN",
            "integrity_note": "Canonical accounting unavailable — no stale snapshot fallback used.",
            "lane": "ACCOUNTING_SSOT",
        }

    _mark_used(sources, "portfolio.csv")
    _mark_used(sources, "tae_accounting_snapshot.json")

    capital_base = _safe_float(accounting.get("starting_capital"))
    if capital_base is None:
        capital_base = _safe_float((accounting.get("capital_base") or {}).get("starting_capital_config"))
    if capital_base is None:
        # Explicit fallback labeled — still report provenance
        capital_base = CAPITAL_BASE
        capital_base_note = "fallback_CAPITAL_BASE_constant"
    else:
        capital_base_note = "accounting.starting_capital"

    account_value = _safe_float(accounting.get("account_value_corrected"))
    realized = _safe_float(accounting.get("corrected_realized_pnl"))
    unrealized = _safe_float(accounting.get("corrected_unrealized_pnl"))
    total_pnl = _safe_float(accounting.get("corrected_total_trading_pnl"))
    cash_available = _safe_float(accounting.get("cash_available"))
    market_value_open = _safe_float(accounting.get("open_positions_value"))
    open_positions_count = accounting.get("open_positions_count")
    open_positions = accounting.get("open_positions") or []
    profit_vs_base = None
    if account_value is not None and capital_base is not None:
        profit_vs_base = round(account_value - float(capital_base), 2)
    return_pct = None
    if profit_vs_base is not None and capital_base:
        return_pct = round((profit_vs_base / float(capital_base)) * 100.0, 4)

    win_rate = None
    profit_factor = None
    max_drawdown_pct = None
    if profit_opt:
        _mark_used(sources, "tae_profit_optimization_audit.json")
        perf = profit_opt.get("baseline_performance") or {}
        win_rate = _safe_float(perf.get("win_rate"))
        profit_factor = _safe_float(perf.get("profit_factor"))
        max_drawdown_pct = _safe_float(perf.get("max_drawdown_pct"))
    elif baseline:
        _mark_used(sources, "tae_baseline_vs_challengers.json")
        base = baseline.get("baseline") or {}
        win_rate = _safe_float(base.get("win_rate"))
        profit_factor = _safe_float(base.get("profit_factor"))
        max_drawdown_pct = _safe_float(base.get("max_drawdown_pct"))

    pipeline_summary = None
    if profit_pipeline:
        _mark_used(sources, "tae_profit_pipeline.json")
        pipeline_summary = profit_pipeline.get("summary")

    top_winners = accounting.get("top_winners_corrected") or []
    top_losers = accounting.get("top_losers_corrected") or []

    positive_blockers: list[str] = []
    missed_blockers: list[str] = []
    if profit_opt:
        for item in profit_opt.get("top_blockers") or []:
            blocker = str(item.get("blocker") or "")
            impact = _safe_float(item.get("expected_dollar_impact"))
            note = str(item.get("note") or "")
            if "Do not weaken" in note or "hard_risk" in blocker:
                positive_blockers.append(blocker)
            elif impact and impact > 0:
                missed_blockers.append(blocker)

    edge_demonstrated = (
        profit_vs_base is not None
        and profit_vs_base > 0
        and profit_factor is not None
        and profit_factor >= 1.0
        and win_rate is not None
        and win_rate >= 0.5
    )

    if edge_demonstrated:
        verdict = "ECONOMIC_EDGE_DEMONSTRATED"
    elif profit_vs_base is not None and profit_vs_base < 0:
        verdict = "ECONOMICALLY_UNPROVEN_NEGATIVE"
    else:
        verdict = "ECONOMICALLY_UNPROVEN"

    validation_day = None
    if validation:
        _mark_used(sources, "tae_30_day_paper_profit_validation.json")
        validation_day = validation.get("current_day")

    return {
        "ssot": "build_accounting_snapshot(portfolio.csv)",
        "ssot_source": SSOT,
        "capital_base": capital_base,
        "capital_base_note": capital_base_note,
        "cash_available": cash_available,
        "cash_available_note": (
            "ACCOUNTING_SSOT cash_available — excludes NON_TRADING_VIRTUAL DEPOSIT; "
            "NOT advisory runtime_snapshot.cash_available_usd"
        ),
        "account_value": account_value,
        "market_value_open": market_value_open,
        "profit_vs_base": profit_vs_base,
        "return_pct": return_pct,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_trading_pnl": total_pnl,
        "open_positions_count": open_positions_count,
        "open_positions": open_positions,
        "accounting_generated_at": accounting.get("generated_at"),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct,
        "research_metrics_lane": "RESEARCH_ONLY_NOT_RUNTIME",
        "top_winners": top_winners[:5],
        "top_losers": top_losers[:5],
        "profit_loss_drivers": {
            "where_profit_is_lost": [x.get("ticker") for x in top_losers[:3] if x.get("ticker")],
            "blockers_positive": positive_blockers[:5],
            "blockers_missed_profit": missed_blockers[:5],
        },
        "paper_pipeline_summary": pipeline_summary,
        "validation_day": validation_day,
        "edge_demonstrated": edge_demonstrated,
        "verdict": verdict,
        "integrity_note": (
            "Fresh corrected accounting rebuild each run; on-disk snapshot not used as economic fallback."
        ),
        "lane": "ACCOUNTING_SSOT",
    }


def _build_architecture(
    *,
    quick: dict[str, Any],
    advisory: dict[str, Any],
    ownership: dict[str, Any] | None,
    governor: dict[str, Any] | None,
    sources: dict[str, SourceRecord],
    latest_execution: dict[str, Any],
) -> dict[str, Any]:
    _mark_used(sources, "tae_quick_health_check.json")
    _mark_used(sources, "tae_live_advisory.json")

    evidence = quick.get("evidence") or {}
    qh_ts = quick.get("timestamp")
    adv_ts = advisory.get("generated_at")
    qh_newer = False
    qdt = _parse_ts(str(qh_ts) if qh_ts else None)
    adt = _parse_ts(str(adv_ts) if adv_ts else None)
    if qdt and adt:
        qh_newer = adt >= qdt

    block_new_buy = bool(advisory.get("block_new_buy"))
    advisory_action = str(advisory.get("action") or "UNKNOWN")
    cached_buy_executat = evidence.get("buy_executat")
    advisory_log = evidence.get("tae_live_advisory")
    latest_display = latest_execution.get("display")
    latest_ok = latest_execution.get("status") == "OK"
    latest_is_buy = str(latest_execution.get("action") or "").upper() == "BUY"

    health_refresh_ok = qh_newer or (
        adt is not None and qdt is not None and (adt - qdt).total_seconds() < 120
    )

    chain_proof = {
        "quick_health_verdict": quick.get("verdict"),
        "quick_health_timestamp": qh_ts,
        "live_advisory_generated_at": adv_ts,
        "health_to_advisory_refresh_aligned": health_refresh_ok,
        "live_advisory_block_new_buy": block_new_buy,
        "live_advisory_action": advisory_action,
        "buy_gate_open": not block_new_buy,
        "latest_buy_permitted_and_executed": bool(latest_ok and latest_is_buy and not block_new_buy),
        "latest_execution": latest_display,
        "latest_execution_source": latest_execution.get("source"),
        "latest_execution_ticker": latest_execution.get("ticker"),
        "cached_health_buy_executat": cached_buy_executat,
        "evidence_advisory_log": advisory_log,
        "note": "Architecture proof uses portfolio/log latest execution — not a hardcoded ticker.",
    }

    parallel_owner_risk = "LOW"
    ownership_verdict = "COORDINATED"
    if ownership:
        _mark_used(sources, "tae_decision_state_ownership_audit.json")
        if ownership.get("executive_verdict") == "DECISION_STATE_EXISTS_BUT_NOT_CONNECTED":
            parallel_owner_risk = "MEDIUM_PAPER_ONLY"
        ownership_verdict = str(ownership.get("executive_verdict") or "UNKNOWN")

    if governor:
        _mark_used(sources, "tae_decision_governor.json")

    stale_ssot_risk = not health_refresh_ok

    if stale_ssot_risk:
        arch_verdict = "ARCHITECTURALLY_INCOMPLETE"
    elif latest_ok and latest_is_buy and not block_new_buy and health_refresh_ok:
        arch_verdict = "OPERATIONALLY_CONNECTED"
    else:
        arch_verdict = "PARTIALLY_CONNECTED"

    return {
        "decision_owner_live": "live_bot.py",
        "decision_owner_paper": "tae_paper_decision_engine.py",
        "canonical_path": "signal → live_bot.manage_portfolio → portfolio.csv",
        "health_to_advisory_refresh": health_refresh_ok,
        "advisory_to_live_gate": {
            "reloads_each_cycle": True,
            "block_new_buy": block_new_buy,
            "action": advisory_action,
        },
        "parallel_owner_risk": parallel_owner_risk,
        "ownership_audit_verdict": ownership_verdict,
        "shadow_modules_advisory_only": [
            "tae_decision_governor.json (SHADOW_ONLY)",
            "research/demos/* (ADVISORY_ONLY)",
        ],
        "stale_ssot_risk": stale_ssot_risk,
        "host_chain_proof": chain_proof,
        "verdict": arch_verdict,
    }


def _build_operations(
    *,
    quick: dict[str, Any],
    advisory: dict[str, Any],
    accounting: dict[str, Any] | None,
    latest_execution: dict[str, Any],
    sources: dict[str, SourceRecord],
    root: Path,
) -> dict[str, Any]:
    _mark_used(sources, "tae_quick_health_check.json")
    _mark_used(sources, "tae_live_advisory.json")

    proc = quick.get("process_status") or {}
    identity = proc.get("identity") or {}
    git = quick.get("git") or {}
    evidence = quick.get("evidence") or {}

    portfolio_path = root / "portfolio.csv"
    if portfolio_path.is_file():
        _mark_used(sources, "portfolio.csv")

    bot_log = root / "bot_output.log"
    if bot_log.is_file():
        _mark_used(sources, "bot_output.log")

    if accounting is not None:
        open_positions = accounting.get("open_positions_count")
        open_position_tickers = [p.get("ticker") for p in (accounting.get("open_positions") or []) if p.get("ticker")]
        sell_mismatch = accounting.get("sell_mismatch_count")
        cash_available = accounting.get("cash_available")
        market_value_open = accounting.get("open_positions_value")
    else:
        open_positions = "UNAVAILABLE"
        open_position_tickers = []
        sell_mismatch = None
        cash_available = "UNAVAILABLE"
        market_value_open = "UNAVAILABLE"

    critical: list[str] = []
    warnings: list[str] = []
    closed: list[str] = []
    open_findings: list[str] = []

    if proc.get("live_bot") != "RUNNING":
        critical.append("live_bot not RUNNING")
    else:
        closed.append("live_bot RUNNING")

    if "RUNNING" not in str(proc.get("dashboard") or ""):
        warnings.append(f"dashboard status: {proc.get('dashboard')}")
    else:
        closed.append("dashboard RUNNING")

    hb = identity.get("heartbeat_age_sec")
    if hb is not None and float(hb) > 120:
        warnings.append(f"heartbeat age elevated: {hb}s")
    elif hb is not None:
        closed.append(f"heartbeat healthy ({hb}s)")

    git_class = str(git.get("classification") or "UNKNOWN")
    if git.get("operationally_relevant_changes"):
        warnings.append("operationally relevant uncommitted changes present")
    elif git_class == "GENERATED_ARTIFACTS_ONLY":
        closed.append("git: generated artifacts only")

    if advisory.get("block_new_buy"):
        open_findings.append("BUY gate active via live advisory RISK_ADVISORY")
    else:
        closed.append("BUY gate open (block_new_buy=False)")

    if sell_mismatch and int(sell_mismatch) > 0:
        warnings.append(
            f"historical SELL PnL mismatches ({sell_mismatch}) — reporting only for live gates"
        )

    if latest_execution.get("status") == "OK":
        closed.append(f"latest execution: {latest_execution.get('display')}")
    else:
        open_findings.append(
            f"latest execution UNAVAILABLE: {latest_execution.get('reason') or 'unknown'}"
        )

    paper_only = True
    no_broker = str(advisory.get("mode", "")).startswith("PAPER")

    ready_paper = (
        proc.get("live_bot") == "RUNNING"
        and not critical
        and git_class in {"CLEAN", "GENERATED_ARTIFACTS_ONLY"}
    )
    ready_live_capital = False

    if critical:
        ops_verdict = "INSTITUTIONALLY_NOT_READY"
    elif ready_paper:
        ops_verdict = "READY_FOR_DISCIPLINED_PAPER_VALIDATION"
    else:
        ops_verdict = "OPERATIONAL_WITH_WARNINGS"

    return {
        "live_bot": proc.get("live_bot"),
        "live_bot_ops": proc.get("live_bot_ops"),
        "dashboard": proc.get("dashboard"),
        "heartbeat_age_sec": hb,
        "duplicate_processes": identity.get("duplicates") or [],
        "git_classification": git_class,
        "operationally_relevant_changes": git.get("operationally_relevant_changes") or [],
        "open_positions": open_positions,
        "open_position_tickers": open_position_tickers,
        "cash_available": cash_available,
        "market_value_open": market_value_open,
        "per_ticker_session_gate": True,
        "recent_activity_today": (quick.get("recent_activity") or {}).get("activity_today"),
        "buy_gate_block_new_buy": advisory.get("block_new_buy"),
        "latest_execution": latest_execution.get("display"),
        "latest_execution_detail": latest_execution,
        "latest_execution_lane": "LIVE_BOT",
        "paper_only_safety": paper_only and no_broker,
        "advisory_cash_available_usd_non_canonical": (
            ((advisory.get("runtime_snapshot") or {}).get("cash_available_usd"))
            if isinstance(advisory.get("runtime_snapshot"), dict)
            else None
        ),
        "advisory_cash_note": (
            "LIVE_ADVISORY runtime_snapshot.cash_available_usd must equal "
            "ACCOUNTING_SSOT cash_available via build_accounting_snapshot "
            "(bridge must not recompute DEPOSIT-inflated cash)."
        ),
        "sell_canonical": True,
        "reconciliation_note": (
            "Historical sell_mismatch_count is reporting-only; live BUY/SELL gates use corrected metrics."
        ),
        "ready_for_disciplined_paper_validation": ready_paper,
        "ready_for_live_capital": ready_live_capital,
        "verdict": ops_verdict,
        "_critical": critical,
        "_warnings": warnings,
        "_closed": closed,
        "_open": open_findings,
    }


def _derive_final_verdict(
    economic: dict[str, Any],
    architecture: dict[str, Any],
    operations: dict[str, Any],
) -> tuple[str, str, list[str], list[str], list[str], list[str]]:
    critical = list(operations.pop("_critical", []))
    warnings = list(operations.pop("_warnings", []))
    closed = list(operations.pop("_closed", []))
    open_findings = list(operations.pop("_open", []))

    if architecture.get("verdict") == "ARCHITECTURALLY_INCOMPLETE":
        return (
            "ARCHITECTURALLY_INCOMPLETE",
            "Regenerate live advisory from current quick health before executive sign-off.",
            critical,
            warnings,
            closed,
            open_findings,
        )

    if critical:
        return (
            "INSTITUTIONALLY_NOT_READY",
            "Restore live bot/dashboard health and re-run executive-review.",
            critical,
            warnings,
            closed,
            open_findings,
        )

    if not economic.get("edge_demonstrated"):
        if operations.get("ready_for_disciplined_paper_validation"):
            return (
                "OPERATIONALLY_CONNECTED_ECONOMICALLY_UNPROVEN",
                "Continue disciplined PAPER validation; do not promote to live capital.",
                critical,
                warnings,
                closed,
                open_findings,
            )
        return (
            "PAPER_VALIDATION_BLOCKED",
            "Resolve operational warnings before continuing paper validation.",
            critical,
            warnings,
            closed,
            open_findings,
        )

    return (
        "READY_FOR_DISCIPLINED_PAPER_VALIDATION",
        "Maintain paper validation discipline; economic edge requires sustained confirmation.",
        critical,
        warnings,
        closed,
        open_findings,
    )


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    sources: dict[str, SourceRecord] = {}
    for name in REQUIRED_SOURCES + OPTIONAL_SOURCES:
        sources[name] = _inspect_source(root, name, canonical=name in REQUIRED_SOURCES)
    for stale in STALE_LIVE_REJECT:
        sources[stale] = _inspect_source(root, stale, canonical=False)

    payloads: dict[str, dict[str, Any] | None] = {
        name: _load_json(root / name) if name.endswith(".json") else None
        for name in REQUIRED_SOURCES + OPTIONAL_SOURCES
        if name.endswith(".json")
    }

    quick = _require_payload(sources, payloads, "tae_quick_health_check.json")
    advisory = _require_payload(sources, payloads, "tae_live_advisory.json")
    if not (root / "portfolio.csv").is_file():
        raise RuntimeError("Required canonical source missing or invalid: portfolio.csv")
    _mark_used(sources, "portfolio.csv")

    accounting, accounting_error = load_fresh_accounting(root)
    latest_execution = resolve_latest_execution(root)
    if (root / "bot_output.log").is_file():
        _mark_used(sources, "bot_output.log")
    if (root / "alerts_log.csv").is_file():
        _mark_used(sources, "alerts_log.csv")
    if (root / "live_signals.csv").is_file():
        _mark_used(sources, "live_signals.csv")

    # Reject silent use of stale on-disk accounting for economics (file may still be inspected).
    stale_file = payloads.get("tae_accounting_snapshot.json")
    if stale_file and accounting is not None:
        sources["tae_accounting_snapshot.json"].used = True
        sources["tae_accounting_snapshot.json"].rejection_reason = (
            "rebuilt_in_memory_each_run; prior on-disk values not used for economics"
        )

    economic = _build_economic(
        accounting=accounting,
        accounting_error=accounting_error,
        profit_pipeline=payloads.get("tae_profit_pipeline.json"),
        profit_opt=payloads.get("tae_profit_optimization_audit.json"),
        baseline=payloads.get("tae_baseline_vs_challengers.json"),
        validation=payloads.get("tae_30_day_paper_profit_validation.json"),
        sources=sources,
    )
    architecture = _build_architecture(
        quick=quick,
        advisory=advisory,
        ownership=payloads.get("tae_decision_state_ownership_audit.json"),
        governor=payloads.get("tae_decision_governor.json"),
        sources=sources,
        latest_execution=latest_execution,
    )
    operations = _build_operations(
        quick=quick,
        advisory=advisory,
        accounting=accounting,
        latest_execution=latest_execution,
        sources=sources,
        root=root,
    )

    final_verdict, next_action, critical, warnings, closed, open_findings = _derive_final_verdict(
        economic, architecture, operations
    )

    if economic.get("verdict") == "ECONOMICALLY_UNPROVEN_NEGATIVE":
        open_findings.append("Economic edge not demonstrated — negative vs 30k capital base")

    priorities: list[str] = []
    if not economic.get("edge_demonstrated"):
        priorities.append("Complete disciplined 30-day paper validation before live promotion")
    if architecture.get("host_chain_proof", {}).get("latest_buy_permitted_and_executed"):
        ticker = architecture.get("host_chain_proof", {}).get("latest_execution_ticker") or "?"
        closed.append(f"Health→advisory→BUY gate→{ticker} execution chain confirmed on host")
    if warnings:
        priorities.append(f"Resolve operational warnings: {warnings[0]}")

    return {
        "schema": SCHEMA,
        "generated_at": _now_iso(),
        "mode": MODE,
        "capital_base": economic.get("capital_base", CAPITAL_BASE),
        "ssot_map": SSOT,
        "ssot_closure": "EXECUTIVE_REPORTING_SSOT_CLOSED" if accounting is not None and latest_execution.get("status") == "OK" else "EXECUTIVE_REPORTING_SSOT_OPEN",
        "accounting_rebuild_error": accounting_error,
        "lanes": {
            "LIVE_BOT": ["process_status", "latest_execution", "buy_gate"],
            "ACCOUNTING_SSOT": ["cash_available", "account_value", "pnl", "open_positions"],
            "RESEARCH_ONLY": ["win_rate", "profit_factor", "max_drawdown_pct"],
            "TAE_PAPER": ["paper_pipeline_summary", "validation_day"],
        },
        "sources": {k: v.to_dict() for k, v in sorted(sources.items())},
        "economic_analysis": economic,
        "architecture_analysis": architecture,
        "operations_analysis": operations,
        "critical_findings": critical,
        "warnings": warnings,
        "closed_findings": closed,
        "open_findings": open_findings,
        "priorities": priorities,
        "final_verdict": final_verdict,
        "next_action": next_action,
    }


def render_markdown(report: dict[str, Any]) -> str:
    econ = report.get("economic_analysis") or {}
    arch = report.get("architecture_analysis") or {}
    ops = report.get("operations_analysis") or {}
    proof = arch.get("host_chain_proof") or {}

    def _md_money(v: Any) -> str:
        if v == "UNAVAILABLE" or v is None:
            return "UNAVAILABLE" if v == "UNAVAILABLE" else "n/a"
        f = _safe_float(v)
        return f"${f:,.2f}" if f is not None else "n/a"

    lines = [
        "# TAE Executive Review",
        "",
        f"**Generated:** {report.get('generated_at')}",
        f"**Mode:** {report.get('mode')}",
        f"**Final verdict:** {report.get('final_verdict')}",
        f"**SSOT closure:** {report.get('ssot_closure')}",
        "",
        "## Economic analysis (ACCOUNTING_SSOT — fresh rebuild)",
        "",
        f"- Capital base: {_md_money(econ.get('capital_base'))}",
        f"- Cash available: {_md_money(econ.get('cash_available'))}",
        f"- Account value: {_md_money(econ.get('account_value'))}",
        f"- Open market value: {_md_money(econ.get('market_value_open'))}",
        f"- Open positions: {econ.get('open_positions_count')}",
        f"- Profit vs base: {_md_money(econ.get('profit_vs_base'))}",
        f"- Realized PnL: {_md_money(econ.get('realized_pnl'))}",
        f"- Unrealized PnL: {_md_money(econ.get('unrealized_pnl'))}",
        f"- Win rate (RESEARCH_ONLY): {econ.get('win_rate')}",
        f"- Profit factor (RESEARCH_ONLY): {econ.get('profit_factor')}",
        f"- Max drawdown % (RESEARCH_ONLY): {econ.get('max_drawdown_pct')}",
        f"- Economic verdict: **{econ.get('verdict')}**",
        "",
        "## Architecture analysis",
        "",
        f"- Decision owner (live): {arch.get('decision_owner_live')}",
        f"- Health → advisory refresh aligned: {arch.get('health_to_advisory_refresh')}",
        f"- Advisory block_new_buy: {proof.get('live_advisory_block_new_buy')}",
        f"- BUY gate open: {proof.get('buy_gate_open')}",
        f"- Latest BUY chain confirmed: {proof.get('latest_buy_permitted_and_executed')} ({proof.get('latest_execution_ticker')})",
        f"- Latest execution: {proof.get('latest_execution')}",
        f"- Open positions: {ops.get('open_positions')}",
        f"- Cash available (accounting SSOT): {ops.get('cash_available')}",
        f"- Architecture verdict: **{arch.get('verdict')}**",
        "",
        "## Operations analysis",
        "",
        f"- Live bot: {ops.get('live_bot')}",
        f"- Dashboard: {ops.get('dashboard')}",
        f"- Heartbeat age (s): {ops.get('heartbeat_age_sec')}",
        f"- Git classification: {ops.get('git_classification')}",
        f"- Latest execution: {ops.get('latest_execution')}",
        f"- Operations verdict: **{ops.get('verdict')}**",
        "",
        "## Critical findings",
        "",
    ]
    for item in report.get("critical_findings") or []:
        lines.append(f"- {item}")
    if not report.get("critical_findings"):
        lines.append("- (none)")

    lines.extend(["", "## Priorities", ""])
    for item in report.get("priorities") or []:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            f"**Next action:** {report.get('next_action')}",
            "",
            "*READ_ONLY executive review — no execution, no portfolio mutation.*",
            "",
        ]
    )
    return "\n".join(lines)


def format_terminal_summary(report: dict[str, Any]) -> str:
    econ = report.get("economic_analysis") or {}
    arch = report.get("architecture_analysis") or {}
    ops = report.get("operations_analysis") or {}
    proof = arch.get("host_chain_proof") or {}

    def _money(v: Any) -> str:
        if v == "UNAVAILABLE":
            return "UNAVAILABLE"
        f = _safe_float(v)
        return f"${f:,.2f}" if f is not None else "n/a"

    def _pct(v: Any) -> str:
        f = _safe_float(v)
        return f"{f:.2%}" if f is not None else "n/a"

    lines = [
        "===== TAE EXECUTIVE REVIEW =====",
        "",
        "ECONOMIC (ACCOUNTING_SSOT — fresh rebuild)",
        f"capital base: {_money(econ.get('capital_base'))}",
        f"cash available: {_money(econ.get('cash_available'))}",
        f"account value: {_money(econ.get('account_value'))}",
        f"open market value: {_money(econ.get('market_value_open'))}",
        f"open positions: {econ.get('open_positions_count')}",
        f"profit vs base: {_money(econ.get('profit_vs_base'))}",
        f"realized PnL: {_money(econ.get('realized_pnl'))}",
        f"unrealized PnL: {_money(econ.get('unrealized_pnl'))}",
        f"win rate (RESEARCH_ONLY): {_pct(econ.get('win_rate'))}",
        f"profit factor (RESEARCH_ONLY): {econ.get('profit_factor') if econ.get('profit_factor') is not None else 'n/a'}",
        f"economic verdict: {econ.get('verdict')}",
        f"accounting generated_at: {econ.get('accounting_generated_at') or econ.get('unavailable_reason') or 'n/a'}",
        "",
        "ARCHITECTURE",
        f"decision owner: {arch.get('decision_owner_live')}",
        f"health → advisory: {arch.get('health_to_advisory_refresh')}",
        f"advisory → live gate: block_new_buy={proof.get('live_advisory_block_new_buy')}",
        f"decision → execution: {proof.get('latest_execution') or 'UNAVAILABLE'}",
        f"execution source: {proof.get('latest_execution_source') or 'n/a'}",
        f"parallel owner risk: {arch.get('parallel_owner_risk')}",
        f"architecture verdict: {arch.get('verdict')}",
        "",
        "OPERATIONS",
        f"live bot: {ops.get('live_bot')}",
        f"dashboard: {ops.get('dashboard')}",
        f"heartbeat: {ops.get('heartbeat_age_sec')}s",
        f"git classification: {ops.get('git_classification')}",
        f"BUY gate: block_new_buy={ops.get('buy_gate_block_new_buy')}",
        f"open positions: {ops.get('open_positions')} {ops.get('open_position_tickers') or []}",
        f"cash available (SSOT): {_money(ops.get('cash_available'))}",
        f"latest execution (LIVE_BOT): {ops.get('latest_execution') or 'UNAVAILABLE'}",
        f"paper-only safety: {ops.get('paper_only_safety')}",
        f"institutional verdict: {ops.get('verdict')}",
        "",
        "CRITICAL FINDINGS",
    ]
    critical = report.get("critical_findings") or []
    if critical:
        for idx, item in enumerate(critical[:3], start=1):
            lines.append(f"{idx}. {item}")
    else:
        lines.append("1. (none)")

    lines.extend(
        [
            "",
            f"FINAL VERDICT: {report.get('final_verdict')}",
            f"NEXT ACTION: {report.get('next_action')}",
            "",
            "Reports:",
            OUTPUT_MD,
            OUTPUT_JSON,
        ]
    )
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], root: Path | None = None) -> tuple[Path, Path]:
    root = (root or project_root()).resolve()
    json_path = root / OUTPUT_JSON
    md_path = root / OUTPUT_MD
    tmp_json = json_path.with_suffix(".json.tmp")
    tmp_md = md_path.with_suffix(".md.tmp")
    tmp_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_md.write_text(render_markdown(report), encoding="utf-8")
    tmp_json.replace(json_path)
    tmp_md.replace(md_path)
    return json_path, md_path


def main() -> int:
    try:
        report = build_report()
    except RuntimeError as exc:
        print(f"TAE executive-review failed: {exc}", flush=True)
        return 2
    write_outputs(report)
    print(format_terminal_summary(report))
    verdict = str(report.get("final_verdict") or "")
    if verdict not in PERMITTED_VERDICTS:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
