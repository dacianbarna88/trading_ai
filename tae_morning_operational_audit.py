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
PROTECTION_JSON = ROOT / "tae_profit_protection_shadow.json"
PPG_JSON = ROOT / "tae_portfolio_profit_governor.json"
APPE_JSON = ROOT / "tae_adaptive_profit_policy_engine.json"
INFRA_JSON = ROOT / "tae_infrastructure_health.json"
PROCESS_JSON = ROOT / "process_health.json"
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
    ("profit_protection", PROTECTION_JSON, 24),
    ("ppg", PPG_JSON, 24),
    ("appe", APPE_JSON, 24),
    ("dpe_adaptive", DPE_ADAPTIVE, 48),
    ("dpe_evaluation", DPE_EVAL, 48),
    ("dpe_learning", DPE_LEARNING, 48),
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
        return any("live_bot.py" in line for line in (result.stdout or "").splitlines())
    return bool((result.stdout or "").strip())


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


def _count_jobs() -> dict[str, Any]:
    counts: Counter[str] = Counter()
    blocked_ids: set[str] = set()
    ready_ids: set[str] = set()
    if not DPE_JOBS.is_file():
        return {"counts": dict(counts), "blocked_unique": 0, "ready_unique": 0}
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
            if status == "BLOCKED" and job_id:
                blocked_ids.add(job_id)
            if status == "READY" and job_id:
                ready_ids.add(job_id)
    except OSError:
        pass
    return {
        "counts": dict(counts),
        "blocked_unique": len(blocked_ids),
        "ready_unique": len(ready_ids),
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
    for label, path, warn_hours in FRESHNESS_TARGETS:
        age = _file_age_hours(path)
        exists = path.is_file()
        generated = None
        payload = _load_json(path) if exists and path.suffix == ".json" else None
        if payload:
            generated = payload.get("generated_at") or payload.get("updated_at")
        status = "OK"
        if not exists:
            status = "MISSING"
            errors.append(f"Missing file: {path}")
        elif age is not None and age > warn_hours:
            status = "STALE"
            warnings.append(f"Stale {label}: {path.name} ({age}h old, threshold {warn_hours}h)")
        rows.append(
            {
                "label": label,
                "path": str(path),
                "exists": exists,
                "age_hours": age,
                "generated_at": generated,
                "status": status,
            }
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
) -> str:
    fail_count = int((infra or {}).get("summary", {}).get("fail") or 0)
    blocking_warnings = [w for w in warnings if "Stale " in w or "Missing file" in w]
    if not integrity_ok or len(errors) >= 1 or fail_count >= 2:
        return "CRITICAL"
    if stale_critical or blocking_warnings or fail_count >= 1 or global_score < 70:
        return "ATTENTION_REQUIRED"
    if global_score < 80 or errors:
        return "ATTENTION_REQUIRED"
    return "READY"


def run_audit() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    accounting = _load_json(ACCOUNTING_JSON)
    gii = _load_json(GII_JSON)
    protection = _load_json(PROTECTION_JSON)
    ppg = _load_json(PPG_JSON)
    appe = _load_json(APPE_JSON)
    infra = _load_json(INFRA_JSON)
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

        profit_pipeline = build_profit_pipeline(write_outputs=True)
    except Exception as exc:
        profit_pipeline = {"error": str(exc)}
        warnings.append(f"Profit pipeline consolidation failed: {exc}")

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
    jobs_blocked = int(job_counts.get("BLOCKED", 0))
    jobs_blocked_unique = int(job_info.get("blocked_unique", 0))

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
    verdict = _compute_verdict(
        global_score,
        errors,
        warnings,
        infra,
        integrity_ok=integrity_ok,
        stale_critical=stale_critical,
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
    if not integrity_ok:
        outstanding_risks.append(f"PAPER profit integrity: {integrity.get('verdict', 'FAIL')}")
    if jobs_blocked_unique:
        outstanding_risks.append(
            f"{jobs_blocked_unique} unique DPE jobs BLOCKED ({jobs_blocked} jsonl lines) — expected HSBA.L COLLAPSE_RISK"
        )
    if str(ppg.get("portfolio_verdict") or "").endswith("HIGH_RISK"):
        outstanding_risks.append("Portfolio flagged HIGH_RISK by PPG")

    next_actions: list[str] = []
    if jobs_ready_unique:
        next_actions.append(f"Review {jobs_ready_unique} unique READY DPE paper jobs (shadow only)")
    if fresh_warnings:
        next_actions.append("Run: python3 tae.py full-paper-cycle")
    if not bot_running:
        next_actions.append("Verify live_bot autostart / process health")
    if adaptive:
        next_actions.append(str(adaptive.get("recommendation") or "Run DPE adaptive review"))
    if not next_actions:
        next_actions.append("Continue shadow monitoring — no live changes required")

    return {
        "generated_at": _now_iso(),
        "mode": MODE,
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
        "jobs_blocked": jobs_blocked,
        "jobs_blocked_unique": jobs_blocked_unique,
        "last_jobs_timestamp": _last_jsonl_timestamp(DPE_JOBS),
        "last_events_timestamp": _last_jsonl_timestamp(DPE_EVENTS),
        "freshness_rows": freshness_rows,
        "errors": errors,
        "warnings": warnings,
        "warning_count": len(warnings),
        "health_scores": health_scores,
        "global_score": global_score,
        "verdict": verdict,
        "integrity_ok": integrity_ok,
        "integrity_metrics": integrity_metrics,
        "reconciliation_ok": bool(reconciliation.get("ok")),
        "synthetic_fill_contamination": contaminated_count,
        "profit_pipeline": profit_pipeline,
        "outstanding_risks": outstanding_risks[:8],
        "next_actions": next_actions[:5],
        "gii_portfolio": gii_portfolio,
        "ppg_metrics": ppg_metrics,
        "appe_summary": appe_summary,
        "protection_daily": protection_daily,
        "overall_eval": overall,
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
        "--- Jobs Waiting ---",
        f"READY: {data.get('jobs_ready_unique', 0)} unique ({data.get('jobs_ready', 0)} lines) | "
        f"BLOCKED: {data.get('jobs_blocked_unique', 0)} unique ({data.get('jobs_blocked', 0)} lines) | "
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


def main() -> int:
    data = run_audit()
    print(format_report(data))
    return 0 if data["verdict"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
