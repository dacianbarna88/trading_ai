#!/usr/bin/env python3
"""
TAE PAPER Execution — apply validated PDE decisions to isolated PAPER portfolio.

PAPER_ONLY | NO_BROKER | NO_LIVE_EXECUTION | NO_LIVE_PROMOTION
Writes only to runtime_outputs/paper_execution/ — never touches live_bot.py or portfolio.csv.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae.paper_portfolio.v1"
MODE = "PAPER_ONLY"
DAILY_EQUITY_SCHEMA = "tae.paper_daily_equity.v1"

OUTPUT_DIR = Path("runtime_outputs/paper_execution")
PORTFOLIO_JSON = OUTPUT_DIR / "paper_portfolio.json"
ORDERS_JSONL = OUTPUT_DIR / "paper_orders.jsonl"
TRADES_JSONL = OUTPUT_DIR / "paper_trades.jsonl"
ATTRIBUTION_JSON = OUTPUT_DIR / "rule_outcome_attribution.json"
MTM_JSON = OUTPUT_DIR / "mark_to_market.json"
DAILY_EQUITY_JSONL = OUTPUT_DIR / "paper_daily_equity.jsonl"
EXECUTION_LOCK = OUTPUT_DIR / "paper_execution.lock"
E3_BLOCKS_JSONL = OUTPUT_DIR / "e3_profit_decay_blocks.jsonl"
E3_AUDIT_JSON = OUTPUT_DIR / "e3_canonical_entry_protection.json"
REPORT_MD = Path("TAE_PAPER_EXECUTION_REPORT.md")
MTM_REPORT_MD = Path("TAE_PAPER_MARK_TO_MARKET_REPORT.md")
CANONICAL_VS_PAPER_MD = Path("TAE_CANONICAL_VS_PAPER_REPORT.md")

DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")
INTEGRITY_REPORT_JSON = Path("tae_paper_profit_integrity_guard_report.json")
INTEGRITY_REPORT_MD = Path("TAE_PAPER_PROFIT_INTEGRITY_GUARD_REPORT.md")
VALIDATION_PROFIT_JSON = Path("tae_30_day_paper_profit_validation.json")
GII_JSON = Path("tae_growth_intelligence.json")

INFLUENCE_DELTA_CAP = 0.008


def _load_live_accounting() -> dict[str, Any]:
    """Always rebuild live economic SSOT — never trust stale tae_accounting_snapshot.json alone."""
    from research_core.accounting.accounting_snapshot import build_accounting_snapshot

    return build_accounting_snapshot(".")

# Canonical E3: block NEW BUY only when lifecycle_stage == PROFIT_DECAY (exact).
# Default ON; set BLOCK_NEW_BUY_DURING_PROFIT_DECAY=false to rollback without code changes.
GII_MAX_AGE_HOURS = 24.0
BLOCK_REASON_PROFIT_DECAY = "BLOCKED_NEW_BUY_PROFIT_DECAY"

# Canonical opening-noise: DEFER NEW BUY in [open, open+N minutes).
# Default ON; set DEFER_NEW_BUY_DURING_OPENING_NOISE=false to rollback.
# Boundary: minutes_since_open < OPENING_NOISE_WINDOW_MINUTES → DEFER; >= → pass.
DEFER_REASON_OPENING_NOISE = "DEFERRED_NEW_BUY_OPENING_NOISE"
DEFAULT_OPENING_NOISE_WINDOW_MINUTES = 15

# Binding Decision Brain SKIP paper entry gate (GLOBAL_ENTRY_GATE_PROVEN).
# PAPER only; blocks NEW V1 BUY / V2 OPEN when canonical Decision Brain = SKIP.
# Default ON; rollback: DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED=false.
# Does NOT hard-gate PPG PROTECT, 7D NEGATIVE, score 100, V2 ADD, SELL, or Hard Risk.
BLOCK_REASON_DECISION_BRAIN_SKIP = "BLOCKED_DECISION_BRAIN_SKIP"
ECONOMIC_CLASS_DECISION_BRAIN_SKIP = "ENTRY_BLOCKED_BY_DECISION_BRAIN_SKIP"
DECISION_BRAIN_SKIP_ACTIONS = frozenset({"SKIP_PAPER", "SKIP"})
DECISION_BRAIN_SKIP_BLOCKS_JSONL = OUTPUT_DIR / "decision_brain_skip_blocks.jsonl"
BINDING_SKIP_FORWARD_COHORT_JSONL = OUTPUT_DIR / "binding_skip_gate_forward_cohort.jsonl"


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

SIGNALS_CSV = Path("live_signals.csv")
SIGNAL_PRICE_MAX_AGE_SECONDS = 3600.0
RISK_PRICE_MAX_AGE_SECONDS = 45.0

TERMINAL_ORDER_STATUSES = frozenset(
    {
        "EXECUTED",
        "NO_CHANGE",
        # Terminal: same decision_id must not retry into a fill after E3 block.
        BLOCK_REASON_PROFIT_DECAY,
        # Terminal: deferred BUY must not auto-fill after window; requires fresh decision.
        DEFER_REASON_OPENING_NOISE,
        # Terminal: Decision Brain SKIP binding gate — no retry into fill without fresh decision.
        BLOCK_REASON_DECISION_BRAIN_SKIP,
    }
)

NON_TERMINAL_ORDER_STATUSES = frozenset(
    {
        "SKIPPED_NO_MARK_PRICE",
        "SKIPPED_NO_POSITION",
        "SKIPPED_SWITCH_NOT_AUTHORIZED",
        "BLOCKED_FAKE_PROFIT_RISK",
        "BLOCKED_HARD_RISK_AT_FILL",
        "SKIPPED_TRAILING_EXIT_NO_LONGER_VALID",
        "SKIPPED_NO_VALID_TRAILING_MARK",
        "BUY_BLOCKED_ACTIVE_PROFIT_TRAILING",
    }
)

HARD_RISK_BREACH_STATUSES = frozenset({"STOP_LOSS_BREACHED", "CRITICAL_LOSS"})


def block_new_buy_during_profit_decay_enabled() -> bool:
    """Feature flag — default true. Rollback: BLOCK_NEW_BUY_DURING_PROFIT_DECAY=false."""
    raw = os.getenv("BLOCK_NEW_BUY_DURING_PROFIT_DECAY", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def load_gii_lifecycle_index(
    path: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """
    Load GII ticker lifecycle SSOT for the E3 entry gate.

    Returns (by_ticker, meta) where meta always includes gate_status:
      OK | PROFIT_DECAY_GATE_DATA_INVALID | PROFIT_DECAY_GATE_STALE | MISSING_FILE
    Fail-open for BUY when not OK — never invent PROFIT_DECAY.
    """
    gii_path = path or GII_JSON
    meta: dict[str, Any] = {
        "ssot": str(gii_path),
        "gate_status": "MISSING_FILE",
        "generated_at": None,
        "age_hours": None,
        "max_age_hours": GII_MAX_AGE_HOURS,
        "ticker_count": 0,
    }
    if not gii_path.is_file():
        return {}, meta
    try:
        raw = json.loads(gii_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        meta["gate_status"] = "PROFIT_DECAY_GATE_DATA_INVALID"
        meta["error"] = str(exc)
        return {}, meta
    if not isinstance(raw, dict):
        meta["gate_status"] = "PROFIT_DECAY_GATE_DATA_INVALID"
        meta["error"] = "GII root is not an object"
        return {}, meta

    generated_at = raw.get("generated_at") or raw.get("updated_at")
    meta["generated_at"] = generated_at
    gen_dt = _parse_ts(str(generated_at) if generated_at else None)
    if gen_dt is None:
        # Fall back to mtime if generated_at missing/unparseable
        try:
            gen_dt = datetime.fromtimestamp(gii_path.stat().st_mtime, tz=timezone.utc)
            meta["generated_at"] = gen_dt.isoformat().replace("+00:00", "Z")
            meta["timestamp_source"] = "mtime"
        except OSError:
            meta["gate_status"] = "PROFIT_DECAY_GATE_DATA_INVALID"
            meta["error"] = "unreadable GII timestamp"
            return {}, meta
    else:
        meta["timestamp_source"] = "generated_at"

    age_h = max(0.0, (datetime.now(timezone.utc) - gen_dt).total_seconds() / 3600.0)
    meta["age_hours"] = round(age_h, 4)
    if age_h > GII_MAX_AGE_HOURS:
        meta["gate_status"] = "PROFIT_DECAY_GATE_STALE"
        # Still index tickers for diagnostics, but caller must not block on stale stage.
    else:
        meta["gate_status"] = "OK"

    by_ticker: dict[str, dict[str, Any]] = {}
    for row in raw.get("tickers") or []:
        if isinstance(row, dict) and row.get("ticker"):
            by_ticker[_s(row.get("ticker")).upper()] = row
    meta["ticker_count"] = len(by_ticker)
    return by_ticker, meta


def evaluate_profit_decay_new_buy_gate(
    *,
    action: str,
    is_new_position: bool,
    ticker: str,
    gii_by_ticker: dict[str, dict[str, Any]] | None,
    gii_meta: dict[str, Any] | None,
    decision_timestamp: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """
    Canonical E3 authorization precondition.

    Blocks only: NEW BUY_PAPER (or BUY) when fresh GII lifecycle_stage == PROFIT_DECAY.
    Does not invent PROFIT_DECAY; does not use collapse_probability as a block threshold.
    Fail-open on missing/stale/invalid GII for BUY path.
    """
    flag_on = block_new_buy_during_profit_decay_enabled() if enabled is None else bool(enabled)
    action_u = _s(action).upper()
    result: dict[str, Any] = {
        "enabled": flag_on,
        "applies": False,
        "blocked": False,
        "authorization": "ALLOW",
        "authorized_action": action_u,
        "original_action": action_u,
        "block_reason": None,
        "diagnostic": None,
        "is_new_position": bool(is_new_position),
        "lifecycle_stage": None,
        "collapse_probability": None,
        "growth_intelligence_timestamp": (gii_meta or {}).get("generated_at"),
        "gii_gate_status": (gii_meta or {}).get("gate_status"),
        "gii_age_hours": (gii_meta or {}).get("age_hours"),
        "decision_timestamp": decision_timestamp,
        "ticker": _s(ticker).upper(),
    }
    if not flag_on:
        result["diagnostic"] = "FEATURE_FLAG_OFF"
        return result
    if action_u not in {"BUY", "BUY_PAPER"}:
        result["diagnostic"] = "ACTION_NOT_BUY"
        return result
    if not is_new_position:
        result["diagnostic"] = "EXISTING_POSITION_ADD_ON_ALLOWED"
        return result

    result["applies"] = True
    meta = gii_meta or {}
    gate_status = _s(meta.get("gate_status")) or "MISSING_FILE"

    if gate_status in {"MISSING_FILE", "PROFIT_DECAY_GATE_DATA_INVALID"}:
        result["diagnostic"] = gate_status if gate_status != "MISSING_FILE" else "PROFIT_DECAY_GATE_DATA_INVALID"
        result["authorization"] = "ALLOW"
        return result
    if gate_status == "PROFIT_DECAY_GATE_STALE":
        result["diagnostic"] = "PROFIT_DECAY_GATE_STALE"
        result["authorization"] = "ALLOW"
        return result

    row = (gii_by_ticker or {}).get(_s(ticker).upper())
    if not row:
        result["diagnostic"] = "NO_LIFECYCLE_EVIDENCE"
        result["authorization"] = "ALLOW"
        return result

    lifecycle = _s(row.get("lifecycle_stage"))
    collapse = row.get("collapse_probability")
    result["lifecycle_stage"] = lifecycle or None
    try:
        result["collapse_probability"] = float(collapse) if collapse is not None else None
    except (TypeError, ValueError):
        result["collapse_probability"] = None

    if lifecycle == "PROFIT_DECAY":
        result["blocked"] = True
        result["authorization"] = "BLOCKED"
        result["authorized_action"] = "HOLD_PAPER"
        result["block_reason"] = BLOCK_REASON_PROFIT_DECAY
        result["diagnostic"] = BLOCK_REASON_PROFIT_DECAY
        return result

    result["diagnostic"] = "LIFECYCLE_NOT_PROFIT_DECAY"
    result["authorization"] = "ALLOW"
    return result


def append_e3_block_event(event: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "e3_profit_decay_blocks.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def summarize_e3_canonical_blocks(*, today: str | None = None) -> dict[str, Any]:
    """Daily audit metrics for Canonical E3 Entry Protection (read-only aggregate)."""
    day = today or datetime.now(timezone.utc).date().isoformat()
    rows: list[dict[str, Any]] = []
    blocks_path = OUTPUT_DIR / "e3_profit_decay_blocks.jsonl"
    if blocks_path.is_file():
        for line in blocks_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    today_rows = [
        r
        for r in rows
        if str(r.get("timestamp") or "").startswith(day)
        or str(r.get("decision_timestamp") or "").startswith(day)
    ]
    tickers = sorted({_s(r.get("ticker")).upper() for r in today_rows if r.get("ticker")})
    capital_not_deployed = round(sum(_f(r.get("capital_not_deployed")) for r in today_rows), 4)
    avoided = round(sum(_f(r.get("avoided_loss")) for r in today_rows), 4)
    missed = round(sum(_f(r.get("missed_profit")) for r in today_rows), 4)
    return {
        "schema": "tae.e3_canonical_entry_protection.v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "enabled": block_new_buy_during_profit_decay_enabled(),
        "blocked_new_buy_profit_decay_count": len(today_rows),
        "blocked_new_buy_profit_decay_tickers": tickers,
        "capital_not_deployed": capital_not_deployed,
        "subsequent_return_1d": None,
        "subsequent_return_3d": None,
        "subsequent_return_5d": None,
        "avoided_loss": avoided,
        "missed_profit": missed,
        "net_e3_value": round(avoided - missed, 4),
        "note": "Activation ≠ profitability; outcomes tracked as events mature",
        "total_blocks_all_time": len(rows),
    }


def morning_audit_e3_canonical_summary() -> dict[str, Any]:
    summary = summarize_e3_canonical_blocks()
    return {
        "enabled": "YES" if summary.get("enabled") else "NO",
        "new_buy_blocked_today": summary.get("blocked_new_buy_profit_decay_count"),
        "tickers": summary.get("blocked_new_buy_profit_decay_tickers"),
        "avoided_loss_tracking": summary.get("avoided_loss"),
        "missed_profit_tracking": summary.get("missed_profit"),
        "net_e3_value": summary.get("net_e3_value"),
    }


def defer_new_buy_during_opening_noise_enabled() -> bool:
    """Feature flag — default true. Rollback: DEFER_NEW_BUY_DURING_OPENING_NOISE=false."""
    raw = os.getenv("DEFER_NEW_BUY_DURING_OPENING_NOISE", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def opening_noise_window_minutes() -> int:
    raw = os.getenv("OPENING_NOISE_WINDOW_MINUTES", str(DEFAULT_OPENING_NOISE_WINDOW_MINUTES)).strip()
    try:
        n = int(raw)
    except ValueError:
        n = DEFAULT_OPENING_NOISE_WINDOW_MINUTES
    return max(1, n)


def evaluate_opening_noise_new_buy_gate(
    *,
    action: str,
    is_new_position: bool,
    ticker: str,
    decision_timestamp: str | None = None,
    now: datetime | None = None,
    enabled: bool | None = None,
    window_minutes: int | None = None,
) -> dict[str, Any]:
    """
    Canonical opening-noise authorization precondition.

    DEFER only: NEW BUY_PAPER when regular session is open AND
    minutes_since_open < window (default 15). Boundary at exactly +15 → PASS.

    Does not apply when market is closed (not mislabeled as opening noise).
    Does not auto-execute after window — deferred decision is terminal for that decision_id.
    """
    from markets.market_hours import ticker_session_context

    flag_on = defer_new_buy_during_opening_noise_enabled() if enabled is None else bool(enabled)
    window = opening_noise_window_minutes() if window_minutes is None else int(window_minutes)
    action_u = _s(action).upper()
    eval_at = now or datetime.now(timezone.utc)
    # Prefer decision timestamp when present (auditability); fill-time still uses now if missing.
    decision_dt = _parse_ts(decision_timestamp) or eval_at
    session = ticker_session_context(ticker, at=decision_dt)

    result: dict[str, Any] = {
        "enabled": flag_on,
        "applies": False,
        "deferred": False,
        "authorization": "ALLOW",
        "authorized_action": action_u,
        "original_action": action_u,
        "defer_reason": None,
        "diagnostic": None,
        "is_new_position": bool(is_new_position),
        "ticker": _s(ticker).upper(),
        "market": session.get("market"),
        "exchange_timezone": session.get("timezone"),
        "regular_session_open": session.get("regular_session_open"),
        "regular_session_close": session.get("regular_session_close"),
        "decision_timestamp": decision_timestamp,
        "minutes_since_open": session.get("minutes_since_open"),
        "opening_noise_window_minutes": window,
        "earliest_recheck_at": None,
        "feature_flag": "DEFER_NEW_BUY_DURING_OPENING_NOISE",
        "session_is_open": bool(session.get("is_open")),
    }

    if not flag_on:
        result["diagnostic"] = "FEATURE_FLAG_OFF"
        return result
    if action_u not in {"BUY", "BUY_PAPER"}:
        result["diagnostic"] = "ACTION_NOT_BUY"
        return result
    if not is_new_position:
        result["diagnostic"] = "EXISTING_POSITION_ADD_ON_ALLOWED"
        return result

    result["applies"] = True

    if not session.get("enabled"):
        result["diagnostic"] = "MARKET_DISABLED"
        result["authorization"] = "ALLOW"
        return result

    if not session.get("is_open"):
        # Off-hours / weekend: do not mislabel as opening noise; leave existing session behavior.
        result["diagnostic"] = "MARKET_CLOSED_NOT_OPENING_NOISE"
        result["authorization"] = "ALLOW"
        return result

    mins = session.get("minutes_since_open")
    if mins is None:
        result["diagnostic"] = "SESSION_BOUNDS_UNAVAILABLE"
        result["authorization"] = "ALLOW"
        return result

    # Boundary: defer strictly while minutes_since_open < window; at == window → pass.
    if mins < float(window):
        earliest = None
        if session.get("regular_session_open"):
            try:
                from datetime import timedelta

                open_dt = datetime.fromisoformat(str(session["regular_session_open"]))
                earliest = (open_dt + timedelta(minutes=window)).isoformat()
            except ValueError:
                earliest = None
        result["deferred"] = True
        result["authorization"] = "DEFERRED"
        result["authorized_action"] = "DEFERRED"
        result["defer_reason"] = DEFER_REASON_OPENING_NOISE
        result["diagnostic"] = DEFER_REASON_OPENING_NOISE
        result["earliest_recheck_at"] = earliest
        return result

    result["diagnostic"] = "OPENING_NOISE_WINDOW_PASSED"
    result["authorization"] = "ALLOW"
    return result


def append_opening_noise_defer_event(event: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "opening_noise_defers.jsonl"
    # Idempotent append: skip if same decision_id already recorded
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _s(row.get("decision_id")) == _s(event.get("decision_id")) and _s(
                row.get("defer_reason")
            ) == DEFER_REASON_OPENING_NOISE:
                return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")


def summarize_opening_noise_defers(*, today: str | None = None) -> dict[str, Any]:
    day = today or datetime.now(timezone.utc).date().isoformat()
    rows: list[dict[str, Any]] = []
    path = OUTPUT_DIR / "opening_noise_defers.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    today_rows = [
        r
        for r in rows
        if str(r.get("timestamp") or "").startswith(day)
        or str(r.get("decision_timestamp") or "").startswith(day)
    ]
    tickers = sorted({_s(r.get("ticker")).upper() for r in today_rows if r.get("ticker")})
    decision_ids = [_s(r.get("decision_id")) for r in today_rows if r.get("decision_id")]
    capital = round(sum(_f(r.get("capital_temporarily_undeployed")) for r in today_rows), 4)
    return {
        "schema": "tae.opening_noise_protection.v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "enabled": defer_new_buy_during_opening_noise_enabled(),
        "window_minutes": opening_noise_window_minutes(),
        "opening_noise_deferred_count": len(today_rows),
        "opening_noise_deferred_tickers": tickers,
        "opening_noise_deferred_decision_ids": decision_ids,
        "opening_noise_requalified_after_window": None,  # requires later join; tracked when fresh BUYs execute
        "opening_noise_expired_without_buy": None,
        "opening_noise_later_blocked_profit_decay": None,
        "opening_noise_later_executed": None,
        "capital_temporarily_undeployed": capital,
        "avoided_opening_loss": round(sum(_f(r.get("avoided_opening_loss")) for r in today_rows), 4),
        "missed_opening_profit": round(sum(_f(r.get("missed_opening_profit")) for r in today_rows), 4),
        "net_opening_protection_value": round(
            sum(_f(r.get("avoided_opening_loss")) for r in today_rows)
            - sum(_f(r.get("missed_opening_profit")) for r in today_rows),
            4,
        ),
        "note": "Activation ≠ profitability; counterfactuals are read-only and mature over time",
        "total_defers_all_time": len(rows),
    }


def decision_brain_skip_paper_gate_enabled() -> bool:
    """Feature flag — default true (PAPER). Rollback: DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED=false."""
    raw = os.getenv("DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def decision_brain_skip_ssot_lookup_enabled() -> bool:
    """When true (default), resolve may read paper_decisions + longitudinal memory.

    Unit tests set DECISION_BRAIN_SKIP_GATE_SSOT_LOOKUP=false via hermetic isolation.
    """
    raw = os.getenv("DECISION_BRAIN_SKIP_GATE_SSOT_LOOKUP", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def normalize_decision_brain_action(action: Any) -> str:
    """Map Decision Brain / PDE / V2 SKIP synonyms to canonical SKIP_PAPER / BUY_PAPER / HOLD_PAPER / …"""
    u = _s(action).upper().replace(" ", "_")
    if u in {"SKIP", "SKIP_PAPER"}:
        return "SKIP_PAPER"
    if u in {"BUY", "BUY_PAPER", "STRONG_BUY", "STRONGBUY"}:
        return "BUY_PAPER"
    if u in {"HOLD", "HOLD_PAPER"}:
        return "HOLD_PAPER"
    if u in {"SELL", "SELL_PAPER"}:
        return "SELL_PAPER"
    if u in {"PROTECT", "PROTECT_PAPER"}:
        return "PROTECT_PAPER"
    if u in {"REDUCE", "REDUCE_PAPER"}:
        return "REDUCE_PAPER"
    return u


def is_decision_brain_skip(action: Any) -> bool:
    return normalize_decision_brain_action(action) in DECISION_BRAIN_SKIP_ACTIONS


def _latest_paper_decision_for_ticker(
    ticker: str,
    *,
    exclude_decision_id: str | None = None,
    decisions_doc: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Latest PDE decision row for ticker from paper_decisions SSOT (read-only)."""
    doc = decisions_doc
    if doc is None:
        doc = load_json(DECISIONS_JSON) or {}
    rows = [r for r in (doc.get("decisions") or []) if isinstance(r, dict)]
    ticker_u = _s(ticker).upper()
    excl = _s(exclude_decision_id)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if _s(row.get("ticker")).upper() != ticker_u:
            continue
        if excl and _s(row.get("decision_id")) == excl:
            continue
        candidates.append(row)
    if not candidates:
        return None
    candidates.sort(key=lambda r: _s(r.get("timestamp") or r.get("generated_at")))
    return candidates[-1]


