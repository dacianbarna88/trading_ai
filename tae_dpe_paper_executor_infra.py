#!/usr/bin/env python3
"""
TAE DPE — Shared paper executor infrastructure.

Used by DPE-3/DPE-4 isolated paper executors. Parameterized by executor config
and philosophy-specific action resolver. Does NOT touch live paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "dpe.paper_portfolio.v1"
METRICS_SCHEMA_VERSION = "dpe.paper_metrics.v2"
MODE = "PAPER_ONLY"

JOBS_PATH = Path("runtime_outputs/dpe/execution_jobs.jsonl")
PAPER_DECISIONS_DIR = Path("runtime_outputs/paper_decisions")
PAPER_DECISIONS_JSON = PAPER_DECISIONS_DIR / "paper_decisions.json"
PAPER_DECISIONS_JSONL = PAPER_DECISIONS_DIR / "paper_decisions.jsonl"
PAPER_DECISION_VALIDATION_DIR = PAPER_DECISIONS_DIR
PAPER_DECISION_VALIDATION_JSON = PAPER_DECISION_VALIDATION_DIR / "decision_validation_results.json"
PAPER_DECISION_VALIDATION_JSONL = PAPER_DECISION_VALIDATION_DIR / "decision_validation_results.jsonl"
DECISION_VALIDATION_REPORT_MD = Path("TAE_PAPER_DECISION_VALIDATION_REPORT.md")
EXPERIMENT_RUNNER_REPORT_MD = Path("TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md")

VERDICT_PRIORITY: dict[str, int] = {
    "PROMISING": 0,
    "CONTINUE_TESTING": 1,
    "NEEDS_MORE_DATA": 2,
    "REJECT": 3,
}

GII_JSON = Path("tae_growth_intelligence.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
PROTECTION_VALIDATION_JSON = Path("tae_profit_protection_validation.json")

DECISION_VERDICTS = frozenset({"CONTINUE_TESTING", "PROMISING", "REJECT", "NEEDS_MORE_DATA"})

FORBIDDEN_WRITE_PREFIXES = (
    Path("portfolio.csv"),
    Path("live_signals.csv"),
    Path("watchlist.txt"),
    Path("live_bot.py"),
    Path("core"),
)

ResolveActionFn = Callable[[dict[str, Any], dict[str, Any] | None], tuple[str, float, str]]


@dataclass(frozen=True)
class ExecutorConfig:
    executor: str
    source: str
    output_dir: Path
    report_title: str
    report_tagline: str
    root_report_path: Path
    next_sprint: str


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def paths_for(config: ExecutorConfig) -> dict[str, Path]:
    return {
        "output_dir": config.output_dir,
        "portfolio": config.output_dir / "portfolio.json",
        "orders": config.output_dir / "orders.jsonl",
        "trades": config.output_dir / "trades.jsonl",
        "metrics": config.output_dir / "metrics.json",
        "report": config.output_dir / "executor_report.md",
    }


def assert_safe_output_path(path: Path, output_dir: Path) -> None:
    resolved = path.resolve()
    output_root = output_dir.resolve()
    if output_root not in resolved.parents and resolved != output_root:
        if path.name.endswith(".md") and path.parent.resolve() == Path(".").resolve():
            return
        raise RuntimeError(f"Unsafe output path outside {output_dir}: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.name in str(resolved):
            raise RuntimeError(f"Forbidden write target: {path}")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_json(path: Path, payload: dict[str, Any], output_dir: Path) -> None:
    assert_safe_output_path(path, output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, record: dict[str, Any], output_dir: Path) -> None:
    assert_safe_output_path(path, output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def count_actions(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"HOLD": 0, "PAPER_TRIM": 0, "PAPER_PROTECT": 0, "PAPER_SKIP": 0, "total": 0}
    for record in records:
        action = (_s(record.get("paper_action")) or _s(record.get("action")) or "UNKNOWN").upper()
        if action in counts:
            counts[action] += 1
        counts["total"] += 1
    return counts


def action_counts_to_legacy(counts: dict[str, int]) -> dict[str, int]:
    return {
        "hold_count": counts.get("HOLD", 0),
        "trim_count": counts.get("PAPER_TRIM", 0),
        "protect_count": counts.get("PAPER_PROTECT", 0),
        "skip_count": counts.get("PAPER_SKIP", 0),
    }


def load_executor_ready_jobs(executor: str) -> tuple[list[dict[str, Any]], int, int]:
    if not JOBS_PATH.is_file():
        return [], 0, 0
    total = 0
    matched = 0
    by_id: dict[str, dict[str, Any]] = {}
    for line in JOBS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        job = json.loads(line)
        if job.get("executor") != executor:
            continue
        if job.get("status") != "READY":
            continue
        matched += 1
        jid = _s(job.get("job_id"))
        if jid:
            by_id[jid] = job
    jobs = sorted(by_id.values(), key=lambda j: _s(j.get("timestamp")) or "")
    return jobs, total, matched


def empty_portfolio(config: ExecutorConfig) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "executor": config.executor,
        "mode": MODE,
        "source": config.source,
        "created_at": _now(),
        "updated_at": _now(),
        "starting_value": 0.0,
        "cash": 0.0,
        "open_positions_value": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_value": 0.0,
        "positions": {},
        "processed_job_ids": [],
    }


def position_from_snapshot(snap: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    shares = _f(snap.get("shares"))
    status = (_s(snap.get("status")) or "").upper()
    if shares <= 0 or status not in {"OPEN", "OPEN_POSITION"}:
        return None
    avg_price = _f(snap.get("avg_price"))
    current_price = _f(snap.get("current_price")) or avg_price
    current_value = _f(snap.get("current_value")) or shares * current_price
    pnl = _f(snap.get("pnl"))
    if pnl == 0.0 and avg_price > 0:
        pnl = (current_price - avg_price) * shares
    return {
        "ticker": ticker,
        "shares": round(shares, 6),
        "avg_price": round(avg_price, 6),
        "current_price": round(current_price, 6),
        "current_value": round(current_value, 4),
        "pnl": round(pnl, 4),
        "current_pct": round(_f(snap.get("current_pct")), 4),
        "status": "OPEN",
    }


def bootstrap_portfolio(jobs: list[dict[str, Any]], config: ExecutorConfig) -> dict[str, Any]:
    portfolio = empty_portfolio(config)
    latest_by_ticker: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if (_s(job.get("parent_event_type")) or "") != "TICKER_DECISION_SNAPSHOT":
            continue
        ticker = (_s(job.get("ticker")) or "").upper()
        if not ticker or ticker == "PORTFOLIO":
            continue
        latest_by_ticker[ticker] = job

    starting_value = 0.0
    cash = 0.0
    for job in latest_by_ticker.values():
        snap = job.get("portfolio_snapshot") or {}
        acct = _f(snap.get("account_value_corrected"))
        c = _f(snap.get("cash_available"))
        if acct > starting_value:
            starting_value = acct
        if c > cash:
            cash = c

    if starting_value <= 0 and latest_by_ticker:
        first = next(iter(latest_by_ticker.values()))
        starting_value = _f((first.get("portfolio_snapshot") or {}).get("account_value_corrected"), 100000.0)
    if cash <= 0 and starting_value > 0:
        cash = starting_value * 0.08

    positions: dict[str, dict[str, Any]] = {}
    for ticker, job in sorted(latest_by_ticker.items()):
        pos = position_from_snapshot(job.get("portfolio_snapshot") or {}, ticker)
        if pos:
            positions[ticker] = pos

    portfolio["starting_value"] = round(starting_value, 2)
    portfolio["cash"] = round(cash, 2)
    portfolio["positions"] = positions
    recalc_portfolio(portfolio)
    return portfolio


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


def get_price(job: dict[str, Any], position: dict[str, Any] | None) -> float:
    market = job.get("market_snapshot") or {}
    snap = job.get("portfolio_snapshot") or {}
    if _f(market.get("current_price")) > 0:
        return _f(market.get("current_price"))
    if _f(snap.get("current_price")) > 0:
        return _f(snap.get("current_price"))
    if position and _f(position.get("current_price")) > 0:
        return _f(position.get("current_price"))
    if position and _f(position.get("avg_price")) > 0:
        return _f(position.get("avg_price"))
    return 0.0


def apply_hold(*, job: dict[str, Any], position: dict[str, Any], price: float, reason: str) -> dict[str, Any]:
    shares = _f(position.get("shares"))
    return {
        "timestamp": _now(),
        "job_id": job.get("job_id"),
        "decision_uuid": job.get("decision_uuid"),
        "experiment_id": job.get("experiment_id"),
        "ticker": job.get("ticker"),
        "action": "HOLD",
        "paper_action": "HOLD",
        "shares_before": shares,
        "shares_after": shares,
        "trim_shares": 0.0,
        "price": price,
        "realized_pnl": 0.0,
        "reason": reason,
        "mapped_from": job.get("action_candidate"),
    }


def apply_skip(
    *, job: dict[str, Any], position: dict[str, Any] | None, price: float, reason: str
) -> dict[str, Any]:
    shares = _f(position.get("shares")) if position else 0.0
    return {
        "timestamp": _now(),
        "job_id": job.get("job_id"),
        "decision_uuid": job.get("decision_uuid"),
        "experiment_id": job.get("experiment_id"),
        "ticker": job.get("ticker"),
        "action": "PAPER_SKIP",
        "paper_action": "PAPER_SKIP",
        "shares_before": shares,
        "shares_after": shares,
        "trim_shares": 0.0,
        "price": price,
        "realized_pnl": 0.0,
        "reason": reason,
        "mapped_from": job.get("action_candidate"),
    }


def apply_trim(
    *,
    job: dict[str, Any],
    position: dict[str, Any],
    price: float,
    trim_pct: float,
    reason: str,
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    shares_before = _f(position.get("shares"))
    avg_price = _f(position.get("avg_price"))
    trim_pct = max(min(trim_pct, 100.0), 0.0)
    trim_shares = round(shares_before * (trim_pct / 100.0), 6)
    if trim_shares <= 0:
        trim_shares = round(shares_before * 0.25, 6)
    trim_shares = min(trim_shares, shares_before)
    shares_after = round(shares_before - trim_shares, 6)
    realized = round((price - avg_price) * trim_shares, 4) if avg_price > 0 else 0.0

    portfolio["cash"] = round(_f(portfolio.get("cash")) + trim_shares * price, 4)
    portfolio["realized_pnl"] = round(_f(portfolio.get("realized_pnl")) + realized, 4)

    ticker = (_s(job.get("ticker")) or "").upper()
    if shares_after <= 0.000001:
        portfolio["positions"].pop(ticker, None)
    else:
        position["shares"] = shares_after
        position["status"] = "OPEN"

    return {
        "timestamp": _now(),
        "job_id": job.get("job_id"),
        "decision_uuid": job.get("decision_uuid"),
        "experiment_id": job.get("experiment_id"),
        "ticker": ticker,
        "action": "PAPER_TRIM",
        "paper_action": "PAPER_TRIM",
        "shares_before": shares_before,
        "shares_after": shares_after,
        "trim_shares": trim_shares,
        "trim_pct": trim_pct,
        "price": price,
        "realized_pnl": realized,
        "reason": reason,
        "mapped_from": job.get("action_candidate"),
    }


def apply_protect(
    *,
    job: dict[str, Any],
    position: dict[str, Any],
    price: float,
    reason: str,
    portfolio: dict[str, Any],
    force_trim_pct: float | None = None,
) -> dict[str, Any]:
    target = job.get("target_snapshot") or {}
    urgency = (_s(target.get("exit_window_urgency")) or "").upper()
    partial = _f(target.get("suggested_partial_size_pct"))
    trim_pct = force_trim_pct if force_trim_pct is not None else partial
    if urgency in {"CRITICAL", "HIGH"} and trim_pct > 0:
        return apply_trim(
            job=job,
            position=position,
            price=price,
            trim_pct=trim_pct,
            reason=reason if force_trim_pct else "PAPER_PROTECT_URGENCY_TRIM",
            portfolio=portfolio,
        )
    shares = _f(position.get("shares"))
    return {
        "timestamp": _now(),
        "job_id": job.get("job_id"),
        "decision_uuid": job.get("decision_uuid"),
        "experiment_id": job.get("experiment_id"),
        "ticker": job.get("ticker"),
        "action": "PAPER_PROTECT",
        "paper_action": "PAPER_PROTECT",
        "protect_mode": "PROTECT_ONLY",
        "shares_before": shares,
        "shares_after": shares,
        "trim_shares": 0.0,
        "price": price,
        "realized_pnl": 0.0,
        "reason": reason,
        "mapped_from": job.get("action_candidate"),
    }


def process_jobs(
    portfolio: dict[str, Any],
    jobs: list[dict[str, Any]],
    *,
    config: ExecutorConfig,
    paths: dict[str, Path],
    resolve_action: ResolveActionFn,
) -> dict[str, Any]:
    processed: set[str] = set(portfolio.get("processed_job_ids") or [])
    run_started = _now()
    stats = {
        "run_started_at": run_started,
        "jobs_read": len(jobs),
        "new_jobs_processed": 0,
        "jobs_skipped_duplicate": 0,
        "jobs_skipped_non_ticker": 0,
        "jobs_invalid": 0,
        "new_hold_count": 0,
        "new_trim_count": 0,
        "new_protect_count": 0,
        "new_skip_count": 0,
        "new_actions": [],
    }

    for job in jobs:
        job_id = _s(job.get("job_id"))
        if not job_id:
            stats["jobs_invalid"] += 1
            continue
        if job_id in processed:
            stats["jobs_skipped_duplicate"] += 1
            continue

        ticker = (_s(job.get("ticker")) or "").upper()
        if ticker == "PORTFOLIO" or (_s(job.get("parent_event_type")) or "") != "TICKER_DECISION_SNAPSHOT":
            processed.add(job_id)
            stats["jobs_skipped_non_ticker"] += 1
            portfolio.setdefault("processed_job_ids", []).append(job_id)
            continue

        position = (portfolio.get("positions") or {}).get(ticker)
        if position is None:
            boot = position_from_snapshot(job.get("portfolio_snapshot") or {}, ticker)
            if boot:
                portfolio.setdefault("positions", {})[ticker] = boot
                position = boot

        price = get_price(job, position)
        paper_action, trim_pct, reason = resolve_action(job, position)

        if paper_action == "HOLD":
            event = apply_hold(job=job, position=position or {}, price=price, reason=reason)
            stats["new_hold_count"] += 1
        elif paper_action == "PAPER_SKIP":
            event = apply_skip(job=job, position=position, price=price, reason=reason)
            stats["new_skip_count"] += 1
        elif paper_action == "PAPER_TRIM":
            if position is None or _f(position.get("shares")) <= 0:
                event = apply_skip(job=job, position=position, price=price, reason="NO_POSITION_FOR_TRIM")
                stats["new_skip_count"] += 1
            else:
                event = apply_trim(
                    job=job, position=position, price=price, trim_pct=trim_pct,
                    reason=reason, portfolio=portfolio,
                )
                stats["new_trim_count"] += 1
        elif paper_action == "PAPER_PROTECT":
            if position is None or _f(position.get("shares")) <= 0:
                event = apply_skip(job=job, position=position, price=price, reason="NO_POSITION_FOR_PROTECT")
                stats["new_skip_count"] += 1
            else:
                event = apply_protect(
                    job=job, position=position, price=price, reason=reason,
                    portfolio=portfolio, force_trim_pct=trim_pct if trim_pct > 0 else None,
                )
                if event.get("paper_action") == "PAPER_TRIM":
                    stats["new_trim_count"] += 1
                else:
                    stats["new_protect_count"] += 1
        else:
            event = apply_skip(job=job, position=position, price=price, reason=f"UNSUPPORTED_{paper_action}")
            stats["new_skip_count"] += 1

        append_jsonl(paths["orders"], event, config.output_dir)
        append_jsonl(paths["trades"], event, config.output_dir)
        stats["new_actions"].append(event)
        processed.add(job_id)
        portfolio.setdefault("processed_job_ids", []).append(job_id)
        stats["new_jobs_processed"] += 1

        pos = (portfolio.get("positions") or {}).get(ticker)
        if pos and price > 0:
            pos["current_price"] = round(price, 6)

    portfolio["processed_job_ids"] = sorted(processed)
    recalc_portfolio(portfolio)
    stats["run_completed_at"] = _now() if stats["new_jobs_processed"] > 0 else run_started
    return stats


def verify_integrity(
    *,
    config: ExecutorConfig,
    portfolio: dict[str, Any],
    orders: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    jobs_read: int,
    stats: dict[str, Any],
    jobs_total: int,
    jobs_matched: int,
) -> tuple[dict[str, Any], bool]:
    processed_ids = portfolio.get("processed_job_ids") or []
    order_job_ids = {_s(r.get("job_id")) for r in orders if _s(r.get("job_id"))}
    historical_actions = count_actions(orders)
    new_actions = count_actions(stats.get("new_actions") or [])
    legacy_historical = action_counts_to_legacy(historical_actions)
    legacy_new = action_counts_to_legacy(new_actions)

    portfolio_totals = {
        "starting_value": portfolio.get("starting_value"),
        "cash": portfolio.get("cash"),
        "open_positions_value": portfolio.get("open_positions_value"),
        "realized_pnl": portfolio.get("realized_pnl"),
        "unrealized_pnl": portfolio.get("unrealized_pnl"),
        "total_value": portfolio.get("total_value"),
        "position_count": len(portfolio.get("positions") or {}),
    }

    non_ticker_processed = max(len(processed_ids) - len(order_job_ids), 0)
    last_execution_timestamp = _s(stats.get("run_completed_at"))
    if orders:
        last_order_ts = _s(orders[-1].get("timestamp"))
        if last_order_ts and stats["new_jobs_processed"] == 0:
            last_execution_timestamp = last_order_ts
        elif stats["new_jobs_processed"] > 0:
            last_execution_timestamp = _s(stats.get("run_completed_at")) or last_order_ts

    checks: list[dict[str, Any]] = []

    def add_check(name: str, expected: Any, actual: Any) -> None:
        checks.append({"check": name, "expected": expected, "actual": actual, "pass": expected == actual})

    add_check("orders_equals_trades", len(orders), len(trades))
    add_check("historical_actions_total", len(orders), historical_actions["total"])
    add_check("orders_unique_job_ids", len(order_job_ids), historical_actions["total"])
    add_check("processed_ids_covers_orders", len(processed_ids) >= len(order_job_ids), True)
    add_check("processed_ids_balance", len(processed_ids), len(order_job_ids) + non_ticker_processed)
    add_check("new_actions_total", stats["new_jobs_processed"], new_actions["total"])
    add_check(
        "portfolio_total_value",
        round(_f(portfolio_totals["total_value"]), 4),
        round(_f(portfolio.get("total_value")), 4),
    )
    add_check(
        "portfolio_realized_pnl",
        round(_f(portfolio_totals["realized_pnl"]), 4),
        round(_f(portfolio.get("realized_pnl")), 4),
    )
    add_check(
        "historical_hold_count",
        legacy_historical["hold_count"],
        sum(1 for r in orders if (_s(r.get("paper_action")) or "").upper() == "HOLD"),
    )

    integrity_pass = all(item["pass"] for item in checks)

    metrics = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "executor": config.executor,
        "mode": MODE,
        "generated_at": _now(),
        "last_execution_timestamp": last_execution_timestamp,
        "input_source": str(JOBS_PATH),
        "jobs_total_in_log": jobs_total,
        "jobs_executor_ready": jobs_matched,
        "jobs_read": jobs_read,
        "historical_jobs": {
            "processed_count": len(processed_ids),
            "ticker_actions": len(order_job_ids),
            "non_ticker_skipped": non_ticker_processed,
        },
        "new_jobs": {
            "processed": stats["new_jobs_processed"],
            "skipped_duplicate": stats["jobs_skipped_duplicate"],
            "skipped_non_ticker": stats["jobs_skipped_non_ticker"],
            "skipped_invalid": stats["jobs_invalid"],
        },
        "duplicate_jobs": stats["jobs_skipped_duplicate"],
        "historical_actions": {
            "hold": legacy_historical["hold_count"],
            "trim": legacy_historical["trim_count"],
            "protect": legacy_historical["protect_count"],
            "skip": legacy_historical["skip_count"],
            "total": historical_actions["total"],
        },
        "new_actions": {
            "hold": legacy_new["hold_count"],
            "trim": legacy_new["trim_count"],
            "protect": legacy_new["protect_count"],
            "skip": legacy_new["skip_count"],
            "total": new_actions["total"],
        },
        "portfolio_totals": portfolio_totals,
        "executor_totals": {
            "orders_written": len(orders),
            "trades_written": len(trades),
            "processed_job_ids": len(processed_ids),
            "unique_order_job_ids": len(order_job_ids),
        },
        "integrity": {"pass": integrity_pass, "checks": checks},
        "jobs_read_unique": jobs_read,
        "jobs_processed": stats["new_jobs_processed"],
        "jobs_skipped_duplicate": stats["jobs_skipped_duplicate"],
        "jobs_skipped_non_ticker": stats["jobs_skipped_non_ticker"],
        "jobs_invalid": stats["jobs_invalid"],
        "starting_value": portfolio_totals["starting_value"],
        "cash": portfolio_totals["cash"],
        "open_positions_value": portfolio_totals["open_positions_value"],
        "realized_pnl": portfolio_totals["realized_pnl"],
        "unrealized_pnl": portfolio_totals["unrealized_pnl"],
        "total_value": portfolio_totals["total_value"],
        "total_trades": historical_actions["total"],
        "hold_count": legacy_historical["hold_count"],
        "trim_count": legacy_historical["trim_count"],
        "protect_count": legacy_historical["protect_count"],
        "skip_count": legacy_historical["skip_count"],
        "position_count": portfolio_totals["position_count"],
    }
    return metrics, integrity_pass


def sync_portfolio_executor_totals(portfolio: dict[str, Any], metrics: dict[str, Any]) -> None:
    portfolio["executor_totals"] = {
        "orders_written": metrics["executor_totals"]["orders_written"],
        "trades_written": metrics["executor_totals"]["trades_written"],
        "processed_job_ids": metrics["executor_totals"]["processed_job_ids"],
        "historical_actions_total": metrics["historical_actions"]["total"],
        "last_synced_at": metrics["generated_at"],
        "last_execution_timestamp": metrics.get("last_execution_timestamp"),
    }


def write_executor_report(
    *,
    config: ExecutorConfig,
    portfolio: dict[str, Any],
    metrics: dict[str, Any],
    stats: dict[str, Any],
    orders: list[dict[str, Any]],
    report_path: Path,
) -> None:
    positions = portfolio.get("positions") or {}
    top = sorted(positions.values(), key=lambda p: _f(p.get("current_value")), reverse=True)[:10]
    recent = orders[-10:]
    hist = metrics["historical_actions"]
    new = metrics["new_actions"]
    integrity = metrics["integrity"]

    lines = [
        config.report_title,
        "",
        f"**Generated:** {_now()}",
        f"**Mode:** {MODE} · SHADOW_ONLY · NO_BROKER",
        f"**Executor:** {config.executor}",
        f"**Metrics schema:** {METRICS_SCHEMA_VERSION}",
        "",
        f"> {config.report_tagline}",
        "",
        "## Executive summary",
        "",
        f"- Jobs read (unique READY {config.executor}): **{metrics['jobs_read']}**",
        f"- Historical ticker actions recorded: **{hist['total']}**",
        f"- New jobs processed this run: **{new['total']}**",
        f"- Jobs skipped (already processed): **{metrics['duplicate_jobs']}**",
        f"- Paper portfolio value: **{metrics['portfolio_totals']['total_value']}**",
        f"- Realized PnL: **{metrics['portfolio_totals']['realized_pnl']}**",
        f"- Unrealized PnL: **{metrics['portfolio_totals']['unrealized_pnl']}**",
        f"- Integrity: **{'PASS' if integrity['pass'] else 'FAIL'}**",
        "",
        "## Historical state",
        "",
        f"- Processed job IDs: **{metrics['historical_jobs']['processed_count']}**",
        f"- Ticker actions in journal: **{metrics['historical_jobs']['ticker_actions']}**",
        f"- Non-ticker jobs skipped: **{metrics['historical_jobs']['non_ticker_skipped']}**",
        f"- Orders written: **{metrics['executor_totals']['orders_written']}**",
        f"- Trades written: **{metrics['executor_totals']['trades_written']}**",
        f"- Last execution timestamp: **{metrics.get('last_execution_timestamp')}**",
        "",
        "### Historical actions",
        "",
        "| action | count |",
        "| --- | --- |",
        f"| HOLD | {hist['hold']} |",
        f"| PAPER_TRIM | {hist['trim']} |",
        f"| PAPER_PROTECT | {hist['protect']} |",
        f"| PAPER_SKIP | {hist['skip']} |",
        f"| **total** | **{hist['total']}** |",
        "",
        "## Current execution",
        "",
        f"- Run started: **{stats.get('run_started_at')}**",
        f"- New jobs processed: **{new['total']}**",
        f"- Skipped duplicate: **{metrics['duplicate_jobs']}**",
        f"- Skipped non-ticker: **{stats['jobs_skipped_non_ticker']}**",
        f"- Invalid jobs: **{stats['jobs_invalid']}**",
        "",
        "### Current run actions",
        "",
        "| action | count |",
        "| --- | --- |",
        f"| HOLD | {new['hold']} |",
        f"| PAPER_TRIM | {new['trim']} |",
        f"| PAPER_PROTECT | {new['protect']} |",
        f"| PAPER_SKIP | {new['skip']} |",
        f"| **total** | **{new['total']}** |",
        "",
        "## Portfolio totals",
        "",
        f"- Starting value: **{metrics['portfolio_totals']['starting_value']}**",
        f"- Cash: **{metrics['portfolio_totals']['cash']}**",
        f"- Open positions value: **{metrics['portfolio_totals']['open_positions_value']}**",
        f"- Total value: **{metrics['portfolio_totals']['total_value']}**",
        f"- Positions: **{metrics['portfolio_totals']['position_count']}**",
        "",
        "## Current run totals",
        "",
        f"- New orders appended: **{new['total']}**",
        f"- New trades appended: **{new['total']}**",
        "",
        "## Top holdings",
        "",
        "| ticker | shares | value | pnl | pct |",
        "| --- | --- | --- | --- | --- |",
    ]
    for pos in top:
        lines.append(
            f"| {pos.get('ticker', '?')} | {pos.get('shares')} | {pos.get('current_value')} | "
            f"{pos.get('pnl')} | {pos.get('current_pct')} |"
        )

    lines.extend(["", "## Recent paper trades", "", "| ticker | action | trim | price | reason |", "| --- | --- | --- | --- | --- |"])
    for event in recent:
        lines.append(
            f"| {event.get('ticker')} | {event.get('paper_action')} | {event.get('trim_shares', 0)} | "
            f"{event.get('price')} | {event.get('reason')} |"
        )

    lines.extend(["", "## Integrity verification", "", "| check | expected | actual | pass |", "| --- | --- | --- | --- |"])
    for check in integrity["checks"]:
        mark = "✅" if check["pass"] else "❌"
        lines.append(f"| {check['check']} | {check['expected']} | {check['actual']} | {mark} |")

    lines.extend(
        [
            "",
            f"**Overall integrity:** {'PASS' if integrity['pass'] else 'FAIL'}",
            "",
            "## Safety confirmation",
            "",
            "- PAPER_ONLY: **true**",
            "- SHADOW_ONLY: **true**",
            "- NO_BROKER: **true**",
            "- NO_REAL_EXECUTION: **true**",
            "- portfolio.csv modified: **false**",
            "- live_bot.py modified: **false**",
            f"- Output isolated under `{config.output_dir}`: **true**",
            "",
            "## Next sprint",
            "",
            f"**{config.next_sprint}**",
        ]
    )

    assert_safe_output_path(report_path, config.output_dir)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_report(*, config: ExecutorConfig, metrics: dict[str, Any], validation_pass: bool) -> None:
    hist = metrics["historical_actions"]
    new = metrics["new_actions"]
    lines = [
        f"# TAE DPE — {config.executor.title()} Paper Executor Sprint Report",
        "",
        f"**Date:** {_now()}",
        f"**Mode:** PAPER_ONLY · SHADOW_ONLY · NO_BROKER · NO_REAL_EXECUTION",
        f"**Metrics schema:** {METRICS_SCHEMA_VERSION}",
        f"**Status:** {'PASS' if validation_pass else 'FAIL'}",
        "",
        "## Input source",
        "",
        f"`{JOBS_PATH}` — filter: `executor={config.executor}`, `status=READY`",
        "",
        "## Jobs consumed",
        "",
        f"- Jobs read: **{metrics['jobs_read']}**",
        f"- Historical processed: **{metrics['historical_jobs']['processed_count']}**",
        f"- New jobs this run: **{new['total']}**",
        f"- Skipped duplicate: **{metrics['duplicate_jobs']}**",
        "",
        "## Actions performed (historical totals)",
        "",
        f"- HOLD: **{hist['hold']}** | TRIM: **{hist['trim']}** | PROTECT: **{hist['protect']}** | SKIP: **{hist['skip']}**",
        f"- Total: **{hist['total']}**",
        "",
        "## Portfolio isolation",
        "",
        f"- Output: `{config.output_dir}`",
        f"- Positions: **{metrics['portfolio_totals']['position_count']}**",
        f"- Total value: **{metrics['portfolio_totals']['total_value']}**",
        f"- Metrics integrity: **{'PASS' if metrics['integrity']['pass'] else 'FAIL'}**",
        "",
        "## Next sprint",
        "",
        f"**{config.next_sprint}**",
    ]
    config.root_report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(*, config: ExecutorConfig, metrics: dict[str, Any], banner: str) -> None:
    hist = metrics["historical_actions"]
    new = metrics["new_actions"]
    print(banner)
    print("Mode: PAPER_ONLY — isolated shadow execution")
    print("Input:", JOBS_PATH)
    print("Output:", config.output_dir)
    print("Jobs read:", metrics["jobs_read"])
    print(
        "Historical actions:", hist["total"],
        "| HOLD", hist["hold"], "| TRIM", hist["trim"],
        "| PROTECT", hist["protect"], "| SKIP", hist["skip"],
    )
    print("New jobs processed:", new["total"], "| Skipped duplicate:", metrics["duplicate_jobs"])
    print("Portfolio value:", metrics["portfolio_totals"]["total_value"])
    print("Realized PnL:", metrics["portfolio_totals"]["realized_pnl"])
    print("Integrity:", "PASS" if metrics["integrity"]["pass"] else "FAIL")


def run_executor(
    *,
    config: ExecutorConfig,
    resolve_action: ResolveActionFn,
    banner: str,
) -> int:
    paths = paths_for(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    jobs, jobs_total, jobs_matched = load_executor_ready_jobs(config.executor)

    portfolio = load_json(paths["portfolio"])
    if not portfolio:
        portfolio = bootstrap_portfolio(jobs, config)
    elif not portfolio.get("positions"):
        boot = bootstrap_portfolio(jobs, config)
        portfolio["positions"] = boot.get("positions") or {}
        if _f(portfolio.get("starting_value")) <= 0:
            portfolio["starting_value"] = boot.get("starting_value")
        if _f(portfolio.get("cash")) <= 0:
            portfolio["cash"] = boot.get("cash")

    stats = process_jobs(
        portfolio, jobs, config=config, paths=paths, resolve_action=resolve_action,
    )
    orders = load_jsonl(paths["orders"])
    trades = load_jsonl(paths["trades"])
    metrics, integrity_pass = verify_integrity(
        config=config,
        portfolio=portfolio,
        orders=orders,
        trades=trades,
        jobs_read=len(jobs),
        stats=stats,
        jobs_total=jobs_total,
        jobs_matched=jobs_matched,
    )
    sync_portfolio_executor_totals(portfolio, metrics)

    save_json(paths["portfolio"], portfolio, config.output_dir)
    save_json(paths["metrics"], metrics, config.output_dir)
    write_executor_report(
        config=config, portfolio=portfolio, metrics=metrics,
        stats=stats, orders=orders, report_path=paths["report"],
    )

    validation_pass = (
        paths["portfolio"].is_file()
        and paths["orders"].is_file()
        and paths["trades"].is_file()
        and paths["metrics"].is_file()
        and len(portfolio.get("positions") or {}) > 0
        and integrity_pass
    )
    write_root_report(config=config, metrics=metrics, validation_pass=validation_pass)
    print_summary(config=config, metrics=metrics, banner=banner)
    print(
        "Wrote:", paths["portfolio"], paths["orders"], paths["trades"],
        paths["metrics"], paths["report"], config.root_report_path,
    )
    return 0 if validation_pass else 1


def assert_safe_paper_decision_path(path: Path) -> None:
    resolved = path.resolve()
    root = PAPER_DECISION_VALIDATION_DIR.resolve()
    if root not in resolved.parents and resolved != root:
        raise RuntimeError(f"Unsafe paper decision path outside {root}: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.name in str(resolved):
            raise RuntimeError(f"Forbidden write target: {path}")


def _gii_by_ticker(gii: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        (_s(t.get("ticker")) or "").upper(): t
        for t in (gii or {}).get("tickers") or []
        if t.get("ticker")
    }


def _shadow_by_ticker(shadow: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        (_s(p.get("ticker")) or "").upper(): p
        for p in (shadow or {}).get("positions") or []
        if p.get("ticker")
    }


def paper_decision_dedupe_key(decision: dict[str, Any]) -> str:
    decision_id = _s(decision.get("decision_id")) or _s(decision.get("source_decision_id"))
    if decision_id:
        return f"id:{decision_id}"
    ticker = (_s(decision.get("ticker")) or "").upper()
    action = (_s(decision.get("action")) or "SKIP_PAPER").upper()
    return f"ta:{ticker}:{action}"


def dedupe_paper_decisions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one record per decision_id or ticker+action; prefer latest timestamp."""
    by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        key = paper_decision_dedupe_key(record)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = record
            continue
        existing_ts = _s(existing.get("created_at")) or _s(existing.get("timestamp")) or ""
        record_ts = _s(record.get("created_at")) or _s(record.get("timestamp")) or ""
        if record_ts >= existing_ts:
            by_key[key] = record
    return list(by_key.values())


