#!/usr/bin/env python3
"""
TAE Morning Operational Audit — READ_ONLY / NO_BROKER / NO_EXECUTION.

Aggregates existing SSOT artifacts into one consolidated morning brief.
Does not modify portfolio, live bot, or run trading engines.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(".")
MODE = "READ_ONLY"

ACCOUNTING_JSON = ROOT / "tae_accounting_snapshot.json"
GII_JSON = ROOT / "tae_growth_intelligence.json"
# Producer SSOT moved under runtime_outputs/generated_reports (tae_artifact_paths).
# Keep root path as legacy fallback for older cycles.
try:
    from tae_artifact_paths import generated_report as _generated_report

    _PROTECTION_SSOT = _generated_report("tae_profit_protection_shadow.json")
except Exception:  # noqa: BLE001
    _PROTECTION_SSOT = ROOT / "runtime_outputs/generated_reports/tae_profit_protection_shadow.json"
PROTECTION_JSON_LEGACY = ROOT / "tae_profit_protection_shadow.json"


def _protection_json_path() -> Path:
    if _PROTECTION_SSOT.is_file():
        return _PROTECTION_SSOT
    return PROTECTION_JSON_LEGACY


# Resolved at import for FRESHNESS_TARGETS; refreshed again at audit time.
PROTECTION_JSON = _protection_json_path()
PPG_JSON = ROOT / "tae_portfolio_profit_governor.json"
APPE_JSON = ROOT / "tae_adaptive_profit_policy_engine.json"


def _infra_json_path() -> Path:
    try:
        from tae_artifact_paths import generated_report as _gr

        ssot = _gr("tae_infrastructure_health.json")
    except Exception:  # noqa: BLE001
        ssot = ROOT / "runtime_outputs/generated_reports/tae_infrastructure_health.json"
    legacy = ROOT / "tae_infrastructure_health.json"
    return ssot if ssot.is_file() else legacy


INFRA_JSON = _infra_json_path()
PROCESS_JSON = ROOT / "process_health.json"
ORCHESTRATION_SUMMARY = ROOT / "runtime_outputs/full_paper_cycle/summary.json"
ORCHESTRATION_RUN_RECORD = ROOT / "runtime_outputs/full_paper_cycle/orchestration_run.json"
BOT_LOG = ROOT / "bot_output.log"
PORTFOLIO_CSV = ROOT / "portfolio.csv"
SIGNALS_CSV = ROOT / "live_signals.csv"

DPE_ADAPTIVE = ROOT / "runtime_outputs/dpe/adaptive/adaptive.json"
DPE_EVAL = ROOT / "runtime_outputs/dpe/result_evaluator/evaluation.json"
DPE_LEARNING = ROOT / "runtime_outputs/dpe/learning/learning.json"
DPE_JOBS = ROOT / "runtime_outputs/dpe/execution_jobs.jsonl"
DPE_EVENTS = ROOT / "runtime_outputs/dpe/decision_events.jsonl"
DPE_COMP_METRICS = ROOT / "runtime_outputs/dpe/paper_competitive/metrics.json"
DPE_COLLAB_METRICS = ROOT / "runtime_outputs/dpe/paper_collaborative/metrics.json"
PAPER_PORTFOLIO_JSON = ROOT / "runtime_outputs/paper_execution/paper_portfolio.json"
INTEGRITY_JSON = ROOT / "tae_paper_profit_integrity_guard_report.json"

FRESHNESS_TARGETS = (
    ("accounting", ACCOUNTING_JSON, 24),
    ("growth_intelligence", GII_JSON, 24),
    ("profit_protection", None, 24),  # path resolved dynamically via _protection_json_path()
    ("ppg", PPG_JSON, 24),
    ("appe", APPE_JSON, 24),
    ("dpe_adaptive", DPE_ADAPTIVE, 48),
    ("dpe_evaluation", DPE_EVAL, 48),
    ("dpe_learning", DPE_LEARNING, 48),
    ("process_health", PROCESS_JSON, 24),
    ("orchestration_run", ORCHESTRATION_RUN_RECORD, 24),
)

TIMESTAMP_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return round((_now() - mtime).total_seconds() / 3600, 1)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(text.replace("Z", "+00:00"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _process_running(pattern: str) -> bool:
    """True if a matching process is running (identity-aware for live_bot)."""
    if pattern == "live_bot.py":
        try:
            from core import process_identity as pi

            pi.reconcile_bot_identity_metadata(project_dir=ROOT.resolve())
            identity, _ = pi.resolve_canonical_bot(project_dir=ROOT.resolve())
            if identity.valid:
                return True
        except Exception:
            pass
    if shutil.which("pgrep") is None:
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-fl", pattern],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if pattern == "live_bot.py":
        return any(
            "live_bot.py" in line and "cursorsandbox" not in line.lower()
            for line in (result.stdout or "").splitlines()
        )
    return bool((result.stdout or "").strip())


def _refresh_infrastructure_health(*, write_report: bool = False) -> dict[str, Any] | None:
    """Build infra health in memory. Persist only when write_report=True."""
    try:
        from tae_infrastructure_health import build_health_report, write_outputs

        report = build_health_report()
        if write_report:
            write_outputs(report)
        return report
    except Exception:
        return None


def _market_session() -> str:
    if BOT_LOG.is_file():
        try:
            tail = BOT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
            text = "\n".join(tail).upper()
            if "CLOSED" in text or "MARKET CLOSED" in text:
                return "CLOSED"
            if "OPEN" in text or "SESSION" in text:
                return "OPEN"
        except OSError:
            pass
    if DPE_EVENTS.is_file():
        try:
            last = DPE_EVENTS.read_text(encoding="utf-8", errors="replace").splitlines()[-1]
            event = json.loads(last)
            session = event.get("market_session_state")
            if session:
                return str(session)
        except (json.JSONDecodeError, OSError, IndexError):
            pass
    if SIGNALS_CSV.is_file():
        return "SIGNALS_ACTIVE"
    return "UNKNOWN"


def _last_log_timestamp() -> str | None:
    if not BOT_LOG.is_file():
        return None
    try:
        lines = BOT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except OSError:
        return None
    for line in reversed(lines):
        match = TIMESTAMP_RE.search(line)
        if match:
            return match.group(1)
    return None


def _job_event_date(job: dict[str, Any]) -> str | None:
    raw = job.get("timestamp") or job.get("ts") or job.get("generated_at") or job.get("updated_at")
    dt = _parse_ts(raw)
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).date().isoformat()


def _count_jobs() -> dict[str, Any]:
    counts: Counter[str] = Counter()
    blocked_ids: set[str] = set()
    ready_ids: set[str] = set()
    blocked_today_ids: set[str] = set()
    ready_today_ids: set[str] = set()
    blocked_today_lines = 0
    ready_today_lines = 0
    blocked_reason_counts: Counter[str] = Counter()
    blocked_ticker_counts: Counter[str] = Counter()
    today = datetime.now(timezone.utc).date().isoformat()
    if not DPE_JOBS.is_file():
        return {
            "counts": dict(counts),
            "blocked_unique": 0,
            "ready_unique": 0,
            "blocked_today_lines": 0,
            "ready_today_lines": 0,
            "blocked_unique_today": 0,
            "ready_unique_today": 0,
            "top_block_reason": None,
            "top_block_ticker": None,
            "average_events_per_blocked_job": None,
            "TOTAL_BLOCKED_EVENT_LINES": 0,
            "UNIQUE_BLOCKED_JOBS": 0,
            "BLOCKED_EVENTS_TODAY": 0,
            "UNIQUE_BLOCKED_JOBS_TODAY": 0,
        }
    try:
        for line in DPE_JOBS.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                job = json.loads(line)
            except json.JSONDecodeError:
                continue
            status = str(job.get("status") or "UNKNOWN").upper()
            counts[status] += 1
            job_id = str(job.get("job_id") or "")
            event_day = _job_event_date(job)
            if status == "BLOCKED":
                if job_id:
                    blocked_ids.add(job_id)
                reason = str(
                    job.get("reason_code")
                    or job.get("block_reason")
                    or job.get("reason")
                    or "UNKNOWN"
                )
                ticker = str(job.get("ticker") or job.get("symbol") or "UNKNOWN").upper()
                blocked_reason_counts[reason] += 1
                blocked_ticker_counts[ticker] += 1
                if event_day == today:
                    blocked_today_lines += 1
                    if job_id:
                        blocked_today_ids.add(job_id)
            if status == "READY":
                if job_id:
                    ready_ids.add(job_id)
                if event_day == today:
                    ready_today_lines += 1
                    if job_id:
                        ready_today_ids.add(job_id)
    except OSError:
        pass
    blocked_lines = int(counts.get("BLOCKED", 0))
    unique_blocked = len(blocked_ids)
    avg_events = (blocked_lines / unique_blocked) if unique_blocked else None
    top_reason = blocked_reason_counts.most_common(1)[0][0] if blocked_reason_counts else None
    top_ticker = blocked_ticker_counts.most_common(1)[0][0] if blocked_ticker_counts else None
    return {
        "counts": dict(counts),
        "blocked_unique": unique_blocked,
        "ready_unique": len(ready_ids),
        "blocked_today_lines": blocked_today_lines,
        "ready_today_lines": ready_today_lines,
        "blocked_unique_today": len(blocked_today_ids),
        "ready_unique_today": len(ready_today_ids),
        "top_block_reason": top_reason,
        "top_block_ticker": top_ticker,
        "average_events_per_blocked_job": avg_events,
        "TOTAL_BLOCKED_EVENT_LINES": blocked_lines,
        "UNIQUE_BLOCKED_JOBS": unique_blocked,
        "BLOCKED_EVENTS_TODAY": blocked_today_lines,
        "UNIQUE_BLOCKED_JOBS_TODAY": len(blocked_today_ids),
        "TOP_BLOCK_REASON": top_reason,
        "TOP_BLOCK_TICKER": top_ticker,
        "AVERAGE_EVENTS_PER_JOB": avg_events,
    }


def _classify_file_hash_drift(
    *,
    name: str,
    before: str | None,
    after: str | None,
    write_report: bool,
    bot_running: bool,
    live_writer_ownership: str | None,
    portfolio_mtime: float | None,
    audit_start_ts: float,
    audit_end_ts: float,
    audit_side_wrote_portfolio: bool = False,
) -> dict[str, Any]:
    """Attribute economic hash drift without dropping the control."""
    if not before or not after or before == after:
        return {
            "file": name,
            "classification": "NO_MUTATION",
            "code": None,
            "severity": None,
            "finding": None,
        }

    evidence = {
        "before": before,
        "after": after,
        "bot_running": bot_running,
        "LIVE_WRITER_OWNERSHIP": live_writer_ownership,
        "portfolio_mtime": portfolio_mtime,
        "audit_start_ts": audit_start_ts,
        "audit_end_ts": audit_end_ts,
        "write_report": write_report,
    }

    if name == "portfolio.csv" and audit_side_wrote_portfolio:
        finding = {
            "code": "ECONOMIC_HASH_DRIFT_AUDIT_SIDE_EFFECT",
            "severity": "CRITICAL",
            "message": (
                "portfolio.csv changed during the audit interval due to an audit-side write; "
                "audit must not mutate the LIVE portfolio"
            ),
            "evidence": {**evidence, "classification": "AUDIT_CAUSED_MUTATION"},
        }
        return {
            "file": name,
            "classification": "AUDIT_CAUSED_MUTATION",
            "code": finding["code"],
            "severity": "CRITICAL",
            "finding": finding,
        }

    # Expected artifact refreshes when --write-report is explicitly requested.
    if write_report and name in {"tae_infrastructure_health.json", "tae_profit_pipeline.json"}:
        return {
            "file": name,
            "classification": "NO_MUTATION",
            "code": None,
            "severity": None,
            "finding": None,
            "note": "expected_write_report_refresh",
        }

    mtime_in_window = False
    if portfolio_mtime is not None and name == "portfolio.csv":
        # Small slack for filesystem timestamp granularity.
        mtime_in_window = (audit_start_ts - 1.0) <= float(portfolio_mtime) <= (audit_end_ts + 2.0)
    evidence["portfolio_write_in_audit_interval"] = mtime_in_window

    single_owner = str(live_writer_ownership or "") == "SINGLE_OWNER_PROVEN"
    if (
        name == "portfolio.csv"
        and bot_running
        and single_owner
        and mtime_in_window
        and not audit_side_wrote_portfolio
    ):
        finding = {
            "code": "ECONOMIC_HASH_DRIFT_EXTERNAL_LIVE_WRITE",
            "severity": "WARNING",
            "message": (
                "portfolio.csv changed during the audit interval due to the active canonical LIVE "
                "writer; no audit-side mutation was detected"
            ),
            "evidence": {
                **evidence,
                "classification": "EXTERNAL_CANONICAL_LIVE_WRITE",
                "verdict": "ECONOMIC_HASH_DRIFT_EXTERNAL_LIVE_WRITE",
            },
        }
        return {
            "file": name,
            "classification": "EXTERNAL_CANONICAL_LIVE_WRITE",
            "code": finding["code"],
            "severity": "WARNING",
            "finding": finding,
        }

    finding = {
        "code": "ECONOMIC_HASH_DRIFT_UNATTRIBUTED",
        "severity": "CRITICAL",
        "message": (
            f"{name} hash changed during the audit interval and the writer could not be "
            "demonstrated as the canonical LIVE owner"
        ),
        "evidence": {**evidence, "classification": "UNKNOWN_MUTATION"},
    }
    return {
        "file": name,
        "classification": "UNKNOWN_MUTATION",
        "code": finding["code"],
        "severity": "CRITICAL",
        "finding": finding,
    }


def _paper_execution_semantics(profit_pipeline: dict[str, Any] | None) -> dict[str, Any]:
    pipeline = profit_pipeline or {}
    summary = pipeline.get("summary") or {}
    flow = pipeline.get("cycle_flow") or {}
    timelines = list(pipeline.get("timelines") or [])
    rollup = dict(pipeline.get("block_reason_rollup") or {})

    candidate_count = int(
        flow.get("new_executable_orders")
        if flow.get("new_executable_orders") is not None
        else summary.get("new_executable_orders") or 0
    )
    executed_count = int(
        flow.get("newly_executed_fills")
        if flow.get("newly_executed_fills") is not None
        else summary.get("newly_executed_fills")
        if summary.get("newly_executed_fills") is not None
        else summary.get("orders_executed") or 0
    )
    blocked_count = int(
        flow.get("blocked_before_execution")
        if flow.get("blocked_before_execution") is not None
        else summary.get("blocked_before_execution") or 0
    )

    block_reasons: Counter[str] = Counter()
    if rollup:
        for reason, count in rollup.items():
            try:
                block_reasons[str(reason)] += int(count)
            except (TypeError, ValueError):
                continue
    else:
        for row in timelines:
            if row.get("cycle_flow") != "blocked_before_execution":
                continue
            status = str((row.get("order") or {}).get("status") or "UNKNOWN")
            block_reasons[status] += 1

    return {
        "PAPER_NEW_EXECUTION_CANDIDATES": candidate_count,
        "PAPER_EXECUTED": executed_count,
        "PAPER_BLOCKED_AFTER_DECISION": blocked_count,
        "candidate_count": candidate_count,
        "executed_count": executed_count,
        "blocked_count": blocked_count,
        "block_reasons": dict(block_reasons),
        "note": (
            "DPE READY jobs are shadow evaluation artifacts and are not canonical PAPER "
            "execution instructions."
        ),
    }


def _last_jsonl_timestamp(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        if not lines:
            return None
        return str(json.loads(lines[-1]).get("timestamp") or "")
    except (json.JSONDecodeError, OSError, IndexError):
        return None


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _top_positions(positions: list[dict[str, Any]], n: int = 3, winners: bool = True) -> list[str]:
    ranked = sorted(
        positions,
        key=lambda p: float(p.get("pnl") or 0),
        reverse=winners,
    )
    if not winners:
        ranked = sorted(positions, key=lambda p: float(p.get("pnl") or 0))
    out: list[str] = []
    for pos in ranked[:n]:
        ticker = pos.get("ticker", "?")
        pnl = _fmt_money(pos.get("pnl"))
        pct = _fmt_pct(pos.get("pnl_pct"))
        out.append(f"{ticker} {pnl} ({pct})")
    return out or ["none"]


def _freshness_audit() -> tuple[list[dict[str, Any]], list[str], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    orch = _load_json(ORCHESTRATION_RUN_RECORD) or _load_json(ORCHESTRATION_SUMMARY) or {}
    orch_run_id = orch.get("orchestration_run_id")
    orch_trading_date = orch.get("trading_date")
    mixed_cycle = False
    for label, path, warn_hours in FRESHNESS_TARGETS:
        if path is None and label == "profit_protection":
            path = _protection_json_path()
        if path is None:
            continue
        age = _file_age_hours(path)
        exists = path.is_file()
        generated = None
        payload = _load_json(path) if exists and path.suffix == ".json" else None
        artifact_run_id = None
        artifact_trading_date = None
        if payload:
            generated = payload.get("generated_at") or payload.get("updated_at")
            artifact_run_id = payload.get("orchestration_run_id")
            artifact_trading_date = payload.get("trading_date")
        status = "OK"
        if not exists:
            status = "MISSING"
            if label in {"profit_protection", "accounting", "orchestration_run"}:
                errors.append(f"Missing file: {path}")
            else:
                warnings.append(f"Missing file: {path}")
        elif age is not None and age > warn_hours:
            status = "STALE"
            warnings.append(f"Stale {label}: {path.name} ({age}h old, threshold {warn_hours}h)")
        if (
            orch_run_id
            and artifact_run_id
            and str(artifact_run_id) != str(orch_run_id)
            and label != "orchestration_run"
        ):
            mixed_cycle = True
            warnings.append(
                f"Mixed-cycle artifact {label}: orchestration_run_id={artifact_run_id} "
                f"!= cycle {orch_run_id}"
            )
        if (
            orch_trading_date
            and artifact_trading_date
            and str(artifact_trading_date) != str(orch_trading_date)
        ):
            mixed_cycle = True
            warnings.append(
                f"Mixed trading_date on {label}: {artifact_trading_date} != {orch_trading_date}"
            )
        rows.append(
            {
                "label": label,
                "path": str(path),
                "exists": exists,
                "age_hours": age,
                "generated_at": generated,
                "orchestration_run_id": artifact_run_id,
                "trading_date": artifact_trading_date,
                "status": status,
                "threshold_hours": warn_hours,
            }
        )
    if mixed_cycle:
        warnings.append(
            "MORNING_AUDIT_MIXED_CYCLE: artifacts from multiple orchestration runs detected"
        )
    return rows, warnings, errors


def _score_infrastructure(infra: dict[str, Any] | None, bot_running: bool) -> tuple[int, list[str]]:
    notes: list[str] = []
    if not infra:
        return 40, ["Infrastructure audit file missing"]
    overall = str(infra.get("overall_status") or "UNKNOWN").upper()
    summary = infra.get("summary") or {}
    critical_fail = int(infra.get("critical_fail_count") or summary.get("fail") or 0)
    score = 95 if overall == "PASS" else 70 if overall == "WARN" else 35
    if overall == "FAIL":
        notes.append(f"Infrastructure overall_status={overall}")
        for item in (infra.get("fail_reasons") or [])[:3]:
            if item.get("critical"):
                notes.append(f"Critical FAIL: {item.get('name')} — {item.get('detail')}")
    if infra.get("runtime_operational"):
        score = max(score, 85)
    elif not bot_running:
        score -= 10
        notes.append("live_bot.py process not detected")
    non_critical = int(infra.get("non_critical_fail_count") or 0)
    if non_critical:
        notes.append(f"Non-critical infra notes: {non_critical}")
    return max(0, min(100, score)), notes


def _score_portfolio(accounting: dict[str, Any] | None) -> tuple[int, list[str]]:
    notes: list[str] = []
    if not accounting:
        return 20, ["Accounting snapshot missing"]
    score = 85
    quality = str(accounting.get("data_quality_status") or "UNKNOWN")
    delta = float(accounting.get("account_value_reconciliation_delta") or 0)
    reconciled = abs(delta) <= 0.01
    if quality == "HISTORICAL_RECONCILIATION_REQUIRED" and reconciled:
        score = 85
        notes.append(
            "Historical ledger: stale reported SELL PnL in portfolio.csv — "
            "canonical corrected metrics reconciled; does not block current PAPER validation"
        )
    elif quality != "OK":
        score -= 15
        notes.append(f"Data quality: {quality}")
    capital = str(accounting.get("capital_base_status") or "")
    eff_cap = float(accounting.get("effective_contributed_capital") or 0)
    if capital.upper() == "CONFIRMED" and reconciled:
        notes.append(f"Capital base: CONFIRMED (${eff_cap:,.0f} contributed)")
    elif "NEEDS" in capital.upper() and reconciled:
        notes.append(f"Capital base review: {capital} (canonical cash path reconciled)")
        score -= 5
    elif "FAIL" in capital.upper():
        score -= 15
        notes.append(f"Capital base: {capital}")
    if not reconciled:
        score -= 25
        notes.append(f"Account reconciliation delta: {delta}")
    return max(0, min(100, score)), notes


def _score_growth(gii: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not gii:
        return 35, ["Growth intelligence missing"]
    portfolio = gii.get("portfolio") or {}
    score = float(portfolio.get("global_growth_score") or portfolio.get("portfolio_growth_quality") or 50)
    verdict = str(gii.get("global_verdict") or "")
    notes = [f"GII verdict: {verdict}"] if verdict else []
    return max(0, min(100, int(round(score)))), notes


def _score_protection(ppg: dict[str, Any] | None, protection: dict[str, Any] | None) -> tuple[int, list[str]]:
    notes: list[str] = []
    if not ppg:
        return 40, ["PPG snapshot missing"]
    metrics = ppg.get("metrics") or {}
    at_risk = float(metrics.get("portfolio_profit_at_risk_score") or 50)
    verdict = str(ppg.get("portfolio_verdict") or "")
    score = max(0, min(100, int(round(100 - at_risk * 0.6))))
    if "HIGH_RISK" in verdict:
        score -= 10
        notes.append(f"PPG verdict: {verdict}")
    if protection:
        daily = protection.get("daily_summary") or {}
        at_risk_n = int(daily.get("num_profit_at_risk") or 0)
        if at_risk_n:
            notes.append(f"Profit at risk positions: {at_risk_n}")
            score -= min(15, at_risk_n * 2)
    return max(0, min(100, score)), notes


def _score_learning(learning: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not learning:
        return 50, ["DPE learning history missing"]
    summary = learning.get("summary") or {}
    records = int(summary.get("total_records") or len(learning.get("records") or []))
    avg_conf = float(summary.get("average_confidence") or 50)
    score = min(100, int(40 + records * 8 + avg_conf * 0.4))
    return score, [f"Learning records: {records}", f"Avg confidence: {avg_conf:.1f}%"]


def _score_dpe(adaptive: dict[str, Any] | None, evaluation: dict[str, Any] | None) -> tuple[int, list[str]]:
    notes: list[str] = []
    if not adaptive or not evaluation:
        return 45, ["DPE adaptive or evaluation missing"]
    conf = float(adaptive.get("confidence") or 50)
    overall = evaluation.get("overall") or {}
    winner = overall.get("winner")
    score = int(round(conf * 0.7 + 30))
    notes.append(f"DPE winner: {winner} @ {overall.get('confidence_pct')}%")
    notes.append(f"Adaptive preferred: {adaptive.get('preferred_philosophy')}")
    return max(0, min(100, score)), notes


def _score_freshness(warnings: list[str], errors: list[str]) -> tuple[int, list[str]]:
    score = 100 - len(errors) * 20 - len(warnings) * 5
    notes = []
    if errors:
        notes.extend(errors[:3])
    if warnings:
        notes.extend(warnings[:3])
    return max(0, min(100, score)), notes


def _compute_verdict(
    global_score: int,
    errors: list[str],
    warnings: list[str],
    infra: dict[str, Any] | None,
    *,
    integrity_ok: bool = True,
    stale_critical: bool = False,
    live_findings: list[dict[str, Any]] | None = None,
    hashes_before: dict[str, str | None] | None = None,
    hashes_after: dict[str, str | None] | None = None,
    hash_drift_classifications: list[dict[str, Any]] | None = None,
) -> str:
    """Return TAE_DAILY_STATUS: HEALTHY | ATTENTION_REQUIRED | BLOCKED | PASS_WITH_WARNINGS."""
    live_findings = live_findings or []
    hash_drift_classifications = hash_drift_classifications or []
    critical_codes = {
        "CANONICAL_WRITER_MISSING",
        "LIVE_BOT_WRITER_BYPASS",
        "STORAGE_WRITER_BYPASS",
        "RECOMPUTE_UNSAFE_WRITER",
        "RECOMPUTE_OPEN_W",
        "PORTFOLIO_MISSING",
        "PORTFOLIO_EMPTY",
        "PORTFOLIO_HEADER_ONLY",
        "PORTFOLIO_NONFINITE",
        "UNAUTHORIZED_PORTFOLIO_SHRINK",
        "DUPLICATE_LIVE_BOT",
        "LOCK_CONFLICT",
        "CRASH_LOOP",
        "SIDECAR_OWNER_MISMATCH",
        "GIT_CONFLICTS",
        "SHRINK_GUARD_MISSING",
        "WRITER_ATOMIC_MISSING",
        "WRITER_FSYNC_MISSING",
        "WRITER_LOCK_MISSING",
        "WRITER_EMPTY_GUARD_MISSING",
        "WRITER_SHRINK_GUARD_MISSING",
        "WRITER_PATH_NOT_CANONICAL",
        "ACCOUNTING_MISMATCH",
        "NEGATIVE_CASH",
        # Attributed critical drift only — external LIVE MTM is WARNING, not BLOCKED.
        "ECONOMIC_HASH_DRIFT_UNATTRIBUTED",
        "ECONOMIC_HASH_DRIFT_AUDIT_SIDE_EFFECT",
        # Legacy code retained as critical if an older producer still emits it without attribution.
        "ECONOMIC_HASH_DRIFT",
    }
    if any(f.get("code") in critical_codes or f.get("severity") == "CRITICAL" for f in live_findings):
        return "BLOCKED"

    # portfolio.csv / accounting JSON hash changes alone do not BLOCK — attribution decides.
    # Accounting snapshot is rebuilt by the audit on purpose; expected external LIVE MTM is WARNING.
    _ = (hashes_before, hashes_after, hash_drift_classifications)

    fail_count = int((infra or {}).get("summary", {}).get("fail") or 0)
    blocking_warnings = [w for w in warnings if "Stale " in w or "Missing file" in w]
    if not integrity_ok or len(errors) >= 1 or fail_count >= 2:
        return "BLOCKED"
    if any(f.get("severity") == "ERROR" for f in live_findings):
        return "ATTENTION_REQUIRED"
    if stale_critical or blocking_warnings or fail_count >= 1 or global_score < 70:
        return "ATTENTION_REQUIRED"
    if global_score < 80 or errors:
        return "ATTENTION_REQUIRED"
    warning_findings = [f for f in live_findings if f.get("severity") == "WARNING"]
    if warning_findings:
        warn_codes = {str(f.get("code") or "") for f in warning_findings}
        # Expected external LIVE MTM during audit is hygiene WARNING, not operator ATTENTION.
        if warn_codes and warn_codes <= {"ECONOMIC_HASH_DRIFT_EXTERNAL_LIVE_WRITE"}:
            return "PASS_WITH_WARNINGS"
        return "ATTENTION_REQUIRED"
    return "HEALTHY"


def _status_layers(
    *,
    verdict: str,
    integrity_ok: bool,
    reconciliation_ok: bool,
    writer_ok: bool,
    live_findings: list[dict[str, Any]],
    v1_v2_comparison: dict[str, Any] | None,
    hash_drift_classifications: list[dict[str, Any]],
) -> dict[str, str]:
    """Separate operational blockers from comparison / shadow noise."""
    critical_ops = any(
        f.get("severity") == "CRITICAL"
        or str(f.get("code") or "").startswith("ECONOMIC_HASH_DRIFT_UNATTRIBUTED")
        or str(f.get("code") or "").startswith("ECONOMIC_HASH_DRIFT_AUDIT")
        or str(f.get("code") or "")
        in {
            "CANONICAL_WRITER_MISSING",
            "DUPLICATE_LIVE_BOT",
            "LOCK_CONFLICT",
            "ACCOUNTING_MISMATCH",
            "NEGATIVE_CASH",
            "UNAUTHORIZED_PORTFOLIO_SHRINK",
            "PORTFOLIO_MISSING",
            "PORTFOLIO_EMPTY",
            "PORTFOLIO_NONFINITE",
            "LIVE_BOT_WRITER_BYPASS",
            "STORAGE_WRITER_BYPASS",
        }
        for f in live_findings
    )
    # Operational status tracks writer/LIVE controls — not V1/V2 comparison validity.
    operational = "BLOCKED" if (critical_ops or not writer_ok) else "PASS"
    paper = "PASS" if integrity_ok and reconciliation_ok else "FAIL"

    cmp_payload = v1_v2_comparison or {}
    cmp_status = str(cmp_payload.get("COMPARISON_STATUS") or cmp_payload.get("verdict") or "")
    if cmp_status in {"DATASETS_NOT_COMPARABLE_BY_DESIGN", "BLOCKED_NOT_COMPARABLE"}:
        economic = "BLOCKED_NOT_COMPARABLE"
    elif cmp_status == "DATA_INTEGRITY_BLOCKED" or str(
        (cmp_payload.get("comparison_integrity") or {}).get("OVERALL_COMPARISON_INTEGRITY") or ""
    ) == "BLOCKED":
        # Duplicate IDs / integrity block comparison, not bot operations.
        economic = "COMPARISON_INTEGRITY_BLOCKED"
    elif cmp_status in {"V1_ECONOMIC_LEADER", "V2_ECONOMIC_LEADER", "ECONOMIC_TIE"}:
        economic = "PASS"
    elif not cmp_payload:
        economic = "N/A"
    else:
        economic = "INSUFFICIENT_OR_OBSERVATIONAL"

    has_warn = any(f.get("severity") == "WARNING" for f in live_findings) or any(
        c.get("classification") == "EXTERNAL_CANONICAL_LIVE_WRITE" for c in hash_drift_classifications
    )
    if operational == "BLOCKED" or paper == "FAIL" or verdict == "BLOCKED":
        overall = "BLOCKED"
    elif has_warn or economic in {"BLOCKED_NOT_COMPARABLE", "COMPARISON_INTEGRITY_BLOCKED"} or verdict in {
        "ATTENTION_REQUIRED",
        "PASS_WITH_WARNINGS",
    }:
        overall = "PASS_WITH_WARNINGS"
    else:
        overall = "PASS"

    return {
        "OPERATIONAL_STATUS": operational,
        "PAPER_INTEGRITY_STATUS": paper,
        "ECONOMIC_COMPARISON_STATUS": economic,
        "OVERALL_STATUS": overall,
    }


def run_audit(*, write_report: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    audit_start_ts = datetime.now(timezone.utc).timestamp()

    from research_core.runtime.morning_audit_checks import run_all_live_checks, _sha256_file

    hash_targets = (
        PORTFOLIO_CSV,
        ACCOUNTING_JSON,
        INFRA_JSON,
        ROOT / "tae_profit_pipeline.json",
    )
    hashes_before = {p.name: _sha256_file(p) for p in hash_targets}
    portfolio_mtime_before = PORTFOLIO_CSV.stat().st_mtime if PORTFOLIO_CSV.is_file() else None

    accounting = _load_json(ACCOUNTING_JSON)
    try:
        from research_core.accounting.accounting_snapshot import build_accounting_snapshot

        accounting = build_accounting_snapshot(ROOT)
    except Exception as exc:
        errors.append(f"Live accounting SSOT rebuild failed: {exc}")
    gii = _load_json(GII_JSON)
    protection = _load_json(_protection_json_path())
    ppg = _load_json(PPG_JSON)
    appe = _load_json(APPE_JSON)
    infra = _refresh_infrastructure_health(write_report=write_report) or _load_json(_infra_json_path())
    process = _load_json(PROCESS_JSON)
    adaptive = _load_json(DPE_ADAPTIVE)
    evaluation = _load_json(DPE_EVAL)
    learning = _load_json(DPE_LEARNING)
    comp_metrics = _load_json(DPE_COMP_METRICS)
    collab_metrics = _load_json(DPE_COLLAB_METRICS)
    paper_portfolio = _load_json(PAPER_PORTFOLIO_JSON)

    integrity: dict[str, Any] = {}
    try:
        from tae_paper_execution import check_paper_profit_integrity

        integrity = check_paper_profit_integrity(
            portfolio=paper_portfolio,
            accounting=accounting,
            write_report_flag=False,
            update_validation_json=False,
        )
    except Exception as exc:
        integrity = {"ok": False, "verdict": "INTEGRITY_CHECK_FAILED", "error": str(exc)}
        errors.append(f"PAPER profit integrity check failed: {exc}")

    profit_pipeline: dict[str, Any] = {}
    try:
        from tae_profit_pipeline import build_profit_pipeline

        profit_pipeline = build_profit_pipeline(write_outputs=bool(write_report))
    except Exception as exc:
        profit_pipeline = {"error": str(exc)}
        warnings.append(f"Profit pipeline consolidation failed: {exc}")

    live_checks = run_all_live_checks(ROOT.resolve())
    live_findings = list(live_checks.get("findings") or [])

    freshness_rows, fresh_warnings, fresh_errors = _freshness_audit()
    warnings.extend(fresh_warnings)
    errors.extend(fresh_errors)
    stale_critical = any(row.get("status") == "STALE" for row in freshness_rows)

    bot_running = _process_running("live_bot.py")
    if not bot_running:
        warnings.append("live_bot.py process not detected")
    if not PORTFOLIO_CSV.is_file():
        errors.append("Missing portfolio.csv")
    if not SIGNALS_CSV.is_file():
        warnings.append("Missing live_signals.csv")
    if not paper_portfolio:
        warnings.append(f"Missing PAPER validation portfolio: {PAPER_PORTFOLIO_JSON}")

    open_positions = list(accounting.get("open_positions") or []) if accounting else []
    job_info = _count_jobs()
    job_counts = job_info["counts"]
    jobs_ready = int(job_counts.get("READY", 0))
    jobs_ready_unique = int(job_info.get("ready_unique", 0))
    jobs_ready_today = int(job_info.get("ready_today_lines", 0))
    jobs_ready_unique_today = int(job_info.get("ready_unique_today", 0))
    jobs_blocked = int(job_counts.get("BLOCKED", 0))
    jobs_blocked_unique = int(job_info.get("blocked_unique", 0))
    jobs_blocked_today = int(job_info.get("blocked_today_lines", 0))
    jobs_blocked_unique_today = int(job_info.get("blocked_unique_today", 0))

    integrity_ok = bool(integrity.get("ok"))
    integrity_metrics = integrity.get("metrics") or {}
    reconciliation = integrity.get("reconciliation") or {}
    contaminated_count = 0
    for check in integrity.get("checks") or []:
        if check.get("name") == "no_synthetic_contamination":
            contaminated_count = int(check.get("findings_count") or 0)

    infra_score, infra_notes = _score_infrastructure(infra, bot_running)
    portfolio_score, portfolio_notes = _score_portfolio(accounting)
    growth_score, growth_notes = _score_growth(gii)
    protection_score, protection_notes = _score_protection(ppg, protection)
    learning_score, learning_notes = _score_learning(learning)
    dpe_score, dpe_notes = _score_dpe(adaptive, evaluation)
    freshness_score, freshness_notes = _score_freshness(warnings, errors)

    health_scores = {
        "infrastructure": infra_score,
        "portfolio": portfolio_score,
        "growth": growth_score,
        "protection": protection_score,
        "learning": learning_score,
        "dpe": dpe_score,
        "data_freshness": freshness_score,
    }
    global_score = int(round(sum(health_scores.values()) / len(health_scores)))

    # Economic NaN / reconciliation hard fails
    if accounting:
        cash = accounting.get("cash_available")
        try:
            if cash is not None and float(cash) < 0:
                live_findings.append(
                    {
                        "code": "NEGATIVE_CASH",
                        "severity": "CRITICAL",
                        "message": f"cash_available negative: {cash}",
                        "evidence": None,
                    }
                )
        except (TypeError, ValueError):
            live_findings.append(
                {
                    "code": "PORTFOLIO_NONFINITE",
                    "severity": "CRITICAL",
                    "message": f"cash_available non-numeric: {cash}",
                    "evidence": None,
                }
            )
        delta = accounting.get("account_value_reconciliation_delta")
        try:
            if delta is not None and abs(float(delta)) > 1.0:
                live_findings.append(
                    {
                        "code": "ACCOUNTING_MISMATCH",
                        "severity": "CRITICAL",
                        "message": f"account_value_reconciliation_delta={delta}",
                        "evidence": None,
                    }
                )
        except (TypeError, ValueError):
            pass

    hashes_after = {p.name: _sha256_file(p) for p in hash_targets}
    audit_end_ts = datetime.now(timezone.utc).timestamp()
    portfolio_mtime_after = PORTFOLIO_CSV.stat().st_mtime if PORTFOLIO_CSV.is_file() else None
    hash_drift_classifications: list[dict[str, Any]] = []
    for name in ("tae_infrastructure_health.json", "tae_profit_pipeline.json", "portfolio.csv"):
        classified = _classify_file_hash_drift(
            name=name,
            before=hashes_before.get(name),
            after=hashes_after.get(name),
            write_report=bool(write_report),
            bot_running=bool(bot_running),
            live_writer_ownership=str(live_checks.get("LIVE_WRITER_OWNERSHIP") or ""),
            portfolio_mtime=portfolio_mtime_after if name == "portfolio.csv" else None,
            audit_start_ts=audit_start_ts,
            audit_end_ts=audit_end_ts,
            audit_side_wrote_portfolio=False,
        )
        hash_drift_classifications.append(classified)
        finding = classified.get("finding")
        if finding:
            live_findings.append(finding)

    # Accounting JSON is rebuilt by the audit on purpose — record classification only.
    if (
        hashes_before.get("tae_accounting_snapshot.json")
        and hashes_after.get("tae_accounting_snapshot.json")
        and hashes_before["tae_accounting_snapshot.json"] != hashes_after["tae_accounting_snapshot.json"]
    ):
        hash_drift_classifications.append(
            {
                "file": "tae_accounting_snapshot.json",
                "classification": "NO_MUTATION",
                "note": "expected_audit_accounting_refresh",
                "before": hashes_before.get("tae_accounting_snapshot.json"),
                "after": hashes_after.get("tae_accounting_snapshot.json"),
                "portfolio_mtime_before": portfolio_mtime_before,
            }
        )

    verdict = _compute_verdict(
        global_score,
        errors,
        warnings,
        infra,
        integrity_ok=integrity_ok,
        stale_critical=stale_critical,
        live_findings=live_findings,
        hashes_before=hashes_before,
        hashes_after=hashes_after,
        hash_drift_classifications=hash_drift_classifications,
    )

    overall = (evaluation or {}).get("overall") or {}
    appe_summary = (appe or {}).get("summary") or {}
    ppg_metrics = (ppg or {}).get("metrics") or {}
    gii_portfolio = (gii or {}).get("portfolio") or {}
    protection_daily = (protection or {}).get("daily_summary") or {}

    outstanding_risks: list[str] = []
    outstanding_risks.extend(portfolio_notes)
    outstanding_risks.extend(protection_notes)
    outstanding_risks.extend(infra_notes)
    for finding in live_findings:
        if finding.get("severity") in {"CRITICAL", "ERROR", "WARNING"}:
            outstanding_risks.append(f"{finding.get('code')}: {finding.get('message')}")
    if not integrity_ok:
        outstanding_risks.append(f"PAPER profit integrity: {integrity.get('verdict', 'FAIL')}")
    if jobs_blocked_unique:
        top_reason = job_info.get("TOP_BLOCK_REASON") or "UNKNOWN"
        top_ticker = job_info.get("TOP_BLOCK_TICKER") or "UNKNOWN"
        outstanding_risks.append(
            f"{jobs_blocked_unique} unique historical shadow jobs have BLOCKED states across "
            f"{jobs_blocked} append-only evaluation events; {jobs_blocked_today} events were "
            f"added today"
            + (
                f", primarily {top_ticker} {top_reason}"
                if jobs_blocked_today or top_ticker != "UNKNOWN"
                else ""
            )
            + "."
        )
    if str((ppg or {}).get("portfolio_verdict") or "").endswith("HIGH_RISK"):
        outstanding_risks.append("Portfolio flagged HIGH_RISK by PPG")

    next_actions: list[str] = []
    if any(f.get("severity") == "CRITICAL" for f in live_findings):
        next_actions.append("Inspect CRITICAL live portfolio / lock / writer findings below")
    if jobs_ready_unique:
        next_actions.append(
            f"DPE shadow READY={jobs_ready_unique} unique cumulative "
            f"({jobs_ready_unique_today} unique today) — not PAPER execution instructions"
        )
    if fresh_warnings:
        next_actions.append("Run: python3 tae.py full-paper-cycle")
    if not bot_running:
        next_actions.append("Verify live_bot autostart / process health")
    if adaptive:
        next_actions.append(str(adaptive.get("recommendation") or "Run DPE adaptive review"))
    if not next_actions:
        next_actions.append("Continue shadow monitoring — no live changes required")

    e3_forward: dict[str, Any] = {}
    e3_canonical: dict[str, Any] = {}
    opening_noise: dict[str, Any] = {}
    try:
        from tae_paper_execution import morning_audit_e3_canonical_summary

        e3_canonical = morning_audit_e3_canonical_summary()
    except Exception as exc:
        e3_canonical = {
            "enabled": "UNAVAILABLE",
            "new_buy_blocked_today": "N/A",
            "tickers": [],
            "avoided_loss_tracking": "N/A",
            "missed_profit_tracking": "N/A",
            "net_e3_value": f"UNAVAILABLE:{exc}",
        }
    try:
        from tae_paper_execution import morning_audit_opening_noise_summary

        opening_noise = morning_audit_opening_noise_summary()
    except Exception as exc:
        opening_noise = {
            "enabled": "UNAVAILABLE",
            "window": "N/A",
            "new_buys_deferred_today": "N/A",
            "requalified": "N/A",
            "executed_after_window": "N/A",
            "expired": "N/A",
            "later_blocked_by_e3": "N/A",
            "net_protection_value": f"UNAVAILABLE:{exc}",
        }
    regional_marks: dict[str, Any] = {}
    try:
        from core.market_data_layer import regional_mark_health_summary

        regional_marks = regional_mark_health_summary()
    except Exception as exc:
        regional_marks = {
            "valid_regional_marks": "N/A",
            "missing_regional_marks": "N/A",
            "stale_regional_marks": "N/A",
            "error": str(exc),
        }
    try:
        from tae_e3_forward_paper import morning_audit_summary

        e3_forward = morning_audit_summary()
    except Exception as exc:
        e3_forward = {
            "status": "UNAVAILABLE",
            "sample_maturity": "N/A",
            "baseline_pnl": "N/A",
            "e3_pnl": "N/A",
            "delta": "N/A",
            "entries_blocked": "N/A",
            "avoided_loss": "N/A",
            "missed_profit": "N/A",
            "current_verdict": f"UNAVAILABLE:{exc}",
        }

    v1_v2_comparison: dict[str, Any] = {}
    try:
        from research_core.economics.v1_v2_economic_comparison import get_v1_v2_economic_comparison

        v1_v2_comparison = get_v1_v2_economic_comparison(
            project_root=ROOT,
            write_report=bool(write_report),
        )
    except Exception as exc:
        # Parallel Paper intentionally retired — comparison is N/A by design, not integrity failure.
        msg = str(exc)
        intentional = "tae_parallel_paper" in msg or "parallel_paper" in msg.lower()
        v1_v2_comparison = {
            "verdict": "DATASETS_NOT_COMPARABLE_BY_DESIGN" if intentional else "DATA_INTEGRITY_BLOCKED",
            "error": msg,
            "overall_economic_leader": "N/A_PARALLEL_PAPER_RETIRED" if intentional else "DATA_INTEGRITY_BLOCKED",
            "difference": {
                "V1_TOTAL_PNL": None,
                "V2_TOTAL_PNL": None,
                "CURRENT_DIFFERENCE": "NOT_APPLICABLE" if intentional else "NOT_PROVEN",
            },
            "main_reason": (
                "V1/V2 parallel-paper comparison retired by infrastructure closure"
                if intentional
                else f"V1/V2 comparison failed: {exc}"
            ),
        }
        if intentional:
            # INFO-only — do not surface as operator warning that flips ATTENTION.
            pass
        else:
            warnings.append(f"V1/V2 economic comparison failed: {exc}")

    paper_exec = _paper_execution_semantics(profit_pipeline)
    status_layers = _status_layers(
        verdict=verdict,
        integrity_ok=integrity_ok,
        reconciliation_ok=bool(reconciliation.get("ok")),
        writer_ok=bool(live_checks.get("CANONICAL_WRITER_OK")),
        live_findings=live_findings,
        v1_v2_comparison=v1_v2_comparison,
        hash_drift_classifications=hash_drift_classifications,
    )
    # Prefer layered overall when operational PASS with non-blocking warnings / comparison noise.
    display_status = verdict
    if verdict == "BLOCKED" or status_layers["OVERALL_STATUS"] == "BLOCKED":
        display_status = "BLOCKED"
    elif verdict in {"HEALTHY", "PASS_WITH_WARNINGS"} and status_layers["OVERALL_STATUS"] == "PASS_WITH_WARNINGS":
        display_status = "PASS_WITH_WARNINGS"
    elif verdict == "HEALTHY" and status_layers["OVERALL_STATUS"] == "PASS":
        display_status = "HEALTHY"

    return {
        "generated_at": _now_iso(),
        "mode": MODE,
        "write_report": bool(write_report),
        "canonical_daily_command": "python3 tae.py morning-audit",
        "accounting": accounting,
        "paper_portfolio": paper_portfolio,
        "integrity": integrity,
        "gii": gii,
        "protection": protection,
        "ppg": ppg,
        "appe": appe,
        "infra": infra,
        "process": process,
        "adaptive": adaptive,
        "evaluation": evaluation,
        "learning": learning,
        "comp_metrics": comp_metrics,
        "collab_metrics": collab_metrics,
        "open_positions": open_positions,
        "top_winners_open": _top_positions(open_positions, winners=True),
        "top_losers_open": _top_positions(open_positions, winners=False),
        "top_winners_closed": [
            f"{w.get('ticker')} {_fmt_money(w.get('pnl'))}"
            for w in (accounting or {}).get("top_winners_corrected") or []
        ][:3],
        "top_losers_closed": [
            f"{w.get('ticker')} {_fmt_money(w.get('pnl'))}"
            for w in (accounting or {}).get("top_losers_corrected") or []
        ][:3],
        "market_session": _market_session(),
        "bot_running": bot_running,
        "last_log_timestamp": _last_log_timestamp(),
        "job_counts": job_counts,
        "jobs_ready": jobs_ready,
        "jobs_ready_unique": jobs_ready_unique,
        "jobs_ready_today": jobs_ready_today,
        "jobs_ready_unique_today": jobs_ready_unique_today,
        "jobs_blocked": jobs_blocked,
        "jobs_blocked_unique": jobs_blocked_unique,
        "jobs_blocked_today": jobs_blocked_today,
        "jobs_blocked_unique_today": jobs_blocked_unique_today,
        "DPE_SHADOW_READY_CUMULATIVE": jobs_ready_unique,
        "DPE_SHADOW_READY_TODAY": jobs_ready_unique_today,
        "job_history": {
            "TOTAL_BLOCKED_EVENT_LINES": job_info.get("TOTAL_BLOCKED_EVENT_LINES"),
            "UNIQUE_BLOCKED_JOBS": job_info.get("UNIQUE_BLOCKED_JOBS"),
            "BLOCKED_EVENTS_TODAY": job_info.get("BLOCKED_EVENTS_TODAY"),
            "UNIQUE_BLOCKED_JOBS_TODAY": job_info.get("UNIQUE_BLOCKED_JOBS_TODAY"),
            "TOP_BLOCK_REASON": job_info.get("TOP_BLOCK_REASON"),
            "TOP_BLOCK_TICKER": job_info.get("TOP_BLOCK_TICKER"),
            "AVERAGE_EVENTS_PER_JOB": job_info.get("AVERAGE_EVENTS_PER_JOB"),
        },
        "paper_execution_semantics": paper_exec,
        "hash_drift_classifications": hash_drift_classifications,
        "last_jobs_timestamp": _last_jsonl_timestamp(DPE_JOBS),
        "last_events_timestamp": _last_jsonl_timestamp(DPE_EVENTS),
        "freshness_rows": freshness_rows,
        "errors": errors,
        "warnings": warnings,
        "warning_count": len(warnings),
        "health_scores": health_scores,
        "global_score": global_score,
        "verdict": display_status,
        "tae_daily_status": display_status,
        "legacy_verdict": verdict,
        **status_layers,
        "live_checks": live_checks,
        "live_findings": live_findings,
        "file_hashes_before": hashes_before,
        "file_hashes_after": hashes_after,
        "LOCK_HEALTH": live_checks.get("LOCK_HEALTH"),
        "LIVE_WRITER_OWNERSHIP": live_checks.get("LIVE_WRITER_OWNERSHIP"),
        "CANONICAL_WRITER_OK": live_checks.get("CANONICAL_WRITER_OK"),
        "SHRINK_STATUS": live_checks.get("SHRINK_STATUS"),
        "integrity_ok": integrity_ok,
        "integrity_metrics": integrity_metrics,
        "reconciliation_ok": bool(reconciliation.get("ok")),
        "synthetic_fill_contamination": contaminated_count,
        "profit_pipeline": profit_pipeline,
        "outstanding_risks": outstanding_risks[:20],
        "next_actions": next_actions[:8],
        "gii_portfolio": gii_portfolio,
        "ppg_metrics": ppg_metrics,
        "appe_summary": appe_summary,
        "protection_daily": protection_daily,
        "overall_eval": overall,
        "e3_forward": e3_forward,
        "e3_canonical": e3_canonical,
        "opening_noise": opening_noise,
        "regional_marks": regional_marks,
        "v1_v2_comparison": v1_v2_comparison,
    }


def format_report(data: dict[str, Any]) -> str:
    accounting = data.get("accounting") or {}
    paper = data.get("paper_portfolio") or {}
    integrity = data.get("integrity") or {}
    integrity_metrics = data.get("integrity_metrics") or integrity.get("metrics") or {}
    gii = data.get("gii") or {}
    protection = data.get("protection") or {}
    ppg = data.get("ppg") or {}
    appe = data.get("appe") or {}
    infra = data.get("infra") or {}
    adaptive = data.get("adaptive") or {}
    evaluation = data.get("evaluation") or {}
    learning = data.get("learning") or {}
    comp_metrics = data.get("comp_metrics") or {}
    collab_metrics = data.get("collab_metrics") or {}
    overall = data.get("overall_eval") or {}
    gii_portfolio = data.get("gii_portfolio") or {}
    ppg_metrics = data.get("ppg_metrics") or {}
    appe_summary = data.get("appe_summary") or {}
    protection_daily = data.get("protection_daily") or {}
    health = data["health_scores"]
    freshness_by_label = {row["label"]: row for row in (data.get("freshness_rows") or [])}

    def _fresh(label: str) -> str:
        row = freshness_by_label.get(label) or {}
        return str(row.get("status") or "N/A")

    integrity_verdict = integrity.get("verdict") or integrity.get("status") or "N/A"
    integrity_pass = "PASS" if data.get("integrity_ok") else "FAIL"
    reconciliation_pass = "PASS" if data.get("reconciliation_ok") else "FAIL"

    lines: list[str] = [
        "===== TAE MORNING OPERATIONAL AUDIT =====",
        f"Generated: {data['generated_at']}",
        f"Mode: {MODE} | NO_BROKER | NO_EXECUTION | NO_LIVE_CHANGE",
        "",
        "--- Operational Contract ---",
        f"accounting: {_fresh('accounting')}",
        f"growth_intelligence: {_fresh('growth_intelligence')}",
        f"profit_protection: {_fresh('profit_protection')}",
        f"ppg: {_fresh('ppg')}",
        f"appe: {_fresh('appe')}",
        f"dpe_adaptive: {_fresh('dpe_adaptive')}",
        f"dpe_evaluation: {_fresh('dpe_evaluation')}",
        f"dpe_learning: {_fresh('dpe_learning')}",
        f"PAPER_PROFIT_INTEGRITY: {integrity_pass} ({integrity_verdict})",
        f"RECONCILIATION: {reconciliation_pass}",
        f"validation_capital_base: {integrity_metrics.get('validation_capital_base', 'N/A')}",
        f"synthetic_fill_contamination: {data.get('synthetic_fill_contamination', 0)}",
        "",
    ]
    pipeline = data.get("profit_pipeline") or {}
    if pipeline and not pipeline.get("error"):
        try:
            from tae_profit_pipeline import format_pipeline_section

            lines.extend(format_pipeline_section(pipeline))
            lines.append("")
        except Exception:
            pass
    lines.extend([
        "--- CANONICAL PORTFOLIO (live bot ledger / portfolio.csv SSOT) ---",
        f"Source: {ACCOUNTING_JSON}",
        f"Account value: {_fmt_money(accounting.get('account_value_corrected'))}",
        f"Cash: {_fmt_money(accounting.get('cash_available'))}",
        f"Open positions: {accounting.get('open_positions_count', len(data.get('open_positions') or []))}",
        f"Realized PnL: {_fmt_money(accounting.get('corrected_realized_pnl'))}",
        f"Unrealized PnL: {_fmt_money(accounting.get('corrected_unrealized_pnl'))}",
        f"Total trading PnL: {_fmt_money(accounting.get('corrected_total_trading_pnl'))}",
        f"Capital base status: {accounting.get('capital_base_status', 'N/A')}",
        f"Effective contributed capital: {_fmt_money(accounting.get('effective_contributed_capital'))}",
        f"Data quality (canonical): {accounting.get('data_quality_status', 'N/A')}",
        "Note: HISTORICAL_RECONCILIATION_REQUIRED reflects stale SELL PnL columns in portfolio.csv only.",
        "",
        "--- PAPER VALIDATION PORTFOLIO (isolated profit-validation SSOT) ---",
        f"Source: {PAPER_PORTFOLIO_JSON}",
        f"Account value: {_fmt_money(integrity_metrics.get('account_value') or paper.get('total_value'))}",
        f"Cash: {_fmt_money(integrity_metrics.get('cash') or paper.get('cash'))}",
        f"Open positions: {integrity_metrics.get('open_positions', len(paper.get('positions') or {}))}",
        f"Realized PnL: {_fmt_money(integrity_metrics.get('realized_pnl') or paper.get('realized_pnl'))}",
        f"Unrealized PnL: {_fmt_money(integrity_metrics.get('unrealized_pnl') or paper.get('unrealized_pnl'))}",
        f"Profit vs validation capital base: {_fmt_money(integrity_metrics.get('profit_vs_capital_base'))}",
        f"Canonical reference (not merged): {_fmt_money(integrity_metrics.get('canonical_account_value'))}",
        "",
        "Open position leaders (canonical):",
        f"  Top winners: {', '.join(data.get('top_winners_open') or [])}",
        f"  Top losers: {', '.join(data.get('top_losers_open') or [])}",
        "",
        "Closed trade leaders (canonical corrected):",
        f"  Top winners: {', '.join(data.get('top_winners_closed') or ['none'])}",
        f"  Top losers: {', '.join(data.get('top_losers_closed') or ['none'])}",
        "",
        "--- Growth Intelligence ---",
        f"Verdict: {gii.get('global_verdict', 'N/A')}",
        f"Global growth score: {gii_portfolio.get('global_growth_score', 'N/A')}",
        f"Growth quality: {gii_portfolio.get('portfolio_growth_quality', 'N/A')}",
        f"Opportunity cost: {_fmt_money(gii_portfolio.get('opportunity_cost_total'))}",
        f"Growth risk: {gii_portfolio.get('growth_risk', 'N/A')}",
        f"Top growth candidates: {', '.join(gii_portfolio.get('top_growth_candidates') or [])}",
        "",
        "--- Profit Protection ---",
        f"Verdict: {protection_daily.get('verdict', protection.get('verdict', 'N/A'))}",
        f"Profit lock active: {protection_daily.get('num_profit_lock_active', 'N/A')}",
        f"Profit at risk: {protection_daily.get('num_profit_at_risk', 'N/A')}",
        f"Missed opportunity: {_fmt_money(protection_daily.get('total_missed_opportunity'))}",
        f"Rules v1: {protection_daily.get('rules_v1_verdict', 'N/A')}",
        "",
        "--- PPG (Portfolio Profit Governor) ---",
        f"Portfolio verdict: {ppg.get('portfolio_verdict', 'N/A')}",
        f"Status: {ppg.get('final_status', 'N/A')}",
        f"Profit quality score: {ppg_metrics.get('portfolio_profit_quality_score', 'N/A')}",
        f"Profit at risk score: {ppg_metrics.get('portfolio_profit_at_risk_score', 'N/A')}",
        f"Protect / trail / watch: {ppg_metrics.get('protect_shadow_count', 0)}/"
        f"{ppg_metrics.get('trail_shadow_count', 0)}/{ppg_metrics.get('watch_shadow_count', 0)}",
        "",
        "--- APPE (Adaptive Profit Policy Engine) ---",
        f"Final verdict: {appe_summary.get('final_verdict', 'N/A')}",
        f"Policy state: {appe_summary.get('latest_policy_state', 'N/A')}",
        f"Suggested shadow policy: {appe_summary.get('latest_suggested_shadow_policy', 'N/A')}",
        f"Portfolio verdict: {appe_summary.get('latest_portfolio_verdict', 'N/A')}",
        "",
        "--- V1 vs V2 (Parallel PAPER profit/loss management; NOT DPE Competitive/Collaborative) ---",
    ])
    try:
        from research_core.economics.v1_v2_economic_comparison import format_comparison_section

        lines.append(format_comparison_section(data.get("v1_v2_comparison") or {}, verbose=False))
        lines.append("")
    except Exception as exc:
        lines.append(f"  unavailable: {exc}")
        lines.append("")
    lines.extend([
        "--- DPE Recommendation ---",
        f"Evaluation winner: {overall.get('winner', 'N/A')} @ {overall.get('confidence_pct', 'N/A')}%",
        f"Competitive realized: {_fmt_money((evaluation.get('competitive') or {}).get('realized_pnl'))}",
        f"Collaborative realized: {_fmt_money((evaluation.get('collaborative') or {}).get('realized_pnl'))}",
        f"Metric wins: COMP {overall.get('competitive_metric_wins', 'N/A')} / "
        f"COLLAB {overall.get('collaborative_metric_wins', 'N/A')} / TIE {overall.get('ties', 'N/A')}",
        "",
        "--- Adaptive Recommendation ---",
        f"Preferred: {adaptive.get('preferred_philosophy', 'N/A')}",
        f"Competitive weight: {_fmt_pct(adaptive.get('competitive_pct'))}",
        f"Collaborative weight: {_fmt_pct(adaptive.get('collaborative_pct'))}",
        f"Confidence: {_fmt_pct(adaptive.get('confidence'))}",
        f"Context: {adaptive.get('context_label', 'N/A')}",
        f"Recommendation: {adaptive.get('recommendation', 'N/A')}",
        "",
        "--- Outstanding Risks ---",
    ])
    for risk in data.get("outstanding_risks") or ["none identified"]:
        lines.append(f"  - {risk}")
    lines.extend([
        "",
        "--- Jobs / Execution Semantics ---",
        "DPE READY jobs are shadow evaluation artifacts and are not canonical PAPER execution instructions.",
        f"DPE_SHADOW_READY_CUMULATIVE: {data.get('DPE_SHADOW_READY_CUMULATIVE', data.get('jobs_ready_unique', 0))} "
        f"unique ({data.get('jobs_ready', 0)} lines)",
        f"DPE_SHADOW_READY_TODAY: {data.get('DPE_SHADOW_READY_TODAY', data.get('jobs_ready_unique_today', 0))} "
        f"unique ({data.get('jobs_ready_today', 0)} lines)",
        f"PAPER_NEW_EXECUTION_CANDIDATES: {(data.get('paper_execution_semantics') or {}).get('PAPER_NEW_EXECUTION_CANDIDATES')}",
        f"PAPER_EXECUTED: {(data.get('paper_execution_semantics') or {}).get('PAPER_EXECUTED')}",
        f"PAPER_BLOCKED_AFTER_DECISION: {(data.get('paper_execution_semantics') or {}).get('PAPER_BLOCKED_AFTER_DECISION')} "
        f"reasons={(data.get('paper_execution_semantics') or {}).get('block_reasons')}",
        f"BLOCKED history: UNIQUE_BLOCKED_JOBS={((data.get('job_history') or {}).get('UNIQUE_BLOCKED_JOBS'))} "
        f"TOTAL_BLOCKED_EVENT_LINES={((data.get('job_history') or {}).get('TOTAL_BLOCKED_EVENT_LINES'))} "
        f"BLOCKED_EVENTS_TODAY={((data.get('job_history') or {}).get('BLOCKED_EVENTS_TODAY'))} "
        f"UNIQUE_BLOCKED_JOBS_TODAY={((data.get('job_history') or {}).get('UNIQUE_BLOCKED_JOBS_TODAY'))} "
        f"TOP={((data.get('job_history') or {}).get('TOP_BLOCK_TICKER'))}/"
        f"{((data.get('job_history') or {}).get('TOP_BLOCK_REASON'))} "
        f"avg_events/job={((data.get('job_history') or {}).get('AVERAGE_EVENTS_PER_JOB'))}",
        f"Counts: {data.get('job_counts') or {}}",
        f"Last job timestamp: {data.get('last_jobs_timestamp') or 'N/A'}",
        "",
        "--- Market Session ---",
        f"Session status: {data.get('market_session', 'UNKNOWN')}",
        f"Bot running: {'yes' if data.get('bot_running') else 'no'}",
        f"Last bot log timestamp: {data.get('last_log_timestamp') or 'N/A'}",
        "",
        "--- Infrastructure Health ---",
        f"Overall: {infra.get('overall_status', 'N/A')}",
        f"Autostart readiness: {infra.get('autostart_readiness', 'N/A')}",
        f"Checks: {(infra.get('summary') or {})}",
        f"Process health snapshot: {(data.get('process') or {}).get('status', 'N/A')} "
        f"@ {(data.get('process') or {}).get('checked_at', 'N/A')}",
        "",
        "--- Last Execution Timestamps ---",
        f"Competitive paper: {comp_metrics.get('last_execution_timestamp', 'N/A')}",
        f"Collaborative paper: {collab_metrics.get('last_execution_timestamp', 'N/A')}",
        f"DPE evaluation: {evaluation.get('generated_at', 'N/A')}",
        f"DPE learning updated: {learning.get('updated_at', 'N/A')}",
        f"DPE adaptive: {adaptive.get('generated_at', 'N/A')}",
        f"Last decision event: {data.get('last_events_timestamp') or 'N/A'}",
        "",
        "--- JSON Freshness ---",
    ])
    for row in data.get("freshness_rows") or []:
        lines.append(
            f"  {row['label']}: {row['status']} | age={row.get('age_hours')}h | "
            f"generated={row.get('generated_at') or 'N/A'}"
        )
    lines.extend([
        "",
        "--- Errors ---",
    ])
    if data.get("errors"):
        lines.extend(f"  ERROR: {err}" for err in data["errors"])
    else:
        lines.append("  none")
    lines.extend([
        "",
        f"Warning count: {data.get('warning_count', 0)}",
    ])
    if data.get("warnings"):
        for warn in data["warnings"][:10]:
            lines.append(f"  WARN: {warn}")

    portfolio_status = (
        f"CANONICAL {_fmt_money(accounting.get('account_value_corrected'))} | "
        f"PAPER {_fmt_money(integrity_metrics.get('account_value'))} | "
        f"{accounting.get('open_positions_count', 0)} canonical open positions"
    )
    growth_status = (
        f"{gii.get('global_verdict', 'N/A')} — growth score "
        f"{gii_portfolio.get('global_growth_score', 'N/A')}"
    )
    protection_status = (
        f"{ppg.get('portfolio_verdict', 'N/A')} — "
        f"{protection_daily.get('num_profit_at_risk', 0)} positions at risk"
    )
    dpe_status = (
        f"{adaptive.get('preferred_philosophy', 'N/A')} preferred "
        f"({_fmt_pct(adaptive.get('collaborative_pct'))} collaborative weight)"
    )
    infra_status = (
        f"{infra.get('overall_status', 'N/A')} — autostart {infra.get('autostart_readiness', 'N/A')}"
    )
    e3 = data.get("e3_forward") or {}
    e3_line = (
        f"status={e3.get('status', 'N/A')} | maturity={e3.get('sample_maturity', 'N/A')} | "
        f"baseline PnL={e3.get('baseline_pnl', 'N/A')} | E3 PnL={e3.get('e3_pnl', 'N/A')} | "
        f"delta={e3.get('delta', 'N/A')} | blocked={e3.get('entries_blocked', 'N/A')} | "
        f"avoided={e3.get('avoided_loss', 'N/A')} | missed={e3.get('missed_profit', 'N/A')} | "
        f"verdict={e3.get('current_verdict', 'N/A')}"
    )
    e3c = data.get("e3_canonical") or {}
    tickers = e3c.get("tickers") or []
    tickers_s = ",".join(tickers[:8]) if tickers else "none"
    e3_canonical_line = (
        f"enabled: {e3c.get('enabled', 'N/A')} | "
        f"new BUY blocked today: {e3c.get('new_buy_blocked_today', 'N/A')} | "
        f"tickers: {tickers_s} | "
        f"avoided-loss tracking: {e3c.get('avoided_loss_tracking', 'N/A')} | "
        f"missed-profit tracking: {e3c.get('missed_profit_tracking', 'N/A')} | "
        f"net E3 value: {e3c.get('net_e3_value', 'N/A')}"
    )
    on = data.get("opening_noise") or {}
    opening_noise_line = (
        f"enabled: {on.get('enabled', 'N/A')} | window: {on.get('window', 'N/A')} | "
        f"new BUYs deferred today: {on.get('new_buys_deferred_today', 'N/A')} | "
        f"requalified: {on.get('requalified', 'N/A')} | "
        f"executed after window: {on.get('executed_after_window', 'N/A')} | "
        f"expired: {on.get('expired', 'N/A')} | "
        f"later blocked by E3: {on.get('later_blocked_by_e3', 'N/A')} | "
        f"net protection value: {on.get('net_protection_value', 'N/A')}"
    )
    rm = data.get("regional_marks") or {}
    def _rm_line(sym: str) -> str:
        row = rm.get(sym) or {}
        if isinstance(row, dict):
            return f"{row.get('status', 'N/A')}"
        return "N/A"
    regional_marks_block = (
        f"AZN.L: {_rm_line('AZN.L')} | BP.L: {_rm_line('BP.L')} | SAP.DE: {_rm_line('SAP.DE')} | "
        f"valid: {rm.get('valid_regional_marks', 'N/A')} | "
        f"missing: {rm.get('missing_regional_marks', 'N/A')} | "
        f"stale: {rm.get('stale_regional_marks', 'N/A')}"
    )
    overall_health = f"{data['verdict']} (score {data['global_score']}/100)"
    today_rec = adaptive.get("recommendation") or overall.get("recommendation") or "Continue shadow monitoring"
    immediate_risks = "; ".join(data.get("outstanding_risks") or []) or "none"
    next_actions = "; ".join(data.get("next_actions") or []) or "none"

    lines.extend([
        "",
        "==========================",
        "TAE MORNING BRIEF",
        "==========================",
        "",
        "Portfolio Status",
        portfolio_status,
        "",
        "Growth Status",
        growth_status,
        "",
        "Protection Status",
        protection_status,
        "",
        "DPE Status",
        dpe_status,
        "",
        "Infrastructure Status",
        infra_status,
        "",
        "Canonical E3 Entry Protection",
        e3_canonical_line,
        "",
        "Canonical Opening-Noise Protection",
        opening_noise_line,
        "",
        "Regional Mark Health",
        regional_marks_block,
        "",
        "E3 Forward PAPER (shadow/historical)",
        e3_line,
        "",
        "Overall Health",
        overall_health,
        "",
        "Today's Recommendation",
        today_rec,
        "",
        "Immediate Risks",
        immediate_risks,
        "",
        "Next Actions",
        next_actions,
        "",
        "TAE HEALTH SCORE",
        f"{data['global_score']}/100",
        "",
        "Breakdown:",
        f"  Infrastructure: {health['infrastructure']}",
        f"  Portfolio: {health['portfolio']}",
        f"  Growth: {health['growth']}",
        f"  Protection: {health['protection']}",
        f"  Learning: {health['learning']}",
        f"  DPE: {health['dpe']}",
        f"  Data freshness: {health['data_freshness']}",
        "",
        data["verdict"],
        "",
    ])
    return "\n".join(lines)


def format_operator_summary(data: dict[str, Any]) -> str:
    accounting = data.get("accounting") or {}
    live = data.get("live_checks") or {}
    writer_ok = "PASS" if data.get("CANONICAL_WRITER_OK") else "FAIL"
    port = (live.get("sections") or {}).get("portfolio_integrity") or {}
    port_ok = "PASS" if port.get("ok") else "FAIL"
    findings = [
        f
        for f in (data.get("live_findings") or [])
        if f.get("severity") in {"CRITICAL", "ERROR", "WARNING"}
    ]
    lines = [
        "TAE MORNING AUDIT",
        f"Timestamp: {data.get('generated_at')}",
        f"Runtime: live | write_report={data.get('write_report')}",
        f"Account value: {_fmt_money(accounting.get('account_value_corrected'))}",
        f"Cash: {_fmt_money(accounting.get('cash_available'))}",
        f"Open positions: {accounting.get('open_positions_count', len(data.get('open_positions') or []))}",
        f"Writer: {writer_ok} ({live.get('LIVE_WRITER_OWNERSHIP')}) lock={live.get('LOCK_HEALTH')}",
        f"Portfolio integrity: {port_ok} | shrink={data.get('SHRINK_STATUS')}",
        f"Decision/execution: PAPER integrity={'PASS' if data.get('integrity_ok') else 'FAIL'} "
        f"recon={'PASS' if data.get('reconciliation_ok') else 'FAIL'}",
        f"Market data: session={data.get('market_session')} bot_running={data.get('bot_running')}",
        f"Learning: DPE score={(data.get('health_scores') or {}).get('learning')}",
        f"Repository: {((live.get('sections') or {}).get('repository') or {}).get('details', {}).get('branch')} "
        f"@ {str(((live.get('sections') or {}).get('repository') or {}).get('details', {}).get('head') or '')[:12]}",
        f"Score: {data.get('global_score')}/100",
        f"OPERATIONAL_STATUS: {data.get('OPERATIONAL_STATUS') or 'N/A'}",
        f"PAPER_INTEGRITY_STATUS: {data.get('PAPER_INTEGRITY_STATUS') or 'N/A'}",
        f"ECONOMIC_COMPARISON_STATUS: {data.get('ECONOMIC_COMPARISON_STATUS') or 'N/A'}",
        f"OVERALL_STATUS: {data.get('OVERALL_STATUS') or data.get('tae_daily_status')}",
        f"FINAL STATUS: {data.get('tae_daily_status') or data.get('verdict')}",
        "",
        "DPE READY jobs are shadow evaluation artifacts and are not canonical PAPER execution instructions.",
        f"DPE_SHADOW_READY_CUMULATIVE={data.get('DPE_SHADOW_READY_CUMULATIVE', data.get('jobs_ready_unique'))} "
        f"DPE_SHADOW_READY_TODAY={data.get('DPE_SHADOW_READY_TODAY', data.get('jobs_ready_unique_today'))} "
        f"PAPER_NEW_EXECUTION_CANDIDATES={(data.get('paper_execution_semantics') or {}).get('candidate_count')} "
        f"PAPER_EXECUTED={(data.get('paper_execution_semantics') or {}).get('executed_count')} "
        f"PAPER_BLOCKED_AFTER_DECISION={(data.get('paper_execution_semantics') or {}).get('blocked_count')} "
        f"block_reasons={(data.get('paper_execution_semantics') or {}).get('block_reasons')}",
        "",
        "INFO: dual-journal recording of the same economic fill is expected; "
        "execution_id integrity separates equivalent dual-journal rows from true conflicts.",
        f"STATE_OWNERSHIP_ISOLATION={(data.get('v1_v2_comparison') or {}).get('STATE_OWNERSHIP_ISOLATION')} "
        f"EXECUTION_ID_INTEGRITY={(data.get('v1_v2_comparison') or {}).get('EXECUTION_ID_INTEGRITY')} "
        f"DUAL_JOURNAL_EQUIVALENT_IDS={(data.get('v1_v2_comparison') or {}).get('DUAL_JOURNAL_EQUIVALENT_IDS')} "
        f"CROSS_ARM_CONTAMINATION={(data.get('v1_v2_comparison') or {}).get('CROSS_ARM_CONTAMINATION')}",
        "",
    ]
    if findings:
        lines.append("--- Failed / warning controls ---")
        for f in findings[:25]:
            lines.append(f"  [{f.get('severity')}] {f.get('code')}: {f.get('message')}")
        lines.append("")
    warns = data.get("warnings") or []
    if warns:
        lines.append("--- Warnings ---")
        for w in warns[:12]:
            lines.append(f"  {w}")
        lines.append("")
    risks = data.get("outstanding_risks") or []
    if risks:
        lines.append("--- Immediate risks ---")
        for r in risks[:12]:
            lines.append(f"  - {r}")
        lines.append("")
    actions = data.get("next_actions") or []
    if actions:
        lines.append("--- Operator actions ---")
        for a in actions:
            lines.append(f"  - {a}")
        lines.append("")
    try:
        from research_core.economics.v1_v2_economic_comparison import format_comparison_section

        lines.append(format_comparison_section(data.get("v1_v2_comparison") or {}, verbose=False))
    except Exception as exc:
        lines.append(f"V1 vs V2 economic section unavailable: {exc}")
        lines.append("")
    lines.append(str(data.get("tae_daily_status") or data.get("verdict")))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import os
    from datetime import datetime, timezone

    parser = argparse.ArgumentParser(description="TAE morning operational audit (canonical daily)")
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Persist infrastructure health + profit pipeline artifacts (default: read-only)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full legacy morning brief in addition to operator summary",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    data = run_audit(write_report=bool(args.write_report))
    # Always persist the audit snapshot — mandatory orchestration freshness artifact.
    data = dict(data)
    data.setdefault("schema", "tae.morning_operational_audit.v1")
    data["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    data["trading_date"] = datetime.now().date().isoformat()
    orch_id = os.environ.get("TAE_ORCHESTRATION_RUN_ID")
    if orch_id:
        data["orchestration_run_id"] = orch_id
    try:
        import subprocess

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode == 0:
            data["source_commit"] = head.stdout.strip()
    except OSError:
        pass
    out_json = ROOT / "tae_morning_operational_audit.json"
    out_md = ROOT / "TAE_MORNING_OPERATIONAL_AUDIT.md"
    out_json.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    summary = format_operator_summary(data)
    out_md.write_text(summary + "\n", encoding="utf-8")

    print(summary)
    if args.verbose:
        print(format_report(data))
        try:
            from research_core.economics.v1_v2_economic_comparison import format_comparison_section

            print(format_comparison_section(data.get("v1_v2_comparison") or {}, verbose=True))
        except Exception as exc:
            print(f"V1 vs V2 verbose section unavailable: {exc}")

    status = str(data.get("tae_daily_status") or data.get("verdict") or "")
    if status in {"HEALTHY", "PASS"}:
        return 0
    if status in {"ATTENTION_REQUIRED", "PASS_WITH_WARNINGS"}:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