def _latest_longitudinal_action_for_ticker(ticker: str) -> tuple[str | None, dict[str, Any] | None]:
    """Latest longitudinal memory action for ticker (Decision Brain audit SSOT). Fail-open."""
    path = Path("runtime_outputs/longitudinal_memory/decisions.jsonl")
    if not path.is_file():
        return None, None
    ticker_u = _s(ticker).upper()
    latest: dict[str, Any] | None = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if _s(row.get("ticker")).upper() != ticker_u:
                continue
            if latest is None or _s(row.get("timestamp")) >= _s(latest.get("timestamp")):
                latest = row
    except OSError:
        return None, None
    if not latest:
        return None, None
    return normalize_decision_brain_action(latest.get("action")), latest


def resolve_decision_brain_verdict(
    *,
    ticker: str,
    decision: dict[str, Any] | None = None,
    execution_reason: str | None = None,
    decisions_doc: dict[str, Any] | None = None,
    explicit_verdict: str | None = None,
) -> dict[str, Any]:
    """
    Resolve canonical Decision Brain verdict for entry-gate consumption.

    Does not invent SKIP. Returns source provenance for attribution.
    Priority:
      1) explicit_verdict / decision.decision_brain_verdict / decision_brain_action
      2) action_changed:SKIP_PAPER->… in execution_reason
      3) decision.previous_action when SKIP
      4) latest other paper_decision action when SKIP
      5) latest longitudinal memory action when SKIP
      6) else None (ALLOW / no SKIP evidence)
    """
    dec = decision or {}
    ticker_u = _s(ticker or dec.get("ticker")).upper()
    sources_checked: list[str] = []

    for key, label in (
        (explicit_verdict, "explicit_verdict"),
        (dec.get("decision_brain_verdict"), "decision.decision_brain_verdict"),
        (dec.get("decision_brain_action"), "decision.decision_brain_action"),
        (dec.get("source_pde_action"), "decision.source_pde_action"),
    ):
        if key is None or _s(key) == "":
            continue
        sources_checked.append(label)
        norm = normalize_decision_brain_action(key)
        # Explicit Decision Brain stamp is authoritative — do not fall through to memory.
        if is_decision_brain_skip(norm):
            return {
                "verdict": "SKIP_PAPER",
                "raw": _s(key),
                "source": label,
                "sources_checked": sources_checked,
                "ticker": ticker_u,
            }
        return {
            "verdict": norm or None,
            "raw": _s(key),
            "source": label,
            "sources_checked": sources_checked,
            "ticker": ticker_u,
        }

    reason = _s(execution_reason or dec.get("execution_reason"))
    sources_checked.append("execution_reason")
    if reason.startswith("action_changed:"):
        # action_changed:SKIP_PAPER->BUY_PAPER
        try:
            body = reason.split(":", 1)[1]
            prior, _new = body.split("->", 1)
            if is_decision_brain_skip(prior):
                return {
                    "verdict": "SKIP_PAPER",
                    "raw": normalize_decision_brain_action(prior),
                    "source": "execution_reason.action_changed",
                    "sources_checked": sources_checked,
                    "ticker": ticker_u,
                    "execution_reason": reason,
                }
        except ValueError:
            pass

    prev = dec.get("previous_action")
    sources_checked.append("decision.previous_action")
    if prev is not None and _s(prev) and is_decision_brain_skip(prev):
        return {
            "verdict": "SKIP_PAPER",
            "raw": normalize_decision_brain_action(prev),
            "source": "decision.previous_action",
            "sources_checked": sources_checked,
            "ticker": ticker_u,
        }

    if not decision_brain_skip_ssot_lookup_enabled():
        sources_checked.append("ssot_lookup_disabled")
        return {
            "verdict": None,
            "raw": None,
            "source": "none",
            "sources_checked": sources_checked,
            "ticker": ticker_u,
            "diagnostic": "SSOT_LOOKUP_DISABLED",
        }

    sources_checked.append("paper_decisions.latest")
    latest_pde = _latest_paper_decision_for_ticker(
        ticker_u,
        exclude_decision_id=_s(dec.get("decision_id")) or None,
        decisions_doc=decisions_doc,
    )
    if latest_pde and is_decision_brain_skip(latest_pde.get("action")):
        return {
            "verdict": "SKIP_PAPER",
            "raw": normalize_decision_brain_action(latest_pde.get("action")),
            "source": "paper_decisions.latest",
            "sources_checked": sources_checked,
            "ticker": ticker_u,
            "source_decision_id": latest_pde.get("decision_id"),
            "source_timestamp": latest_pde.get("timestamp"),
        }

    sources_checked.append("longitudinal_memory.latest")
    mem_action, mem_row = _latest_longitudinal_action_for_ticker(ticker_u)
    if mem_action and is_decision_brain_skip(mem_action):
        return {
            "verdict": "SKIP_PAPER",
            "raw": mem_action,
            "source": "longitudinal_memory.latest",
            "sources_checked": sources_checked,
            "ticker": ticker_u,
            "source_decision_id": (mem_row or {}).get("decision_id"),
            "source_timestamp": (mem_row or {}).get("timestamp"),
        }

    return {
        "verdict": None,
        "raw": None,
        "source": "none",
        "sources_checked": sources_checked,
        "ticker": ticker_u,
    }


def evaluate_decision_brain_skip_new_entry_gate(
    *,
    action: str,
    is_new_position: bool,
    ticker: str,
    decision: dict[str, Any] | None = None,
    execution_reason: str | None = None,
    decisions_doc: dict[str, Any] | None = None,
    explicit_verdict: str | None = None,
    entry_kind: str = "BUY",
    strategy_id: str | None = None,
    enabled: bool | None = None,
    live_money: bool = False,
    broker_executed: bool = False,
) -> dict[str, Any]:
    """
    Binding PAPER gate: block NEW entry when canonical Decision Brain = SKIP.

    Applies to: V1 BUY_PAPER (new position) and V2 OPEN (entry_kind=OPEN).
    Does not apply to: ADD / SELL / HOLD / existing positions / LIVE / broker.
    """
    flag_on = decision_brain_skip_paper_gate_enabled() if enabled is None else bool(enabled)
    action_u = _s(action).upper()
    entry_u = _s(entry_kind).upper() or "BUY"
    dec = decision or {}
    strategy = _s(strategy_id or dec.get("strategy_id") or "V1").upper() or "V1"

    result: dict[str, Any] = {
        "enabled": flag_on,
        "applies": False,
        "blocked": False,
        "authorization": "ALLOW",
        "authorized_action": action_u,
        "original_action": action_u,
        "block_reason": None,
        "diagnostic": None,
        "is_new_position": bool(is_new_position),
        "entry_kind": entry_u,
        "strategy_id": strategy,
        "ticker": _s(ticker).upper(),
        "decision_brain_verdict": None,
        "decision_brain_source": None,
        "gate_name": "DECISION_BRAIN_SKIP_PAPER_GATE",
        "economic_class": None,
        "feature_flag": "DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED",
        "mode": MODE,
        "live_money": bool(live_money),
        "broker_executed": bool(broker_executed),
        "counterfactual_class": None,
    }

    if live_money or broker_executed or MODE not in {"PAPER_ONLY", "PAPER"}:
        result["diagnostic"] = "LIVE_OR_BROKER_NOT_IN_SCOPE"
        return result
    if not flag_on:
        result["diagnostic"] = "FEATURE_FLAG_OFF"
        return result
    if entry_u in {"ADD", "ADD_TRANCHE"}:
        result["diagnostic"] = "V2_ADD_NOT_IN_SCOPE"
        return result
    if action_u not in {"BUY", "BUY_PAPER", "OPEN", "OPEN_CYCLE"} and entry_u not in {"BUY", "OPEN", "OPEN_CYCLE"}:
        result["diagnostic"] = "ACTION_NOT_NEW_ENTRY"
        return result
    if not is_new_position and entry_u not in {"OPEN", "OPEN_CYCLE"}:
        result["diagnostic"] = "EXISTING_POSITION_NOT_IN_SCOPE"
        return result

    result["applies"] = True
    resolved = resolve_decision_brain_verdict(
        ticker=ticker,
        decision=dec,
        execution_reason=execution_reason,
        decisions_doc=decisions_doc,
        explicit_verdict=explicit_verdict,
    )
    result["decision_brain_verdict"] = resolved.get("verdict")
    result["decision_brain_source"] = resolved.get("source")
    result["decision_brain_resolution"] = resolved

    if resolved.get("verdict") == "SKIP_PAPER":
        result["blocked"] = True
        result["authorization"] = "BLOCKED"
        result["authorized_action"] = "SKIP_PAPER"
        result["block_reason"] = BLOCK_REASON_DECISION_BRAIN_SKIP
        result["diagnostic"] = BLOCK_REASON_DECISION_BRAIN_SKIP
        result["economic_class"] = ECONOMIC_CLASS_DECISION_BRAIN_SKIP
        result["counterfactual_class"] = "BINDING_SKIP_GATE_BLOCK"
        result["final_action"] = "BLOCKED_DECISION_BRAIN_SKIP"
        return result

    result["diagnostic"] = "NO_CANONICAL_SKIP_VERDICT"
    result["authorization"] = "ALLOW"
    return result