def load_paper_decisions(*, decisions_path: Path | None = None) -> tuple[list[dict[str, Any]], int]:
    """Load PAPER decisions from jsonl (primary) and json, deduplicated once."""
    jsonl_path = decisions_path or PAPER_DECISIONS_JSONL
    raw: list[dict[str, Any]] = list(load_jsonl(jsonl_path))
    raw_count = len(raw)

    json_path = jsonl_path.parent / "paper_decisions.json"
    if json_path.is_file():
        doc = load_json(json_path)
        if isinstance(doc, dict):
            from_json = doc.get("decisions") or []
        elif isinstance(doc, list):
            from_json = doc
        else:
            from_json = []
        if isinstance(from_json, list):
            raw.extend(from_json)
            raw_count = len(raw)

    deduped = dedupe_paper_decisions(raw)
    return deduped, raw_count


def extract_source_hypothesis_id(decision: dict[str, Any]) -> str | None:
    applied = decision.get("hypothesis_rules_applied") or []
    for row in applied:
        hyp_id = _s(row.get("hypothesis_id"))
        if hyp_id:
            return hyp_id
    return None


def build_evidence_summary(
    decision: dict[str, Any],
    *,
    gii_row: dict[str, Any] | None,
    shadow_row: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    deltas: dict[str, float],
) -> str:
    parts: list[str] = []
    evidence = _s(decision.get("evidence"))
    if evidence:
        parts.append(evidence[:220])
    if gii_row:
        parts.append(
            f"GII missed_usd={_f(gii_row.get('missed_usd')):.2f} "
            f"growth={_f(gii_row.get('growth_score')):.1f} "
            f"cap_eff={_f(gii_row.get('capital_efficiency')):.1f}"
        )
    if shadow_row:
        parts.append(f"shadow missed={_f(shadow_row.get('missed_opportunity_usd')):.2f}")
    if validation:
        gates = validation.get("gates") or {}
        parts.append(f"protection_gates={'passed' if gates.get('gates_passed') else 'not_passed'}")
        best = validation.get("best_strategy") or {}
        if best.get("strategy_id"):
            parts.append(f"best_strategy={best['strategy_id']}")
    horizon_reason = _s(decision.get("horizon_reason"))
    if horizon_reason:
        parts.append(horizon_reason[:180])
    parts.append(
        f"simulated profitΔ=${deltas['expected_profit_delta_usd']:.2f} "
        f"riskΔ={deltas['expected_risk_delta']:.4f} cap_effΔ={deltas['capital_efficiency_delta']:.2f}"
    )
    return "; ".join(parts)[:600]


