#!/usr/bin/env python3
"""
TAE Longitudinal Outcome Memory — canonical PAPER decision lifecycle storage.

PAPER_ONLY | READ_ONLY | NO_BROKER | NO_LIVE_EXECUTION
Extends existing PAPER workflow; does NOT create a new decision engine.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae_longitudinal_outcome_memory"
VERSION = "v1"
MODE = "PAPER_ONLY"

OUTPUT_DIR = Path("runtime_outputs/longitudinal_memory")
MEMORY_JSONL = OUTPUT_DIR / "decisions.jsonl"
MEMORY_INDEX_JSON = OUTPUT_DIR / "memory_index.json"
KNOWLEDGE_JSON = OUTPUT_DIR / "knowledge.json"
ADAPTATION_HINTS_JSON = OUTPUT_DIR / "adaptation_hints.json"
AUDIT_JSON = OUTPUT_DIR / "outcome_source_audit.json"

REPORT_MEMORY_MD = Path("TAE_LONGITUDINAL_MEMORY_REPORT.md")
REPORT_SURVIVAL_MD = Path("TAE_STRATEGY_SURVIVAL_REPORT.md")
REPORT_LEARNING_MD = Path("TAE_LONG_TERM_LEARNING_REPORT.md")
REPORT_PHILOSOPHY_MD = Path("TAE_PHILOSOPHY_PERFORMANCE_REPORT.md")

PAPER_DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")
EXPERIMENTS_JSON = Path("runtime_outputs/learning_to_profit/experiment_results.json")
PROMOTION_JSON = Path("runtime_outputs/full_paper_cycle/promotion_gate.json")
ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
DPE_LEARNING_JSON = Path("runtime_outputs/dpe/learning/learning.json")
DPE_EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
CONFIDENCE_JSON = Path("tae_confidence_evolution.json")
REPLAY_JSON = Path("tae_decision_replay.json")
GII_JSON = Path("tae_growth_intelligence.json")
PCE_JSON = Path("tae_profit_context_engine.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
LIFECYCLE_JSON = Path("tae_winner_lifecycle_profiler.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
PAPER_PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
PAPER_TRADES_JSONL = Path("runtime_outputs/paper_execution/paper_trades.jsonl")
PAPER_ORDERS_JSONL = Path("runtime_outputs/paper_execution/paper_orders.jsonl")
PAPER_ATTRIBUTION_JSON = Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
PAPER_MTM_JSON = Path("runtime_outputs/paper_execution/mark_to_market.json")

CHECKPOINT_OFFSETS_DAYS: tuple[tuple[str, int], ...] = (
    ("+1d", 1),
    ("+3d", 3),
    ("+5d", 5),
    ("+10d", 10),
    ("+20d", 20),
    ("+60d", 60),
    ("+120d", 120),
    ("+250td", 250),
)

OUTCOME_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "paper_decisions", "path": str(PAPER_DECISIONS_JSON), "producer": "tae_paper_decision_engine.py", "consumer": "longitudinal_memory"},
    {"id": "decision_validation", "path": str(VALIDATION_JSON), "producer": "tae_dpe_paper_executor_infra.py", "consumer": "longitudinal_memory"},
    {"id": "experiment_results", "path": str(EXPERIMENTS_JSON), "producer": "tae_paper_experiment_runner.py", "consumer": "longitudinal_memory"},
    {"id": "promotion_gate", "path": str(PROMOTION_JSON), "producer": "tae_full_paper_cycle.py", "consumer": "longitudinal_memory"},
    {"id": "dpe_learning", "path": str(DPE_LEARNING_JSON), "producer": "tae_dpe_learning_engine.py", "consumer": "longitudinal_memory"},
    {"id": "dpe_adaptive", "path": str(ADAPTIVE_JSON), "producer": "tae_dpe_adaptive_selector.py", "consumer": "longitudinal_memory"},
    {"id": "confidence_evolution", "path": str(CONFIDENCE_JSON), "producer": "tae_confidence_evolution.py", "consumer": "longitudinal_memory"},
    {"id": "decision_replay", "path": str(REPLAY_JSON), "producer": "tae_decision_replay_composer.py", "consumer": "longitudinal_memory"},
    {"id": "growth_intelligence", "path": str(GII_JSON), "producer": "tae_growth_intelligence.py", "consumer": "longitudinal_memory"},
    {"id": "profit_context", "path": str(PCE_JSON), "producer": "tae_profit_context_engine.py", "consumer": "longitudinal_memory"},
    {"id": "winner_lifecycle", "path": str(LIFECYCLE_JSON), "producer": "tae_winner_lifecycle_profiler.py", "consumer": "longitudinal_memory"},
    {"id": "opportunity_ledger", "path": str(LEDGER_JSON), "producer": "tae_opportunity_cost_ledger.py", "consumer": "longitudinal_memory"},
    {"id": "paper_portfolio", "path": str(PAPER_PORTFOLIO_JSON), "producer": "tae_paper_execution.py", "consumer": "longitudinal_memory"},
    {"id": "paper_trades", "path": str(PAPER_TRADES_JSONL), "producer": "tae_paper_execution.py", "consumer": "longitudinal_memory"},
    {"id": "paper_orders", "path": str(PAPER_ORDERS_JSONL), "producer": "tae_paper_execution.py", "consumer": "longitudinal_memory"},
    {"id": "rule_outcome_attribution", "path": str(PAPER_ATTRIBUTION_JSON), "producer": "tae_paper_execution.py", "consumer": "longitudinal_memory"},
    {"id": "paper_mark_to_market", "path": str(PAPER_MTM_JSON), "producer": "tae_paper_execution.py", "consumer": "longitudinal_memory"},
)

FORBIDDEN_WRITE_PREFIXES = (
    "live_bot.py",
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "core/",
    "research_core/",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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


def file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600, 2)


def assert_safe_path(path: Path) -> None:
    resolved = str(path.resolve())
    if OUTPUT_DIR.resolve() not in path.resolve().parents and path.resolve() != OUTPUT_DIR.resolve():
        if path.suffix == ".md" and path.parent.resolve() == Path(".").resolve():
            return
        raise RuntimeError(f"Unsafe path outside longitudinal_memory: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def audit_outcome_sources() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for spec in OUTCOME_SOURCES:
        path = Path(spec["path"])
        age = file_age_hours(path)
        rows.append(
            {
                **spec,
                "present": path.is_file(),
                "freshness_hours": age,
                "retention": "persistent" if path.is_file() else "missing",
                "missing_information": [] if path.is_file() else ["file absent"],
            }
        )
    return {
        "schema": "tae_outcome_source_audit",
        "generated_at": _now(),
        "sources": rows,
        "present_count": sum(1 for r in rows if r["present"]),
        "total_count": len(rows),
    }


def load_memory_index() -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if not MEMORY_JSONL.is_file():
        return by_id
    for line in MEMORY_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            did = _s(row.get("decision_id"))
            if did:
                by_id[did] = row
        except json.JSONDecodeError:
            continue
    return by_id


def save_memory_index(records: dict[str, dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assert_safe_path(MEMORY_JSONL)
    with MEMORY_JSONL.open("w", encoding="utf-8") as handle:
        for row in sorted(records.values(), key=lambda r: r.get("timestamp") or ""):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def index_gii(gii: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _s(t.get("ticker")).upper(): t
        for t in (gii or {}).get("tickers") or []
        if t.get("ticker")
    }


def index_pce_tickers(pce: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    tickers = (pce or {}).get("tickers") or []
    if isinstance(tickers, dict):
        return {k.upper(): v for k, v in tickers.items()}
    return {_s(t.get("ticker")).upper(): t for t in tickers if isinstance(t, dict) and t.get("ticker")}


def index_validation(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_s(r.get("decision_id") or r.get("source_decision_id")): r for r in results if r.get("decision_id") or r.get("source_decision_id")}


def index_promotion(recs: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in recs:
        key = (_s(r.get("ticker")).upper(), _s(r.get("action")).upper())
        out[key] = r
    return out


def experiments_by_ticker(experiments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for exp in experiments:
        for raw in exp.get("affected_tickers") or ["_PORTFOLIO"]:
            out.setdefault(_s(raw).upper(), []).append(exp)
    return out


def horizon_fields(horizon_context: dict[str, Any] | None) -> dict[str, Any]:
    ctx = horizon_context or {}
    out: dict[str, Any] = {}
    for label in ("7D", "1M", "1Y", "2Y", "5Y", "10Y", "20Y"):
        row = ctx.get(label) or {}
        out[label] = {
            "return_pct": row.get("return_pct"),
            "trend": row.get("trend"),
        }
    return out


def build_memory_record(
    decision: dict[str, Any],
    *,
    validation: dict[str, Any] | None,
    promotion: dict[str, Any] | None,
    gii_row: dict[str, Any] | None,
    pce_row: dict[str, Any] | None,
    philosophy: str,
    market_regime: str,
    volatility_regime: str,
    appe_policy: str,
    ppg_posture: str,
    protection_state: str,
    experiment: dict[str, Any] | None,
) -> dict[str, Any]:
    ts = _s(decision.get("timestamp") or decision.get("created_at") or _now())
    decision_id = _s(decision.get("decision_id"))
    ticker = _s(decision.get("ticker")).upper()
    action = _s(decision.get("action")).upper()
    hz = decision.get("horizon_context") or (validation or {}).get("horizon_context")

    record: dict[str, Any] = {
        "memory_id": f"LMEM-{decision_id}",
        "decision_id": decision_id,
        "ticker": ticker,
        "timestamp": ts,
        "action": action,
        "philosophy": philosophy,
        "market_regime": market_regime,
        "volatility_regime": volatility_regime,
        "horizons": horizon_fields(hz if isinstance(hz, dict) else None),
        "short_term_trend_7d": decision.get("short_term_trend_7d") or (validation or {}).get("short_term_trend_7d"),
        "monthly_trend": decision.get("monthly_trend") or (validation or {}).get("monthly_trend"),
        "yearly_trend": decision.get("yearly_trend") or (validation or {}).get("yearly_trend"),
        "long_term_trend": decision.get("long_term_trend") or (validation or {}).get("long_term_trend"),
        "horizon_alignment_score": decision.get("horizon_alignment_score") or (validation or {}).get("horizon_alignment_score"),
        "horizon_conflict_flag": decision.get("horizon_conflict_flag") or (validation or {}).get("horizon_conflict_flag"),
        "growth_score": _f((gii_row or {}).get("growth_score")),
        "capital_efficiency": _f((gii_row or {}).get("capital_efficiency")),
        "opportunity_cost_usd": _f((gii_row or {}).get("missed_usd")),
        "profit_protection_state": protection_state,
        "ppg_posture": ppg_posture,
        "appe_policy": appe_policy,
        "confidence": _f(decision.get("confidence")),
        "validation_rule": decision.get("validation_rule"),
        "rejection_rule": decision.get("rejection_rule"),
        "experiment_id": (experiment or {}).get("experiment_id") or (experiment or {}).get("hypothesis_id"),
        "validation_verdict": (validation or {}).get("verdict"),
        "promotion_recommendation": (promotion or {}).get("promotion_recommendation"),
        "live_promotion_allowed": False,
        "reason": (validation or {}).get("reason") or decision.get("horizon_reason"),
        "evidence": decision.get("evidence"),
        "expected_profit_delta": _f(decision.get("expected_profit_delta")),
        "expected_risk_delta": _f(decision.get("expected_risk_delta")),
        "capital_efficiency_delta": _f(decision.get("capital_efficiency_delta")),
        "mode": MODE,
        "checkpoints": [],
        "memory_created_at": _now(),
        "memory_updated_at": _now(),
    }

    base_dt = _parse_ts(ts) or datetime.now(timezone.utc)
    record["checkpoints"] = [
        {
            "checkpoint": label,
            "offset_days": days,
            "due_at": (base_dt + timedelta(days=days)).isoformat(),
            "status": "PENDING",
        }
        for label, days in CHECKPOINT_OFFSETS_DAYS
    ]
    return record


def load_orders_by_decision() -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    if not PAPER_ORDERS_JSONL.is_file():
        return by_id
    for line in PAPER_ORDERS_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            did = _s(row.get("decision_id"))
            if did:
                by_id[did] = row
        except json.JSONDecodeError:
            continue
    return by_id


def checkpoint_snapshot(
    ticker: str,
    *,
    gii_row: dict[str, Any] | None,
    pce_row: dict[str, Any] | None,
    accounting: dict[str, Any] | None,
    market_regime: str,
    paper_portfolio: dict[str, Any] | None = None,
    mtm_doc: dict[str, Any] | None = None,
    execution_order: dict[str, Any] | None = None,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pos_pnl = None
    pos_pnl_pct = None
    price_proxy = None
    mark_source = None

    paper_pos = ((paper_portfolio or {}).get("positions") or {}).get(ticker.upper())
    if paper_pos:
        pos_pnl = _f(paper_pos.get("pnl"))
        pos_pnl_pct = _f(paper_pos.get("unrealized_pct") or paper_pos.get("current_pct"))
        price_proxy = _f(paper_pos.get("current_price"))
        mark_source = paper_pos.get("mark_source")
    else:
        for pos in (accounting or {}).get("open_positions") or []:
            if _s(pos.get("ticker")).upper() == ticker.upper():
                pos_pnl = _f(pos.get("pnl"))
                pos_pnl_pct = _f(pos.get("pnl_pct"))
                break

    for mtm_row in (mtm_doc or {}).get("positions") or []:
        if _s(mtm_row.get("ticker")).upper() == ticker.upper():
            price_proxy = _f(mtm_row.get("current_price")) or price_proxy
            mark_source = mtm_row.get("mark_source") or mark_source
            pos_pnl = _f(mtm_row.get("unrealized_pnl")) if mtm_row.get("unrealized_pnl") is not None else pos_pnl
            break

    expected = _f((record or {}).get("expected_profit_delta"))
    actual = pos_pnl if pos_pnl is not None else _f((execution_order or {}).get("simulated_pnl_impact"))
    verdict = _s((record or {}).get("validation_verdict"))
    if actual > 0 or (expected > 0 and actual >= expected * 0.5):
        outcome = "success"
    elif actual < 0:
        outcome = "failure"
    elif verdict == "NEEDS_MORE_DATA":
        outcome = "needs_more_data"
    else:
        outcome = "needs_more_data"

    return {
        "recorded_at": _now(),
        "price_proxy": price_proxy,
        "price_source": mark_source,
        "pnl_usd": pos_pnl,
        "pnl_pct": pos_pnl_pct,
        "actual_profit_delta": actual,
        "expected_profit_delta": expected,
        "profit_delta_gap": round(actual - expected, 4) if expected else actual,
        "drawdown_pct": _f((pce_row or {}).get("drawdown") or (gii_row or {}).get("drawdown")),
        "run_up_pct": _f((paper_pos or {}).get("run_up_pct") or (gii_row or {}).get("high_pct")),
        "volatility_proxy": _f((gii_row or {}).get("collapse_probability")),
        "capital_efficiency": _f((gii_row or {}).get("capital_efficiency")),
        "opportunity_cost_usd": _f((gii_row or {}).get("missed_usd")),
        "regime": market_regime,
        "lifecycle_stage": _s((gii_row or {}).get("lifecycle_stage")),
        "horizon_alignment_score": None,
        "validation_status": "CHECKPOINT_RECORDED",
        "rule_sources": (execution_order or {}).get("rule_sources") or [],
        "action": (record or {}).get("action") or (execution_order or {}).get("action"),
        "verdict": verdict,
        "outcome": outcome,
    }


def update_checkpoints(
    records: dict[str, dict[str, Any]],
    *,
    gii_by: dict[str, dict[str, Any]],
    pce_by: dict[str, dict[str, Any]],
    accounting: dict[str, Any] | None,
    market_regime: str,
    paper_portfolio: dict[str, Any] | None = None,
    mtm_doc: dict[str, Any] | None = None,
    orders_by_decision: dict[str, dict[str, Any]] | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    updated = 0
    orders_by_decision = orders_by_decision or load_orders_by_decision()
    for record in records.values():
        ticker = record.get("ticker") or ""
        did = _s(record.get("decision_id"))
        gii_row = gii_by.get(ticker.upper())
        pce_row = pce_by.get(ticker.upper())
        execution_order = orders_by_decision.get(did)
        for cp in record.get("checkpoints") or []:
            if cp.get("status") == "RECORDED":
                continue
            due = _parse_ts(cp.get("due_at"))
            if due and now >= due:
                snap = checkpoint_snapshot(
                    ticker,
                    gii_row=gii_row,
                    pce_row=pce_row,
                    accounting=accounting,
                    market_regime=market_regime,
                    paper_portfolio=paper_portfolio,
                    mtm_doc=mtm_doc,
                    execution_order=execution_order,
                    record=record,
                )
                snap["horizon_alignment_score"] = record.get("horizon_alignment_score")
                cp.update(snap)
                cp["status"] = "RECORDED"
                updated += 1
        record["memory_updated_at"] = _now()
    return updated


def ingest_decisions(records: dict[str, dict[str, Any]]) -> tuple[int, int, int]:
    decisions_doc = load_json(PAPER_DECISIONS_JSON) or {}
    validation_doc = load_json(VALIDATION_JSON) or {}
    promotion_doc = load_json(PROMOTION_JSON) or {}
    experiments_doc = load_json(EXPERIMENTS_JSON) or {}
    adaptive = load_json(ADAPTIVE_JSON) or {}
    gii = load_json(GII_JSON) or {}
    pce = load_json(PCE_JSON) or {}
    appe = load_json(APPE_JSON) or {}
    ppg = load_json(PPG_JSON) or {}
    shadow = load_json(SHADOW_JSON) or {}

    philosophy = _s(adaptive.get("preferred_philosophy"), "UNKNOWN")
    market_regime = _s(((pce or {}).get("market_snapshot") or {}).get("regime", {}).get("regime"), "UNKNOWN")
    volatility_regime = _s(
        ((pce or {}).get("global_summary") or {}).get("dominant_volatility_context"),
        "UNKNOWN",
    )
    appe_policy = _s((appe or {}).get("latest_observation", {}).get("policy_state"), "UNKNOWN")

    gii_by = index_gii(gii)
    pce_by = index_pce_tickers(pce)
    val_by = index_validation(validation_doc.get("results") or [])
    prom_by = index_promotion(promotion_doc.get("recommendations") or [])
    exp_by = experiments_by_ticker(experiments_doc.get("experiments") or [])

    shadow_by = {
        _s(p.get("ticker")).upper(): p
        for p in (shadow or {}).get("positions") or []
        if p.get("ticker")
    }
    ppg_by: dict[str, str] = {}
    for key in ("top_5_risky_tickers", "top_5_keep_winners"):
        for row in (ppg or {}).get(key) or []:
            if isinstance(row, dict) and row.get("ticker"):
                ppg_by[_s(row["ticker"]).upper()] = _s(row.get("governor_posture"))

    new_count = 0
    action_change_count = 0
    for decision in decisions_doc.get("decisions") or []:
        did = _s(decision.get("decision_id"))
        if not did:
            continue
        action = _s(decision.get("action")).upper()
        if did in records:
            existing = records[did]
            prev_action = _s(existing.get("action")).upper()
            if prev_action == action:
                continue
            action_change_count += 1
            changes = list(existing.get("action_changes") or [])
            changes.append(
                {
                    "event": "ACTION_CHANGE",
                    "timestamp": _now(),
                    "previous_action": prev_action,
                    "new_action": action,
                    "decision_switch_authorized": decision.get("decision_switch_authorized"),
                    "switch_reason": decision.get("switch_reason"),
                    "hard_rule_override": bool((decision.get("hard_risk_discipline") or {}).get("override")),
                    "cooldown_status": decision.get("cooldown_status"),
                    "churn_risk": decision.get("churn_risk"),
                    "ev_margin_actual": decision.get("ev_margin_actual"),
                    "ev_margin_required": decision.get("ev_margin_required"),
                }
            )
            existing["action_changes"] = changes
            existing["action_change_count"] = len(changes)
            existing["action"] = action
            existing["confidence"] = _f(decision.get("confidence"))
            existing["expected_profit_delta"] = _f(decision.get("expected_profit_delta"))
            existing["expected_risk_delta"] = _f(decision.get("expected_risk_delta"))
            existing["decision_state_evidence"] = decision.get("decision_state_evidence")
            existing["memory_updated_at"] = _now()
            continue
        ticker = _s(decision.get("ticker")).upper()
        action = _s(decision.get("action")).upper()
        exps = exp_by.get(ticker) or exp_by.get("_PORTFOLIO") or []
        experiment = exps[0] if exps else None
        shadow_row = shadow_by.get(ticker) or {}
        record = build_memory_record(
            decision,
            validation=val_by.get(did),
            promotion=prom_by.get((ticker, action)),
            gii_row=gii_by.get(ticker),
            pce_row=pce_by.get(ticker),
            philosophy=philosophy,
            market_regime=market_regime,
            volatility_regime=volatility_regime,
            appe_policy=appe_policy,
            ppg_posture=ppg_by.get(ticker, "UNKNOWN"),
            protection_state=_s(shadow_row.get("protection_signal") or shadow_row.get("classification"), "UNKNOWN"),
            experiment=experiment,
        )
        records[did] = record
        new_count += 1

    for did, record in records.items():
        val = val_by.get(did)
        if val:
            record["validation_verdict"] = val.get("verdict")
            record["reason"] = val.get("reason") or record.get("reason")
        key = (_s(record.get("ticker")).upper(), _s(record.get("action")).upper())
        prom = prom_by.get(key)
        if prom:
            record["promotion_recommendation"] = prom.get("promotion_recommendation")

    accounting = load_json(ACCOUNTING_JSON)
    paper_portfolio = load_json(PAPER_PORTFOLIO_JSON)
    mtm_doc = load_json(PAPER_MTM_JSON)
    orders_by = load_orders_by_decision()
    cp_updated = update_checkpoints(
        records,
        gii_by=gii_by,
        pce_by=pce_by,
        accounting=accounting,
        market_regime=market_regime,
        paper_portfolio=paper_portfolio,
        mtm_doc=mtm_doc,
        orders_by_decision=orders_by,
    )
    return new_count, cp_updated, action_change_count


def aggregate_learning(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_action: dict[str, list[dict[str, Any]]] = {}
    by_philosophy: dict[str, list[dict[str, Any]]] = {}
    for rec in records.values():
        by_action.setdefault(_s(rec.get("action")), []).append(rec)
        by_philosophy.setdefault(_s(rec.get("philosophy")), []).append(rec)

    def success_rate(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        wins = sum(1 for r in rows if _s(r.get("validation_verdict")) in {"PROMISING", "CONTINUE_TESTING"})
        return round(100.0 * wins / len(rows), 1)

    action_stats = {
        action: {"count": len(rows), "success_rate_pct": success_rate(rows)}
        for action, rows in by_action.items()
    }
    checkpoint_outcomes: list[dict[str, Any]] = []
    for rec in records.values():
        for cp in rec.get("checkpoints") or []:
            if cp.get("status") == "RECORDED" and cp.get("outcome"):
                checkpoint_outcomes.append(cp)

    wins = [c for c in checkpoint_outcomes if c.get("outcome") == "success"]
    losses = [c for c in checkpoint_outcomes if c.get("outcome") == "failure"]
    win_pnls = [_f(c.get("actual_profit_delta")) for c in wins]
    loss_pnls = [_f(c.get("actual_profit_delta")) for c in losses]
    avg_winner = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
    avg_loser = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
    win_rate = len(wins) / len(checkpoint_outcomes) if checkpoint_outcomes else 0.0
    gross_win = sum(p for p in win_pnls if p > 0)
    gross_loss = abs(sum(p for p in loss_pnls if p < 0))
    profit_factor = round(gross_win / gross_loss, 4) if gross_loss > 0 else None
    expectancy = round((win_rate * avg_winner) + ((1 - win_rate) * avg_loser), 4) if checkpoint_outcomes else 0.0

    survival_metrics = {
        "checkpoint_count": len(checkpoint_outcomes),
        "win_rate": round(win_rate, 4),
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "average_winner": round(avg_winner, 4),
        "average_loser": round(avg_loser, 4),
        "max_drawdown_pct": round(
            max((_f(c.get("drawdown_pct")) for c in checkpoint_outcomes), default=0.0),
            4,
        ),
    }

    philosophy_stats = {
        phil: {"count": len(rows), "success_rate_pct": success_rate(rows)}
        for phil, rows in by_philosophy.items()
    }

    horizon_conflict = [r for r in records.values() if r.get("horizon_conflict_flag")]
    horizon_aligned = [r for r in records.values() if not r.get("horizon_conflict_flag")]

    return {
        "action_performance": action_stats,
        "philosophy_performance": philosophy_stats,
        "horizon_conflict_count": len(horizon_conflict),
        "horizon_aligned_count": len(horizon_aligned),
        "total_records": len(records),
        "survival_metrics": survival_metrics,
    }


def extract_knowledge(records: dict[str, dict[str, Any]], learning: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    action_perf = learning.get("action_performance") or {}

    for action, stats in sorted(action_perf.items(), key=lambda x: -x[1].get("success_rate_pct", 0)):
        rate = stats.get("success_rate_pct", 0)
        count = stats.get("count", 0)
        if count < 2:
            continue
        rules.append(
            {
                "rule_id": f"KNOW-{action}",
                "category": "action_reliability",
                "statement": f"In PAPER validation, {action} showed {rate}% PROMISING/CONTINUE rate over {count} decisions.",
                "evidence_count": count,
                "confidence": min(0.95, count / 20.0),
            }
        )

    protect_rows = [r for r in records.values() if r.get("action") == "PROTECT_PAPER"]
    if len(protect_rows) >= 2:
        avg_risk = sum(_f(r.get("expected_risk_delta")) for r in protect_rows) / len(protect_rows)
        rules.append(
            {
                "rule_id": "KNOW-PROTECT-DRAWDOWN",
                "category": "protection",
                "statement": f"PROTECT_PAPER decisions averaged expected risk delta {avg_risk:.3f} across {len(protect_rows)} cases.",
                "evidence_count": len(protect_rows),
                "confidence": 0.6,
            }
        )

    collab = learning.get("philosophy_performance", {}).get("COLLABORATIVE", {})
    comp = learning.get("philosophy_performance", {}).get("COMPETITIVE", {})
    if collab.get("count") and comp.get("count"):
        better = "COLLABORATIVE" if collab.get("success_rate_pct", 0) >= comp.get("success_rate_pct", 0) else "COMPETITIVE"
        rules.append(
            {
                "rule_id": "KNOW-PHILOSOPHY",
                "category": "philosophy",
                "statement": (
                    f"In accumulated PAPER memory, {better} philosophy shows higher validation success "
                    f"(COLLABORATIVE {collab.get('success_rate_pct')}%, COMPETITIVE {comp.get('success_rate_pct')}%)."
                ),
                "evidence_count": collab.get("count", 0) + comp.get("count", 0),
                "confidence": 0.55,
            }
        )

    aligned = learning.get("horizon_aligned_count", 0)
    conflict = learning.get("horizon_conflict_count", 0)
    if aligned + conflict > 0:
        rules.append(
            {
                "rule_id": "KNOW-HORIZON",
                "category": "horizon",
                "statement": f"Horizon alignment present in {aligned} decisions; conflicts in {conflict} decisions.",
                "evidence_count": aligned + conflict,
                "confidence": 0.5,
            }
        )

    return rules


def build_adaptation_hints(learning: dict[str, Any], knowledge: list[dict[str, Any]]) -> dict[str, Any]:
    action_bias: dict[str, float] = {}
    for action, stats in (learning.get("action_performance") or {}).items():
        rate = stats.get("success_rate_pct", 50.0)
        action_bias[action] = round((rate - 50.0) / 100.0, 3)

    phil_perf = learning.get("philosophy_performance") or {}
    phil_bias = {
        phil: round((stats.get("success_rate_pct", 50.0) - 50.0) / 100.0, 3)
        for phil, stats in phil_perf.items()
    }

    return {
        "schema": "tae_longitudinal_adaptation_hints",
        "mode": MODE,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "action_confidence_bias": action_bias,
        "philosophy_confidence_bias": phil_bias,
        "knowledge_rules_applied": len(knowledge),
        "source": "runtime_outputs/longitudinal_memory/decisions.jsonl",
    }


def write_reports(
    *,
    audit: dict[str, Any],
    index: dict[str, Any],
    learning: dict[str, Any],
    knowledge: list[dict[str, Any]],
    hints: dict[str, Any],
) -> None:
    REPORT_MEMORY_MD.write_text(
        "\n".join(
            [
                "# TAE Longitudinal Memory Report",
                "",
                f"**Generated:** {_now()}",
                f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
                "",
                f"- Total memory records: **{index.get('total_records', 0)}**",
                f"- New this run: **{index.get('new_records', 0)}**",
                f"- Checkpoints updated: **{index.get('checkpoints_updated', 0)}**",
                f"- Outcome sources present: **{audit.get('present_count')}/{audit.get('total_count')}**",
                "",
                "## Canonical storage",
                "",
                f"- `{MEMORY_JSONL}`",
                f"- `{MEMORY_INDEX_JSON}`",
                f"- `{KNOWLEDGE_JSON}`",
                "",
                "## Action performance",
                "",
                "| action | count | success % |",
                "| --- | --- | --- |",
            ]
            + [
                f"| {a} | {s.get('count')} | {s.get('success_rate_pct')} |"
                for a, s in (learning.get("action_performance") or {}).items()
            ]
            + ["", "## Knowledge rules", ""]
            + [f"- {k.get('statement')}" for k in knowledge[:10]]
        )
        + "\n",
        encoding="utf-8",
    )

    REPORT_SURVIVAL_MD.write_text(
        "\n".join(
            [
                "# TAE Strategy Survival Report",
                "",
                f"**Generated:** {_now()}",
                "",
                "Tracks PAPER decision survival via longitudinal checkpoints (+1d … +250td).",
                "",
                f"- Records with checkpoints: **{index.get('total_records', 0)}**",
                f"- Checkpoints recorded this run: **{index.get('checkpoints_updated', 0)}**",
                "",
                "## Survival by action",
                "",
                "| action | decisions | validation success % |",
                "| --- | --- | --- |",
            ]
            + [
                f"| {a} | {s.get('count')} | {s.get('success_rate_pct')} |"
                for a, s in (learning.get("action_performance") or {}).items()
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    REPORT_LEARNING_MD.write_text(
        "\n".join(
            [
                "# TAE Long Term Learning Report",
                "",
                f"**Generated:** {_now()}",
                "",
                "## Learning questions (evidence-based)",
                "",
            ]
            + [f"- {k.get('statement')}" for k in knowledge]
            + [
                "",
                "## Adaptation hints (for existing PDE/LTP)",
                "",
                f"- Action biases: `{json.dumps(hints.get('action_confidence_bias') or {})}`",
                f"- Philosophy biases: `{json.dumps(hints.get('philosophy_confidence_bias') or {})}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    REPORT_PHILOSOPHY_MD.write_text(
        "\n".join(
            [
                "# TAE Philosophy Performance Report",
                "",
                f"**Generated:** {_now()}",
                "",
                "| philosophy | decisions | success % |",
                "| --- | --- | --- |",
            ]
            + [
                f"| {p} | {s.get('count')} | {s.get('success_rate_pct')} |"
                for p, s in (learning.get("philosophy_performance") or {}).items()
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_longitudinal_memory(*, write_reports_flag: bool = True) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = audit_outcome_sources()
    assert_safe_path(AUDIT_JSON)
    AUDIT_JSON.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    records = load_memory_index()
    new_count, cp_updated, action_change_count = ingest_decisions(records)
    save_memory_index(records)

    learning = aggregate_learning(records)
    knowledge = extract_knowledge(records, learning)
    hints = build_adaptation_hints(learning, knowledge)

    index = {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "generated_at": _now(),
        "total_records": len(records),
        "new_records": new_count,
        "action_change_events": action_change_count,
        "checkpoints_updated": cp_updated,
        "learning": learning,
        "knowledge_count": len(knowledge),
    }

    assert_safe_path(MEMORY_INDEX_JSON)
    assert_safe_path(KNOWLEDGE_JSON)
    assert_safe_path(ADAPTATION_HINTS_JSON)
    MEMORY_INDEX_JSON.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    KNOWLEDGE_JSON.write_text(json.dumps({"rules": knowledge, "generated_at": _now()}, indent=2) + "\n", encoding="utf-8")
    ADAPTATION_HINTS_JSON.write_text(json.dumps(hints, indent=2) + "\n", encoding="utf-8")

    if write_reports_flag:
        write_reports(audit=audit, index=index, learning=learning, knowledge=knowledge, hints=hints)

    return {
        "ok": True,
        "index": index,
        "audit": audit,
        "knowledge": knowledge,
        "hints": hints,
    }


def main() -> int:
    print("===== TAE LONGITUDINAL OUTCOME MEMORY =====")
    print(f"Mode: {MODE} | canonical storage | NO_BROKER | NO_LIVE_PROMOTION")
    result = run_longitudinal_memory()
    idx = result["index"]
    print("Total records:", idx["total_records"])
    print("New records:", idx["new_records"])
    print("Checkpoints updated:", idx["checkpoints_updated"])
    print("Knowledge rules:", idx["knowledge_count"])
    print("Wrote:", MEMORY_JSONL, MEMORY_INDEX_JSON, KNOWLEDGE_JSON, ADAPTATION_HINTS_JSON)
    print("Reports:", REPORT_MEMORY_MD, REPORT_SURVIVAL_MD, REPORT_LEARNING_MD, REPORT_PHILOSOPHY_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