def append_decision_brain_skip_block_event(event: dict[str, Any]) -> None:
    """Canonical block journal + forward cohort seed (idempotent on decision_id)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    did = _s(event.get("decision_id"))
    if DECISION_BRAIN_SKIP_BLOCKS_JSONL.is_file() and did:
        for line in DECISION_BRAIN_SKIP_BLOCKS_JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _s(row.get("decision_id")) == did and _s(row.get("block_reason")) == BLOCK_REASON_DECISION_BRAIN_SKIP:
                return
    with DECISION_BRAIN_SKIP_BLOCKS_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")

    cohort = {
        "schema": "tae.binding_skip_gate_forward_cohort.v1",
        "cohort": "BINDING_SKIP_GATE_FORWARD_COHORT",
        "status": "PENDING",
        "verdict": "PENDING",
        "timestamp": event.get("timestamp") or _now(),
        "strategy_id": event.get("strategy_id"),
        "ticker": event.get("ticker"),
        "decision_id": event.get("decision_id"),
        "orchestration_run_id": event.get("orchestration_run_id"),
        "blocked_price": event.get("mark_price") or event.get("blocked_price"),
        "decision_brain_verdict": event.get("decision_brain_verdict"),
        "decision_brain_source": event.get("decision_brain_source"),
        "gate_name": event.get("gate_name") or "DECISION_BRAIN_SKIP_PAPER_GATE",
        "block_reason": BLOCK_REASON_DECISION_BRAIN_SKIP,
        "economic_class": ECONOMIC_CLASS_DECISION_BRAIN_SKIP,
        "score": event.get("score"),
        "confidence": event.get("confidence"),
        "ppg_verdict": event.get("ppg_verdict"),
        "forecast_7d": event.get("forecast_7d"),
        "regime": event.get("regime"),
        "learning_influence": event.get("learning_influence"),
        "return_1d": None,
        "return_2d": None,
        "return_5d": None,
        "return_7d": None,
        "mfe": None,
        "mae": None,
        "avoided_loss": None,
        "missed_profit": None,
        "simulated_original_outcome": None,
    }
    with BINDING_SKIP_FORWARD_COHORT_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(cohort, default=str) + "\n")


def build_decision_brain_skip_attribution(
    *,
    gate: dict[str, Any],
    decision: dict[str, Any],
    strategy_id: str,
    mark_price: float | None,
    capital_not_deployed: float = 0.0,
) -> dict[str, Any]:
    """Attribution payload for blocked PAPER entries (canonical journal fields)."""
    dec = decision or {}
    learning = (
        dec.get("rule_lifecycle_evidence")
        or dec.get("learning_influence")
        or dec.get("adaptive_weight_evidence")
        or {}
    )
    return {
        "timestamp": _now(),
        "strategy_id": _s(strategy_id or dec.get("strategy_id") or "V1").upper() or "V1",
        "ticker": _s(gate.get("ticker") or dec.get("ticker")).upper(),
        "decision_id": _s(dec.get("decision_id")),
        "orchestration_run_id": dec.get("orchestration_run_id"),
        "original_action": _s(dec.get("action") or gate.get("original_action")),
        "final_action": "BLOCKED_DECISION_BRAIN_SKIP",
        "decision_brain_verdict": gate.get("decision_brain_verdict"),
        "decision_brain_source": gate.get("decision_brain_source"),
        "gate_name": "DECISION_BRAIN_SKIP_PAPER_GATE",
        "block_reason": BLOCK_REASON_DECISION_BRAIN_SKIP,
        "economic_class": ECONOMIC_CLASS_DECISION_BRAIN_SKIP,
        "counterfactual_class": "BINDING_SKIP_GATE_BLOCK",
        "score": dec.get("score") or dec.get("source_score"),
        "confidence": dec.get("confidence"),
        "ppg_verdict": dec.get("ppg_posture")
        or dec.get("profit_protection_state")
        or ((dec.get("protection_validation_gates_passed") or {}) if isinstance(dec.get("protection_validation_gates_passed"), dict) else None),
        "forecast_7d": dec.get("short_term_trend_7d"),
        "regime": dec.get("horizon_context") or dec.get("regime"),
        "learning_influence": learning,
        "mark_price": mark_price,
        "blocked_price": mark_price,
        "capital_not_deployed": round(float(capital_not_deployed or 0.0), 4),
        "avoided_loss": 0.0,
        "missed_profit": 0.0,
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
        "feature_flag": "DECISION_BRAIN_SKIP_PAPER_GATE_ENABLED",
        "is_new_position": True,
    }


def morning_audit_opening_noise_summary() -> dict[str, Any]:
    summary = summarize_opening_noise_defers()
    return {
        "enabled": "YES" if summary.get("enabled") else "NO",
        "window": f"{summary.get('window_minutes')}m",
        "new_buys_deferred_today": summary.get("opening_noise_deferred_count"),
        "requalified": summary.get("opening_noise_requalified_after_window"),
        "executed_after_window": summary.get("opening_noise_later_executed"),
        "expired": summary.get("opening_noise_expired_without_buy"),
        "later_blocked_by_e3": summary.get("opening_noise_later_blocked_profit_decay"),
        "net_protection_value": summary.get("net_opening_protection_value"),
        "tickers": summary.get("opening_noise_deferred_tickers"),
    }


def evaluate_fill_time_hard_risk(
    ticker: str,
    *,
    avg_price: float,
    current_price: float,
    shares: float,
) -> dict[str, Any]:
    """Reuse canonical hard-risk evaluator at fill time (no new risk rules)."""
    from hard_risk_guardian import evaluate_position_risk

    return evaluate_position_risk(
        ticker,
        avg_price=avg_price,
        current_price=current_price,
        shares=shares,
    )


def fill_time_hard_risk_blocks_action(action: str, risk: dict[str, Any] | None) -> bool:
    """True when fill-time breach forbids executing a non-SELL approved action."""
    if not risk:
        return False
    if _s(risk.get("status")) not in HARD_RISK_BREACH_STATUSES:
        return False
    return _s(action).upper() != "SELL_PAPER"


def proactive_hard_risk_exit_scan_enabled() -> bool:
    """Feature flag — default true (PAPER). Rollback: PROACTIVE_HARD_RISK_EXIT_SCAN_ENABLED=false."""
    raw = os.getenv("PROACTIVE_HARD_RISK_EXIT_SCAN_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _position_mark_for_hard_risk(pos: dict[str, Any]) -> float:
    """Best available mark for proactive hard-risk scan (no look-ahead)."""
    for key in ("current_price", "last_valid_mark", "mark_price"):
        px = _f(pos.get(key))
        if px > 0:
            return px
    return 0.0


def execute_proactive_hard_risk_exits(
    portfolio: dict[str, Any],
    *,
    accounting: dict[str, Any] | None,
    processed: set[str],
    last_orders: dict[str, dict[str, Any]],
    roi001_challenger: bool = False,
    gii_by_ticker: dict[str, dict[str, Any]] | None = None,
    gii_meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Scan open PAPER positions and force SELL when hard-risk is breached between PDE cycles.

    Economic rationale (profitability recovery): historical losses crystallized at −5% to −6%
    because SELL fired only on the next PDE tick. Replaying closed trades with a −3% cap on
    each leg improves net P&L and profit factor without widening risk limits.
    Uses existing hard_risk_guardian thresholds; does not alter LIVE or broker paths.
    """
    if not proactive_hard_risk_exit_scan_enabled():
        return []

    orders: list[dict[str, Any]] = []
    positions = portfolio.get("positions") or {}
    if not isinstance(positions, dict):
        return orders

    day_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    for ticker, pos in list(positions.items()):
        if not isinstance(pos, dict):
            continue
        shares = _f(pos.get("shares"))
        avg = _f(pos.get("avg_price"))
        mark = _position_mark_for_hard_risk(pos)
        if shares <= 0 or avg <= 0 or mark <= 0:
            continue

        risk = evaluate_fill_time_hard_risk(
            _s(ticker).upper(),
            avg_price=avg,
            current_price=mark,
            shares=shares,
        )
        if _s(risk.get("status")) not in HARD_RISK_BREACH_STATUSES:
            continue

        decision_id = f"HR-PROACTIVE-{_s(ticker).upper()}-{day_stamp}"
        ok, reason = should_execute_decision(
            decision_id,
            "SELL_PAPER",
            processed=processed,
            last_orders=last_orders,
            cycle_ts=None,
            cycle_orders={},
        )
        if not ok:
            continue

        decision = {
            "decision_id": decision_id,
            "ticker": _s(ticker).upper(),
            "action": "SELL_PAPER",
            "confidence": 0.95,
            "timestamp": _now(),
            "execution_source": "PROACTIVE_HARD_RISK_SCAN",
            "hard_risk_discipline": {
                "override": True,
                "evaluated": True,
                "status": risk.get("status"),
                "hard_rule": risk.get("hard_rule"),
                "pnl_pct": risk.get("pnl_pct"),
                "required_action": risk.get("required_action"),
                "proactive_scan": True,
            },
            "evidence": [
                f"proactive hard-risk scan: {risk.get('hard_rule')} "
                f"pnl={_f(risk.get('pnl_pct')):.2f}% mark={mark} avg={avg}"
            ],
            "mode": MODE,
            "broker_executed": False,
            "live_money": False,
        }
        order = execute_decision(
            decision,
            portfolio,
            accounting=accounting,
            all_decisions=[decision],
            execution_reason="proactive_hard_risk_scan",
            roi001_challenger=roi001_challenger,
            gii_by_ticker=gii_by_ticker,
            gii_meta=gii_meta,
        )
        order["execution_source"] = "PROACTIVE_HARD_RISK_SCAN"
        order["proactive_hard_risk"] = risk
        orders.append(order)
        append_jsonl(ORDERS_JSONL, order)
        processed.add(decision_id)
        last_orders[decision_id] = order

    if orders:
        recalc_portfolio(portfolio)

    return orders


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def is_terminal_order_status(status: str, *, executed: bool | None = None, is_trade: bool | None = None) -> bool:
    st = _s(status).upper()
    if st in TERMINAL_ORDER_STATUSES:
        return True
    if st in NON_TERMINAL_ORDER_STATUSES:
        return False
    if executed is True or is_trade is True:
        return True
    return st not in NON_TERMINAL_ORDER_STATUSES and st != ""


def _load_signal_prices(signals_csv: Path | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    path = Path(signals_csv) if signals_csv is not None else SIGNALS_CSV
    if not path.is_file():
        return out
    try:
        import csv

        with path.open(encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                ticker = _s(row.get("Ticker")).upper()
                if not ticker:
                    continue
                px = _f(row.get("Price"))
                if px > 0:
                    out[ticker] = {"price": px, "timestamp": _s(row.get("Time")), "signal": _s(row.get("Signal"))}
    except OSError:
        return out
    return out


def _signal_age_seconds(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    text = timestamp.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
        except ValueError:
            continue
    return None


def _valid_resolved_price(value: Any) -> float | None:
    """Reject None / NaN / Inf / non-positive / non-numeric marks.

    Numeric strings are rejected — callers must supply a real float/int mark.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    px = float(value)
    if px != px or px in (float("inf"), float("-inf")) or px <= 0:
        return None
    return px


def resolve_mark_price(
    ticker: str,
    accounting: dict[str, Any] | None,
    decision: dict[str, Any],
    pos: dict[str, Any] | None = None,
    *,
    runtime_root: Path | str | None = None,
    injected_provider: Any | None = None,
    allow_host_fallback: bool = True,
    signals_csv: Path | str | None = None,
) -> dict[str, Any]:
    """Deterministic fill-price resolution — no synthetic fallback.

    Priority:
      1) injected_provider (explicit test/runtime injection)
      2) arm-local open position mark
      3) explicit signals_csv / runtime_root signals (never silent host leak)
      4) host live_signals / yfinance only when allow_host_fallback=True
      5) accounting / decision snapshot helpers
    """
    ticker_u = _s(ticker).upper()
    attempts: list[dict[str, Any]] = []
    root = Path(runtime_root) if runtime_root is not None else None

    if injected_provider is not None:
        try:
            provided = injected_provider(ticker_u)
        except TypeError:
            provided = injected_provider()
        if isinstance(provided, tuple):
            px_raw, source, status = (list(provided) + [None, None, "DATA_OK"])[:3]
            px = _valid_resolved_price(px_raw)
            if px is not None:
                attempts.append(
                    {
                        "source": source or "injected_provider",
                        "price": px,
                        "status": status or "DATA_OK",
                        "fresh": True,
                        "selected": True,
                    }
                )
                return {
                    "price": px,
                    "source": source or "injected_provider",
                    "timestamp": _now(),
                    "freshness": "FRESH",
                    "attempts": attempts,
                }
        else:
            px = _valid_resolved_price(provided)
            if px is not None:
                attempts.append(
                    {"source": "injected_provider", "price": px, "fresh": True, "selected": True}
                )
                return {
                    "price": px,
                    "source": "injected_provider",
                    "timestamp": _now(),
                    "freshness": "FRESH",
                    "attempts": attempts,
                }

    if pos and _f(pos.get("shares")) > 0:
        px = _valid_resolved_price(pos.get("current_price"))
        if px is not None:
            attempts.append({"source": "paper_position", "price": px, "fresh": True, "selected": True})
            return {
                "price": px,
                "source": _s(pos.get("mark_source")) or "paper_position",
                "timestamp": pos.get("mark_timestamp"),
                "freshness": "FRESH",
                "attempts": attempts,
            }

    explicit_signals: Path | None = None
    if signals_csv is not None:
        explicit_signals = Path(signals_csv)
    elif root is not None:
        for name in ("live_signals.csv", "signals.csv"):
            candidate = root / name
            if candidate.is_file():
                explicit_signals = candidate
                break

    # Host live_signals.csv is used only when explicitly allowed.
    if explicit_signals is not None or allow_host_fallback:
        signal_path = explicit_signals if explicit_signals is not None else (SIGNALS_CSV if allow_host_fallback else None)
        if signal_path is not None:
            signals = _load_signal_prices(signal_path)
            sig = signals.get(ticker_u) or {}
            sig_px = _valid_resolved_price(sig.get("price"))
            sig_age = _signal_age_seconds(sig.get("timestamp"))
            if sig_px is not None:
                fresh = sig_age is not None and sig_age <= SIGNAL_PRICE_MAX_AGE_SECONDS
                source_name = str(signal_path) if explicit_signals is not None else "live_signals.csv"
                attempts.append(
                    {
                        "source": source_name,
                        "price": sig_px,
                        "timestamp": sig.get("timestamp"),
                        "age_seconds": sig_age,
                        "fresh": fresh,
                        "selected": fresh,
                    }
                )
                if fresh:
                    return {
                        "price": sig_px,
                        "source": source_name,
                        "timestamp": sig.get("timestamp"),
                        "freshness": "FRESH",
                        "attempts": attempts,
                    }

    if pos:
        px = _valid_resolved_price(pos.get("current_price"))
        mark_source = _s(pos.get("mark_source"))
        mark_status = _s(pos.get("mark_status"))
        if px is not None and mark_status in {"LIVE", "DATA_OK", "FRESH"}:
            attempts.append({"source": "paper_position_mtm", "price": px, "fresh": True, "selected": True})
            return {
                "price": px,
                "source": mark_source or "paper_position_mtm",
                "timestamp": pos.get("mark_timestamp"),
                "freshness": "FRESH",
                "attempts": attempts,
            }
        if px is not None:
            attempts.append({"source": "paper_position_stale", "price": px, "fresh": False, "selected": False})

    if allow_host_fallback:
        live_px, live_source, live_status = _fetch_ticker_price(ticker_u)
        live_px_v = _valid_resolved_price(live_px)
        if live_px_v is not None:
            fresh = live_status in {"DATA_OK", "LIVE", "FRESH"}
            attempts.append(
                {
                    "source": live_source or "yfinance",
                    "price": live_px_v,
                    "status": live_status,
                    "fresh": fresh,
                    "selected": fresh,
                }
            )
            if fresh:
                return {
                    "price": live_px_v,
                    "source": live_source or "yfinance",
                    "timestamp": _now(),
                    "freshness": "FRESH",
                    "attempts": attempts,
                }

    for row in (accounting or {}).get("open_positions") or []:
        if _s(row.get("ticker")).upper() != ticker_u:
            continue
        px = _valid_resolved_price(row.get("current_price"))
        if px is not None:
            attempts.append({"source": "accounting_open_position", "price": px, "fresh": True, "selected": True})
            return {
                "price": px,
                "source": "accounting_open_position",
                "timestamp": (accounting or {}).get("generated_at"),
                "freshness": "FRESH",
                "attempts": attempts,
            }

    snap_px = _valid_resolved_price((decision.get("portfolio_snapshot") or {}).get("current_price"))
    if snap_px is not None:
        attempts.append({"source": "decision_portfolio_snapshot", "price": snap_px, "fresh": False, "selected": False})

    return {
        "price": 0.0,
        "source": "UNAVAILABLE",
        "timestamp": None,
        "freshness": "UNAVAILABLE",
        "attempts": attempts,
    }


def reconcile_processed_decision_ids(
    processed: set[str],
    last_orders: dict[str, dict[str, Any]],
) -> set[str]:
    """Drop decision_ids whose last order ended non-terminal — allow recovery."""
    cleaned = set(processed)
    for did in list(cleaned):
        last = last_orders.get(did) or {}
        status = _s(last.get("status")).upper()
        if status in NON_TERMINAL_ORDER_STATUSES:
            cleaned.discard(did)
    return cleaned


def _retry_cooldown_active(
    decision_id: str,
    *,
    last_orders: dict[str, dict[str, Any]],
    cycle_ts: datetime | None,
    cycle_orders: dict[str, dict[str, Any]],
) -> bool:
    if decision_id in cycle_orders:
        return True
    last = last_orders.get(decision_id) or {}
    last_ts = _parse_ts(last.get("timestamp"))
    if cycle_ts and last_ts and last_ts >= cycle_ts:
        status = _s(last.get("status")).upper()
        if status in {"SKIPPED_NO_MARK_PRICE", "SKIPPED_RETRY_COOLDOWN"}:
            return True
    return False


def audit_mark_price_failures(*, tickers: list[str] | None = None) -> dict[str, Any]:
    """Phase 1 audit — trace mark-price resolution for SKIPPED_NO_MARK_PRICE cases."""
    accounting = _load_live_accounting()
    decisions_doc = load_json(DECISIONS_JSON) or {}
    portfolio = load_json(PORTFOLIO_JSON) or {}
    orders = load_jsonl(ORDERS_JSONL)
    signals = _load_signal_prices()

    if tickers is None:
        tickers = sorted(
            {
                _s(o.get("ticker")).upper()
                for o in orders
                if _s(o.get("status")).upper() == "SKIPPED_NO_MARK_PRICE"
            }
        )
        if "HD" not in tickers:
            tickers = ["HD"] + tickers

    cases: list[dict[str, Any]] = []
    for ticker in tickers:
        ticker_u = _s(ticker).upper()
        pos = (portfolio.get("positions") or {}).get(ticker_u)
        decision = next(
            (d for d in (decisions_doc.get("decisions") or []) if _s(d.get("ticker")).upper() == ticker_u),
            {"ticker": ticker_u},
        )
        resolved = resolve_mark_price(ticker_u, accounting, decision, pos=pos)
        sig = signals.get(ticker_u) or {}
        acct_open = any(
            _s(r.get("ticker")).upper() == ticker_u for r in (accounting.get("open_positions") or [])
        )
        last_skips = [
            o
            for o in orders
            if _s(o.get("ticker")).upper() == ticker_u and _s(o.get("status")).upper() == "SKIPPED_NO_MARK_PRICE"
        ]
        cases.append(
            {
                "ticker": ticker_u,
                "ticker_normalized": ticker_u,
                "market_suffix": "none" if "." not in ticker_u else ticker_u.rsplit(".", 1)[-1],
                "session": "unknown",
                "price_sources_attempted": resolved.get("attempts") or [],
                "failure_reason": "no_fresh_mark_in_legacy_fill_path" if resolved["price"] <= 0 else "resolved_now",
                "live_signal_price": _f(sig.get("price")),
                "live_signal_timestamp": sig.get("timestamp"),
                "canonical_open_position": acct_open,
                "valid_mark_exists_elsewhere": resolved["price"] > 0,
                "symbol_mapping_issue": False,
                "temporary_unavailability": resolved["price"] <= 0 and _f(sig.get("price")) <= 0,
                "market_closed": False,
                "resolved_price": resolved["price"],
                "resolved_source": resolved["source"],
                "resolved_freshness": resolved["freshness"],
                "skip_order_count": len(last_skips),
                "last_skip_at": (last_skips[-1].get("timestamp") if last_skips else None),
            }
        )

    return {
        "schema": "tae_non_terminal_order_recovery_audit",
        "generated_at": _now(),
        "root_cause_summary": (
            "fill_price_for_position consulted only accounting/decision snapshot; "
            "live_signals.csv and market-data layer were not used for new-entry BUY fills."
        ),
        "cases": cases,
    }


def write_non_terminal_recovery_audit() -> dict[str, Any]:
    payload = audit_mark_price_failures()
    report_md = Path("TAE_NON_TERMINAL_ORDER_RECOVERY_AUDIT.md")
    report_json = Path("tae_non_terminal_order_recovery_audit.json")
    lines = [
        "# TAE Non-Terminal Order Recovery Audit",
        "",
        f"**Generated:** {payload['generated_at'][:19]}",
        "",
        "## Root cause",
        "",
        payload["root_cause_summary"],
        "",
        "## Mark-price failure cases",
        "",
    ]
    for case in payload["cases"]:
        lines.extend(
            [
                f"### {case['ticker']}",
                "",
                f"- Live signal price: **{case['live_signal_price']}** @ {case.get('live_signal_timestamp')}",
                f"- Resolved now: **{case['resolved_price']}** ({case['resolved_source']}, {case['resolved_freshness']})",
                f"- Canonical open position: **{case['canonical_open_position']}**",
                f"- Valid mark elsewhere: **{case['valid_mark_exists_elsewhere']}**",
                f"- Failure reason: {case['failure_reason']}",
                f"- Skip orders: {case['skip_order_count']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Terminal vs non-terminal",
            "",
            f"- **Terminal:** {', '.join(sorted(TERMINAL_ORDER_STATUSES))}",
            f"- **Non-terminal:** {', '.join(sorted(NON_TERMINAL_ORDER_STATUSES))}",
            "",
        ]
    )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


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
        if path.parent.resolve() == Path(".").resolve():
            allowed_root = {
                REPORT_MD.name,
                MTM_REPORT_MD.name,
                CANONICAL_VS_PAPER_MD.name,
                INTEGRITY_REPORT_MD.name,
                INTEGRITY_REPORT_JSON.name,
                VALIDATION_PROFIT_JSON.name,
            }
            if path.name in allowed_root:
                return
        raise RuntimeError(f"Unsafe output path outside {OUTPUT_DIR}: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomic replace — crash mid-write must not leave a truncated portfolio SSOT."""
    assert_safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    assert_safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _execution_lock_path() -> Path:
    """Resolve lock under current OUTPUT_DIR (honors test remounts)."""
    return OUTPUT_DIR / "paper_execution.lock"