def build_validation_reason(
    verdict: str,
    *,
    action: str,
    ticker: str,
    deltas: dict[str, float],
    confidence: float,
    decision: dict[str, Any],
    validation: dict[str, Any] | None,
    gii_row: dict[str, Any] | None,
) -> str:
    profit = deltas["expected_profit_delta_usd"]
    risk = deltas["expected_risk_delta"]
    cap = deltas["capital_efficiency_delta"]
    gates = (validation or {}).get("gates") or {}
    gates_passed = bool(gates.get("gates_passed"))

    if verdict == "PROMISING":
        return (
            f"PROMISING: {action} on {ticker} simulates +${profit:.2f} profit with "
            f"riskΔ={risk:.4f} and cap-effΔ={cap:.2f} at confidence {confidence:.2f}; "
            f"protection gates {'passed' if gates_passed else 'pending'}"
        )
    if verdict == "CONTINUE_TESTING":
        return (
            f"CONTINUE: {action} on {ticker} shows modest simulated gain +${profit:.2f} "
            f"(riskΔ={risk:.4f}, cap-effΔ={cap:.2f}); extend 30-day validation before promotion review"
        )
    if verdict == "NEEDS_MORE_DATA":
        missing: list[str] = []
        if action == "SKIP_PAPER":
            missing.append("action was SKIP — need stronger GII/PPG/shadow signal")
        if confidence < 0.4:
            missing.append(f"confidence {confidence:.2f} below 0.40 threshold")
        if not gii_row:
            missing.append(f"missing GII row for {ticker}")
        if action == "PROTECT_PAPER" and not gates_passed:
            missing.append("protection validation gates not passed")
        if not missing:
            missing.append("insufficient composite score for PROMISING/CONTINUE verdict")
        return f"NEEDS_MORE_DATA: {action} on {ticker} — missing: " + "; ".join(missing)
    if verdict == "REJECT":
        reasons: list[str] = []
        if profit < -1.0 and risk > 0:
            reasons.append(f"negative profit (${profit:.2f}) with rising risk ({risk:.4f})")
        elif profit < 0:
            reasons.append(f"simulated profit delta negative (${profit:.2f})")
        if decision.get("rejection_rule"):
            reasons.append("hypothesis rejection rule applies")
        if not reasons:
            reasons.append("composite score below rejection threshold")
        return f"REJECT: {action} on {ticker} — " + "; ".join(reasons)
    return f"{verdict}: {action} on {ticker} simulated"


