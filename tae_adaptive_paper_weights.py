#!/usr/bin/env python3
"""
TAE Adaptive PAPER Weights — evidence-driven action confidence from existing learning.

PAPER_ONLY | NO_BROKER | NO_LIVE_EXECUTION | NO_LIVE_PROMOTION
Does NOT create a new decision engine; persists capped weights for PDE consumption.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "tae_adaptive_paper_weights"
VERSION = "v1"
MODE = "PAPER_ONLY"

OUTPUT_DIR = Path("runtime_outputs/adaptive_weights")
WEIGHTS_JSON = OUTPUT_DIR / "paper_action_weights.json"
HISTORY_JSONL = OUTPUT_DIR / "paper_action_weights_history.jsonl"
REPORT_MD = Path("TAE_ADAPTIVE_WEIGHTS_REPORT.md")

VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")
EXPERIMENTS_JSON = Path("runtime_outputs/learning_to_profit/experiment_results.json")
ADAPTATION_HINTS_JSON = Path("runtime_outputs/longitudinal_memory/adaptation_hints.json")
CONFIDENCE_JSON = Path("tae_confidence_evolution.json")
DPE_ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
MEMORY_INDEX_JSON = Path("runtime_outputs/longitudinal_memory/memory_index.json")
LONGITUDINAL_KNOWLEDGE_JSON = Path("runtime_outputs/longitudinal_memory/knowledge.json")
RULE_ATTRIBUTION_JSON = Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")

PAPER_ACTIONS = (
    "BUY_PAPER",
    "SELL_PAPER",
    "HOLD_PAPER",
    "REDUCE_PAPER",
    "PROTECT_PAPER",
    "ROTATE_PAPER",
    "SKIP_PAPER",
)

DEFAULT_WEIGHT = 1.0
MIN_WEIGHT = 0.85
MAX_WEIGHT = 1.15
MAX_DAILY_DELTA = 0.02
TICKER_ADJ_CAP = 0.01

VERDICT_DELTA = {
    "PROMISING": 0.012,
    "CONTINUE_TESTING": 0.004,
    "REJECT": -0.012,
    "NEEDS_MORE_DATA": -0.002,
}

# When RULE_ATTRIBUTION_JSON (actual PAPER trade/MTM outcomes) has evidence for an
# action, simulated evidence (VALIDATION_JSON, EXPERIMENTS_JSON) is discounted rather
# than summed at parity, so real outcomes dominate the learning signal where both exist.
SIMULATED_EVIDENCE_DISCOUNT = 0.3

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
    if OUTPUT_DIR.resolve() not in path.resolve().parents and path.resolve() != OUTPUT_DIR.resolve():
        if path.suffix == ".md" and path.parent.resolve() == Path(".").resolve():
            return
        raise RuntimeError(f"Unsafe path outside adaptive_weights: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def clamp_weight(value: float) -> float:
    return round(max(MIN_WEIGHT, min(MAX_WEIGHT, value)), 4)


def clamp_delta(delta: float) -> float:
    return round(max(-MAX_DAILY_DELTA, min(MAX_DAILY_DELTA, delta)), 4)


def load_previous_weights() -> dict[str, dict[str, Any]]:
    doc = load_json(WEIGHTS_JSON) or {}
    prev: dict[str, dict[str, Any]] = {}
    for action in PAPER_ACTIONS:
        row = (doc.get("weights") or {}).get(action) or {}
        prev[action] = {
            "new_weight": _f(row.get("new_weight"), DEFAULT_WEIGHT),
            "reason": row.get("reason"),
        }
    return prev


def aggregate_validation_by_action(validation: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    by_action: dict[str, dict[str, int]] = {a: {} for a in PAPER_ACTIONS}
    for row in (validation or {}).get("results") or []:
        action = _s(row.get("action")).upper()
        verdict = _s(row.get("verdict")).upper()
        if action not in by_action:
            continue
        counts = by_action[action]
        counts[verdict] = counts.get(verdict, 0) + 1
    return by_action


def map_experiment_action_for_weights(paper_experiment_action: str) -> str | None:
    """Reuse PDE mapping without importing PDE (avoid cycles)."""
    mapping = {
        "PAPER_TRAILING_PROTECT_TRIM": "REDUCE_PAPER",
        "PAPER_LIFECYCLE_TRIM": "REDUCE_PAPER",
        "PAPER_PORTFOLIO_PROTECT": "PROTECT_PAPER",
        "PAPER_REALLOCATION": "ROTATE_PAPER",
        "PAPER_ROTATION_REDUCE": "ROTATE_PAPER",
        "PAPER_LIFECYCLE_HOLD": "HOLD_PAPER",
    }
    return mapping.get(_s(paper_experiment_action).upper())


def aggregate_experiments_by_action(experiments_doc: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    """Only reproducible/actionable experiment rows affect weights — not raw portfolio maintenance."""
    by_action: dict[str, dict[str, int]] = {a: {} for a in PAPER_ACTIONS}
    for row in (experiments_doc or {}).get("experiments") or []:
        verdict = _s(row.get("verdict")).upper()
        if verdict not in {"PROMISING", "CONTINUE_TESTING", "REJECT"}:
            continue
        paper_action = _s(row.get("paper_experiment_action")).upper()
        if paper_action in {"PAPER_DPE_PHILOSOPHY_WEIGHT", "PAPER_MAINTENANCE_REFRESH", "PAPER_DECISION_REPLAY", "PAPER_CONFIDENCE_SHADOW", "PAPER_PATTERN_DISCOVERY"}:
            continue
        mapped = map_experiment_action_for_weights(paper_action)
        if not mapped:
            continue
        deltas = row.get("deltas") or {}
        profit_delta = _f(deltas.get("expected_profit_delta_usd"))
        if verdict == "PROMISING" and profit_delta < 1.0:
            continue
        # Require ticker support for actionable weight influence
        tickers = row.get("affected_tickers") or []
        if not tickers:
            continue
        counts = by_action[mapped]
        counts[verdict] = counts.get(verdict, 0) + 1
    return by_action


def experiment_attribution_rows(experiments_doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (experiments_doc or {}).get("experiments") or []:
        mapped = map_experiment_action_for_weights(_s(row.get("paper_experiment_action")))
        if not mapped:
            continue
        if _s(row.get("verdict")).upper() not in {"PROMISING", "CONTINUE_TESTING", "REJECT"}:
            continue
        if not (row.get("affected_tickers") or []):
            continue
        rows.append(
            {
                "experiment_id": _s(row.get("hypothesis_id")),
                "action": mapped,
                "verdict": _s(row.get("verdict")).upper(),
                "profit_delta": _f((row.get("deltas") or {}).get("expected_profit_delta_usd")),
            }
        )
    return rows


def aggregate_ticker_validation(validation: dict[str, Any] | None) -> dict[str, dict[str, dict[str, int]]]:
    out: dict[str, dict[str, dict[str, int]]] = {}
    for row in (validation or {}).get("results") or []:
        ticker = _s(row.get("ticker")).upper()
        action = _s(row.get("action")).upper()
        verdict = _s(row.get("verdict")).upper()
        if not ticker or action not in PAPER_ACTIONS:
            continue
        out.setdefault(ticker, {}).setdefault(action, {})
        bucket = out[ticker][action]
        bucket[verdict] = bucket.get(verdict, 0) + 1
    return out


def confidence_evolution_risk_adjustment(confidence_doc: dict[str, Any] | None) -> tuple[float, str]:
    final_rec = _s((confidence_doc or {}).get("final_recommendation")).upper()
    if "DO_NOT_PROMOTE" in final_rec or "INSUFFICIENT" in final_rec:
        return -0.003, f"confidence evolution caution: {final_rec or 'caution'}"
    return 0.0, ""


def hints_action_delta(hints: dict[str, Any] | None, action: str) -> tuple[float, str]:
    bias = _f((hints or {}).get("action_confidence_bias", {}).get(action))
    if not bias:
        return 0.0, ""
    delta = clamp_delta(bias * 0.02)
    return delta, f"longitudinal hint bias {bias:+.3f}"


def longitudinal_knowledge_action_delta(action: str, knowledge_doc: dict[str, Any] | None) -> tuple[float, str]:
    rules = (knowledge_doc or {}).get("rules") or []
    raw = 0.0
    matched: list[str] = []
    action_token = action.replace("_PAPER", "")
    for rule in rules:
        rid = _s(rule.get("rule_id")).upper()
        if action_token not in rid and not rid.endswith(action):
            continue
        conf = _f(rule.get("confidence"), 0.5)
        raw += (conf - 0.5) * 0.02
        matched.append(rid)
    if not matched:
        return 0.0, ""
    delta = clamp_delta(raw)
    return delta, f"longitudinal knowledge rules {','.join(matched[:3])}"


def rule_attribution_action_delta(action: str, attribution_doc: dict[str, Any] | None) -> tuple[float, str]:
    rules = (attribution_doc or {}).get("rules") or {}
    if not rules:
        return 0.0, ""
    raw = 0.0
    matched: list[str] = []
    for rule_id, row in rules.items():
        assoc = _s(row.get("associated_action") or row.get("last_action")).upper()
        if assoc and assoc != action:
            rid = _s(rule_id).upper()
            action_token = action.replace("_PAPER", "")
            if action_token not in rid and action not in rid:
                continue
        influence = _f(row.get("recommended_influence_delta"))
        if influence == 0.0:
            influence = _f(row.get("weight_delta"))
        if influence == 0.0:
            continue
        raw += influence
        matched.append(_s(rule_id))
    if not matched:
        return 0.0, ""
    delta = clamp_delta(raw)
    return delta, f"actual rule outcomes {','.join(matched[:3])}"


def compute_action_weight(
    action: str,
    *,
    verdict_counts: dict[str, int],
    previous_weight: float,
    hints: dict[str, Any] | None,
    knowledge_doc: dict[str, Any] | None,
    attribution_doc: dict[str, Any] | None,
    global_risk_adj: float,
    evidence_sources: list[str],
    experiment_counts: dict[str, int] | None = None,
    experiment_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw_delta = 0.0
    reasons: list[str] = []

    # Real evidence (actual PAPER trade/MTM outcomes) is resolved first so that, when
    # present for this action, simulated evidence below is discounted rather than
    # summed at parity with it.
    attr_delta, attr_reason = rule_attribution_action_delta(action, attribution_doc)
    simulated_discount = SIMULATED_EVIDENCE_DISCOUNT if attr_delta != 0.0 else 1.0

    total = sum(verdict_counts.values())
    if total:
        evidence_sources.append(str(VALIDATION_JSON))
        for verdict, count in verdict_counts.items():
            base = VERDICT_DELTA.get(verdict, 0.0)
            if base == 0.0:
                continue
            contrib = base * (count / total) * simulated_discount
            raw_delta += contrib
            discount_note = " [discounted: real evidence present]" if simulated_discount != 1.0 else ""
            reasons.append(f"{verdict}×{count} → {contrib:+.4f}{discount_note}")

    exp_counts = experiment_counts or {}
    exp_total = sum(exp_counts.values())
    if exp_total:
        evidence_sources.append(str(EXPERIMENTS_JSON))
        for verdict, count in exp_counts.items():
            base = VERDICT_DELTA.get(verdict, 0.0) * 0.75  # capped relative to decision validation
            if base == 0.0:
                continue
            contrib = clamp_delta(base * (count / exp_total) * simulated_discount)
            raw_delta += contrib
            matched_ids = [
                r.get("experiment_id")
                for r in (experiment_rows or [])
                if r.get("action") == action and r.get("verdict") == verdict
            ]
            id_note = f" [{','.join(matched_ids[:3])}]" if matched_ids else ""
            discount_note = " [discounted: real evidence present]" if simulated_discount != 1.0 else ""
            reasons.append(f"experiment {verdict}×{count}{id_note} → {contrib:+.4f}{discount_note}")

    hint_delta, hint_reason = hints_action_delta(hints, action)
    if hint_delta:
        raw_delta += hint_delta
        reasons.append(hint_reason)
        evidence_sources.append(str(ADAPTATION_HINTS_JSON))

    know_delta, know_reason = longitudinal_knowledge_action_delta(action, knowledge_doc)
    if know_delta:
        raw_delta += know_delta
        reasons.append(know_reason)
        evidence_sources.append(str(LONGITUDINAL_KNOWLEDGE_JSON))

    if attr_delta:
        raw_delta += attr_delta
        reasons.append(attr_reason)
        evidence_sources.append(str(RULE_ATTRIBUTION_JSON))

    if action == "BUY_PAPER" and global_risk_adj:
        raw_delta += global_risk_adj
        reasons.append(f"BUY risk adjustment {global_risk_adj:+.4f}")

    capped_delta = clamp_delta(raw_delta)
    cap_applied = capped_delta != round(raw_delta, 4)
    new_weight = clamp_weight(previous_weight + capped_delta)

    return {
        "action": action,
        "previous_weight": round(previous_weight, 4),
        "new_weight": new_weight,
        "delta": round(new_weight - previous_weight, 4),
        "raw_delta": round(raw_delta, 4),
        "evidence_sources": sorted(set(evidence_sources)),
        "reason": "; ".join(reasons) if reasons else "no evidence change — weight preserved",
        "confidence_support": round(max(0.0, min(1.0, 0.5 + capped_delta * 10)), 3),
        "risk_adjustment": round(global_risk_adj if action == "BUY_PAPER" else 0.0, 4),
        "cap_applied": cap_applied,
        "mode": MODE,
        "live_promotion_allowed": False,
        "verdict_counts": verdict_counts,
    }


def compute_ticker_weights(
    ticker_validation: dict[str, dict[str, dict[str, int]]],
) -> dict[str, dict[str, dict[str, Any]]]:
    ticker_weights: dict[str, dict[str, dict[str, Any]]] = {}
    for ticker, actions in ticker_validation.items():
        ticker_weights[ticker] = {}
        for action, verdict_counts in actions.items():
            raw = 0.0
            total = sum(verdict_counts.values())
            if not total:
                continue
            for verdict, count in verdict_counts.items():
                raw += VERDICT_DELTA.get(verdict, 0.0) * (count / total)
            adj = round(max(-TICKER_ADJ_CAP, min(TICKER_ADJ_CAP, raw)), 4)
            if adj:
                ticker_weights[ticker][action] = {
                    "adjustment": adj,
                    "effective_weight": clamp_weight(DEFAULT_WEIGHT + adj),
                    "verdict_counts": verdict_counts,
                    "reason": f"ticker-specific validation evidence for {ticker}/{action}",
                    "cap_applied": adj != round(raw, 4),
                    "mode": MODE,
                    "live_promotion_allowed": False,
                }
    return ticker_weights


def append_history(records: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assert_safe_path(HISTORY_JSONL)
    with HISTORY_JSONL.open("a", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps({**row, "recorded_at": _now()}, ensure_ascii=False) + "\n")


def write_report(doc: dict[str, Any]) -> None:
    weights = doc.get("weights") or {}
    lines = [
        "# TAE Adaptive Weights Report",
        "",
        f"**Generated:** {doc.get('generated_at')}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
        "",
        f"- Actions weighted: **{len(weights)}**",
        f"- Max daily delta cap: **{MAX_DAILY_DELTA}**",
        f"- Weight range: **{MIN_WEIGHT}–{MAX_WEIGHT}**",
        "",
        "## Action weights",
        "",
        "| action | previous | new | delta | cap | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for action in PAPER_ACTIONS:
        row = weights.get(action) or {}
        lines.append(
            f"| {action} | {row.get('previous_weight')} | {row.get('new_weight')} | "
            f"{row.get('delta')} | {row.get('cap_applied')} | {str(row.get('reason', ''))[:80]} |"
        )
    lines.extend(
        [
            "",
            "## Evidence sources",
            "",
            f"- Validation: `{VALIDATION_JSON}`",
            f"- Experiment results (actionable only): `{EXPERIMENTS_JSON}`",
            f"- Longitudinal hints: `{ADAPTATION_HINTS_JSON}`",
            f"- Longitudinal knowledge: `{LONGITUDINAL_KNOWLEDGE_JSON}`",
            f"- Paper execution attribution: `{RULE_ATTRIBUTION_JSON}`",
            f"- Confidence evolution: `{CONFIDENCE_JSON}`",
            f"- DPE adaptive: `{DPE_ADAPTIVE_JSON}`",
            "",
            "## PDE consumption",
            "",
            f"- Weights file: `{WEIGHTS_JSON}`",
            "- Applied in `score_actions_for_ticker()` as score multipliers",
            "- Decisions include `adaptive_weight_evidence` field",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_adaptive_paper_weights(*, write_report_flag: bool = True) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    validation = load_json(VALIDATION_JSON)
    hints = load_json(ADAPTATION_HINTS_JSON)
    confidence = load_json(CONFIDENCE_JSON)
    dpe_adaptive = load_json(DPE_ADAPTIVE_JSON)
    memory_index = load_json(MEMORY_INDEX_JSON)
    knowledge_doc = load_json(LONGITUDINAL_KNOWLEDGE_JSON)
    attribution_doc = load_json(RULE_ATTRIBUTION_JSON)
    experiments_doc = load_json(EXPERIMENTS_JSON)

    previous = load_previous_weights()
    by_action = aggregate_validation_by_action(validation)
    by_ticker = aggregate_ticker_validation(validation)
    by_experiment = aggregate_experiments_by_action(experiments_doc)
    experiment_rows = experiment_attribution_rows(experiments_doc)
    global_risk_adj, risk_reason = confidence_evolution_risk_adjustment(confidence)

    weights: dict[str, dict[str, Any]] = {}
    history_rows: list[dict[str, Any]] = []
    base_sources: list[str] = []
    if dpe_adaptive:
        base_sources.append(str(DPE_ADAPTIVE_JSON))
    if memory_index:
        base_sources.append(str(MEMORY_INDEX_JSON))

    for action in PAPER_ACTIONS:
        row = compute_action_weight(
            action,
            verdict_counts=by_action.get(action) or {},
            previous_weight=_f(previous.get(action, {}).get("new_weight"), DEFAULT_WEIGHT),
            hints=hints,
            knowledge_doc=knowledge_doc,
            attribution_doc=attribution_doc,
            global_risk_adj=global_risk_adj,
            evidence_sources=list(base_sources),
            experiment_counts=by_experiment.get(action) or {},
            experiment_rows=[r for r in experiment_rows if r.get("action") == action],
        )
        if risk_reason and action == "BUY_PAPER":
            row["reason"] = f"{row['reason']}; {risk_reason}" if row.get("reason") else risk_reason
            row["evidence_sources"] = sorted(set(row["evidence_sources"] + [str(CONFIDENCE_JSON)]))
        weights[action] = row
        history_rows.append(row)

    ticker_weights = compute_ticker_weights(by_ticker)

    doc = {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "max_daily_delta": MAX_DAILY_DELTA,
        "weight_range": {"min": MIN_WEIGHT, "max": MAX_WEIGHT},
        "dpe_preferred_philosophy": _s((dpe_adaptive or {}).get("preferred_philosophy")),
        "dpe_confidence": _f((dpe_adaptive or {}).get("confidence")),
        "longitudinal_records": _f((memory_index or {}).get("total_records")),
        "validation_decisions": _f((validation or {}).get("decisions_consumed")),
        "paper_execution_rules": len((attribution_doc or {}).get("rules") or {}),
        "experiment_actionable_rows": len(experiment_rows),
        "experiment_weight_counts": by_experiment,
        "weights": weights,
        "ticker_weights": ticker_weights,
    }

    assert_safe_path(WEIGHTS_JSON)
    from tae_learning_persistence import atomic_write_json, learning_state_lock

    with learning_state_lock(blocking=True):
        atomic_write_json(WEIGHTS_JSON, doc)
        append_history(history_rows)
        if write_report_flag:
            write_report(doc)
    return {"ok": True, "document": doc}


def effective_weight_for(action: str, ticker: str, weights_doc: dict[str, Any] | None) -> dict[str, Any]:
    doc = weights_doc or {}
    action_row = (doc.get("weights") or {}).get(action) or {}
    base = _f(action_row.get("new_weight"), DEFAULT_WEIGHT)
    ticker_row = ((doc.get("ticker_weights") or {}).get(ticker.upper()) or {}).get(action) or {}
    adj = _f(ticker_row.get("adjustment"))
    effective = clamp_weight(base + adj)
    return {
        "action": action,
        "base_weight": base,
        "ticker_adjustment": adj,
        "effective_multiplier": effective,
        "reason": action_row.get("reason"),
        "ticker_reason": ticker_row.get("reason"),
        "cap_applied": bool(action_row.get("cap_applied") or ticker_row.get("cap_applied")),
        "mode": MODE,
        "live_promotion_allowed": False,
    }


def main() -> int:
    print("===== TAE ADAPTIVE PAPER WEIGHTS =====")
    print(f"Mode: {MODE} | capped daily deltas | NO_BROKER | NO_LIVE_PROMOTION")
    result = run_adaptive_paper_weights()
    doc = result["document"]
    print("Actions weighted:", len(doc.get("weights") or {}))
    print("Ticker adjustments:", len(doc.get("ticker_weights") or {}))
    print("Wrote:", WEIGHTS_JSON, HISTORY_JSONL, REPORT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