def _acquire_execution_lock():
    """Exclusive process lock for paper execution mutations (exactly-once across processes)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _execution_lock_path()
    assert_safe_path(lock_path)
    handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _release_execution_lock(handle) -> None:
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


TRAILING_MERGE_FIELDS = (
    "position_cycle_id",
    "profit_trailing_active",
    "profit_trailing_activation_threshold_pct",
    "profit_trailing_drawdown_pct",
    "profit_trailing_activation_timestamp",
    "profit_trailing_activation_mark",
    "profit_trailing_peak_price",
    "profit_trailing_peak_timestamp",
    "profit_trailing_last_valid_mark",
    "profit_trailing_state_version",
    "profit_trailing_bootstrap_completed",
    "profit_trailing_pce_verdict",
    "profit_trailing_pce_wired",
)


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return "missing"
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_daily_equity_rows(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DAILY_EQUITY_JSONL
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _count_completed_cycles(trades: list[dict[str, Any]] | None = None) -> int:
    rows = trades if trades is not None else load_jsonl(TRADES_JSONL)
    cycles: set[str] = set()
    for trade in rows:
        if not (trade.get("is_trade") or trade.get("record_type") == "paper_trade"):
            continue
        action = _s(trade.get("action")).upper()
        if action not in {"SELL_PAPER", "ROTATE_PAPER"}:
            continue
        after = trade.get("after_position") or trade.get("position_after") or {}
        if _f(after.get("shares")) > 0:
            continue
        cid = _s(trade.get("position_cycle_id") or (trade.get("before_position") or {}).get("position_cycle_id"))
        if cid:
            cycles.add(cid)
        else:
            cycles.add(f"legacy:{trade.get('decision_id') or trade.get('timestamp')}")
    return len(cycles)


def build_paper_daily_equity_observation(
    portfolio: dict[str, Any],
    *,
    reconciliation: dict[str, Any] | None = None,
    timestamp_utc: str | None = None,
    equity_path: Path | None = None,
) -> dict[str, Any]:
    """Build one canonical PAPER equity observation from current MTM portfolio state.

    Uses only paper_portfolio / paper_orders / paper_trades — never LIVE portfolio.csv.
    """
    ts = timestamp_utc or _now()
    accounting_date = ts[:10]
    cash = round(_f(portfolio.get("cash")), 6)
    open_value = round(_f(portfolio.get("open_positions_value")), 6)
    total_equity = round(_f(portfolio.get("total_value")), 6)
    realized = round(_f(portfolio.get("realized_pnl")), 6)
    unrealized = round(_f(portfolio.get("unrealized_pnl")), 6)
    starting = round(
        _f(
            portfolio.get("validation_capital_base")
            or portfolio.get("starting_value")
            or portfolio.get("starting_capital")
            or 30000.0
        ),
        6,
    )
    peak = round(_f(portfolio.get("peak_value") or total_equity), 6)
    drawdown = round(max(0.0, peak - total_equity), 6)
    drawdown_pct = round((drawdown / peak) * 100.0, 6) if peak > 0 else 0.0
    open_positions = len(
        [p for p in (portfolio.get("positions") or {}).values() if _f((p or {}).get("shares")) > 0]
    )
    capital_deployed = open_value
    capital_utilization = round(open_value / total_equity, 6) if total_equity > 0 else 0.0
    portfolio_hash = _sha256_file(PORTFOLIO_JSON)
    trades_hash = _sha256_file(TRADES_JSONL)
    orders_hash = _sha256_file(ORDERS_JSONL)
    state_version = hashlib.sha256(
        f"{accounting_date}:{portfolio_hash}:{trades_hash}:{orders_hash}".encode()
    ).hexdigest()[:24]
    observation_id = f"PEQ-{accounting_date}-{state_version}"

    identity_delta = round(total_equity - (cash + open_value), 6)
    cumulative_net = round(realized + unrealized, 6)
    book_delta = round(total_equity - (starting + cumulative_net), 6)
    # Prefer portfolio validator when present; else identity/book checks.
    recon = reconciliation or validate_portfolio_reconciliation(portfolio)
    recon_delta = round(_f(recon.get("delta"), identity_delta), 6)
    if recon.get("ok") is True and abs(identity_delta) <= 0.01 and abs(book_delta) <= 0.50:
        recon_status = "RECONCILED"
        recon_delta = 0.0
    elif abs(identity_delta) <= 0.01:
        recon_status = _s(recon.get("status"), "IDENTITY_OK_BOOK_DELTA")
    else:
        recon_status = _s(recon.get("status"), "RECONCILIATION_DELTA")

    prior_rows = [
        r
        for r in _load_daily_equity_rows(equity_path)
        if r.get("record_type") != "CORRECTION" and r.get("accounting_date")
    ]
    prior_same_date = [r for r in prior_rows if r.get("accounting_date") == accounting_date]
    last_prior = prior_rows[-1] if prior_rows else None
    if last_prior and last_prior.get("accounting_date") != accounting_date:
        daily_pnl = round(total_equity - _f(last_prior.get("total_equity")), 6)
        prior_eq = _f(last_prior.get("total_equity"))
        daily_return = round(daily_pnl / prior_eq, 8) if prior_eq else 0.0
    elif prior_same_date:
        daily_pnl = round(total_equity - _f(prior_same_date[-1].get("total_equity")), 6)
        prior_eq = _f(prior_same_date[-1].get("total_equity"))
        daily_return = round(daily_pnl / prior_eq, 8) if prior_eq else 0.0
    else:
        daily_pnl = round(total_equity - starting, 6)
        daily_return = round(daily_pnl / starting, 8) if starting else 0.0

    return {
        "schema_version": DAILY_EQUITY_SCHEMA,
        "record_type": "DAILY_EQUITY",
        "observation_id": observation_id,
        "timestamp_utc": ts,
        "accounting_date": accounting_date,
        "source_portfolio_hash": portfolio_hash,
        "source_trades_hash": trades_hash,
        "source_orders_hash": orders_hash,
        "canonical_state_version": state_version,
        "data_mode": "PAPER",
        "source_system": "canonical_paper_mtm",
        "source_files": [str(PORTFOLIO_JSON), str(TRADES_JSONL), str(ORDERS_JSONL)],
        "account_basis": "PAPER_ISOLATED",
        "starting_capital": starting,
        "cash": cash,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "total_equity": total_equity,
        "gross_market_value": open_value,
        "capital_deployed": capital_deployed,
        "capital_utilization": capital_utilization,
        "open_positions": open_positions,
        "completed_cycles_to_date": _count_completed_cycles(),
        "daily_pnl": daily_pnl,
        "daily_return": daily_return,
        "equity_peak": peak,
        "drawdown": drawdown,
        "drawdown_pct": drawdown_pct,
        "fees": round(_f(portfolio.get("fees")), 6),
        "slippage": round(_f(portfolio.get("slippage")), 6),
        "fx_effect": round(_f(portfolio.get("fx_effect")), 6),
        "reconciliation_delta": recon_delta,
        "reconciliation_status": recon_status,
        "identity_check_delta": identity_delta,
        "book_check_delta": book_delta,
        "mode": MODE,
        "broker_executed": False,
        "live_money": False,
    }


def append_paper_daily_equity_observation(
    portfolio: dict[str, Any],
    *,
    reconciliation: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Append-only, idempotent PAPER daily equity observation (no portfolio mutation)."""
    target = path or DAILY_EQUITY_JSONL
    obs = build_paper_daily_equity_observation(
        portfolio, reconciliation=reconciliation, equity_path=target
    )
    existing = _load_daily_equity_rows(target)
    for row in existing:
        if row.get("observation_id") == obs["observation_id"]:
            return {"ok": True, "appended": False, "idempotent": True, "observation": obs}
    same_date = [
        r
        for r in existing
        if r.get("accounting_date") == obs["accounting_date"] and r.get("record_type") == "DAILY_EQUITY"
    ]
    if same_date and same_date[-1].get("canonical_state_version") != obs["canonical_state_version"]:
        correction = {
            "schema_version": DAILY_EQUITY_SCHEMA,
            "record_type": "CORRECTION",
            "observation_id": f"PEQ-CORR-{obs['observation_id']}",
            "timestamp_utc": _now(),
            "accounting_date": obs["accounting_date"],
            "replaces_observation_id": same_date[-1].get("observation_id"),
            "new_observation_id": obs["observation_id"],
            "reason": "canonical_paper_state_changed_same_accounting_date",
            "data_mode": "PAPER",
            "source_system": "canonical_paper_mtm",
            "mode": MODE,
        }
        append_jsonl(target, correction)
    append_jsonl(target, obs)
    return {"ok": True, "appended": True, "idempotent": False, "observation": obs}


def trailing_lifecycle_fields(
    decision: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    status: str,
    reason: str,
    executed: bool,
) -> dict[str, Any]:
    """Observability-only trailing lifecycle fields for order/trade journals (no policy change)."""
    from tae_paper_profit_trailing import (
        REASON_EXIT,
        REASON_SOFT_SUPPRESSED,
        is_trailing_exit_decision,
        trailing_active_on_position,
    )

    before_active = trailing_active_on_position(before)
    after_active = trailing_active_on_position(after)
    reason_code = _s(decision.get("reason_code"))
    soft_suppressed = REASON_SOFT_SUPPRESSED in reason or reason_code == REASON_SOFT_SUPPRESSED
    trailing_exit = bool(executed and is_trailing_exit_decision(decision) and status == "EXECUTED")
    peak_before = before.get("profit_trailing_peak_price")
    peak_after = after.get("profit_trailing_peak_price")
    peak_update = False
    if peak_before is not None and peak_after is not None:
        peak_update = _f(peak_after) > _f(peak_before) + 1e-12
    elif peak_after is not None and peak_before is None and after_active:
        peak_update = True
    dd = None
    mark = after.get("profit_trailing_last_valid_mark") or before.get("profit_trailing_last_valid_mark")
    peak_for_dd = peak_after if peak_after is not None else peak_before
    if mark is not None and peak_for_dd is not None and _f(peak_for_dd) > 0:
        dd = round((_f(peak_for_dd) - _f(mark)) / _f(peak_for_dd), 8)
    cycle_close = None
    if executed and _f(after.get("shares")) <= 0 and _f(before.get("shares")) > 0:
        if trailing_exit:
            cycle_close = REASON_EXIT
        elif "HARD RISK" in reason.upper() or "HARD_STOP" in reason.upper() or "CRITICAL_STOP" in reason.upper():
            cycle_close = "HARD_RISK_EXIT"
        else:
            cycle_close = _s(decision.get("reason_code")) or "CYCLE_CLOSED"
    return {
        "trailing_eligible": bool(before.get("position_cycle_id") or after.get("position_cycle_id")),
        "trailing_activation_timestamp": after.get("profit_trailing_activation_timestamp")
        or before.get("profit_trailing_activation_timestamp"),
        "trailing_activation_mark": after.get("profit_trailing_activation_mark")
        or before.get("profit_trailing_activation_mark"),
        "trailing_peak_before": peak_before,
        "trailing_peak_after": peak_after,
        "trailing_peak_update": peak_update,
        "trailing_drawdown_pct": dd,
        "soft_exit_suppressed": soft_suppressed,
        "soft_exit_suppressed_reason": REASON_SOFT_SUPPRESSED if soft_suppressed else None,
        "trailing_exit_authorized": is_trailing_exit_decision(decision),
        "trailing_exit_fill": trailing_exit,
        "trailing_realized_pnl": round(_f(decision.get("realized_pnl")), 6) if trailing_exit else None,
        "cycle_close_reason": cycle_close,
        "profit_trailing_active_before": before_active,
        "profit_trailing_active_after": after_active,
    }


def adaptive_control_vs_executed_fields(
    *,
    sizing: dict[str, Any] | None,
    fill_price: float,
    fill_shares: float,
    executed_notional: float,
) -> dict[str, Any]:
    """Read-only Adaptive attribution fields derived from existing sizing result (no shadow cash)."""
    sizing = sizing or {}
    control_notional = _f(sizing.get("control_notional"))
    exec_notional = _f(sizing.get("executed_notional"), executed_notional)
    px = _f(fill_price)
    base_qty = round(control_notional / px, 8) if px > 0 and control_notional > 0 else 0.0
    exec_qty = round(fill_shares, 8) if fill_shares > 0 else (
        round(exec_notional / px, 8) if px > 0 and exec_notional > 0 else 0.0
    )
    mult = None
    if control_notional > 0 and exec_notional > 0:
        mult = round(exec_notional / control_notional, 8)
    components = {
        "used_arm": sizing.get("used_arm"),
        "control_formula_id": sizing.get("control_formula_id"),
        "challenger_formula_id": sizing.get("challenger_formula_id"),
        "challenger_notional_raw": sizing.get("challenger_notional_raw"),
        "selection_note": sizing.get("selection_note"),
        "reason_code": sizing.get("reason_code"),
    }
    return {
        "base_quantity_before_adaptive": base_qty,
        "base_capital_before_adaptive": round(control_notional, 6),
        "adaptive_multiplier": mult,
        "adaptive_components": components,
        "executed_quantity": exec_qty,
        "executed_capital": round(exec_notional, 6),
        "neutral_quantity_shadow": base_qty,
        "neutral_capital_shadow": round(control_notional, 6),
        "control_notional": round(control_notional, 6),
        "executed_notional": round(exec_notional, 6),
    }


def compute_adaptive_exit_attribution(
    *,
    entry_order: dict[str, Any] | None,
    exit_trade: dict[str, Any],
) -> dict[str, Any]:
    """Analytical neutral-size PnL using the same canonical exit prices (no portfolio mutation)."""
    entry = entry_order or {}
    before = exit_trade.get("before_position") or exit_trade.get("position_before") or {}
    exit_px = _f(exit_trade.get("fill_price"))
    entry_px = _f(before.get("avg_price")) or _f(entry.get("fill_price"))
    exec_qty = _f(exit_trade.get("fill_shares") or before.get("shares"))
    neutral_qty = _f(entry.get("neutral_quantity_shadow") or entry.get("base_quantity_before_adaptive"))
    if neutral_qty <= 0 and _f(entry.get("control_notional")) > 0 and entry_px > 0:
        neutral_qty = round(_f(entry.get("control_notional")) / entry_px, 8)
    executed_pnl = round(_f(exit_trade.get("realized_pnl")), 6)
    if exec_qty > 0 and entry_px > 0 and exit_px > 0 and executed_pnl == 0:
        executed_pnl = round((exit_px - entry_px) * exec_qty, 6)
    neutral_pnl = None
    if neutral_qty > 0 and entry_px > 0 and exit_px > 0:
        neutral_pnl = round((exit_px - entry_px) * neutral_qty, 6)
    incremental = None if neutral_pnl is None else round(executed_pnl - neutral_pnl, 6)
    capital_diff = round(
        _f(entry.get("executed_capital") or entry.get("executed_notional"))
        - _f(entry.get("neutral_capital_shadow") or entry.get("control_notional") or entry.get("base_capital_before_adaptive")),
        6,
    )
    return {
        "executed_pnl": executed_pnl,
        "neutral_size_shadow_pnl": neutral_pnl,
        "incremental_adaptive_pnl": incremental,
        "executed_drawdown_contribution": min(0.0, executed_pnl),
        "neutral_drawdown_contribution": None if neutral_pnl is None else min(0.0, neutral_pnl),
        "capital_difference": capital_diff,
        "adaptive_attribution_mode": "ANALYTICAL_SAME_PRICES",
        "shadow_portfolio_mutated": False,
        "shadow_cash_mutated": False,
    }