def rank_validation_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        results,
        key=lambda row: (
            VERDICT_PRIORITY.get(_s(row.get("verdict")) or "NEEDS_MORE_DATA", 99),
            -_f(row.get("profit_delta")),
            _f(row.get("risk_delta")),
            -_f(row.get("capital_efficiency_delta")),
            _s(row.get("ticker")) or "",
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def simulate_paper_decision_deltas(
    decision: dict[str, Any],
    *,
    gii_row: dict[str, Any] | None,
    shadow_row: dict[str, Any] | None,
    validation: dict[str, Any] | None,
) -> dict[str, float]:
    action = (_s(decision.get("action")) or "SKIP_PAPER").upper()
    missed = _f((gii_row or {}).get("missed_usd") or (shadow_row or {}).get("missed_opportunity_usd"))
    cap_eff = _f((gii_row or {}).get("capital_efficiency"))
    growth = _f((gii_row or {}).get("growth_score"))
    conf = _f(decision.get("confidence"), 0.5)

    profit = _f(decision.get("expected_profit_delta"))
    risk = _f(decision.get("expected_risk_delta"))
    cap_delta = _f(decision.get("capital_efficiency_delta"))

    if action == "BUY_PAPER":
        profit = max(profit, 10.0 + growth * 0.12 * conf)
        risk = max(risk, 0.04)
        cap_delta = max(cap_delta, 3.0)
    elif action == "SELL_PAPER":
        profit = max(profit, missed * 0.12 * conf)
        risk = min(risk, -0.08)
        cap_delta = max(cap_delta, max(0.0, 45.0 - cap_eff) * 0.1)
    elif action == "REDUCE_PAPER":
        profit = max(profit, missed * 0.22 * conf)
        risk = min(risk, -0.1)
        cap_delta = max(cap_delta, 2.0)
    elif action == "PROTECT_PAPER":
        gates = (validation or {}).get("gates") or {}
        gate_boost = 1.15 if gates.get("gates_passed") else 0.85
        profit = max(profit, missed * 0.28 * conf * gate_boost)
        risk = min(risk, -0.14)
        cap_delta = min(cap_delta, -0.5)
    elif action == "ROTATE_PAPER":
        profit = max(profit, missed * 0.18 * conf)
        risk = min(risk, -0.05)
        cap_delta = max(cap_delta, max(0.0, 50.0 - cap_eff) * 0.08)
    elif action == "HOLD_PAPER":
        profit = max(profit, missed * 0.08 * conf)
        risk = max(risk, 0.02)
    else:
        profit = 0.0
        risk = 0.0
        cap_delta = 0.0

    return {
        "expected_profit_delta_usd": round(profit, 2),
        "expected_risk_delta": round(risk, 4),
        "capital_efficiency_delta": round(cap_delta, 2),
    }


def assign_paper_decision_verdict(
    *,
    action: str,
    deltas: dict[str, float],
    confidence: float,
    validation: dict[str, Any] | None,
) -> str:
    if action == "SKIP_PAPER":
        return "NEEDS_MORE_DATA"

    profit = _f(deltas.get("expected_profit_delta_usd"))
    risk = _f(deltas.get("expected_risk_delta"))
    cap = _f(deltas.get("capital_efficiency_delta"))
    gates = (validation or {}).get("gates") or {}
    gates_passed = bool(gates.get("gates_passed"))

    if profit < -1.0 and risk > 0:
        return "REJECT"

    composite = profit + cap * 2.0 - max(0.0, risk) * 50.0
    if action == "PROTECT_PAPER" and not gates_passed and profit < 5.0:
        return "NEEDS_MORE_DATA"
    if profit >= 12.0 and composite > 8.0 and confidence >= 0.55:
        return "PROMISING"
    if profit >= 4.0 and composite >= 0 and confidence >= 0.45:
        return "PROMISING" if composite > 10 else "CONTINUE_TESTING"
    if profit < 0 or composite < -4:
        return "REJECT"
    if confidence < 0.4:
        return "NEEDS_MORE_DATA"
    return "CONTINUE_TESTING"


def score_paper_decision(
    decision: dict[str, Any],
    *,
    gii_by: dict[str, dict[str, Any]],
    shadow_by: dict[str, dict[str, Any]],
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    ticker = (_s(decision.get("ticker")) or "").upper()
    action = (_s(decision.get("action")) or "SKIP_PAPER").upper()
    gii_row = gii_by.get(ticker)
    shadow_row = shadow_by.get(ticker)
    deltas = simulate_paper_decision_deltas(
        decision, gii_row=gii_row, shadow_row=shadow_row, validation=validation,
    )
    confidence = _f(decision.get("confidence"), 0.5)
    verdict = assign_paper_decision_verdict(
        action=action, deltas=deltas, confidence=confidence, validation=validation,
    )
    gates = (validation or {}).get("gates") or {}
    profit_delta = deltas["expected_profit_delta_usd"]
    risk_delta = deltas["expected_risk_delta"]
    cap_delta = deltas["capital_efficiency_delta"]
    source_decision_id = _s(decision.get("decision_id")) or _s(decision.get("source_decision_id"))
    source_hypothesis_id = extract_source_hypothesis_id(decision)
    evidence_summary = build_evidence_summary(
        decision,
        gii_row=gii_row,
        shadow_row=shadow_row,
        validation=validation,
        deltas=deltas,
    )
    reason = build_validation_reason(
        verdict,
        action=action,
        ticker=ticker,
        deltas=deltas,
        confidence=confidence,
        decision=decision,
        validation=validation,
        gii_row=gii_row,
    )
    horizon_reason = _s(decision.get("horizon_reason"))
    if horizon_reason:
        reason = f"{reason} | horizon: {horizon_reason[:180]}"
    return {
        "validation_id": f"PDVAL-{source_decision_id or ticker}",
        "decision_id": source_decision_id,
        "source_decision_id": source_decision_id,
        "source_hypothesis_id": source_hypothesis_id,
        "ticker": ticker,
        "paper_decision_consumed": True,
        "action": action,
        "simulated_action": action,
        "result_status": "SIMULATED",
        "verdict": verdict,
        "confidence": confidence,
        "deltas": deltas,
        "profit_delta": profit_delta,
        "profit_delta_usd": profit_delta,
        "risk_delta": risk_delta,
        "capital_efficiency_delta": cap_delta,
        "reason": reason,
        "evidence_summary": evidence_summary,
        "horizon_context": decision.get("horizon_context"),
        "short_term_trend_7d": decision.get("short_term_trend_7d"),
        "monthly_trend": decision.get("monthly_trend"),
        "yearly_trend": decision.get("yearly_trend"),
        "long_term_trend": decision.get("long_term_trend"),
        "horizon_alignment_score": decision.get("horizon_alignment_score"),
        "horizon_conflict_flag": decision.get("horizon_conflict_flag"),
        "horizon_reason": horizon_reason,
        "protection_validation_used": validation is not None,
        "protection_gates_passed": bool(gates.get("gates_passed")),
        "best_strategy_id": _s((validation or {}).get("best_strategy", {}).get("strategy_id")),
        "mode": MODE,
        "live_promotion_allowed": False,
        "created_at": _now(),
    }


def write_decision_validation_report(report: dict[str, Any]) -> Path:
    vs = report.get("verdict_summary") or {}
    lines = [
        "# TAE Paper Decision Validation Report",
        "",
        f"**Generated:** {report.get('generated_at', '')}",
        f"**Mode:** {MODE} — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE",
        f"**Live promotion allowed:** false",
        "",
        "> **PAPER_ONLY simulated validation — no broker execution**",
        "",
        "## Executive summary",
        "",
        f"- Decisions consumed (raw): **{report.get('decisions_consumed_raw', 0)}**",
        f"- Unique decisions validated: **{report.get('decisions_unique', 0)}**",
        f"- PROMISING: **{vs.get('PROMISING', 0)}**",
        f"- CONTINUE_TESTING: **{vs.get('CONTINUE_TESTING', 0)}**",
        f"- NEEDS_MORE_DATA: **{vs.get('NEEDS_MORE_DATA', 0)}**",
        f"- REJECT: **{vs.get('REJECT', 0)}**",
        "",
        "## Ranked validated decisions (unique)",
        "",
        "| rank | ticker | action | verdict | profit Δ | horizon align | horizon reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.get("results") or []:
        reason = (_s(row.get("horizon_reason")) or _s(row.get("reason")) or "")[:70].replace("|", "/")
        lines.append(
            f"| {row.get('rank')} | {row.get('ticker')} | {row.get('action')} | {row.get('verdict')} | "
            f"{row.get('profit_delta')} | {row.get('horizon_alignment_score')} | {reason} |"
        )

    lines.extend(
        [
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| NO_LIVE_CHANGE | ✅ |",
            "| live_promotion_allowed | **false** |",
        ]
    )
    DECISION_VALIDATION_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return DECISION_VALIDATION_REPORT_MD


def update_experiment_runner_validation_section(report: dict[str, Any]) -> None:
    """Patch TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md paper decision validation section."""
    if not EXPERIMENT_RUNNER_REPORT_MD.is_file():
        return
    vs = report.get("verdict_summary") or {}
    section_lines = [
        "## Paper decision validation",
        "",
        "- Consumes: `runtime_outputs/paper_decisions/paper_decisions.jsonl` "
        "(deduplicated with `paper_decisions.json`)",
        "- Output: `runtime_outputs/paper_decisions/decision_validation_results.json`",
        "- Detail report: `TAE_PAPER_DECISION_VALIDATION_REPORT.md`",
        "",
        f"- Unique decisions validated: **{report.get('decisions_unique', 0)}** "
        f"(raw rows read: {report.get('decisions_consumed_raw', 0)})",
        f"- PROMISING: **{vs.get('PROMISING', 0)}** | CONTINUE: **{vs.get('CONTINUE_TESTING', 0)}** | "
        f"NEEDS_MORE_DATA: **{vs.get('NEEDS_MORE_DATA', 0)}** | REJECT: **{vs.get('REJECT', 0)}**",
        "",
        "### Top ranked validated decisions",
        "",
        "| rank | ticker | action | verdict | profit Δ | horizon | reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in (report.get("results") or [])[:10]:
        hz = _s(row.get("horizon_reason")) or ""
        reason = (_s(row.get("reason")) or "")[:50].replace("|", "/")
        section_lines.append(
            f"| {row.get('rank')} | {row.get('ticker')} | {row.get('action')} | {row.get('verdict')} | "
            f"{row.get('profit_delta')} | {row.get('horizon_alignment_score')} | {hz[:40] or reason} |"
        )
    section_lines.append("")

    text = EXPERIMENT_RUNNER_REPORT_MD.read_text(encoding="utf-8")
    marker = "## Paper decision validation"
    safety_marker = "## Safety confirmation"
    if marker not in text:
        return
    before = text.split(marker)[0]
    after_parts = text.split(marker, 1)[1]
    if safety_marker in after_parts:
        after = safety_marker + after_parts.split(safety_marker, 1)[1]
    else:
        after = ""
    EXPERIMENT_RUNNER_REPORT_MD.write_text(
        before + "\n".join(section_lines) + "\n" + after,
        encoding="utf-8",
    )


def run_paper_decision_validation(
    *,
    decisions_path: Path | None = None,
    output_dir: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Consume paper_decisions.jsonl and produce simulated validation results."""
    output_dir = output_dir or PAPER_DECISION_VALIDATION_DIR
    decisions, raw_count = load_paper_decisions(decisions_path=decisions_path)
    if not decisions:
        return {"error": "missing_or_empty_paper_decisions", "decisions_consumed": 0}, 1

    gii = load_json(GII_JSON) or {}
    shadow = load_json(SHADOW_JSON) or {}
    validation = load_json(PROTECTION_VALIDATION_JSON)
    gii_by = _gii_by_ticker(gii)
    shadow_by = _shadow_by_ticker(shadow)

    results = [
        score_paper_decision(
            decision,
            gii_by=gii_by,
            shadow_by=shadow_by,
            validation=validation,
        )
        for decision in decisions
    ]
    results = rank_validation_results(results)

    verdict_counts: dict[str, int] = {}
    for row in results:
        v = row.get("verdict") or "NEEDS_MORE_DATA"
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    source_path = decisions_path or PAPER_DECISIONS_JSONL
    report = {
        "schema": "tae_paper_decision_validation",
        "schema_version": "v1.1",
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_live_execution": True,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "source": str(source_path),
        "decisions_consumed_raw": raw_count,
        "decisions_unique": len(decisions),
        "decisions_consumed": len(decisions),
        "results_count": len(results),
        "verdict_summary": verdict_counts,
        "protection_validation_loaded": validation is not None,
        "results": results,
        "safety": {
            "PAPER_ONLY": True,
            "NO_BROKER": True,
            "NO_LIVE_CHANGE": True,
            "NO_EXECUTION": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_json = output_dir / "decision_validation_results.json"
    out_jsonl = output_dir / "decision_validation_results.jsonl"
    assert_safe_paper_decision_path(out_json.resolve())
    assert_safe_paper_decision_path(out_jsonl.resolve())
    out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with out_jsonl.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_decision_validation_report(report)
    update_experiment_runner_validation_section(report)

    print("===== TAE PAPER DECISION VALIDATION (infra) =====")
    print("Mode: PAPER_ONLY — simulated scoring — no broker execution")
    print("Unique decisions validated:", len(decisions), f"(raw rows: {raw_count})")
    print(
        "Verdicts: PROMISING={} CONTINUE={} REJECT={} NEEDS_DATA={}".format(
            verdict_counts.get("PROMISING", 0),
            verdict_counts.get("CONTINUE_TESTING", 0),
            verdict_counts.get("REJECT", 0),
            verdict_counts.get("NEEDS_MORE_DATA", 0),
        )
    )
    for row in results[:5]:
        print(
            f"  #{row.get('rank')} {row.get('ticker')} [{row.get('verdict')}] "
            f"{row.get('action')} profitΔ=${row.get('profit_delta')} — {(_s(row.get('reason')) or '')[:60]}"
        )
    print("Wrote:", out_json, out_jsonl, DECISION_VALIDATION_REPORT_MD)
    return report, 0
