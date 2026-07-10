#!/usr/bin/env python3
"""
TAE DPE-2 — Execution Splitter — SHADOW_ONLY / READ_ONLY.

Routes Decision Events into isolated Competitive and Collaborative execution jobs.
Does NOT execute trades, alter decisions, or modify live behavior.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dpe.execution_job.v1"
MODE = "SHADOW_ONLY"
SOURCE = "tae_execution_splitter"
EVENT_ORIGIN = "SHADOW"

DECISION_EVENTS = Path("runtime_outputs/dpe/decision_events.jsonl")
JOBS_LOG = Path("runtime_outputs/dpe/execution_jobs.jsonl")
DPE_DIR = Path("runtime_outputs/dpe")
OUTPUT_MD = Path("tae_execution_splitter.md")
OUTPUT_JSON = Path("tae_execution_splitter.json")

GII_JSON = Path("tae_growth_intelligence.json")
GROWTH_ANALYTICS_JSON = Path("tae_profit_growth_analytics.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
TARGET_JSON = Path("tae_profit_target_adapter.json")
PHILOSOPHY_JSON = Path("tae_market_philosophy_lab.json")

EXECUTORS = ("COMPETITIVE", "COLLABORATIVE")
STATUSES = ("QUEUED", "READY", "BLOCKED", "INVALID")

UPSTREAM_REUSE = [
    "runtime_outputs/dpe/decision_events.jsonl — parent Decision Events (DPE-1)",
    "tae_growth_intelligence.json — growth_phase, portfolio policy context",
    "tae_profit_growth_analytics.json — market_regime hints, core metrics",
    "tae_adaptive_profit_policy_engine.json — policy_state enrichment",
    "tae_portfolio_profit_governor.json — portfolio_policy in decision_context",
    "tae_profit_target_adapter.json — target_snapshot passthrough",
    "tae_market_philosophy_lab.json — philosophy_snapshot passthrough",
]

NOT_DUPLICATED = (
    "Does not recompute GII scores, profit targets, philosophy models, accounting, "
    "or protection logic. Maps existing Decision Event snapshots into dual routing jobs only."
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_job_id(parent_event_id: str, executor: str) -> str:
    raw = f"{parent_event_id}|{executor}|{SCHEMA_VERSION}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{parent_event_id}_{executor}_{digest}"


def decision_uuid_for_event(parent_event_id: str) -> str:
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(namespace, f"{parent_event_id}|dpe.decision"))


def experiment_id_for_batch(events: list[dict[str, Any]]) -> str:
    if not events:
        return "EXP000001"
    timestamps = sorted({_s(e.get("timestamp")) or "" for e in events})
    key = timestamps[-1][:10].replace("-", "") if timestamps[-1] else "000001"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    num = int(digest[:6], 16) % 999999 + 1
    return f"EXP{num:06d}"


def load_decision_events() -> tuple[list[dict[str, Any]], bool, str | None]:
    if not DECISION_EVENTS.is_file():
        return [], False, "runtime_outputs/dpe/decision_events.jsonl missing — run DPE-1 first"
    by_id: dict[str, dict[str, Any]] = {}
    try:
        for line in DECISION_EVENTS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            eid = _s(event.get("event_id"))
            if eid:
                by_id[eid] = event
    except (json.JSONDecodeError, OSError) as exc:
        return [], True, f"failed to parse decision_events.jsonl: {exc}"
    return list(by_id.values()), True, None


def load_artifact_sources() -> tuple[dict[str, bool], list[str]]:
    paths = {
        "tae_growth_intelligence.json": GII_JSON,
        "tae_profit_growth_analytics.json": GROWTH_ANALYTICS_JSON,
        "tae_adaptive_profit_policy_engine.json": APPE_JSON,
        "tae_portfolio_profit_governor.json": PPG_JSON,
        "tae_profit_target_adapter.json": TARGET_JSON,
        "tae_market_philosophy_lab.json": PHILOSOPHY_JSON,
        "runtime_outputs/dpe/decision_events.jsonl": DECISION_EVENTS,
    }
    loaded: dict[str, bool] = {}
    missing: list[str] = []
    for name, path in paths.items():
        ok = path.is_file()
        loaded[name] = ok
        if not ok:
            missing.append(name)
    return loaded, missing


def decision_context_from_artifacts(
    event: dict[str, Any],
    gii: dict[str, Any] | None,
    analytics: dict[str, Any] | None,
    ppg: dict[str, Any] | None,
) -> dict[str, Any]:
    gii_port = (gii or {}).get("portfolio") or {}
    analytics_ctx = (analytics or {}).get("portfolio_policy_context") or {}
    ppg_summary = (ppg or {}).get("summary") or {}
    growth = event.get("growth_snapshot") or {}
    policy = event.get("portfolio_policy_snapshot") or {}

    return {
        "market_regime": _s(
            (gii or {}).get("global_verdict")
            or analytics_ctx.get("market_regime")
            or analytics_ctx.get("regime")
        ),
        "market_session": _s(event.get("market_session_state")),
        "volatility": _s(gii_port.get("growth_risk") or analytics_ctx.get("volatility")),
        "breadth": _s(analytics_ctx.get("breadth") or (analytics or {}).get("core_metrics", {}).get("breadth")),
        "portfolio_policy": _s(policy.get("portfolio_target_policy") or policy.get("policy_state")),
        "growth_phase": _s(growth.get("lifecycle_stage") or gii_port.get("growth_maturity_pct")),
    }


def infer_decision_reason(event: dict[str, Any]) -> str:
    growth = event.get("growth_snapshot") or {}
    phil = event.get("philosophy_snapshot") or {}
    policy = event.get("portfolio_policy_snapshot") or {}
    strategy = (_s(growth.get("recommended_shadow_strategy")) or "").upper()

    collapse = _f(growth.get("collapse_probability")) or 0.0
    growth_score = _f(growth.get("growth_score")) or 0.0
    harmony = _f(phil.get("market_harmony_score")) or 0.0
    policy_state = (_s(policy.get("policy_state")) or "").upper()

    if collapse >= 0.5:
        return "COLLAPSE_RISK"
    if "CAPITAL_PRESERVATION" in (_s(policy.get("suggested_shadow_policy")) or "").upper():
        return "DEFENSIVE_POLICY"
    if harmony >= 60:
        return "MARKET_HARMONY"
    if growth_score >= 70 or "KEEP_GROWING" in strategy:
        return "HIGH_GROWTH"
    if "KEEP" in strategy or "MONITOR" in strategy or "HOLD" in strategy:
        return "KEEP_WINNER"
    if policy_state in {"HIGH_RISK", "CRITICAL"}:
        return "DEFENSIVE_POLICY"
    return "KEEP_WINNER"


def action_candidate_from_event(event: dict[str, Any], executor: str) -> str:
    strategy = (_s((event.get("growth_snapshot") or {}).get("recommended_shadow_strategy")) or "").upper()
    signal = (_s((event.get("signal_snapshot") or {}).get("signal")) or "").upper()
    mapping = {
        "KEEP_GROWING_SHADOW": "HOLD_WINNER",
        "HOLD_AND_MONITOR_SHADOW": "MONITOR",
        "PROTECT_PROFIT_SHADOW": "PROTECT",
        "TIGHTEN_TRAIL_SHADOW": "TRIM_TRAIL",
        "REDUCE_EXPOSURE_SHADOW": "REDUCE",
    }
    for key, action in mapping.items():
        if key in strategy:
            return action
    if "SELL" in signal:
        return "EXIT_CANDIDATE"
    if "BUY" in signal:
        return "ENTRY_CANDIDATE" if executor == "COMPETITIVE" else "ACCUMULATE_CANDIDATE"
    return "ROUTE_ONLY"


def market_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    price = event.get("price_snapshot") or {}
    signal = event.get("signal_snapshot") or {}
    return {
        "market_session_state": _s(event.get("market_session_state")),
        "current_price": _f(price.get("current_price")),
        "high_pct": _f(price.get("high_pct")),
        "drawdown_pct": _f(price.get("drawdown_pct")),
        "signal": _s(signal.get("signal")),
        "signal_score": _f(signal.get("score")),
        "rsi": _f(signal.get("rsi")),
    }


def portfolio_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    pos = event.get("position_snapshot") or {}
    acct = event.get("account_snapshot") or {}
    return {
        "shares": _f(pos.get("shares")),
        "avg_price": _f(pos.get("avg_price")),
        "current_price": _f(pos.get("current_price")),
        "current_pct": _f(pos.get("current_pct")),
        "current_value": _f(pos.get("current_value")),
        "pnl": _f(pos.get("pnl")),
        "status": _s(pos.get("status")),
        "account_value_corrected": _f(acct.get("account_value_corrected")),
        "cash_available": _f(acct.get("cash_available")),
    }


def policy_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    policy = event.get("portfolio_policy_snapshot") or {}
    risk = event.get("risk_snapshot") or {}
    return {
        "portfolio_verdict": _s(policy.get("portfolio_verdict")),
        "policy_state": _s(policy.get("policy_state")),
        "suggested_shadow_policy": _s(policy.get("suggested_shadow_policy")),
        "portfolio_target_policy": _s(policy.get("portfolio_target_policy")),
        "governor_recommendation": _s(risk.get("governor_recommendation")),
        "pce_verdict": _s(risk.get("pce_verdict")),
        "opportunity_cost_total": _f(risk.get("opportunity_cost_total")),
    }


def validate_event(event: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for field in ("event_id", "timestamp", "event_type", "ticker", "schema_version"):
        if not _s(event.get(field)):
            missing.append(field)
    if _s(event.get("schema_version")) != "dpe.decision_event.v1":
        missing.append("schema_version_mismatch")
    return len(missing) == 0, missing


def job_status(
    event: dict[str, Any],
    executor: str,
    valid: bool,
    missing_fields: list[str],
) -> str:
    if not valid:
        return "INVALID"
    phil = event.get("philosophy_snapshot") or {}
    pref = (_s(phil.get("philosophy_preference")) or "").upper()
    policy = event.get("portfolio_policy_snapshot") or {}
    verdict = (_s(policy.get("portfolio_verdict")) or "").upper()

    if executor == "COMPETITIVE" and pref == "AVOID":
        return "BLOCKED"
    if executor == "COLLABORATIVE" and pref == "AVOID" and "REDUCE" in (
        _s((event.get("growth_snapshot") or {}).get("recommended_shadow_strategy")) or ""
    ).upper():
        return "BLOCKED"
    if verdict == "PORTFOLIO_CRITICAL":
        return "BLOCKED"

    required_groups = (
        "growth_snapshot",
        "target_snapshot",
        "philosophy_snapshot",
        "portfolio_policy_snapshot",
    )
    for group in required_groups:
        if not isinstance(event.get(group), dict):
            missing_fields.append(group)
            return "INVALID"

    snapshots = [
        event.get("growth_snapshot"),
        event.get("target_snapshot"),
        event.get("philosophy_snapshot"),
        event.get("portfolio_policy_snapshot"),
    ]
    has_data = any(
        any(v is not None for v in (snap or {}).values()) for snap in snapshots if isinstance(snap, dict)
    )
    if not has_data:
        return "QUEUED"
    if missing_fields:
        return "QUEUED"
    return "READY"


def split_event(
    event: dict[str, Any],
    experiment_id: str,
    gii: dict[str, Any] | None,
    analytics: dict[str, Any] | None,
    ppg: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    valid, missing = validate_event(event)
    parent_id = _s(event.get("event_id")) or "UNKNOWN"
    decision_uuid = decision_uuid_for_event(parent_id)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ticker = _s(event.get("ticker")) or "UNKNOWN"
    reason = infer_decision_reason(event)
    context = decision_context_from_artifacts(event, gii, analytics, ppg)

    jobs: list[dict[str, Any]] = []
    for executor in EXECUTORS:
        status = job_status(event, executor, valid, list(missing))
        jobs.append(
            {
                "job_id": stable_job_id(parent_id, executor),
                "decision_uuid": decision_uuid,
                "experiment_id": experiment_id,
                "parent_event_id": parent_id,
                "timestamp": timestamp,
                "executor": executor,
                "ticker": ticker,
                "action_candidate": action_candidate_from_event(event, executor),
                "event_origin": EVENT_ORIGIN,
                "decision_reason": reason,
                "decision_context": context,
                "market_snapshot": market_snapshot(event),
                "portfolio_snapshot": portfolio_snapshot(event),
                "growth_snapshot": dict(event.get("growth_snapshot") or {}),
                "target_snapshot": dict(event.get("target_snapshot") or {}),
                "policy_snapshot": policy_snapshot(event),
                "philosophy_snapshot": dict(event.get("philosophy_snapshot") or {}),
                "status": status,
                "schema_version": SCHEMA_VERSION,
                "source": SOURCE,
                "mode": MODE,
                "parent_event_type": _s(event.get("event_type")),
            }
        )
    return jobs, missing


def split_all_events(
    events: list[dict[str, Any]],
    gii: dict[str, Any] | None,
    analytics: dict[str, Any] | None,
    ppg: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    experiment_id = experiment_id_for_batch(events)
    all_jobs: list[dict[str, Any]] = []
    all_missing: set[str] = set()
    for event in events:
        jobs, missing = split_event(event, experiment_id, gii, analytics, ppg)
        all_jobs.extend(jobs)
        all_missing.update(missing)
    return all_jobs, {
        "experiment_id": experiment_id,
        "missing_event_fields": sorted(all_missing),
    }


def append_jobs(jobs: list[dict[str, Any]]) -> tuple[int, int, set[str]]:
    DPE_DIR.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if JOBS_LOG.is_file():
        try:
            for line in JOBS_LOG.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                jid = _s(row.get("job_id"))
                if jid:
                    existing.add(jid)
        except (json.JSONDecodeError, OSError):
            pass
    seen: set[str] = set()
    written = 0
    skipped = 0
    with JOBS_LOG.open("a", encoding="utf-8") as handle:
        for job in jobs:
            jid = job["job_id"]
            if jid in seen or jid in existing:
                skipped += 1
                continue
            seen.add(jid)
            handle.write(json.dumps(job, separators=(",", ":")) + "\n")
            written += 1
    return written, skipped, seen


def compute_metrics(jobs: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    competitive = [j for j in jobs if j["executor"] == "COMPETITIVE"]
    collaborative = [j for j in jobs if j["executor"] == "COLLABORATIVE"]
    blocked = [j for j in jobs if j["status"] == "BLOCKED"]
    job_ids = [j["job_id"] for j in jobs]
    duplicate_jobs = len(job_ids) - len(set(job_ids))

    uuid_counts: dict[str, int] = {}
    for job in jobs:
        uid = job["decision_uuid"]
        uuid_counts[uid] = uuid_counts.get(uid, 0) + 1
    # Each decision event should produce exactly one UUID shared by two executor jobs.
    duplicate_uuid_anomalies = sum(1 for count in uuid_counts.values() if count != 2)

    return {
        "total_events": len(events),
        "competitive_jobs": len(competitive),
        "collaborative_jobs": len(collaborative),
        "blocked_jobs": len(blocked),
        "ready_jobs": sum(1 for j in jobs if j["status"] == "READY"),
        "queued_jobs": sum(1 for j in jobs if j["status"] == "QUEUED"),
        "invalid_jobs": sum(1 for j in jobs if j["status"] == "INVALID"),
        "schema_version": SCHEMA_VERSION,
        "missing_fields": [],
        "duplicate_uuids": duplicate_uuid_anomalies,
        "duplicate_jobs": duplicate_jobs,
        "shared_decision_uuids": len(uuid_counts),
    }


def write_json_output(
    metrics: dict[str, Any],
    sources_loaded: dict[str, bool],
    missing_sources: list[str],
    experiment_id: str,
    written: int,
    skipped: int,
) -> None:
    payload = {
        "schema": "tae_execution_splitter",
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "experiment_id": experiment_id,
        "jobs_log": str(JOBS_LOG),
        "decision_events_source": str(DECISION_EVENTS),
        "metrics": metrics,
        "sources_loaded": sources_loaded,
        "missing_sources": missing_sources,
        "jobs_written_this_run": written,
        "jobs_skipped_duplicates_this_run": skipped,
        "executors": list(EXECUTORS),
        "statuses": list(STATUSES),
        "event_origins": ["LIVE", "SHADOW", "REPLAY", "SIMULATION", "BACKTEST"],
        "decision_reasons": [
            "KEEP_WINNER",
            "HIGH_GROWTH",
            "COLLAPSE_RISK",
            "MARKET_HARMONY",
            "DEFENSIVE_POLICY",
        ],
        "reuse_audit": UPSTREAM_REUSE,
        "not_duplicated": NOT_DUPLICATED,
        "safety": {
            "read_only": True,
            "shadow_only": True,
            "no_broker": True,
            "no_execution": True,
            "no_portfolio_change": True,
            "no_live_bot_change": True,
            "no_advisory_change": True,
        },
        "next_sprint": "TAE DPE-3 — Competitive Paper Executor",
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_report(
    *,
    metrics: dict[str, Any],
    sources_loaded: dict[str, bool],
    missing_sources: list[str],
    events: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    written: int,
    skipped: int,
    experiment_id: str,
    parse_error: str | None,
) -> None:
    ticker_jobs = [j for j in jobs if j.get("parent_event_type") == "TICKER_DECISION_SNAPSHOT"]

    lines = [
        "# TAE Execution Splitter (DPE-2)",
        "",
        f"**Generated:** {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"**Mode:** {MODE} — READ_ONLY",
        f"**Schema version:** {SCHEMA_VERSION}",
        f"**Experiment ID:** {experiment_id}",
        "",
        "> **Routing only — no execution, no portfolio change, no live behavior change**",
        "",
        "## Executive summary",
        "",
        f"- Decision events processed: **{metrics['total_events']}**",
        f"- Jobs built this run: **{len(jobs)}**",
        f"- Jobs appended: **{written}** (skipped duplicates in run: **{skipped}**)",
        f"- Competitive jobs: **{metrics['competitive_jobs']}**",
        f"- Collaborative jobs: **{metrics['collaborative_jobs']}**",
        f"- Blocked jobs: **{metrics['blocked_jobs']}**",
        f"- Ready jobs: **{metrics['ready_jobs']}**",
        f"- Jobs log: `{JOBS_LOG}`",
        "",
        "## Architecture summary",
        "",
        "```text",
        "decision_events.jsonl  →  Execution Splitter  →  execution_jobs.jsonl",
        "                              │",
        "                    ┌─────────┴─────────┐",
        "                    │                   │",
        "             COMPETITIVE            COLLABORATIVE",
        "               (Job A)                (Job B)",
        "                    │                   │",
        "                    └─────────┬─────────┘",
        "                              ▼",
        "                    DPE-3 / DPE-4 Paper Executors",
        "```",
        "",
        "## Routing diagram",
        "",
        "```mermaid",
        "flowchart LR",
        "  DEB[Decision Event Bus] --> SPL[Execution Splitter]",
        "  SPL --> JC[Competitive Job]",
        "  SPL --> JL[Collaborative Job]",
        "  JC --> EX3[DPE-3 Competitive Executor]",
        "  JL --> EX4[DPE-4 Collaborative Executor]",
        "```",
        "",
        "## Schema version",
        "",
        f"`{SCHEMA_VERSION}` — see `tae_execution_splitter.json`",
        "",
        "## Metrics",
        "",
        "| metric | value |",
        "| --- | --- |",
    ]
    for key in (
        "total_events",
        "competitive_jobs",
        "collaborative_jobs",
        "blocked_jobs",
        "ready_jobs",
        "queued_jobs",
        "invalid_jobs",
        "duplicate_uuids",
        "duplicate_jobs",
    ):
        lines.append(f"| {key} | {metrics[key]} |")

    lines.extend(["", "## Source status", "", "| source | loaded |", "| --- | --- |"])
    for name, ok in sorted(sources_loaded.items()):
        lines.append(f"| {name} | {'✅' if ok else '❌'} |")

    if missing_sources:
        lines.extend(["", "**Missing sources:**", ""])
        for item in missing_sources:
            lines.append(f"- {item}")
    if parse_error:
        lines.extend(["", f"**Parse note:** {parse_error}", ""])

    lines.extend(
        [
            "",
            "## Reuse audit",
            "",
            "Artifacts consumed read-only (no upstream Python imports):",
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
            "## Ticker job summary",
            "",
            "| ticker | competitive | collaborative | reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    by_ticker: dict[str, dict[str, str]] = {}
    for job in ticker_jobs:
        by_ticker.setdefault(job["ticker"], {})[job["executor"]] = job["status"]
    for ticker in sorted(by_ticker.keys())[:20]:
        row = by_ticker[ticker]
        sample = next(j for j in ticker_jobs if j["ticker"] == ticker)
        lines.append(
            f"| {ticker} | {row.get('COMPETITIVE', '—')} | {row.get('COLLABORATIVE', '—')} | "
            f"{sample.get('decision_reason')} |"
        )

    lines.extend(
        [
            "",
            "## Event log path",
            "",
            f"`{JOBS_LOG}`",
            "",
            "## How this feeds DPE-3",
            "",
            "DPE-3 Competitive Paper Executor will consume `COMPETITIVE` jobs with status `READY` "
            "from `execution_jobs.jsonl`. DPE-4 handles `COLLABORATIVE` jobs. No execution occurs here.",
            "",
            "## Safety confirmation",
            "",
            "- READ_ONLY: **true**",
            "- SHADOW_ONLY: **true**",
            "- NO_BROKER: **true**",
            "- NO_EXECUTION: **true**",
            "- NO_PORTFOLIO_CHANGE: **true**",
            "- NO_LIVE_BOT_CHANGE: **true**",
            "- NO_ADVISORY_CHANGE: **true**",
            "",
            "## Recommended next sprint",
            "",
            "**TAE DPE-3 — Competitive Paper Executor**",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(metrics: dict[str, Any], written: int, missing_sources: list[str]) -> None:
    print("===== TAE EXECUTION SPLITTER (DPE-2) =====")
    print("Mode: SHADOW_ONLY — routing only, no execution")
    print("Schema:", SCHEMA_VERSION)
    print("Events processed:", metrics["total_events"])
    print("Jobs built:", metrics["competitive_jobs"] + metrics["collaborative_jobs"])
    print("Competitive:", metrics["competitive_jobs"], "| Collaborative:", metrics["collaborative_jobs"])
    print("Blocked:", metrics["blocked_jobs"], "| Ready:", metrics["ready_jobs"])
    print("Jobs appended:", written)
    print("Jobs log:", JOBS_LOG)
    if missing_sources:
        print("Missing sources:", ", ".join(missing_sources))


def main() -> int:
    sources_loaded, missing_sources = load_artifact_sources()
    events, events_file_ok, parse_error = load_decision_events()

    gii, _ = load_json(GII_JSON)
    analytics, _ = load_json(GROWTH_ANALYTICS_JSON)
    ppg, _ = load_json(PPG_JSON)

    if not events:
        print("WARNING: no decision events to split", file=__import__("sys").stderr)

    jobs, split_meta = split_all_events(events, gii, analytics, ppg)
    metrics = compute_metrics(jobs, events)
    metrics["missing_fields"] = split_meta.get("missing_event_fields") or []
    written, skipped, _ = append_jobs(jobs)

    write_json_output(
        metrics,
        sources_loaded,
        missing_sources,
        split_meta["experiment_id"],
        written,
        skipped,
    )
    write_report(
        metrics=metrics,
        sources_loaded=sources_loaded,
        missing_sources=missing_sources,
        events=events,
        jobs=jobs,
        written=written,
        skipped=skipped,
        experiment_id=split_meta["experiment_id"],
        parse_error=parse_error,
    )
    print_summary(metrics, written, missing_sources)
    print("Wrote:", OUTPUT_MD, OUTPUT_JSON, JOBS_LOG)
    return 0 if events_file_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