def merge_and_persist_profit_trailing_state(
    ctx_positions: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Canonical portfolio mutation owner for profit-trailing field merges.

    PDE evaluates trailing transitions in-memory; this function is the sole
    writer that merges trailing fields into paper_portfolio.json under lock.
    Does not invent fills or change cash/shares except via sync_portfolio_profit_trailing
    state-field updates on existing open positions.
    """
    from tae_paper_profit_trailing import (
        load_pce_by_ticker,
        sync_portfolio_profit_trailing,
        wire_paper_profit_protection,
    )

    lock = _acquire_execution_lock()
    try:
        disk = load_json(PORTFOLIO_JSON) if PORTFOLIO_JSON.is_file() else {}
        if not isinstance(disk, dict):
            disk = {"schema": SCHEMA, "positions": {}, "cash": 0.0}
        disk_positions = disk.setdefault("positions", {})
        src_positions = ctx_positions if isinstance(ctx_positions, dict) else {}
        for ticker, src in src_positions.items():
            if not isinstance(src, dict):
                continue
            dst = disk_positions.get(ticker)
            if not isinstance(dst, dict):
                # Do not create positions from trailing-only context — requires shares already open.
                if _f(src.get("shares")) <= 0:
                    continue
                disk_positions[ticker] = dict(src)
                continue
            for key in TRAILING_MERGE_FIELDS:
                if key in src:
                    dst[key] = src[key]
        gii_by_ticker, _gii_meta = load_gii_lifecycle_index()
        wire_paper_profit_protection(
            disk,
            pce_by=load_pce_by_ticker(),
            gii_by=gii_by_ticker,
        )
        sync_portfolio_profit_trailing(disk)
        save_json(PORTFOLIO_JSON, disk)
        return disk
    finally:
        _release_execution_lock(lock)


RECONCILE_EPS = 0.02
EXPECTED_VALIDATION_CAPITAL_BASE = 30000.0
SYNTHETIC_FILL_ANCHOR = 100.0


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
    snap = {
        "shares": _f(pos.get("shares")),
        "avg_price": _f(pos.get("avg_price")),
        "current_price": _f(pos.get("current_price")),
        "current_value": _f(pos.get("current_value")),
        "pnl": _f(pos.get("pnl")),
        "protect_mode": pos.get("protect_mode"),
        "status": pos.get("status", "CLOSED"),
        "position_cycle_id": pos.get("position_cycle_id"),
        "profit_trailing_active": bool(pos.get("profit_trailing_active")),
        "profit_trailing_peak_price": pos.get("profit_trailing_peak_price"),
        "profit_trailing_activation_mark": pos.get("profit_trailing_activation_mark"),
        "profit_trailing_bootstrap_completed": bool(pos.get("profit_trailing_bootstrap_completed")),
    }
    return snap


def price_for_ticker(ticker: str, accounting: dict[str, Any] | None, decision: dict[str, Any]) -> float:
    resolved = resolve_mark_price(ticker, accounting, decision)
    return _f(resolved.get("price"))


def fill_price_for_position(
    pos: dict[str, Any] | None,
    ticker: str,
    accounting: dict[str, Any] | None,
    decision: dict[str, Any],
) -> float:
    """MTM/current price for fills — never use avg_price or synthetic defaults as fill."""
    resolved = resolve_mark_price(ticker, accounting, decision, pos=pos)
    px = _f(resolved.get("price"))
    if px > 0 and pos:
        avg = _f(pos.get("avg_price"))
        if avg > 0 and abs(px - avg) < 0.0001:
            px = 0.0
    return px if px > 0 else 0.0


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
    acct = accounting or _load_live_accounting()
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


def _resolved_mark_price(
    ticker: str,
    *,
    pos: dict[str, Any] | None,
    accounting: dict[str, Any] | None,
    decision: dict[str, Any] | None,
) -> float:
    if pos:
        px = _f(pos.get("current_price"))
        if px > 0:
            return px
    return price_for_ticker(ticker, accounting, decision or {})


def _has_proven_mark_source(
    ticker: str,
    pos: dict[str, Any] | None,
    accounting: dict[str, Any] | None,
) -> bool:
    if pos and _s(pos.get("mark_source")) not in {"", "UNAVAILABLE"}:
        return True
    for row in (accounting or {}).get("open_positions") or []:
        if _s(row.get("ticker")).upper() == ticker.upper() and _f(row.get("current_price")) > 0:
            return True
    return False


def is_suspicious_synthetic_fill_price(
    fill_price: float,
    ticker: str,
    *,
    pos: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    accounting: dict[str, Any] | None = None,
) -> bool:
    """Reject $100 fills unless accounting/mark source proves a real ~$100 instrument."""
    if abs(fill_price - SYNTHETIC_FILL_ANCHOR) >= 0.01:
        return False
    if pos:
        current = _f(pos.get("current_price"))
        avg = _f(pos.get("avg_price"))
        if current > 0 and abs(current - fill_price) < 0.01:
            return False
        if abs(avg - SYNTHETIC_FILL_ANCHOR) < 0.01 and current > SYNTHETIC_FILL_ANCHOR + 50.0:
            return True
    if not _has_proven_mark_source(ticker, pos, accounting):
        return True
    market_px = _resolved_mark_price(ticker, pos=pos, accounting=accounting, decision=decision)
    if market_px > 0 and abs(market_px - SYNTHETIC_FILL_ANCHOR) <= 15.0:
        return False
    return True


def is_suspicious_avg_price_position(ticker: str, pos: dict[str, Any]) -> bool:
    avg = _f(pos.get("avg_price"))
    current = _f(pos.get("current_price"))
    if abs(avg - SYNTHETIC_FILL_ANCHOR) >= 0.01:
        return False
    if current <= SYNTHETIC_FILL_ANCHOR + 15.0:
        return False
    return True


def trades_have_synthetic_fill_contamination(trades: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    rows = trades if trades is not None else load_jsonl(TRADES_JSONL)
    for trade in rows:
        action = _s(trade.get("action")).upper()
        if action not in {"BUY_PAPER", "SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER"}:
            continue
        fill_price = _f(trade.get("fill_price") or trade.get("price"))
        ticker = _s(trade.get("ticker")).upper()
        before = trade.get("before_position") or trade.get("position_before") or {}
        if action == "BUY_PAPER" and is_suspicious_synthetic_fill_price(
            fill_price,
            ticker,
            pos=trade.get("after_position") or trade.get("position_after"),
            decision={"portfolio_snapshot": before},
            accounting=None,
        ):
            findings.append(
                {
                    "code": "SYNTHETIC_FILL_TRADE",
                    "ticker": ticker,
                    "decision_id": trade.get("decision_id"),
                    "action": action,
                    "fill_price": fill_price,
                    "timestamp": trade.get("timestamp"),
                }
            )
    return findings


def collect_fake_profit_contamination(
    portfolio: dict[str, Any] | None = None,
    accounting: dict[str, Any] | None = None,
    *,
    trades: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    paper = portfolio or load_json(PORTFOLIO_JSON) or {}
    acct = accounting if accounting is not None else _load_live_accounting()

    for ticker, pos in (paper.get("positions") or {}).items():
        if is_suspicious_avg_price_position(ticker, pos):
            findings.append(
                {
                    "code": "SUSPICIOUS_AVG_PRICE",
                    "ticker": ticker,
                    "avg_price": _f(pos.get("avg_price")),
                    "current_price": _f(pos.get("current_price")),
                    "unrealized_pnl": _f(pos.get("pnl")),
                }
            )

    findings.extend(trades_have_synthetic_fill_contamination(trades))

    canon = _canonical_account_value(acct)
    paper_val = _f(paper.get("total_value"))
    if canon > 0 and paper_val - canon > 1000:
        findings.append(
            {
                "code": "PAPER_CANONICAL_VALUE_GAP",
                "paper_account_value": paper_val,
                "canonical_account_value": canon,
                "delta": round(paper_val - canon, 4),
            }
        )

    for order in orders or load_jsonl(ORDERS_JSONL):
        if _s(order.get("status")) == "BLOCKED_FAKE_PROFIT_RISK":
            findings.append(
                {
                    "code": "BLOCKED_ORDER",
                    "ticker": order.get("ticker"),
                    "decision_id": order.get("decision_id"),
                    "action": order.get("action"),
                    "reason": order.get("reason"),
                }
            )
    return findings


def check_paper_profit_integrity(
    *,
    portfolio: dict[str, Any] | None = None,
    accounting: dict[str, Any] | None = None,
    trades: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
    write_report_flag: bool = True,
    update_validation_json: bool = True,
) -> dict[str, Any]:
    """Preflight guard — profit validation is invalid until this passes."""
    paper = portfolio or load_json(PORTFOLIO_JSON) or {}
    acct = accounting if accounting is not None else _load_live_accounting()
    reconciliation = validate_portfolio_reconciliation(paper)

    capital_base = _f(paper.get("validation_capital_base"))
    if capital_base <= 0:
        capital_base = _validation_capital_base(acct)
    account_value = _f(paper.get("total_value"))
    profit_vs_capital_base = round(account_value - EXPECTED_VALIDATION_CAPITAL_BASE, 4)
    contaminated = collect_fake_profit_contamination(paper, acct, trades=trades, orders=orders)

    checks: list[dict[str, Any]] = [
        {
            "name": "no_synthetic_fill_fallback",
            "pass": True,
            "detail": "price_for_ticker/fill_price_for_position return 0.0 without mark",
        },
        {
            "name": "validation_capital_base_exact",
            "pass": abs(capital_base - EXPECTED_VALIDATION_CAPITAL_BASE) <= RECONCILE_EPS,
            "expected": EXPECTED_VALIDATION_CAPITAL_BASE,
            "actual": capital_base,
        },
        {
            "name": "account_value_formula",
            "pass": reconciliation.get("ok", False),
            "detail": "cash + open_positions_value",
        },
        {
            "name": "profit_vs_capital_base_formula",
            "pass": True,
            "expected": profit_vs_capital_base,
            "actual": profit_vs_capital_base,
            "formula": "account_value - validation_capital_base",
        },
        {
            "name": "no_synthetic_contamination",
            "pass": not contaminated,
            "findings_count": len(contaminated),
        },
        {
            "name": "portfolio_reconciliation",
            "pass": reconciliation.get("ok", False),
        },
    ]

    ok = all(item["pass"] for item in checks)
    if not ok and any(f.get("code") in {"SYNTHETIC_FILL_TRADE", "SUSPICIOUS_AVG_PRICE", "PAPER_CANONICAL_VALUE_GAP"} for f in contaminated):
        verdict = "BLOCKED_FAKE_PROFIT_RISK"
    elif not ok and not checks[1]["pass"]:
        verdict = "BLOCKED_BY_UNRESOLVED_CAPITAL_DEFECT"
    elif ok:
        verdict = "PAPER_PROFIT_INTEGRITY_CLOSED"
    else:
        verdict = "BLOCKED_FAKE_PROFIT_RISK"

    payload = {
        "schema": "tae_paper_profit_integrity_guard",
        "version": "v1",
        "generated_at": _now(),
        "ok": ok,
        "status": verdict,
        "verdict": verdict,
        "validation_safe_to_resume": ok,
        "checks": checks,
        "contaminated": contaminated,
        "metrics": {
            "validation_capital_base": capital_base,
            "account_value": account_value,
            "cash": _f(paper.get("cash")),
            "open_positions": len(paper.get("positions") or {}),
            "realized_pnl": _f(paper.get("realized_pnl")),
            "unrealized_pnl": _f(paper.get("unrealized_pnl")),
            "total_pnl_internal": _f(paper.get("total_pnl")),
            "profit_vs_capital_base": profit_vs_capital_base,
            "canonical_account_value": _canonical_account_value(acct),
        },
        "reconciliation": reconciliation,
    }

    if write_report_flag:
        write_profit_integrity_guard_report(payload)
    if update_validation_json:
        update_validation_profit_integrity_status(payload)
    return payload


def write_profit_integrity_guard_report(integrity: dict[str, Any]) -> None:
    save_json(INTEGRITY_REPORT_JSON, integrity)
    metrics = integrity.get("metrics") or {}
    lines = [
        "# TAE PAPER Profit Integrity Guard Report",
        "",
        f"**Generated:** {integrity.get('generated_at')}",
        f"**Verdict:** **{integrity.get('verdict')}**",
        f"**Validation safe to resume:** **{integrity.get('validation_safe_to_resume')}**",
        "",
        "## Metrics",
        "",
        f"- Validation capital base: **${metrics.get('validation_capital_base', 0):,.2f}**",
        f"- Account value: **${metrics.get('account_value', 0):,.2f}**",
        f"- Profit vs $30k base: **${metrics.get('profit_vs_capital_base', 0):,.2f}**",
        f"- Realized PnL: **${metrics.get('realized_pnl', 0):,.2f}**",
        f"- Unrealized PnL: **${metrics.get('unrealized_pnl', 0):,.2f}**",
        "",
        "## Checks",
        "",
        "| check | pass | detail |",
        "| --- | --- | --- |",
    ]
    for check in integrity.get("checks") or []:
        lines.append(
            f"| {check.get('name')} | {check.get('pass')} | "
            f"{check.get('detail') or check.get('formula') or check.get('findings_count', '')} |"
        )
    contaminated = integrity.get("contaminated") or []
    lines.extend(["", "## Contamination", ""])
    if contaminated:
        for item in contaminated:
            lines.append(f"- `{item.get('code')}` {item.get('ticker') or ''} {json.dumps(item, ensure_ascii=False)}")
    else:
        lines.append("- none detected")
    INTEGRITY_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_validation_profit_integrity_status(integrity: dict[str, Any]) -> None:
    if not VALIDATION_PROFIT_JSON.is_file():
        return
    try:
        doc = json.loads(VALIDATION_PROFIT_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    doc["profit_integrity"] = {
        "status": integrity.get("status"),
        "ok": integrity.get("ok"),
        "validation_safe_to_resume": integrity.get("validation_safe_to_resume"),
        "updated_at": integrity.get("generated_at"),
        "metrics": integrity.get("metrics"),
        "contaminated_count": len(integrity.get("contaminated") or []),
    }
    if not integrity.get("ok"):
        doc["validation_blocked"] = True
        doc["validation_block_reason"] = integrity.get("verdict")
    else:
        doc.pop("validation_blocked", None)
        doc.pop("validation_block_reason", None)
    VALIDATION_PROFIT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def extract_rule_sources(decision: dict[str, Any]) -> list[str]:
    rules: list[str] = []
    for hyp in decision.get("hypothesis_rules_applied") or []:
        rid = _s(hyp.get("hypothesis_id"))
        if rid:
            rules.append(rid)
    exp_id = _s(decision.get("experiment_id"))
    if exp_id and exp_id not in rules:
        rules.append(exp_id)
    for row in (decision.get("experiment_capital_evidence") or {}).get("authorized_challengers") or []:
        rid = _s(row.get("experiment_id"))
        if rid and rid not in rules:
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


def baseline_reduce_trim_pct(confidence: float) -> float:
    """Hardcoded REDUCE sizing (ROI-001 baseline)."""
    return 30.0 if _f(confidence, 0.5) < 0.7 else 20.0


def resolve_reduce_trim_pct(
    confidence: float,
    ticker: str,
    *,
    challenger: bool = False,
    pta_row: dict[str, Any] | None = None,
) -> tuple[float, str]:
    """
    ROI-001 sizing: baseline hardcoded vs challenger PTA suggested_partial_size_pct.

    Production default is baseline (challenger=False). No other behaviour changes.
    """
    baseline = baseline_reduce_trim_pct(confidence)
    if not challenger:
        return baseline, "baseline_hardcoded"
    suggested = None if not isinstance(pta_row, dict) else pta_row.get("suggested_partial_size_pct")
    if suggested is None:
        return baseline, "challenger_fallback_no_pta"
    try:
        pct = float(suggested)
    except (TypeError, ValueError):
        return baseline, "challenger_fallback_invalid_pta"
    if pct <= 0.0 or pct > 100.0:
        return baseline, "challenger_fallback_invalid_pta"
    return pct, "challenger_pta_suggested"


def load_pta_by_ticker() -> dict[str, dict[str, Any]]:
    """Read-only index of existing Profit Target Adapter rows (ROI-001 challenger)."""
    path = Path("tae_profit_target_adapter.json")
    doc = load_json(path) or {}
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("tickers") or []:
        if not isinstance(row, dict):
            continue
        tk = _s(row.get("ticker")).upper()
        if tk:
            out[tk] = row
    return out


def _sell_shares(
    portfolio: dict[str, Any],
    ticker: str,
    shares_to_sell: float,
    fill_price: float,
    *,
    apply_paper_tx_costs: bool = False,
    paper_tx_cost_cfg: dict[str, Any] | None = None,
) -> tuple[float, float, dict[str, Any] | None]:
    """Returns (realized_pnl_net, gross_proceeds, after_position_or_none).

    When ``apply_paper_tx_costs`` is True (explicit PAPER activation only):
    cash credit = gross_proceeds - transaction_cost; realized is net of sell costs.
    BUY costs already in avg_price are not deducted again.
    """
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if not pos:
        portfolio["_last_paper_fill_economics"] = None
        return 0.0, 0.0, None
    shares_before = _f(pos.get("shares"))
    avg_price = _f(pos.get("avg_price"))
    shares_to_sell = min(shares_to_sell, shares_before)
    if shares_to_sell <= 0:
        portfolio["_last_paper_fill_economics"] = None
        return 0.0, 0.0, pos
    cost_basis = round(avg_price * shares_to_sell, 4) if avg_price > 0 else 0.0
    gross_proceeds = round(shares_to_sell * fill_price, 4)
    economics: dict[str, Any]
    if apply_paper_tx_costs:
        from tae_paper_transaction_costs import sell_cash_credit

        economics = sell_cash_credit(gross_proceeds, cfg=paper_tx_cost_cfg)
        net_proceeds = round(_f(economics.get("net_proceeds")), 4)
        tx_cost = round(_f(economics.get("total_transaction_cost")), 4)
    else:
        net_proceeds = gross_proceeds
        tx_cost = 0.0
        economics = {
            "cost_model_version": None,
            "gross_notional": gross_proceeds,
            "gross_proceeds": gross_proceeds,
            "slippage_cost": 0.0,
            "spread_cost": 0.0,
            "commission_cost": 0.0,
            "total_transaction_cost": 0.0,
            "net_proceeds": net_proceeds,
            "net_cash_movement": net_proceeds,
            "cash_credit": net_proceeds,
            "cost_configuration": None,
            "enabled": False,
        }
    realized_gross = round(gross_proceeds - cost_basis, 4) if avg_price > 0 else 0.0
    realized = round(net_proceeds - cost_basis, 4) if avg_price > 0 else 0.0
    shares_after = round(shares_before - shares_to_sell, 6)
    portfolio["cash"] = round(_f(portfolio.get("cash")) + net_proceeds, 4)
    portfolio["realized_pnl"] = round(_f(portfolio.get("realized_pnl")) + realized, 4)
    economics = dict(economics)
    economics["side"] = "SELL"
    economics["gross_proceeds"] = gross_proceeds
    economics["cost_basis"] = cost_basis
    economics["realized_pnl_gross"] = realized_gross
    economics["realized_pnl_net"] = realized
    economics["total_transaction_cost"] = tx_cost
    portfolio["_last_paper_fill_economics"] = economics
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
    *,
    apply_paper_tx_costs: bool = False,
    paper_tx_cost_cfg: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Buy fill. With ``apply_paper_tx_costs``, cash debit = notional + cost and
    cost basis includes the BUY cost (single accounting rule). Requested notional
    is not silently shrunk when costs push debit over cash — fill is blocked.
    """
    if price <= 0 or notional <= 0:
        portfolio["_last_paper_fill_economics"] = None
        return 0.0, portfolio.get("positions", {}).get(ticker) or {}
    cash = _f(portfolio.get("cash"))
    economics: dict[str, Any]
    if apply_paper_tx_costs:
        from tae_paper_transaction_costs import buy_cash_debit

        economics = buy_cash_debit(notional, cfg=paper_tx_cost_cfg)
        debit = round(_f(economics.get("cash_debit")), 4)
        tx_cost = round(_f(economics.get("total_transaction_cost")), 4)
        if debit > cash + 1e-9:
            economics = dict(economics)
            economics["blocked"] = "INSUFFICIENT_CASH_FOR_COST"
            economics["side"] = "BUY"
            portfolio["_last_paper_fill_economics"] = economics
            return 0.0, portfolio.get("positions", {}).get(ticker) or {}
    else:
        notional = min(notional, cash)
        if notional <= 0:
            portfolio["_last_paper_fill_economics"] = None
            return 0.0, portfolio.get("positions", {}).get(ticker) or {}
        tx_cost = 0.0
        debit = notional
        economics = {
            "cost_model_version": None,
            "gross_notional": notional,
            "slippage_cost": 0.0,
            "spread_cost": 0.0,
            "commission_cost": 0.0,
            "total_transaction_cost": 0.0,
            "cash_debit": debit,
            "net_cash_movement": -debit,
            "cost_configuration": None,
            "enabled": False,
        }
    shares = round(notional / price, 6)
    if shares <= 0:
        portfolio["_last_paper_fill_economics"] = None
        return 0.0, portfolio.get("positions", {}).get(ticker) or {}
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
    # All-in cost basis: BUY transaction cost included once in invested capital.
    invested = round(notional + tx_cost, 6)
    if new_shares > 0:
        pos["avg_price"] = round(
            ((prev_shares * prev_avg) + invested) / new_shares,
            6,
        )
    pos["shares"] = round(new_shares, 6)
    pos["current_price"] = round(price, 6)
    pos["status"] = "OPEN"
    # 0 → positive: mint a new position cycle; scale-in keeps the same cycle.
    if prev_shares <= 0 and new_shares > 0:
        from tae_paper_profit_trailing import clear_profit_trailing_fields, mint_position_cycle_id

        clear_profit_trailing_fields(pos)
        pos.pop("position_cycle_id", None)
        pos["position_cycle_id"] = mint_position_cycle_id(ticker)
        # New opens are prospective — no historical bootstrap; first +5% uses ACTIVATED.
        pos["profit_trailing_active"] = False
        pos["profit_trailing_bootstrap_completed"] = True
    positions[ticker] = pos
    portfolio["cash"] = round(cash - debit, 4)
    economics = dict(economics)
    economics["side"] = "BUY"
    economics["gross_notional"] = round(notional, 6)
    economics["fill_price"] = round(price, 6)
    economics["shares"] = shares
    portfolio["_last_paper_fill_economics"] = economics
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
    roi001_challenger: bool = False,
    pta_by: dict[str, dict[str, Any]] | None = None,
    gii_by_ticker: dict[str, dict[str, Any]] | None = None,
    gii_meta: dict[str, Any] | None = None,
    strategy_v2_enabled_override: bool | None = None,
    strategy_v2_cycle_path: Path | None = None,
    strategy_v2_journal_path: Path | None = None,
    strategy_v2_persist: bool = True,
    apply_paper_tx_costs: bool = False,
    paper_tx_cost_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Strategy V2: only when decision is explicitly marked. Flag default false → block, no capital move.
    # V1 path below is unchanged for unmarked decisions.
    # Paper tx costs: explicit activation only (parallel PAPER paths); default off preserves legacy.
    try:
        from tae_strategy_v2_foundation import (
            decision_has_strategy_v2,
            execute_strategy_v2_decision,
        )

        if decision_has_strategy_v2(decision):
            return execute_strategy_v2_decision(
                decision,
                portfolio,
                accounting=accounting,
                enabled_override=strategy_v2_enabled_override,
                cycle_path=strategy_v2_cycle_path,
                journal_path=strategy_v2_journal_path,
                persist=strategy_v2_persist,
                apply_paper_tx_costs=apply_paper_tx_costs,
                paper_tx_cost_cfg=paper_tx_cost_cfg,
            )
    except ImportError:
        pass

    action = _s(decision.get("action")).upper()
    ticker = _s(decision.get("ticker")).upper()
    decision_id = _s(decision.get("decision_id"))
    confidence = _f(decision.get("confidence"), 0.5)
    risk_score = _f(decision.get("risk_score"))
    expected_delta = _f(decision.get("expected_profit_delta"))
    rule_sources = extract_rule_sources(decision)

    positions = portfolio.setdefault("positions", {})
    pos_ref = positions.get(ticker)
    mark = resolve_mark_price(ticker, accounting, decision, pos=pos_ref)
    fill_price = _f(mark.get("price"))
    price = fill_price
    if fill_price <= 0 and _has_open_position(_position_snapshot(pos_ref)):
        fallback = _f((_position_snapshot(pos_ref)).get("current_price"))
        if fallback > 0:
            fill_price = fallback
            price = fallback
            mark = {
                "price": fallback,
                "source": "position_fallback",
                "timestamp": pos_ref.get("mark_timestamp") if pos_ref else None,
                "freshness": "FRESH",
                "attempts": [],
            }

    cash_before = round(_f(portfolio.get("cash")), 4)
    before = _position_snapshot(positions.get(ticker))
    is_new_position = not _has_open_position(before)
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
    fill_time_hard_risk: dict[str, Any] | None = None
    e3_gate: dict[str, Any] | None = None
    opening_gate: dict[str, Any] | None = None
    db_skip_gate: dict[str, Any] | None = None
    original_action = action
    authorized_action = action

    # Sprint 1: revalidate hard risk immediately before any capital mutation.
    if _has_open_position(before):
        eval_price = fill_price if fill_price > 0 else _f(before.get("current_price"))
        if eval_price > 0:
            fill_time_hard_risk = evaluate_fill_time_hard_risk(
                ticker,
                avg_price=_f(before.get("avg_price")),
                current_price=eval_price,
                shares=_f(before.get("shares")),
            )

    requires_position = action in {"SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER"}
    if fill_time_hard_risk_blocks_action(action, fill_time_hard_risk):
        status = "BLOCKED_HARD_RISK_AT_FILL"
        reason = (
            f"fill-time hard risk {fill_time_hard_risk.get('hard_rule')}: "
            f"{_f(fill_time_hard_risk.get('pnl_pct')):.2f}% — blocked {action} "
            f"(required={_s(fill_time_hard_risk.get('required_action'))}; "
            f"approved_action unchanged)"
        )
        executed = False
        is_trade = False
        after = before
    elif requires_position and not _has_open_position(before):
        status = "SKIPPED_NO_POSITION"
        reason = f"{action} skipped — no open paper position for {ticker}"
    elif action == "SKIP_PAPER":
        status = "NO_CHANGE"
    elif action == "HOLD_PAPER":
        status = "NO_CHANGE"
    elif action == "SELL_PAPER":
        if fill_price <= 0:
            from tae_paper_profit_trailing import STATUS_SKIP_NO_MARK, is_trailing_exit_decision

            if is_trailing_exit_decision(decision):
                status = STATUS_SKIP_NO_MARK
                reason = f"PROFIT_TRAILING exit skipped — no valid fill mark for {ticker}"
            else:
                status = "SKIPPED_NO_MARK_PRICE"
                reason = f"SELL_PAPER skipped — no mark price for {ticker}"
        elif is_suspicious_synthetic_fill_price(
            fill_price, ticker, pos=pos_ref, decision=decision, accounting=accounting
        ):
            status = "BLOCKED_FAKE_PROFIT_RISK"
            reason = f"SELL_PAPER blocked — suspicious ${SYNTHETIC_FILL_ANCHOR:.0f} fill for {ticker}"
        else:
            from tae_paper_profit_trailing import (
                REASON_EXIT,
                is_trailing_exit_decision,
                revalidate_trailing_exit_at_fill,
            )

            sell_shares = _f(before.get("shares"))
            avg = _f(before.get("avg_price"))
            if is_trailing_exit_decision(decision):
                reval = revalidate_trailing_exit_at_fill(
                    fill_mark=fill_price,
                    peak_price=_f(before.get("profit_trailing_peak_price")),
                    trailing_active=bool(before.get("profit_trailing_active")),
                    shares=sell_shares,
                    position_cycle_id=_s(before.get("position_cycle_id")),
                    decision_cycle_id=_s(decision.get("position_cycle_id")),
                )
                if not reval.get("ok"):
                    status = _s(reval.get("status"), "SKIPPED_TRAILING_EXIT_NO_LONGER_VALID")
                    reason = (
                        f"PROFIT_TRAILING revalidation failed: {reval.get('reject_reason')} "
                        f"fill={fill_price} peak={before.get('profit_trailing_peak_price')} "
                        f"dd={reval.get('drawdown_from_peak')}"
                    )
                    executed = False
                    is_trade = False
                    after = before
                else:
                    cost_basis = round(avg * sell_shares, 4) if avg > 0 else 0.0
                    realized_pnl, gross_value, after_pos = _sell_shares(
                        portfolio, ticker, sell_shares, fill_price
                    )
                    fill_shares = sell_shares
                    capital_impact = round(gross_value, 4)
                    after = _position_snapshot(after_pos)
                    status = "EXECUTED"
                    executed = True
                    is_trade = fill_shares > 0
                    reason = f"{REASON_EXIT} fill revalidated dd={reval.get('drawdown_from_peak')} — {reason}"
            else:
                cost_basis = round(avg * sell_shares, 4) if avg > 0 else 0.0
                realized_pnl, gross_value, after_pos = _sell_shares(
                    portfolio, ticker, sell_shares, fill_price
                )
                fill_shares = sell_shares
                capital_impact = round(gross_value, 4)
                after = _position_snapshot(after_pos)
                status = "EXECUTED"
                executed = True
                is_trade = fill_shares > 0
    elif action == "REDUCE_PAPER":
        from tae_paper_profit_trailing import REASON_SOFT_SUPPRESSED, trailing_active_on_position

        if trailing_active_on_position(before):
            status = "NO_CHANGE"
            reason = f"{REASON_SOFT_SUPPRESSED}: REDUCE blocked while profit trailing active"
            executed = False
            is_trade = False
            after = before
        elif fill_price <= 0:
            status = "SKIPPED_NO_MARK_PRICE"
            reason = f"REDUCE_PAPER skipped — no mark price for {ticker}"
        elif is_suspicious_synthetic_fill_price(
            fill_price, ticker, pos=pos_ref, decision=decision, accounting=accounting
        ):
            status = "BLOCKED_FAKE_PROFIT_RISK"
            reason = f"REDUCE_PAPER blocked — suspicious ${SYNTHETIC_FILL_ANCHOR:.0f} fill for {ticker}"
        else:
            pta_row = None
            if roi001_challenger:
                index = pta_by if pta_by is not None else load_pta_by_ticker()
                pta_row = index.get(ticker)
            trim_pct, trim_source = resolve_reduce_trim_pct(
                confidence,
                ticker,
                challenger=bool(roi001_challenger),
                pta_row=pta_row,
            )
            trim_shares = _f(before.get("shares")) * (trim_pct / 100.0)
            avg = _f(before.get("avg_price"))
            cost_basis = round(avg * trim_shares, 4) if avg > 0 else 0.0
            # Round to share precision — refuse EXECUTED on zero/dust fills
            trim_shares = round(trim_shares, 6)
            if trim_shares <= 0:
                fill_shares = 0.0
                after = before
                status = "NO_CHANGE"
                executed = False
                is_trade = False
                reason = f"REDUCE_PAPER zero shares (trim {trim_pct:.0f}% [{trim_source}]) — {reason}"
            else:
                realized_pnl, gross_value, after_pos = _sell_shares(portfolio, ticker, trim_shares, fill_price)
                fill_shares = trim_shares
                capital_impact = round(gross_value, 4)
                after = _position_snapshot(after_pos)
                reason = f"REDUCE_PAPER trim {trim_pct:.0f}% [{trim_source}] — {reason}"
                status = "EXECUTED"
                executed = True
                is_trade = True
    elif action == "PROTECT_PAPER":
        from tae_paper_profit_trailing import REASON_SOFT_SUPPRESSED, trailing_active_on_position

        pos = positions.get(ticker)
        prev_protect = before.get("protect_mode")
        if trailing_active_on_position(before):
            status = "NO_CHANGE"
            reason = f"{REASON_SOFT_SUPPRESSED}: PROTECT blocked while profit trailing active"
            executed = False
            is_trade = False
            after = before
        elif risk_score >= 80 and _f(pos.get("shares")) > 0:
            if fill_price <= 0:
                status = "SKIPPED_NO_MARK_PRICE"
                reason = f"PROTECT_PAPER trim skipped — no mark price for {ticker}"
            elif is_suspicious_synthetic_fill_price(
                fill_price, ticker, pos=pos_ref, decision=decision, accounting=accounting
            ):
                status = "BLOCKED_FAKE_PROFIT_RISK"
                reason = f"PROTECT_PAPER trim blocked — suspicious ${SYNTHETIC_FILL_ANCHOR:.0f} fill for {ticker}"
            else:
                trim_shares = _f(pos.get("shares")) * 0.1
                avg = _f(before.get("avg_price"))
                cost_basis = round(avg * trim_shares, 4) if avg > 0 else 0.0
                realized_pnl, gross_value, after_pos = _sell_shares(portfolio, ticker, trim_shares, fill_price)
                fill_shares = trim_shares
                after = _position_snapshot(after_pos)
                reason = f"PROTECT_PAPER urgency trim 10% — {reason}"
                is_trade = fill_shares > 0
                status = "EXECUTED"
                executed = True
        else:
            pos["protect_mode"] = "TRAIL_SHADOW"
            after = _position_snapshot(pos)
            reason = f"PROTECT_PAPER protect-only — {reason}"
            if prev_protect != "TRAIL_SHADOW":
                status = "EXECUTED"
                executed = True
            else:
                status = "NO_CHANGE"
    elif action == "BUY_PAPER":
        from tae_paper_profit_trailing import REASON_BUY_BLOCKED, trailing_active_on_position

        # Scale-in / rebuy blocked while profit trailing owns the open cycle.
        if trailing_active_on_position(before):
            status = REASON_BUY_BLOCKED
            reason = f"{REASON_BUY_BLOCKED}: scale-in blocked for active profit trailing cycle"
            executed = False
            is_trade = False
            after = before
        else:
            # Gate order for NEW BUY (fill-time):
            # 1) hard-risk already applied above for open positions (N/A for flat)
            # 2) opening-noise defer (temporal)
            # 3) E3 PROFIT_DECAY block (economic)
            # 4) mark/synthetic/cash checks → fill
            decision_ts = _s(decision.get("timestamp") or decision.get("generated_at")) or None
            opening_gate = evaluate_opening_noise_new_buy_gate(
                action=action,
                is_new_position=is_new_position,
                ticker=ticker,
                decision_timestamp=decision_ts,
            )
            if opening_gate.get("deferred"):
                status = DEFER_REASON_OPENING_NOISE
                authorized_action = "DEFERRED"
                reason = (
                    f"{DEFER_REASON_OPENING_NOISE} — market={opening_gate.get('market')} "
                    f"mins_since_open={opening_gate.get('minutes_since_open')} "
                    f"window={opening_gate.get('opening_noise_window_minutes')} "
                    f"earliest_recheck={opening_gate.get('earliest_recheck_at')} "
                    f"(fresh decision required after window; no auto-fill)"
                )
                executed = False
                is_trade = False
                after = before
                cash = _f(portfolio.get("cash"))
                notional_estimate = min(cash * max(0.05, confidence * 0.12), cash * 0.15) if cash > 0 else 0.0
                append_opening_noise_defer_event(
                    {
                        "timestamp": _now(),
                        "decision_id": decision_id,
                        "ticker": ticker,
                        "market": opening_gate.get("market"),
                        "original_action": original_action,
                        "authorized_action": "DEFERRED",
                        "defer_reason": DEFER_REASON_OPENING_NOISE,
                        "exchange_timezone": opening_gate.get("exchange_timezone"),
                        "regular_session_open": opening_gate.get("regular_session_open"),
                        "decision_timestamp": decision_ts,
                        "minutes_since_open": opening_gate.get("minutes_since_open"),
                        "opening_noise_window_minutes": opening_gate.get("opening_noise_window_minutes"),
                        "earliest_recheck_at": opening_gate.get("earliest_recheck_at"),
                        "is_new_position": True,
                        "feature_flag": "DEFER_NEW_BUY_DURING_OPENING_NOISE",
                        "capital_temporarily_undeployed": round(notional_estimate, 4),
                        "avoided_opening_loss": 0.0,
                        "missed_opening_profit": 0.0,
                        "mark_price": fill_price if fill_price > 0 else None,
                        "mode": MODE,
                        "broker_executed": False,
                        "live_money": False,
                    }
                )
            else:
                # Canonical E3 authorization: block NEW BUY only when fresh lifecycle == PROFIT_DECAY.
                e3_gate = evaluate_profit_decay_new_buy_gate(
                    action=action,
                    is_new_position=is_new_position,
                    ticker=ticker,
                    gii_by_ticker=gii_by_ticker,
                    gii_meta=gii_meta,
                    decision_timestamp=decision_ts,
                )
                if e3_gate.get("blocked"):
                    status = BLOCK_REASON_PROFIT_DECAY
                    authorized_action = _s(e3_gate.get("authorized_action")) or "HOLD_PAPER"
                    reason = (
                        f"{BLOCK_REASON_PROFIT_DECAY} — original={original_action} "
                        f"authorized={authorized_action} lifecycle={e3_gate.get('lifecycle_stage')} "
                        f"collapse={e3_gate.get('collapse_probability')} "
                        f"gii_ts={e3_gate.get('growth_intelligence_timestamp')}"
                    )
                    executed = False
                    is_trade = False
                    after = before
                    cash = _f(portfolio.get("cash"))
                    notional_estimate = min(cash * max(0.05, confidence * 0.12), cash * 0.15) if cash > 0 else 0.0
                    append_e3_block_event(
                        {
                            "timestamp": _now(),
                            "decision_id": decision_id,
                            "ticker": ticker,
                            "original_action": original_action,
                            "authorized_action": authorized_action,
                            "lifecycle_stage": e3_gate.get("lifecycle_stage"),
                            "collapse_probability": e3_gate.get("collapse_probability"),
                            "growth_intelligence_timestamp": e3_gate.get("growth_intelligence_timestamp"),
                            "gii_age_hours": e3_gate.get("gii_age_hours"),
                            "gii_gate_status": e3_gate.get("gii_gate_status"),
                            "block_reason": BLOCK_REASON_PROFIT_DECAY,
                            "decision_timestamp": e3_gate.get("decision_timestamp"),
                            "is_new_position": True,
                            "capital_not_deployed": round(notional_estimate, 4),
                            "avoided_loss": 0.0,
                            "missed_profit": 0.0,
                            "mark_price": fill_price if fill_price > 0 else None,
                            "mode": MODE,
                            "broker_executed": False,
                            "live_money": False,
                        }
                    )
                else:
                    # Binding Decision Brain SKIP gate (PAPER NEW BUY only).
                    db_skip_gate = evaluate_decision_brain_skip_new_entry_gate(
                        action=action,
                        is_new_position=is_new_position,
                        ticker=ticker,
                        decision=decision,
                        execution_reason=execution_reason,
                        entry_kind="BUY",
                        strategy_id=_s(decision.get("strategy_id") or portfolio.get("strategy_id") or "V1") or "V1",
                    )
                    if db_skip_gate.get("blocked"):
                        status = BLOCK_REASON_DECISION_BRAIN_SKIP
                        authorized_action = "SKIP_PAPER"
                        reason = (
                            f"{BLOCK_REASON_DECISION_BRAIN_SKIP} — original={original_action} "
                            f"authorized=SKIP_PAPER source={db_skip_gate.get('decision_brain_source')} "
                            f"verdict={db_skip_gate.get('decision_brain_verdict')}"
                        )
                        executed = False
                        is_trade = False
                        after = before
                        cash = _f(portfolio.get("cash"))
                        notional_estimate = (
                            min(cash * max(0.05, confidence * 0.12), cash * 0.15) if cash > 0 else 0.0
                        )
                        attr = build_decision_brain_skip_attribution(
                            gate=db_skip_gate,
                            decision=decision,
                            strategy_id=_s(db_skip_gate.get("strategy_id") or "V1"),
                            mark_price=fill_price if fill_price > 0 else None,
                            capital_not_deployed=notional_estimate,
                        )
                        append_decision_brain_skip_block_event(attr)
                    elif fill_price <= 0:
                        status = "SKIPPED_NO_MARK_PRICE"
                        reason = f"BUY_PAPER skipped — no mark price for {ticker}"
                    elif is_suspicious_synthetic_fill_price(
                        fill_price, ticker, pos=pos_ref, decision=decision, accounting=accounting
                    ):
                        status = "BLOCKED_FAKE_PROFIT_RISK"
                        reason = f"BUY_PAPER blocked — suspicious ${SYNTHETIC_FILL_ANCHOR:.0f} fill for {ticker}"
                    else:
                        cash = _f(portfolio.get("cash"))
                        notional = min(cash * max(0.05, confidence * 0.12), cash * 0.15)
                        deployment_meta: dict[str, Any] = {}
                        sizing_result: dict[str, Any] = {}
                        try:
                            import tae_adaptive_deployment as adep

                            sizing = adep.resolve_buy_notional(
                                control_notional=notional,
                                inputs={
                                    "cash_available": cash,
                                    "cash_reserve": 0.0,
                                    "maximum_position_notional": cash * 0.15,
                                    "confidence": confidence,
                                    "current_open_positions": len(
                                        [
                                            x
                                            for x in (portfolio.get("positions") or {}).values()
                                            if _f((x or {}).get("shares")) > 0
                                        ]
                                    ),
                                    "maximum_positions": 20,
                                },
                                ticker=ticker,
                                arm="CANONICAL_PAPER",
                            )
                            sizing_result = dict(sizing or {})
                            deployment_meta = dict(sizing.get("deployment") or {})
                            if sizing.get("blocked"):
                                status = _s(sizing.get("reason_code")) or "BLOCKED_ADAPTIVE_DEPLOYMENT"
                                reason = f"BUY_PAPER blocked by adaptive deployment — {status}"
                                notional = 0.0
                                bought = 0.0
                                after_pos = portfolio.get("positions", {}).get(ticker) or {}
                            else:
                                notional = _f(sizing.get("executed_notional"), notional)
                                bought, after_pos = _buy_shares(portfolio, ticker, notional, fill_price)
                        except Exception:
                            bought, after_pos = _buy_shares(portfolio, ticker, notional, fill_price)
                        fill_shares = bought if notional > 0 else 0.0
                        if fill_shares > 0:
                            gross_value = round(notional, 4)
                            capital_impact = round(-notional, 4)
                            after = _position_snapshot(after_pos)
                            status = "EXECUTED"
                            executed = True
                            is_trade = True
                            if deployment_meta:
                                decision["adaptive_deployment"] = deployment_meta
                                for _k, _v in deployment_meta.items():
                                    if _k not in decision:
                                        decision[_k] = _v
                                if deployment_meta.get("experiment_arm") == "CHALLENGER":
                                    try:
                                        import tae_adaptive_deployment as adep

                                        adep.record_challenger_exposure(
                                            notional, arm="CANONICAL_PAPER", ticker=ticker
                                        )
                                    except Exception:
                                        pass
                            if sizing_result:
                                decision["adaptive_sizing"] = sizing_result
                                decision.update(
                                    adaptive_control_vs_executed_fields(
                                        sizing=sizing_result,
                                        fill_price=fill_price,
                                        fill_shares=fill_shares,
                                        executed_notional=notional,
                                    )
                                )
                        elif status not in {
                            "BLOCKED_ADAPTIVE_DEPLOYMENT",
                            "BLOCKED_TICKER_SCOPE",
                            "BLOCKED_NON_FINITE_QTY",
                            "BLOCKED_UNKNOWN_FORMULA",
                            "BLOCKED_INVALID_CONFIG",
                            "BLOCKED_CAPITAL_CAP",
                            "BLOCKED_LIVE_LOCK",
                            "BLOCKED_NO_VALID_LKG",
                            "BLOCKED_HARD_RISK",
                            "BLOCKED_RECONCILIATION",
                            "BLOCKED_DATA_QUALITY",
                        } and not str(status).startswith("BLOCKED_"):
                            status = "SKIPPED_NO_CASH"
                            reason = f"BUY_PAPER skipped — insufficient cash for {ticker}"
    elif action == "ROTATE_PAPER":
        from tae_paper_profit_trailing import REASON_SOFT_SUPPRESSED, trailing_active_on_position

        if trailing_active_on_position(before):
            status = "NO_CHANGE"
            reason = f"{REASON_SOFT_SUPPRESSED}: ROTATE blocked while profit trailing active"
            executed = False
            is_trade = False
            after = before
        elif fill_price <= 0:
            status = "SKIPPED_NO_MARK_PRICE"
            reason = f"ROTATE_PAPER skipped — no mark price for {ticker}"
        elif is_suspicious_synthetic_fill_price(
            fill_price, ticker, pos=pos_ref, decision=decision, accounting=accounting
        ):
            status = "BLOCKED_FAKE_PROFIT_RISK"
            reason = f"ROTATE_PAPER blocked — suspicious ${SYNTHETIC_FILL_ANCHOR:.0f} fill for {ticker}"
        else:
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
                if tgt_price <= 0 or is_suspicious_synthetic_fill_price(
                    tgt_price, tgt_ticker, pos=(portfolio.get("positions") or {}).get(tgt_ticker),
                    decision=target, accounting=accounting,
                ):
                    reason = f"ROTATE_PAPER {ticker} sell-only — no valid mark for {tgt_ticker}"
                else:
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

    if status not in {
        "SKIPPED_NO_POSITION",
        "SKIPPED_NO_MARK_PRICE",
        "BLOCKED_FAKE_PROFIT_RISK",
        "BLOCKED_HARD_RISK_AT_FILL",
        BLOCK_REASON_PROFIT_DECAY,
        BLOCK_REASON_DECISION_BRAIN_SKIP,
        DEFER_REASON_OPENING_NOISE,
        "BUY_BLOCKED_ACTIVE_PROFIT_TRAILING",
        "SKIPPED_TRAILING_EXIT_NO_LONGER_VALID",
        "SKIPPED_NO_VALID_TRAILING_MARK",
    }:
        recalc_portfolio(portfolio)

    cash_after = round(_f(portfolio.get("cash")), 4)

    order = {
        "timestamp": _now(),
        "decision_id": decision_id,
        "ticker": ticker,
        "action": action,
        "original_action": original_action,
        "authorized_action": authorized_action,
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
        "mark_source": mark.get("source"),
        "mark_timestamp": mark.get("timestamp"),
        "mark_freshness": mark.get("freshness"),
        "mark_resolution_attempts": mark.get("attempts") or [],
        "order_classification": "TERMINAL" if is_terminal_order_status(status, executed=executed, is_trade=is_trade) else "NON_TERMINAL",
        "fill_time_hard_risk": fill_time_hard_risk,
        "e3_entry_gate": e3_gate,
        "opening_noise_gate": opening_gate,
        "decision_brain_skip_gate": db_skip_gate,
        "is_new_position": is_new_position,
        "block_reason": (
            ((db_skip_gate or {}).get("block_reason") if db_skip_gate else None)
            or ((e3_gate or {}).get("block_reason") if e3_gate else None)
        ),
        "defer_reason": (opening_gate or {}).get("defer_reason") if opening_gate else None,
        "economic_class": (db_skip_gate or {}).get("economic_class"),
        "decision_brain_verdict": (db_skip_gate or {}).get("decision_brain_verdict"),
        "strategy_id": _s(decision.get("strategy_id") or portfolio.get("strategy_id") or "V1") or "V1",
        "reason_code": _s(decision.get("reason_code")) or None,
        "position_cycle_id": _s(decision.get("position_cycle_id") or before.get("position_cycle_id"))
        or None,
    }
    order.update(
        trailing_lifecycle_fields(
            decision,
            before,
            after,
            status=status,
            reason=reason,
            executed=executed,
        )
    )
    for key in (
        "base_quantity_before_adaptive",
        "base_capital_before_adaptive",
        "adaptive_multiplier",
        "adaptive_components",
        "executed_quantity",
        "executed_capital",
        "neutral_quantity_shadow",
        "neutral_capital_shadow",
        "control_notional",
        "executed_notional",
        "adaptive_sizing",
    ):
        if key in decision:
            order[key] = decision[key]
    # Propagate adaptive deployment metadata (BUY challenger or control stamp).
    dep_meta = decision.get("adaptive_deployment")
    if isinstance(dep_meta, dict) and dep_meta:
        order["adaptive_deployment"] = dep_meta
        for key in (
            "deployment_id",
            "deployment_version",
            "deployment_state",
            "experiment_id",
            "experiment_arm",
            "formula_id",
            "formula_version",
            "config_version",
            "git_head",
            "selection_reason",
        ):
            if key in dep_meta and key not in order:
                order[key] = dep_meta[key]
    elif action == "BUY_PAPER":
        try:
            import tae_adaptive_deployment as adep

            stamp = adep.deployment_metadata(selection_reason="paper_execution_stamp")
            order["adaptive_deployment"] = stamp
            for key, val in stamp.items():
                if key not in order:
                    order[key] = val
        except Exception:
            pass
    if (
        executed
        and action in {"SELL_PAPER", "ROTATE_PAPER"}
        and _f(after.get("shares")) <= 0
        and _f(before.get("shares")) > 0
    ):
        entry_order = None
        cycle_id = _s(order.get("position_cycle_id") or before.get("position_cycle_id"))
        ticker_u = _s(ticker).upper()
        for prior in reversed(load_jsonl(ORDERS_JSONL)):
            if _s(prior.get("action")).upper() != "BUY_PAPER":
                continue
            if _s(prior.get("ticker")).upper() != ticker_u:
                continue
            if not prior.get("executed"):
                continue
            prior_cycle = _s(prior.get("position_cycle_id") or (prior.get("position_after") or {}).get("position_cycle_id"))
            if cycle_id and prior_cycle and prior_cycle != cycle_id:
                continue
            entry_order = prior
            break
        order["adaptive_exit_attribution"] = compute_adaptive_exit_attribution(
            entry_order=entry_order,
            exit_trade=order,
        )
        if order.get("trailing_exit_fill") and order.get("trailing_realized_pnl") is None:
            order["trailing_realized_pnl"] = round(_f(order.get("realized_pnl")), 6)
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
    accounting = _load_live_accounting()
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
    cycle_ts: datetime | None = None,
    cycle_orders: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """Exactly-once gate: honor terminal fills on disk even if processed ids were not persisted."""
    if not decision_id:
        return False, "missing decision_id"

    last = last_orders.get(decision_id) or {}
    prior_action = _s(last.get("action")).upper()
    last_status = _s(last.get("status")).upper()

    if last:
        if prior_action and prior_action != action:
            return True, f"action_changed:{prior_action}->{action}"
        if last_status in NON_TERMINAL_ORDER_STATUSES:
            if _retry_cooldown_active(
                decision_id,
                last_orders=last_orders,
                cycle_ts=cycle_ts,
                cycle_orders=cycle_orders or {},
            ):
                return False, "retry_cooldown_active"
            return True, f"retry_after_non_terminal:{last_status}"
        # Crash recovery: orders.jsonl may already hold EXECUTED while portfolio
        # processed_decision_ids was not saved — never treat as new_decision.
        if is_terminal_order_status(
            last_status,
            executed=bool(last.get("executed")),
            is_trade=bool(last.get("is_trade")),
        ):
            return False, "already_processed_same_action"

    if decision_id in processed:
        return False, "already_processed_same_action"

    return True, "new_decision"


def run_paper_execution(*, write_report_flag: bool = True) -> dict[str, Any]:
    lock_handle = _acquire_execution_lock()
    try:
        return _run_paper_execution_body(write_report_flag=write_report_flag)
    finally:
        _release_execution_lock(lock_handle)


def _run_paper_execution_body(*, write_report_flag: bool = True) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    decisions_doc = load_json(DECISIONS_JSON)
    if not decisions_doc:
        return {"ok": False, "error": f"missing {DECISIONS_JSON}"}

    decisions = list(decisions_doc.get("decisions") or [])
    accounting = _load_live_accounting()
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

    trade_contamination = trades_have_synthetic_fill_contamination()
    if not trade_contamination:
        backfill_portfolio_realized_from_trades(portfolio, TRADES_JSONL)
    baseline_reset = ensure_accounting_baseline(portfolio) if existing else False
    if not baseline_reset:
        recalc_portfolio(portfolio)

    preflight = check_paper_profit_integrity(
        portfolio=portfolio,
        accounting=accounting,
        write_report_flag=True,
        update_validation_json=True,
    )
    portfolio["profit_integrity_status"] = preflight.get("status")
    portfolio["profit_integrity_ok"] = preflight.get("ok")
    if not preflight.get("ok"):
        save_json(PORTFOLIO_JSON, portfolio)
        return {
            "ok": False,
            "error": preflight.get("verdict"),
            "blocked": True,
            "integrity": preflight,
            "contaminated": preflight.get("contaminated") or [],
        }
    processed = set(portfolio.get("processed_decision_ids") or [])
    last_orders = load_orders_by_decision(ORDERS_JSONL)
    processed = reconcile_processed_decision_ids(processed, last_orders)
    cycle_ts = _parse_ts(decisions_doc.get("generated_at"))
    cycle_orders: dict[str, dict[str, Any]] = {}

    removed_legacy_trades = sanitize_trades_file(TRADES_JSONL)
    before_snapshot = _portfolio_snapshot(portfolio)

    orders: list[dict[str, Any]] = []
    action_counts: dict[str, int] = {}
    trades_written = 0
    reexecuted = 0
    skipped_same_action = 0
    skipped_switch = 0
    accepted_switch = 0
    non_terminal_retries = 0
    retry_cooldown_blocks = 0

    retry_state: dict[str, Any] = dict(portfolio.get("non_terminal_retry_state") or {})

    try:
        from tae_roi001_challenger import resolve_roi_production_flags

        roi_flags = resolve_roi_production_flags()
    except Exception:
        roi_flags = {"roi001_challenger": False}
    roi001_challenger = bool(roi_flags.get("roi001_challenger"))

    gii_by_ticker, gii_meta = load_gii_lifecycle_index()

    from tae_paper_profit_trailing import load_pce_by_ticker, wire_paper_profit_protection

    wire_paper_profit_protection(
        portfolio,
        pce_by=load_pce_by_ticker(),
        gii_by=gii_by_ticker,
    )

    proactive_orders = execute_proactive_hard_risk_exits(
        portfolio,
        accounting=accounting,
        processed=processed,
        last_orders=last_orders,
        roi001_challenger=roi001_challenger,
        gii_by_ticker=gii_by_ticker,
        gii_meta=gii_meta,
    )
    for order in proactive_orders:
        orders.append(order)
        if order.get("is_trade"):
            trade = {**order, "record_type": "paper_trade", "shares": order.get("fill_shares")}
            append_jsonl(TRADES_JSONL, trade)
            trades_written += 1
        action_counts["SELL_PAPER"] = action_counts.get("SELL_PAPER", 0) + 1

    for decision in decisions:
        decision_id = _s(decision.get("decision_id"))
        action = _s(decision.get("action")).upper()
        ok, reason = should_execute_decision(
            decision_id,
            action,
            processed=processed,
            last_orders=last_orders,
            cycle_ts=cycle_ts,
            cycle_orders=cycle_orders,
        )
        if not ok:
            if reason == "retry_cooldown_active":
                retry_cooldown_blocks += 1
                last = last_orders.get(decision_id) or {}
                order = {
                    "timestamp": _now(),
                    "decision_id": decision_id,
                    "ticker": _s(decision.get("ticker")).upper(),
                    "action": action,
                    "status": "SKIPPED_RETRY_COOLDOWN",
                    "executed": False,
                    "is_trade": False,
                    "execution_reason": reason,
                    "previous_status": last.get("status"),
                    "retry_count": _f((retry_state.get(decision_id) or {}).get("retry_count")),
                    "order_classification": "NON_TERMINAL",
                    "mode": MODE,
                    "broker_executed": False,
                    "live_money": False,
                }
                orders.append(order)
                append_jsonl(ORDERS_JSONL, order)
                cycle_orders[decision_id] = order
            else:
                # Explicit audit row so profit-pipeline can join same-cycle block reasons
                # (no portfolio mutation; does not re-open idempotency).
                skipped_same_action += 1
                last = last_orders.get(decision_id) or {}
                order = {
                    "timestamp": _now(),
                    "decision_id": decision_id,
                    "ticker": _s(decision.get("ticker")).upper(),
                    "action": action,
                    "status": "NO_CHANGE",
                    "executed": False,
                    "is_trade": False,
                    "fill_shares": 0.0,
                    "execution_reason": reason,
                    "action_changed": False,
                    "previous_status": last.get("status"),
                    "previous_action": last.get("action"),
                    "reason": f"{reason} — prior terminal order exists for this decision_id",
                    "source": "INITIAL_EXECUTION",
                    "order_classification": "TERMINAL_AUDIT",
                    "mode": MODE,
                    "broker_executed": False,
                    "live_money": False,
                }
                orders.append(order)
                append_jsonl(ORDERS_JSONL, order)
                cycle_orders[decision_id] = order
                last_orders[decision_id] = order
            continue
        if action not in PAPER_ACTIONS:
            continue
        if reason.startswith("retry_after_non_terminal"):
            non_terminal_retries += 1
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
            roi001_challenger=roi001_challenger,
            gii_by_ticker=gii_by_ticker,
            gii_meta=gii_meta,
        )
        order["execution_reason"] = reason
        if reason.startswith("retry_after_non_terminal"):
            prev = last_orders.get(decision_id) or {}
            order["previous_status"] = prev.get("status")
            entry = retry_state.setdefault(decision_id, {"retry_count": 0})
            entry["retry_count"] = int(_f(entry.get("retry_count"))) + 1
            entry["last_status"] = order.get("status")
            entry["last_retry_at"] = order.get("timestamp")
            entry["retry_reason"] = reason
            entry["mark_source"] = order.get("mark_source")
            entry["mark_timestamp"] = order.get("mark_timestamp")
            entry["classification"] = order.get("order_classification")
        orders.append(order)
        append_jsonl(ORDERS_JSONL, order)
        cycle_orders[decision_id] = order
        if order.get("is_trade"):
            trade = {**order, "record_type": "paper_trade", "shares": order.get("fill_shares")}
            append_jsonl(TRADES_JSONL, trade)
            trades_written += 1
        action_counts[action] = action_counts.get(action, 0) + 1
        if is_terminal_order_status(
            _s(order.get("status")),
            executed=bool(order.get("executed")),
            is_trade=bool(order.get("is_trade")),
        ):
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
    portfolio["non_terminal_retry_state"] = retry_state
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
        "non_terminal_retries": non_terminal_retries,
        "retry_cooldown_blocks": retry_cooldown_blocks,
        "e3_blocked_new_buy_profit_decay": sum(
            1 for o in orders if _s(o.get("status")) == BLOCK_REASON_PROFIT_DECAY
        ),
        "opening_noise_deferred_new_buy": sum(
            1 for o in orders if _s(o.get("status")) == DEFER_REASON_OPENING_NOISE
        ),
    }

    e3_audit = summarize_e3_canonical_blocks()
    e3_audit["gii_meta"] = gii_meta
    save_json(OUTPUT_DIR / "e3_canonical_entry_protection.json", e3_audit)

    opening_audit = summarize_opening_noise_defers()
    save_json(OUTPUT_DIR / "opening_noise_protection.json", opening_audit)

    post_integrity = check_paper_profit_integrity(
        portfolio=portfolio,
        accounting=accounting,
        orders=orders,
        write_report_flag=True,
        update_validation_json=True,
    )
    portfolio["profit_integrity_status"] = post_integrity.get("status")
    portfolio["profit_integrity_ok"] = post_integrity.get("ok")
    save_json(PORTFOLIO_JSON, portfolio)

    payload = {
        "ok": validation["ok"] and post_integrity.get("ok", True),
        "generated_at": _now(),
        "decisions_consumed": len(decisions),
        "stats": stats,
        "validation": validation,
        "integrity": post_integrity,
        "action_counts": action_counts,
        "portfolio": portfolio,
        "attribution_rules": len(attribution.get("rules") or {}),
        "e3_canonical_entry_protection": e3_audit,
        "opening_noise_protection": opening_audit,
    }
    if write_report_flag:
        write_report(payload)
    return payload


