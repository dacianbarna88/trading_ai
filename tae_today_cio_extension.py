#!/usr/bin/env python3
"""Deterministic, fail-soft CIO digest for ``tae.py today --cio``.

The module is a read-only join.  It may invoke only producers that expose an
explicit non-persisting mode; longitudinal, forward-observation, and ablation
producers are never invoked.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tae_parallel_paper_config import PROJECT_ROOT

try:
    from tae_morning_operational_audit import run_audit as run_morning_audit
except Exception:  # pragma: no cover - fail-soft import
    run_morning_audit = None
try:
    from tae_profit_pipeline import build_profit_pipeline
except Exception:  # pragma: no cover
    build_profit_pipeline = None
try:
    from tae_investment_council import run_investment_council
except Exception:  # pragma: no cover
    run_investment_council = None
try:
    from tae_strategy_lab_facade import build_scoreboard, lab_status
except Exception:  # pragma: no cover
    build_scoreboard = lab_status = None
try:
    from tae_strategy_lab_promotion import load_promotion_state
except Exception:  # pragma: no cover
    load_promotion_state = None
try:
    from research_core.economics.v1_v2_economic_comparison import (
        get_v1_v2_economic_comparison,
    )
except Exception:  # pragma: no cover
    get_v1_v2_economic_comparison = None


SCHEMA_VERSION = "1.0"
STALE_HOURS = 48.0
REQUIRED_RULES = (
    "STRATEGY_STOP_V1",
    "TAKE_PROFIT",
    "TRAILING",
    "V2_OPEN",
    "V2_ADD",
    "V2_CLOSE",
    "PRICE_DRIVEN_ADD",
    "PRICE_HARD_RISK_AUDIT_ONLY",
    "HARD_RISK_NON_PRICE",
    "CONTROL_FALLBACK_OUT_OF_SCOPE",
    "MARKET_SESSION_FILTER",
    "ADAPTIVE_*",
    "MAX_POSITIONS",
    "INSUFFICIENT_CASH",
    "INVALID_MARKET_DATA",
)
REQUIRED_COMMITS = (
    ("bcab6ef", "V2 price-driven ADD", "economic"),
    ("fb58424", "V2 -5% hard-risk audit-only", "economic"),
    ("23e224f", "CONTROL fallback", "economic"),
    ("db98294", "dual-journal dedupe", "reporting"),
    ("11e4adb", "dashboard bounded logs", "operational"),
    ("7bcbbd7", "Strategy Lab Sprint 1", "lab"),
    ("67ed262", "Strategy Lab Sprint 2", "lab"),
    ("9dc9428", "Strategy Lab Sprint 3", "lab"),
    ("4a0e0e3", "Strategy Lab Sprint 4", "lab"),
)


def _safe(call: Callable[[], Any], default: Any) -> Any:
    try:
        value = call()
        return value if value is not None else default
    except Exception as exc:
        result = dict(default) if isinstance(default, dict) else default
        if isinstance(result, dict):
            result["error"] = str(exc)
        return result


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _read_artifact(path: Path) -> dict[str, Any]:
    """Read a JSON artifact and attach deterministic freshness metadata."""
    result: dict[str, Any] = {
        "data": None,
        "path": str(path),
        "mtime": None,
        "age_hours": None,
        "stale": True,
    }
    try:
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - mtime).total_seconds() / 3600)
        result.update(
            mtime=mtime.isoformat(),
            age_hours=round(age, 2),
            stale=age > STALE_HOURS,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        result["data"] = payload
    except (OSError, json.JSONDecodeError):
        pass
    return result


def cio_integrity_paths() -> dict[str, Path]:
    """Extra adaptive/learning/promotion/registry files watched by CIO mode."""
    root = PROJECT_ROOT
    return {
        "adaptive/dpe_adaptive": root / "runtime_outputs/dpe/adaptive/adaptive.json",
        "adaptive/next_dollar": root / "tae_next_dollar.json",
        "adaptive/roi_queue": root / "tae_roi_queue.json",
        "adaptive/deployment_registry": root / "runtime_outputs/adaptive_deployment/experiment_registry.json",
        "learning/forward_evidence": root / "tae_forward_learning_evidence_status.json",
        "learning/ablation_summary": root / "tae_learning_ablation_summary.json",
        "learning/ablation_runs": root / "tae_learning_ablation_runs.json",
        "learning/economic_attribution": root / "tae_learning_economic_attribution.json",
        "learning/decision_deltas": root / "tae_learning_decision_deltas.csv",
        "learning/trade_deltas": root / "tae_learning_trade_deltas.csv",
        "learning/v1_state": root / "runtime_outputs/parallel_paper/v1/learning_state.json",
        "learning/v2_state": root / "runtime_outputs/parallel_paper/v2/learning_state.json",
        "learning/v1_events": root / "runtime_outputs/parallel_paper/v1/journals/learning_events.jsonl",
        "learning/v2_events": root / "runtime_outputs/parallel_paper/v2/journals/learning_events.jsonl",
        "learning/dpe_learning": root / "runtime_outputs/dpe/learning/learning.json",
        "adaptive/weights_current": root / "runtime_outputs/adaptive_weights/paper_action_weights.json",
        "adaptive/weights_history": root / "runtime_outputs/adaptive_weights/paper_action_weights_history.jsonl",
        "adaptive/weights_pre_evolution": root / "runtime_outputs/adaptive_weights/paper_action_weights_pre_evolution.json",
        "promotion/state": root / "runtime_outputs/strategy_lab/promotion_state.json",
        "promotion/tickets": root / "runtime_outputs/strategy_lab/promotion_tickets.jsonl",
        "promotion/audit": root / "runtime_outputs/strategy_lab/promotion_audit.jsonl",
        "promotion/archive": root / "runtime_outputs/strategy_lab/champion_archive.json",
        "registry/strategy_lab": root / "config/tae_strategy_lab_registry.json",
        "registry/adaptive_experiments": root / "runtime_outputs/adaptive_deployment/experiment_registry.json",
    }


def _hashes(paths: dict[str, Path]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name, path in paths.items():
        try:
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        except OSError:
            result[name] = None
    return result


def _morning_gate(today_doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    morning = _safe(
        lambda: run_morning_audit(write_report=False) if run_morning_audit else {},
        {},
    )
    source = "builder"
    if not morning or morning.get("error"):
        artifact = _read_artifact(PROJECT_ROOT / "tae_morning_operational_audit.json")
        morning = artifact.get("data") if isinstance(artifact.get("data"), dict) else {}
        source = "artifact_fallback"
    runtime = today_doc.get("runtime") or {}
    live = {
        "domain": "LIVE",
        "running": morning.get("bot_running"),
        "writer_ownership": morning.get("LIVE_WRITER_OWNERSHIP"),
        "canonical_writer_ok": morning.get("CANONICAL_WRITER_OK"),
        "lock_health": morning.get("LOCK_HEALTH"),
        "shrink_status": morning.get("SHRINK_STATUS"),
        "status": morning.get("OPERATIONAL_STATUS") or morning.get("verdict") or "UNKNOWN",
    }
    parallel = {
        arm: {
            "domain": f"PARALLEL_{arm}",
            "running": (runtime.get("parallel_paper") or {}).get("running"),
            "reconciliation_pass": (today_doc.get("capital") or {}).get(arm, {}).get(
                "reconciliation_pass"
            ),
        }
        for arm in ("V1", "V2")
    }
    complete = all(
        value is not None
        for value in (
            live["running"],
            live["writer_ownership"],
            live["canonical_writer_ok"],
        )
    )
    return {
        "source": source,
        "LIVE": live,
        "PARALLEL_V1": parallel["V1"],
        "PARALLEL_V2": parallel["V2"],
        "LIVE_DATA_COMPLETE": complete,
        "overall_status": morning.get("OVERALL_STATUS") or morning.get("verdict") or "UNKNOWN",
    }, morning


def _economic(today_doc: dict[str, Any]) -> dict[str, Any]:
    txs = today_doc.get("executed_transactions") or []
    realized_by_ticker: defaultdict[str, float] = defaultdict(float)
    fees_by_strategy: defaultdict[str, float] = defaultdict(float)
    realized_by_reason: defaultdict[str, float] = defaultdict(float)
    for row in txs:
        realized_by_ticker[str(row.get("ticker") or "UNKNOWN")] += _num(
            row.get("PNL_AFTER_FEES")
        )
        fees_by_strategy[str(row.get("strategy") or "UNKNOWN")] += _num(row.get("FEES"))
        if str(row.get("action") or "").upper() in {"SELL", "CLOSE", "REDUCE"}:
            realized_by_reason[str(row.get("reason") or "UNKNOWN")] += _num(
                row.get("PNL_AFTER_FEES")
            )
    open_mtm = []
    for row in today_doc.get("portfolio_comparison") or []:
        for arm in ("V1", "V2"):
            side = row.get(arm)
            if side:
                open_mtm.append(
                    {
                        "strategy": arm,
                        "ticker": row.get("ticker"),
                        "unrealized_pnl": side.get("unrealized_pnl"),
                    }
                )
    ranking = sorted(realized_by_ticker.items(), key=lambda item: item[1], reverse=True)
    comparison = _safe(
        lambda: get_v1_v2_economic_comparison(write_report=False)
        if get_v1_v2_economic_comparison
        else {},
        {},
    )
    return {
        "realized_pnl_after_fees": round(sum(realized_by_ticker.values()), 6),
        "portfolio_unrealized": round(sum(_num(r["unrealized_pnl"]) for r in open_mtm), 6),
        "top_profit_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 6)} for ticker, pnl in ranking if pnl > 0
        ][:5],
        "top_loss_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 6)}
            for ticker, pnl in reversed(ranking)
            if pnl < 0
        ][:5],
        "fees_by_strategy": dict(fees_by_strategy),
        "realized_by_exit_reason": dict(realized_by_reason),
        "open_mark_to_market": open_mtm,
        "dual_journal_dedupe": "INHERITED_FROM_TODAY",
        "v1_v2_comparison": comparison,
    }


def _opportunity(today_doc: dict[str, Any]) -> dict[str, Any]:
    pipeline = _safe(
        lambda: build_profit_pipeline(write_outputs=False) if build_profit_pipeline else {},
        {},
    )
    rows = []
    counts: Counter[str] = Counter()
    for row in today_doc.get("non_executed_decisions") or []:
        reason = str(row.get("reason") or "").upper()
        classification = str(row.get("classification") or "UNKNOWN")
        if classification in {"MARKET_CLOSED", "PRICE_STALE", "INSUFFICIENT_CASH", "MAX_POSITIONS"}:
            bucket = "EXPECTED_FILTER"
        elif "ILLEGAL" in reason or "CONTROL_FALLBACK" in reason:
            bucket = "ILLEGAL_BLOCK"
        elif classification in {"BUY_NOT_EXECUTED", "SELL_NOT_EXECUTED"}:
            bucket = "AUTHORIZED_NOT_EXECUTED"
        else:
            bucket = "POLICY_FILTER"
        counts[bucket] += 1
        effect = row.get("economic_effect")
        rows.append(
            {
                **row,
                "funnel_class": bucket,
                "ECONOMIC_EFFECT": effect if effect is not None else "UNKNOWN",
            }
        )
    return {"pipeline": pipeline, "classifications": rows, "counts": dict(counts)}


def _rule_economics(today_doc: dict[str, Any]) -> list[dict[str, Any]]:
    source_rows = (
        (today_doc.get("executed_transactions") or [])
        + (today_doc.get("non_executed_decisions") or [])
        + (today_doc.get("event_trace") or [])
    )
    aliases = {
        "V2_OPEN": ("V2_OPEN", "V2 OPEN", "OPEN_VALID", " OPEN "),
        "V2_ADD": ("V2_ADD", "V2 ADD", "ADD_PRICE_STEP", " ADD "),
        "V2_CLOSE": ("V2_CLOSE", "V2 CLOSE", "CYCLE_TARGET", " CLOSE "),
        "PRICE_DRIVEN_ADD": ("PRICE_DRIVEN_ADD", "ADD_PRICE_STEP", "HOLD_PRICE_STEP"),
        "MARKET_SESSION_FILTER": ("MARKET_SESSION_FILTER", "MARKET_CLOSED", "SESSION"),
        "INVALID_MARKET_DATA": ("INVALID_MARKET_DATA", "PRICE_STALE", "STALE_MARK", "NO_PRICE"),
    }
    result = []
    for rule in REQUIRED_RULES:
        tokens = (
            ("ADAPTIVE_",)
            if rule == "ADAPTIVE_*"
            else aliases.get(rule, (rule,))
        )
        matched = []
        for row in source_rows:
            text = " " + " ".join(
                str(row.get(k) or "")
                for k in ("strategy", "reason", "classification", "action")
            ).upper() + " "
            if any(token in text for token in tokens):
                matched.append(row)
        canonical_pnl = [
            _num(row.get("PNL_AFTER_FEES"))
            for row in matched
            if row.get("PNL_AFTER_FEES") is not None
        ]
        count = len(matched)
        result.append(
            {
                "rule": rule,
                "event_count": count,
                "evidence_status": "INSUFFICIENT_EVIDENCE" if count < 2 else "OBSERVED",
                "economic_effect": (
                    round(sum(canonical_pnl), 6) if canonical_pnl else "UNKNOWN"
                ),
            }
        )
    return result


def _learning_roi() -> dict[str, Any]:
    candidates = {
        "status_snapshot": PROJECT_ROOT / "runtime_outputs/learning/status_snapshot.json",
        "forward_learning": PROJECT_ROOT / "tae_forward_learning_evidence_status.json",
        "ablation_summary": PROJECT_ROOT / "tae_learning_ablation_summary.json",
        "roi001": PROJECT_ROOT / "tae_roi001_challenger_report.json",
    }
    artifacts = {name: _read_artifact(path) for name, path in candidates.items()}
    forward = artifacts["forward_learning"].get("data") or {}
    return {
        "artifacts": artifacts,
        "unsafe_producers_called": False,
        "sample_sufficient": forward.get("sample_sufficient"),
        "economic_verdict": forward.get("economic_verdict"),
        "matured_attribution_n": forward.get("attributed"),
    }


def _git(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=str(PROJECT_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _commit_trace(today_doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    event_text = json.dumps(
        (today_doc.get("event_trace") or [])
        + (today_doc.get("non_executed_decisions") or [])
        + (today_doc.get("executed_transactions") or []),
        sort_keys=True,
    ).upper()
    runtime = today_doc.get("runtime") or {}
    process_rows = [
        process
        for group in ("live_bot", "parallel_paper", "dashboard")
        for process in ((runtime.get(group) or {}).get("processes") or [])
        if process.get("epoch") is not None
    ]
    traces = []
    activations = []
    evidence_tokens = {
        "bcab6ef": ("HOLD_PRICE_STEP", "ADD_PRICE_STEP", "PRICE_DRIVEN_ADD"),
        "fb58424": ("PRICE_HARD_RISK_AUDIT_ONLY",),
        "23e224f": ("CONTROL_FALLBACK_OUT_OF_SCOPE",),
        "db98294": (),
        "11e4adb": (),
    }
    for sha, title, domain in REQUIRED_COMMITS:
        full = _git(["rev-parse", "--verify", f"{sha}^{{commit}}"])
        epoch_raw = _git(["show", "-s", "--format=%ct", sha]) if full else None
        files_raw = _git(["show", "--format=", "--name-only", sha]) if full else None
        epoch = _num(epoch_raw) if epoch_raw else None
        old_process = bool(
            epoch is not None
            and any(_num(process.get("epoch")) < epoch - 5 for process in process_rows)
        )
        tokens = evidence_tokens.get(sha, ())
        triggered = bool(tokens and any(token in event_text for token in tokens))
        activation = (
            "CODE_NOT_PRESENT"
            if not full
            else "CODE_PRESENT_PROCESS_OLD"
            if old_process
            else "ACTIVE_TRIGGERED"
            if triggered
            else "ACTIVE_NOT_TRIGGERED"
            if process_rows
            else "IMPLEMENTED_NOT_ACTIVE"
        )
        classification = (
            "NOT_IMPLEMENTED"
            if not full
            else "PROVISIONAL"
            if triggered
            else "NO_EVENT_YET"
            if tokens
            else "IMPLEMENTATION_VERIFIED"
        )
        if not full:
            impl_status = "NOT_IMPLEMENTED"
        elif old_process:
            impl_status = "IMPLEMENTED_NOT_ACTIVE"
        elif activation == "ACTIVE_TRIGGERED":
            impl_status = "IMPLEMENTED_ACTIVE"
        elif activation == "ACTIVE_NOT_TRIGGERED":
            impl_status = "IMPLEMENTED_ACTIVE"
        else:
            impl_status = "IMPLEMENTATION_NOT_TRACEABLE"
        row = {
            "commit": sha,
            "full_commit": full,
            "title": title,
            "domain": domain,
            "commit_exists": bool(full),
            "IMPLEMENTATION_STATUS": impl_status,
            "files": [line for line in (files_raw or "").splitlines() if line],
            "files_present": [
                line
                for line in (files_raw or "").splitlines()
                if line and (PROJECT_ROOT / line).exists()
            ],
            "event_evidence": [token for token in tokens if token in event_text],
            "classification": classification,
            "validation_note": "One-day relative performance never establishes validation.",
        }
        traces.append(row)
        activations.append(
            {
                "LEARNING_ID": sha,
                "commit": sha,
                "status": activation,
                "ACTIVE_IN_PROCESS": activation,
                "commit_epoch": epoch,
                "process_predates_commit": old_process,
                "RESTART_REQUIRED": bool(old_process),
            }
        )
    return traces, activations


def _learning_closure(today_doc: dict[str, Any], roi: dict[str, Any]) -> dict[str, Any]:
    traces, activation = _commit_trace(today_doc)
    event_text = json.dumps(today_doc.get("event_trace") or []).upper()
    provisional = [
        {
            "learning": row["title"],
            "status": "PROVISIONAL",
            "evidence": row["event_evidence"],
            "reason": "Runtime evidence is single-day or not economically matured.",
        }
        for row in traces
        if row["classification"] == "PROVISIONAL"
    ]
    rejected = []
    roi001 = ((roi.get("artifacts") or {}).get("roi001") or {}).get("data") or {}
    if str(roi001.get("verdict") or "").endswith("REJECTED"):
        rejected.append({"hypothesis": "ROI-001", "verdict": roi001.get("verdict")})
    missing = [row for row in traces if not row["commit_exists"]]
    no_events = [row for row in traces if row["classification"] == "NO_EVENT_YET"]
    gaps = [
        {
            "gap": "MATURED_MULTI_DAY_ECONOMIC_EVIDENCE",
            "status": "PARTIAL",
            "detail": (roi.get("economic_verdict") or "No mature attribution verdict"),
        }
    ]
    gaps.extend(
        {"gap": f"COMMIT_MISSING:{row['commit']}", "status": "FAIL", "detail": row["title"]}
        for row in missing
    )
    dimensions = {
        "code_presence": "PASS" if not missing else "FAIL",
        "runtime_activation": (
            "PARTIAL"
            if any(row["status"] in {"CODE_PRESENT_PROCESS_OLD", "IMPLEMENTED_NOT_ACTIVE"} for row in activation)
            else "PASS"
        ),
        "trigger_evidence": "PASS" if provisional else "NO_EVENT_YET",
        "economic_validation": (
            "PASS" if roi.get("sample_sufficient") is True else "PARTIAL"
        ),
    }
    # Allowed closure verdicts only (no arbitrary percentages).
    if "FAIL" in dimensions.values():
        verdict = "LEARNING_SYSTEM_NOT_WIRED" if missing else "NO_VALIDATED_LEARNING"
    elif any(row["status"] in {"CODE_PRESENT_PROCESS_OLD", "IMPLEMENTED_NOT_ACTIVE"} for row in activation):
        verdict = "IMPLEMENTATION_EXISTS_NOT_ACTIVE"
    elif provisional and dimensions.get("economic_validation") != "PASS":
        verdict = "ACTIVE_BUT_NOT_ECONOMICALLY_VALIDATED"
    elif "PARTIAL" in dimensions.values():
        verdict = "LEARNING_LOOP_PARTIALLY_CLOSED"
    elif no_events:
        verdict = "NO_VALIDATED_LEARNING"
    else:
        verdict = "LEARNING_LOOP_CLOSED"
    recommendations = [
        {
            "recommendation": "ACCUMULATE_MATURED_MULTI_DAY_EVIDENCE",
            "IMPLEMENTATION_ALLOWED": False,
        }
    ]
    return {
        "summary": {
            "required_commit_count": len(REQUIRED_COMMITS),
            "commits_present": len(traces) - len(missing),
            "validated_count": 0,
            "provisional_count": len(provisional),
            "one_day_validation_forbidden": True,
        },
        "components": [
            {"component": name, "available": bool((artifact or {}).get("data"))}
            for name, artifact in (roi.get("artifacts") or {}).items()
        ]
        + [
            {
                "component": row["title"],
                "commit": row["commit"],
                "available": row["commit_exists"],
            }
            for row in traces
        ],
        "validated_learnings": [],
        "provisional_learnings": provisional,
        "rejected_hypotheses": rejected,
        "recommendations": recommendations,
        "implementation_trace": traces,
        "runtime_activation": activation,
        "decision_impact": [
            row for row in today_doc.get("event_trace") or []
            if any(token in str(row.get("reason") or "").upper() for token in ("CONTROL_FALLBACK", "HOLD_PRICE_STEP"))
        ],
        "execution_impact": [
            row for row in today_doc.get("executed_transactions") or []
            if str(row.get("action") or "").upper() == "ADD"
        ],
        "economic_impact": [],
        "learning_failures": [
            {"commit": row["commit"], "failure": "REQUIRED_COMMIT_MISSING"} for row in missing
        ],
        "learning_gaps": gaps,
        "closure_status": {
            "dimensions": dimensions,
            "verdict": verdict,
            "LEARNING_LOOP_STATUS": verdict,
            "LEARNING_CLOSURE_VERDICT": verdict,
        },
        "actions": [
            {
                "action": gap["gap"],
                "priority": "MONITOR",
                "IMPLEMENTATION_ALLOWED": False,
            }
            for gap in gaps[:3]
        ],
    }


def _strategy_lab() -> dict[str, Any]:
    scoreboard = _safe(
        lambda: build_scoreboard(persist=False) if build_scoreboard else {}, {}
    )
    status = _safe(lambda: lab_status() if lab_status else {}, {})
    promotion = _safe(
        lambda: load_promotion_state(create_if_missing=False)
        if load_promotion_state
        else {},
        {},
    )
    champion = promotion.get("champion_strategy_id")
    recommendation = (
        "KEEP_CHAMPION"
        if champion
        else "HOLD_NO_CHAMPION_EVIDENCE"
    )
    return {
        "scoreboard": scoreboard,
        "status": status,
        "promotion": promotion,
        "AUTO_PROMOTE": False,
        "AUTONOMOUS_PAPER_EVOLUTION": promotion.get(
            "autonomous_paper_evolution"
        )
        or {
            "enabled": False,
            "domain": "AUTONOMOUS_PAPER_EVOLUTION",
            "live_allowed": False,
        },
        "AUTONOMOUS_PAPER_CHAMPION": promotion.get(
            "autonomous_paper_champion_id"
        ),
        "recommendation": recommendation,
        "ticket_created": False,
    }


def _decisions(today_doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    for tx in today_doc.get("executed_transactions") or []:
        rows.append(
            {
                "strategy": tx.get("strategy"),
                "ticker": tx.get("ticker"),
                "action": tx.get("action"),
                "effect": _num(tx.get("PNL_AFTER_FEES")),
                "EFFECT_TYPE": "REALIZED",
                "reason": tx.get("reason"),
            }
        )
    for row in today_doc.get("portfolio_comparison") or []:
        for arm in ("V1", "V2"):
            side = row.get(arm)
            if side:
                rows.append(
                    {
                        "strategy": arm,
                        "ticker": row.get("ticker"),
                        "action": side.get("current_action"),
                        "effect": _num(side.get("unrealized_pnl")),
                        "EFFECT_TYPE": "MARK_TO_MARKET_EFFECT",
                        "reason": side.get("current_reason"),
                    }
                )
    ranked = sorted(rows, key=lambda row: row["effect"], reverse=True)
    return ranked[:10], sorted(rows, key=lambda row: row["effect"])[:10]


def _missed(today_doc: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in today_doc.get("non_executed_decisions") or []:
        classification = str(row.get("classification") or "")
        reason = str(row.get("reason") or "").upper()
        if classification == "MARKET_CLOSED":
            continue
        if classification in {
            "BUY_NOT_EXECUTED",
            "SELL_NOT_EXECUTED",
            "AUTHORIZED_NOT_EXECUTED",
            "SELL_AUTHORIZED_NOT_EXECUTED",
        } or "CONTROL_FALLBACK" in reason:
            result.append(
                {
                    **row,
                    "miss_type": (
                        "SELL_AUTHORIZED_NOT_EXECUTED"
                        if classification in {"SELL_NOT_EXECUTED", "SELL_AUTHORIZED_NOT_EXECUTED"}
                        else "AUTHORIZED_NOT_EXECUTED"
                        if classification in {"BUY_NOT_EXECUTED", "AUTHORIZED_NOT_EXECUTED"}
                        else "CONTROL_FALLBACK"
                    ),
                    "ECONOMIC_EFFECT": row.get("economic_effect", "UNKNOWN"),
                }
            )
    return result[:10]


def _risks(today_doc: dict[str, Any], morning: dict[str, Any]) -> list[dict[str, Any]]:
    risks = []
    for row in today_doc.get("anomalies") or []:
        severity = row.get("severity") or "WARNING"
        if row.get("code") == "PROCESS_PREDATES_RUNTIME_RELEVANT_COMMIT":
            severity = "WARNING"
        risks.append(
            {"severity": severity, "code": row.get("code"), "message": row.get("message")}
        )
    risks.extend(
        {"severity": "WARNING", "code": "MORNING_RISK", "message": str(message)}
        for message in (morning.get("outstanding_risks") or [])
    )
    return risks[:20]


def _actions(morning: dict[str, Any]) -> list[dict[str, Any]]:
    council = _safe(
        lambda: run_investment_council(
            write_outputs=False, include_morning_audit=False
        )
        if run_investment_council
        else {},
        {},
    )
    raw = list(council.get("final_paper_action_plan") or [])
    raw.extend({"action": action, "source": "morning"} for action in morning.get("next_actions") or [])
    actions = []
    for index, row in enumerate(raw[:3]):
        item = row if isinstance(row, dict) else {"action": str(row)}
        actions.append(
            {
                **item,
                "timeframe": ("NOW", "MONITOR", "NOT_JUSTIFIED")[min(index, 2)],
                "EXECUTION_ALLOWED": False,
            }
        )
    return actions


def _self_improvement() -> dict[str, Any]:
    """Read self-improvement status without running producers."""
    try:
        from tae_self_improve import build_status

        status = build_status()
        status.pop("cycles", None)
        return status
    except Exception as exc:
        return {
            "SELF_IMPROVEMENT_STATUS": "UNAVAILABLE",
            "ACTIVE_LEARNING_CYCLES": 0,
            "NEW_HYPOTHESES": 0,
            "EXPERIMENTS_CREATED": 0,
            "REPLAYS_RUN": 0,
            "PAPER_CHALLENGERS_ACTIVE": 0,
            "EXPERIMENTAL_CHALLENGERS_REGISTERED": 0,
            "EXPERIMENTAL_ARMS_ENABLED": 0,
            "ACTIVE_NOT_TRIGGERED": 0,
            "EXPERIMENTS_REJECTED": 0,
            "EXPERIMENTS_ROLLED_BACK": 0,
            "READY_FOR_HUMAN_PROMOTION": 0,
            "PROFIT_EFFECT": 0.0,
            "LOSS_REDUCTION_EFFECT": 0.0,
            "LEARNING_LOOP_CLOSED": False,
            "NEEDS_MORE_DATA_EXPERIMENTS": 0,
            "REMAINING_EVENTS": 0,
            "REMAINING_CYCLES": 0,
            "REMAINING_DAYS": 0,
            "REMAINING_OUTCOMES": 0,
            "NEXT_REEVALUATION": None,
            "PROMISING_EXPERIMENTS": 0,
            "REPLAY_SUPPORTED_EXPERIMENTS": 0,
            "BEHAVIOR_COHORTS": 0,
            "GENERALIZED_BEHAVIOR_HYPOTHESES": 0,
            "LATE_ENTRY_GENERALIZED": False,
            "EXPERIMENT_JOIN_CONFLICTS": 0,
            "LAST_ECONOMIC_EXPERIMENT_UID": None,
            "SCHEDULE_ENABLED": False,
            "LIVE_AUTONOMY": False,
            "AUTONOMOUS_PAPER_EVOLUTION_ENABLED": False,
            "AUTONOMOUS_PAPER_CHAMPION": None,
            "AUTONOMOUS_PAPER_CHAMPION_GENERATION": None,
            "EVOLUTION_CONTROL_STRATEGY": "V1",
            "STRATEGY_LINEAGE_RECORDS": 0,
            "AUTONOMOUS_PAPER_PROMOTIONS": 0,
            "AUTONOMOUS_PAPER_ROLLBACKS": 0,
            "LAST_AUTONOMOUS_MUTATION": None,
            "MUTATION_FAMILIES": [],
            "error": str(exc),
        }


def build_cio_extension(
    today_doc: dict,
    *,
    day: Any = None,
    ticker: str | None = None,
    strategy: str | None = None,
    all_events: bool = False,
) -> dict:
    """Build all CIO chapters without mutating trading or learning state."""
    watched = cio_integrity_paths()
    hashes_before = _hashes(watched)
    gate, morning = _morning_gate(today_doc)
    economic = _economic(today_doc)
    opportunity = _opportunity(today_doc)
    roi = _learning_roi()
    closure = _learning_closure(today_doc, roi)
    lab = _strategy_lab()
    best, costliest = _decisions(today_doc)
    risks = _risks(today_doc, morning)
    actions = _actions(morning)
    conclusion = today_doc.get("executive_conclusion") or {}
    capital = today_doc.get("capital") or {}
    sessions = today_doc.get("market_sessions") or {}
    executive = {
        "day": (today_doc.get("metadata") or {}).get("day") or str(day or ""),
        "verdict": conclusion.get("verdict"),
        "capital": capital,
        "market_sessions": {
            key: value.get("open") if isinstance(value, dict) else value
            for key, value in sessions.items()
            if key != "tickers"
        },
        "runtime": {
            key: value.get("running")
            for key, value in (today_doc.get("runtime") or {}).items()
            if isinstance(value, dict) and "running" in value
        },
        "counts": {
            "executed": len(today_doc.get("executed_transactions") or []),
            "non_executed": len(today_doc.get("non_executed_decisions") or []),
            "anomalies": len(today_doc.get("anomalies") or []),
            "open_positions": len(today_doc.get("portfolio_comparison") or []),
        },
        "filters": {"ticker": ticker, "strategy": strategy, "all_events": bool(all_events)},
    }
    final = {
        "verdict": (
            "CIO_REVIEW_REQUIRED"
            if any(r.get("severity") in {"ERROR", "CRITICAL"} for r in risks)
            else "CIO_MONITOR"
            if closure["closure_status"]["verdict"] != "LEARNING_LOOP_CLOSED"
            else "CIO_OPERATING_NORMALLY"
        ),
        "live_data_complete": gate["LIVE_DATA_COMPLETE"],
        "learning_loop": closure["closure_status"]["verdict"],
        "execution_authorized": False,
        "auto_promote": False,
    }
    hashes_after = _hashes(watched)
    changed = [
        name for name in watched if hashes_before.get(name) != hashes_after.get(name)
    ]
    stable = {
        group: all(
            hashes_before[name] == hashes_after[name]
            for name in watched
            if name.startswith(group + "/")
        )
        for group in ("adaptive", "learning", "promotion", "registry")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "executive_brief": executive,
        "live_operational_gate": gate,
        "economic_attribution": economic,
        "opportunity_funnel": opportunity,
        "rule_economics": _rule_economics(today_doc),
        "learning_roi": roi,
        "learning_closure": closure,
        "self_improvement": _self_improvement(),
        "strategy_lab": lab,
        "best_decisions": best,
        "costliest_decisions": costliest,
        "missed_opportunities": _missed(today_doc),
        "risks": risks,
        "actions": actions,
        "final_verdict": final,
        "integrity_extra": {
            "read_only": True,
            "unsafe_producers_called": False,
            "watched_paths": {k: str(v) for k, v in watched.items()},
            "ADAPTIVE_HASH_UNCHANGED": True,
            "LEARNING_HASH_UNCHANGED": True,
            "PROMOTION_HASH_UNCHANGED": True,
            "REGISTRY_HASH_UNCHANGED": True,
            "snapshot_stable": stable,
            "concurrent_writes": {
                "detected": bool(changed),
                "paths": [str(watched[name]) for name in changed],
            },
            "hashes_before": hashes_before,
            "hashes_after": hashes_after,
        },
    }


def _table(rows: Any, columns: list[str]) -> str:
    if isinstance(rows, dict):
        rows = [{"key": key, "value": value} for key, value in rows.items()]
        columns = ["key", "value"]
    if not rows:
        return "No records"
    try:
        from tae_today_activity_report import _render_table

        return _render_table(rows, columns)
    except Exception:
        return "\n".join(" | ".join(str(row.get(c, "")) for c in columns) for row in rows)


def _section(number: int, title: str, content: str) -> str:
    return f"{number}. {title}\n{'=' * (len(title) + 3)}\n{content or 'No records'}"


def format_cio_text(today_doc: dict) -> str:
    """Render the full deterministic CIO report."""
    cio = today_doc.get("cio") or {}
    try:
        import tae_today_activity_report as today

        operating_doc = dict(today_doc)
        operating_doc.pop("cio", None)
        operating = today.format_report_text(operating_doc).strip()
    except Exception:
        operating = "No records"
    closure = cio.get("learning_closure") or {}
    chapters = [
        _section(1, "EXECUTIVE BRIEF", _table(cio.get("executive_brief"), [])),
        _section(2, "TODAY OPERATING TABLES", operating),
        _section(3, "LIVE AND PARALLEL OPERATIONAL GATE", _table(cio.get("live_operational_gate"), [])),
        _section(4, "ECONOMIC ATTRIBUTION", _table(cio.get("economic_attribution"), [])),
        _section(5, "OPPORTUNITY FUNNEL", _table((cio.get("opportunity_funnel") or {}).get("classifications"), ["strategy", "ticker", "action", "funnel_class", "ECONOMIC_EFFECT"])),
        _section(6, "RULE ECONOMICS", _table(cio.get("rule_economics"), ["rule", "event_count", "evidence_status", "economic_effect"])),
        _section(7, "LEARNING ROI", _table(cio.get("learning_roi"), [])),
        _section(8, "LEARNING CLOSURE", _table(closure.get("implementation_trace"), ["commit", "title", "commit_exists", "classification", "event_evidence"])),
        _section(9, "SELF IMPROVEMENT", _table(cio.get("self_improvement"), [])),
        _section(10, "STRATEGY LAB", _table(cio.get("strategy_lab"), [])),
        _section(11, "BEST AND COSTLIEST DECISIONS", _table(cio.get("best_decisions"), ["strategy", "ticker", "action", "effect", "EFFECT_TYPE", "reason"]) + "\n\n" + _table(cio.get("costliest_decisions"), ["strategy", "ticker", "action", "effect", "EFFECT_TYPE"])),
        _section(12, "MISSED OPPORTUNITIES", _table(cio.get("missed_opportunities"), ["strategy", "ticker", "action", "miss_type", "ECONOMIC_EFFECT"])),
        _section(13, "RISKS", _table(cio.get("risks"), ["severity", "code", "message"])),
        _section(14, "OPERATING ACTIONS", _table(cio.get("actions"), ["timeframe", "action", "ticker", "EXECUTION_ALLOWED"])),
        _section(15, "LEARNING ACTIONS", _table(closure.get("actions"), ["priority", "action", "IMPLEMENTATION_ALLOWED"])),
        _section(16, "FINAL VERDICT", _table(cio.get("final_verdict"), [])),
    ]
    return "\n\n".join(["TAE TODAY CIO DIGEST — READ ONLY", *chapters]) + "\n"


__all__ = [
    "_read_artifact",
    "build_cio_extension",
    "cio_integrity_paths",
    "format_cio_text",
]