ACTIONABLE_EXEC_ACTIONS = frozenset(
    {"BUY_PAPER", "SELL_PAPER", "REDUCE_PAPER", "ROTATE_PAPER", "PROTECT_PAPER"}
)


def _decision_action_index(doc: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in (doc or {}).get("decisions") or []:
        ticker = _s(row.get("ticker")).upper()
        if ticker:
            out[ticker] = row
    return out


def run_post_learning_changed_execution(
    *,
    before_decisions: dict[str, Any] | None = None,
    after_decisions: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    write_report_flag: bool = False,
) -> dict[str, Any]:
    """Execute only decisions whose action changed during constitutional evolution.

    Controlled: action_changed required, Decision State + Hard Risk preserved,
    same-action idempotency preserved, at most once per ticker per call.
    Does not execute HOLD/SKIP. source=POST_LEARNING_EVOLUTION.
    """
    lock_handle = _acquire_execution_lock()
    try:
        return _run_post_learning_changed_execution_body(
            before_decisions=before_decisions,
            after_decisions=after_decisions,
            cycle_id=cycle_id,
            write_report_flag=write_report_flag,
        )
    finally:
        _release_execution_lock(lock_handle)


def _run_post_learning_changed_execution_body(
    *,
    before_decisions: dict[str, Any] | None = None,
    after_decisions: dict[str, Any] | None = None,
    cycle_id: str | None = None,
    write_report_flag: bool = False,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before_doc = before_decisions or load_json(Path("runtime_outputs/paper_decisions/paper_decisions_pre_evolution.json"))
    after_doc = after_decisions or load_json(DECISIONS_JSON)
    if not after_doc:
        return {"ok": False, "error": f"missing {DECISIONS_JSON}", "executed_tickers": []}

    before_idx = _decision_action_index(before_doc)
    after_idx = _decision_action_index(after_doc)
    cycle_id = cycle_id or _s(after_doc.get("generated_at")) or _now()

    changed: list[tuple[str, dict[str, Any], str, str]] = []
    for ticker, after in after_idx.items():
        after_action = _s(after.get("action")).upper()
        before_action = _s((before_idx.get(ticker) or {}).get("action")).upper()
        if after_action == before_action:
            continue
        if after_action in {"HOLD_PAPER", "SKIP_PAPER", ""}:
            continue
        if after_action not in ACTIONABLE_EXEC_ACTIONS:
            continue
        changed.append((ticker, after, before_action, after_action))

    if not changed:
        return {
            "ok": True,
            "generated_at": _now(),
            "cycle_id": cycle_id,
            "source": "POST_LEARNING_EVOLUTION",
            "candidates": 0,
            "executed_tickers": [],
            "orders_created": 0,
            "trades_written": 0,
            "skipped": [],
            "note": "no actionable action changes from constitutional evolution",
        }

    accounting = _load_live_accounting()
    portfolio = load_json(PORTFOLIO_JSON) or bootstrap_portfolio(accounting, None)
    processed = set(portfolio.get("processed_decision_ids") or [])
    last_orders = load_orders_by_decision(ORDERS_JSONL)
    processed = reconcile_processed_decision_ids(processed, last_orders)
    cycle_ts = _parse_ts(after_doc.get("generated_at"))
    cycle_orders: dict[str, dict[str, Any]] = {}
    executed_this_call: set[str] = set()

    try:
        from tae_roi001_challenger import resolve_roi_production_flags

        roi_flags = resolve_roi_production_flags()
    except Exception:
        roi_flags = {"roi001_challenger": False}
    roi001_challenger = bool(roi_flags.get("roi001_challenger"))

    gii_by_ticker, gii_meta = load_gii_lifecycle_index()

    orders: list[dict[str, Any]] = []
    trades_written = 0
    skipped: list[dict[str, Any]] = []
    all_decisions = list(after_doc.get("decisions") or [])

    for ticker, decision, before_action, after_action in changed:
        if ticker in executed_this_call:
            skipped.append({"ticker": ticker, "reason": "already_executed_this_post_learning_pass"})
            continue
        decision_id = _s(decision.get("decision_id"))
        action = after_action
        ok, reason = should_execute_decision(
            decision_id,
            action,
            processed=processed,
            last_orders=last_orders,
            cycle_ts=cycle_ts,
            cycle_orders=cycle_orders,
        )
        # Force action_changed only when the last terminal order action still differs
        # from the post-learning action (prevents duplicate post-learning executes).
        if not ok and reason == "already_processed_same_action" and before_action and before_action != action:
            last_action = _s((last_orders.get(decision_id) or {}).get("action")).upper()
            if last_action != action:
                ok, reason = True, f"action_changed:{before_action}->{action}"
        if not ok:
            skipped.append({"ticker": ticker, "decision_id": decision_id, "reason": reason})
            continue

        if reason.startswith("action_changed") or before_action != action:
            hard_override = bool((decision.get("hard_risk_discipline") or {}).get("override"))
            switch_ok = bool(decision.get("decision_switch_authorized"))
            if not hard_override and not switch_ok:
                order = {
                    "timestamp": _now(),
                    "decision_id": decision_id,
                    "ticker": ticker,
                    "action": action,
                    "status": "SKIPPED_SWITCH_NOT_AUTHORIZED",
                    "executed": False,
                    "is_trade": False,
                    "execution_reason": reason if reason.startswith("action_changed") else f"action_changed:{before_action}->{action}",
                    "action_changed": True,
                    "action_before": before_action,
                    "action_after": after_action,
                    "source": "POST_LEARNING_EVOLUTION",
                    "cycle_id": cycle_id,
                    "decision_switch_authorized": False,
                    "switch_reason": _s(decision.get("switch_reason")),
                    "mode": MODE,
                    "broker_executed": False,
                    "live_money": False,
                }
                orders.append(order)
                append_jsonl(ORDERS_JSONL, order)
                cycle_orders[decision_id] = order
                skipped.append({"ticker": ticker, "reason": "switch_not_authorized"})
                continue

        exec_reason = reason if reason.startswith("action_changed") else f"action_changed:{before_action}->{action}"
        order = execute_decision(
            decision,
            portfolio,
            accounting=accounting,
            all_decisions=all_decisions,
            execution_reason=exec_reason,
            roi001_challenger=roi001_challenger,
            gii_by_ticker=gii_by_ticker,
            gii_meta=gii_meta,
        )
        order["execution_reason"] = exec_reason
        order["action_changed"] = True
        order["action_before"] = before_action
        order["action_after"] = after_action
        order["source"] = "POST_LEARNING_EVOLUTION"
        order["cycle_id"] = cycle_id
        orders.append(order)
        append_jsonl(ORDERS_JSONL, order)
        cycle_orders[decision_id] = order
        last_orders[decision_id] = order
        executed_this_call.add(ticker)
        if order.get("is_trade"):
            trade = {
                **order,
                "record_type": "paper_trade",
                "shares": order.get("fill_shares"),
                "source": "POST_LEARNING_EVOLUTION",
                "cycle_id": cycle_id,
            }
            append_jsonl(TRADES_JSONL, trade)
            trades_written += 1
        if is_terminal_order_status(
            _s(order.get("status")),
            executed=bool(order.get("executed")),
            is_trade=bool(order.get("is_trade")),
        ):
            processed.add(decision_id)

    recalc_portfolio(portfolio)
    portfolio["processed_decision_ids"] = sorted(processed)
    portfolio["last_post_learning_execution_at"] = _now()
    save_json(PORTFOLIO_JSON, portfolio)

    integrity = check_paper_profit_integrity(
        portfolio=portfolio,
        accounting=accounting,
        orders=orders,
        write_report_flag=write_report_flag,
        update_validation_json=True,
    )
    recon = validate_portfolio_reconciliation(portfolio)

    return {
        "ok": bool(integrity.get("ok")) and _s((recon or {}).get("status")).upper() == "PASS",
        "generated_at": _now(),
        "cycle_id": cycle_id,
        "source": "POST_LEARNING_EVOLUTION",
        "candidates": len(changed),
        "executed_tickers": sorted(executed_this_call),
        "orders_created": len(orders),
        "trades_written": trades_written,
        "skipped": skipped,
        "integrity": integrity,
        "reconciliation": recon,
    }


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
        import math

        from core.market_data_layer import get_market_price

        result = get_market_price(ticker, purpose="risk")
        price = result.price
        if price is not None and math.isfinite(float(price)) and float(price) > 0:
            return float(price), result.source or "yfinance", result.status
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

    equity_append: dict[str, Any] = {"ok": False, "skipped": True}
    try:
        equity_append = append_paper_daily_equity_observation(portfolio, reconciliation=reconciliation)
        mtm_doc["daily_equity"] = {
            "appended": bool(equity_append.get("appended")),
            "idempotent": bool(equity_append.get("idempotent")),
            "observation_id": (equity_append.get("observation") or {}).get("observation_id"),
            "path": str(DAILY_EQUITY_JSONL),
        }
        save_json(MTM_JSON, mtm_doc)
    except Exception as exc:
        equity_append = {"ok": False, "error": str(exc), "fail_open": True}

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
        "daily_equity": equity_append,
    }


def compare_canonical_vs_paper(
    *,
    write_report_flag: bool = True,
    accounting_path: Path | str | None = None,
    paper_path: Path | str | None = None,
    canonical_snapshot: dict[str, Any] | None = None,
    mtm_path: Path | str | None = None,
    report_path: Path | str | None = None,
) -> dict[str, Any]:
    """Compare canonical LIVE accounting vs isolated PAPER portfolio.

    Explicit fixture paths / snapshots win. Host LIVE rebuild runs only when no
    fixture is supplied (production default).
    """
    if canonical_snapshot is not None:
        accounting = dict(canonical_snapshot)
        accounting_source = "canonical_snapshot"
    elif accounting_path is not None:
        accounting = load_json(Path(accounting_path)) or {}
        accounting_source = str(Path(accounting_path))
    else:
        accounting = _load_live_accounting()
        accounting_source = "build_accounting_snapshot"

    paper_file = Path(paper_path) if paper_path is not None else PORTFOLIO_JSON
    paper = load_json(paper_file) or {}
    mtm_file = Path(mtm_path) if mtm_path is not None else MTM_JSON
    mtm = load_json(mtm_file) or {}
    report_md = Path(report_path) if report_path is not None else CANONICAL_VS_PAPER_MD

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
        "sources": {
            "accounting": accounting_source,
            "paper": str(paper_file),
            "mtm": str(mtm_file),
        },
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
        report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
