#!/usr/bin/env python3
"""
TAE Paper Experiment Runner — PAPER_ONLY / READ_ONLY / NO_BROKER.

Executes read-only scoring experiments for learning-to-profit hypotheses.
Consumes bridge queue output; does NOT modify live paths or execute broker orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_decision_event_bus import open_positions_from_portfolio, read_csv_rows

SCHEMA = "tae_paper_experiment_runner"
VERSION = "v1"
MODE = "PAPER_ONLY"

INPUT_DIR = Path("runtime_outputs/learning_to_profit")
HYPOTHESES_JSON = INPUT_DIR / "hypotheses.json"
QUEUE_JSONL = INPUT_DIR / "paper_experiment_queue.jsonl"
OUTPUT_DIR = INPUT_DIR
RESULTS_JSON = OUTPUT_DIR / "experiment_results.json"
RESULTS_JSONL = OUTPUT_DIR / "experiment_results.jsonl"
REPORT_MD = Path("TAE_PAPER_EXPERIMENT_RUNNER_REPORT.md")

GII_JSON = Path("tae_growth_intelligence.json")
LIFECYCLE_JSON = Path("tae_winner_lifecycle_profiler.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
DPE_EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
DPE_COMP_METRICS = Path("runtime_outputs/dpe/paper_competitive/metrics.json")
DPE_COLLAB_METRICS = Path("runtime_outputs/dpe/paper_collaborative/metrics.json")
PORTFOLIO_CSV = Path("portfolio.csv")

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
    "research_core/",
)

VERDICTS = frozenset({"CONTINUE_TESTING", "PROMISING", "REJECT", "NEEDS_MORE_DATA"})


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
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if path.resolve() != REPORT_MD.resolve() and output_root not in path.resolve().parents:
        raise RuntimeError(f"Unsafe output path outside learning_to_profit/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def index_by_ticker(rows: list[dict[str, Any]], key: str = "ticker") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = _s(row.get(key)).upper()
        if ticker:
            out[ticker] = row
    return out


def build_scoring_context() -> dict[str, Any]:
    gii = load_json(GII_JSON) or {}
    lifecycle = load_json(LIFECYCLE_JSON) or {}
    ledger = load_json(LEDGER_JSON) or {}
    shadow = load_json(SHADOW_JSON) or {}
    dpe_eval = load_json(DPE_EVAL_JSON) or {}
    comp_metrics = load_json(DPE_COMP_METRICS) or {}
    collab_metrics = load_json(DPE_COLLAB_METRICS) or {}

    live_rows = read_csv_rows(PORTFOLIO_CSV) if PORTFOLIO_CSV.is_file() else []
    live_positions = open_positions_from_portfolio(live_rows)

    gii_tickers = index_by_ticker(gii.get("tickers") or [])
    lifecycle_profiles = index_by_ticker(lifecycle.get("profiles") or [])
    ledger_rows = index_by_ticker(ledger.get("ledger") or [])
    shadow_positions = index_by_ticker(shadow.get("positions") or [])

    portfolio_gii = gii.get("portfolio") or {}
    return {
        "gii_by_ticker": gii_tickers,
        "lifecycle_by_ticker": lifecycle_profiles,
        "ledger_by_ticker": ledger_rows,
        "shadow_by_ticker": shadow_positions,
        "live_positions": live_positions,
        "portfolio_gii": portfolio_gii,
        "dpe_evaluation": dpe_eval,
        "dpe_competitive_totals": comp_metrics.get("portfolio_totals") or {},
        "dpe_collaborative_totals": collab_metrics.get("portfolio_totals") or {},
        "sources_present": {
            "hypotheses": HYPOTHESES_JSON.is_file(),
            "queue": QUEUE_JSONL.is_file(),
            "gii": GII_JSON.is_file(),
            "lifecycle": LIFECYCLE_JSON.is_file(),
            "ledger": LEDGER_JSON.is_file(),
            "shadow": SHADOW_JSON.is_file(),
            "dpe_eval": DPE_EVAL_JSON.is_file(),
            "dpe_competitive": DPE_COMP_METRICS.is_file(),
            "dpe_collaborative": DPE_COLLAB_METRICS.is_file(),
            "live_portfolio": PORTFOLIO_CSV.is_file(),
        },
    }


def isolated_ticker_state(
    tickers: list[str],
    *,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    live = ctx.get("live_positions") or {}
    gii = ctx.get("gii_by_ticker") or {}
    shadow = ctx.get("shadow_by_ticker") or {}
    positions: dict[str, Any] = {}
    for raw in tickers:
        ticker = _s(raw).upper()
        if not ticker:
            continue
        positions[ticker] = {
            "live_snapshot": live.get(ticker),
            "gii": gii.get(ticker),
            "shadow": shadow.get(ticker),
            "lifecycle": (ctx.get("lifecycle_by_ticker") or {}).get(ticker),
            "ledger": (ctx.get("ledger_by_ticker") or {}).get(ticker),
        }
    return {"affected_tickers": tickers, "positions": positions}


def baseline_metrics_for_tickers(tickers: list[str], ctx: dict[str, Any]) -> dict[str, float]:
    gii = ctx.get("gii_by_ticker") or {}
    shadow = ctx.get("shadow_by_ticker") or {}
    missed = 0.0
    capture = 0.0
    cap_eff = 0.0
    risk = 0.0
    count = 0
    for raw in tickers:
        ticker = _s(raw).upper()
        row = gii.get(ticker) or {}
        sh = shadow.get(ticker) or {}
        if not row and not sh:
            continue
        count += 1
        missed += _f(row.get("missed_usd") or sh.get("missed_opportunity_usd"))
        capture += _f(row.get("profit_capture_efficiency"))
        cap_eff += _f(row.get("capital_efficiency"))
        risk += _f(row.get("collapse_probability") or row.get("opportunity_score") / 100)
    if count == 0:
        port = ctx.get("portfolio_gii") or {}
        return {
            "missed_usd": _f(port.get("opportunity_cost_total")),
            "profit_capture_rate": _f(port.get("profit_capture_rate")),
            "capital_efficiency": _f(port.get("capital_efficiency")),
            "risk_score": _f(port.get("growth_risk")),
            "position_count": 0.0,
        }
    return {
        "missed_usd": round(missed, 2),
        "profit_capture_rate": round(capture / count, 4),
        "capital_efficiency": round(cap_eff / count, 2),
        "risk_score": round(risk / count, 4),
        "position_count": float(count),
    }


def score_lifecycle_hold(tickers: list[str], ctx: dict[str, Any], confidence: float) -> dict[str, float]:
    baseline = baseline_metrics_for_tickers(tickers, ctx)
    gii = ctx.get("gii_by_ticker") or {}
    capture_gain = 0.0
    for raw in tickers:
        row = gii.get(_s(raw).upper()) or {}
        missed = _f(row.get("missed_usd"))
        survival = _f(row.get("survival_probability"), 0.5)
        capture_gain += missed * min(0.35, 0.12 + survival * 0.2) * confidence
    profit_delta = round(capture_gain, 2)
    risk_delta = round(baseline["risk_score"] * 0.05, 4)
    cap_delta = round(-baseline["capital_efficiency"] * 0.02, 2)
    hyp_capture = baseline["profit_capture_rate"] + (0.03 * confidence)
    return {
        "expected_profit_delta_usd": profit_delta,
        "expected_profit_delta_pct": round(profit_delta / max(1.0, baseline["missed_usd"]) * 100, 2),
        "risk_delta": risk_delta,
        "capital_efficiency_delta": cap_delta,
        "hypothesis_profit_capture_rate": round(hyp_capture, 4),
        "hypothesis_capital_efficiency": round(baseline["capital_efficiency"] + cap_delta, 2),
    }


def score_lifecycle_trim(tickers: list[str], ctx: dict[str, Any], confidence: float) -> dict[str, float]:
    baseline = baseline_metrics_for_tickers(tickers, ctx)
    gii = ctx.get("gii_by_ticker") or {}
    profit_delta = 0.0
    for raw in tickers:
        row = gii.get(_s(raw).upper()) or {}
        missed = _f(row.get("missed_usd"))
        collapse = _f(row.get("collapse_probability"))
        profit_delta += missed * min(0.25, 0.08 + collapse * 0.15) * confidence
    profit_delta = round(profit_delta, 2)
    risk_delta = round(-baseline["risk_score"] * 0.12, 4)
    cap_delta = round(baseline["capital_efficiency"] * 0.04, 2)
    return {
        "expected_profit_delta_usd": profit_delta,
        "expected_profit_delta_pct": round(profit_delta / max(1.0, baseline["missed_usd"]) * 100, 2),
        "risk_delta": risk_delta,
        "capital_efficiency_delta": cap_delta,
        "hypothesis_profit_capture_rate": round(baseline["profit_capture_rate"] + 0.02 * confidence, 4),
        "hypothesis_capital_efficiency": round(baseline["capital_efficiency"] + cap_delta, 2),
    }


def score_protection(tickers: list[str], ctx: dict[str, Any], confidence: float) -> dict[str, float]:
    baseline = baseline_metrics_for_tickers(tickers, ctx)
    shadow = ctx.get("shadow_by_ticker") or {}
    profit_delta = 0.0
    for raw in tickers:
        sh = shadow.get(_s(raw).upper()) or {}
        missed = _f(sh.get("missed_opportunity_usd") or (ctx.get("gii_by_ticker") or {}).get(_s(raw).upper(), {}).get("missed_usd"))
        protected = max(
            _f(sh.get("estimated_trailing_value_1")),
            _f(sh.get("estimated_trailing_value_1_5")),
            _f(sh.get("estimated_protected_value_20")),
            _f(sh.get("estimated_protected_value_30")),
        )
        profit_delta += max(missed * 0.2 * confidence, protected * 0.15)
    profit_delta = round(profit_delta, 2)
    risk_delta = round(-baseline["risk_score"] * 0.18, 4)
    cap_delta = round(-baseline["capital_efficiency"] * 0.01, 2)
    return {
        "expected_profit_delta_usd": profit_delta,
        "expected_profit_delta_pct": round(profit_delta / max(1.0, baseline["missed_usd"]) * 100, 2),
        "risk_delta": risk_delta,
        "capital_efficiency_delta": cap_delta,
        "hypothesis_profit_capture_rate": round(baseline["profit_capture_rate"] + 0.04 * confidence, 4),
        "hypothesis_capital_efficiency": round(baseline["capital_efficiency"] + cap_delta, 2),
    }


def score_rotation(tickers: list[str], ctx: dict[str, Any], confidence: float) -> dict[str, float]:
    baseline = baseline_metrics_for_tickers(tickers, ctx)
    gii = ctx.get("gii_by_ticker") or {}
    profit_delta = 0.0
    cap_delta = 0.0
    for raw in tickers:
        row = gii.get(_s(raw).upper()) or {}
        missed = _f(row.get("missed_usd"))
        cap_eff = _f(row.get("capital_efficiency"))
        profit_delta += missed * 0.18 * confidence
        cap_delta += max(0.0, 45.0 - cap_eff) * 0.08
    cap_delta = round(cap_delta / max(1, len(tickers)), 2)
    profit_delta = round(profit_delta, 2)
    risk_delta = round(-baseline["risk_score"] * 0.06, 4)
    return {
        "expected_profit_delta_usd": profit_delta,
        "expected_profit_delta_pct": round(profit_delta / max(1.0, baseline["missed_usd"]) * 100, 2),
        "risk_delta": risk_delta,
        "capital_efficiency_delta": cap_delta,
        "hypothesis_profit_capture_rate": round(baseline["profit_capture_rate"] + 0.05 * confidence, 4),
        "hypothesis_capital_efficiency": round(baseline["capital_efficiency"] + cap_delta, 2),
    }


def score_dpe_philosophy(ctx: dict[str, Any], confidence: float) -> dict[str, float]:
    comp = ctx.get("dpe_competitive_totals") or {}
    collab = ctx.get("dpe_collaborative_totals") or {}
    eval_overall = (ctx.get("dpe_evaluation") or {}).get("overall") or {}
    winner = _s(eval_overall.get("winner"), "TIE")

    comp_pnl = _f(comp.get("realized_pnl")) + _f(comp.get("unrealized_pnl"))
    collab_pnl = _f(collab.get("realized_pnl")) + _f(collab.get("unrealized_pnl"))
    comp_start = _f(comp.get("starting_value"), 1.0)
    collab_start = _f(collab.get("starting_value"), 1.0)
    comp_cap = comp_pnl / comp_start * 100
    collab_cap = collab_pnl / collab_start * 100

    if winner == "COLLABORATIVE":
        profit_delta = round(collab_pnl - comp_pnl, 2)
        cap_delta = round(collab_cap - comp_cap, 2)
        risk_delta = round(-0.05, 4)
    elif winner == "COMPETITIVE":
        profit_delta = round(comp_pnl - collab_pnl, 2)
        cap_delta = round(comp_cap - collab_cap, 2)
        risk_delta = round(0.03, 4)
    else:
        profit_delta = round((collab_pnl - comp_pnl) * 0.5, 2)
        cap_delta = round((collab_cap - comp_cap) * 0.5, 2)
        risk_delta = 0.0

    profit_delta = round(profit_delta * confidence, 2)
    baseline_capture = _f((ctx.get("portfolio_gii") or {}).get("profit_capture_rate"))
    return {
        "expected_profit_delta_usd": profit_delta,
        "expected_profit_delta_pct": round(profit_delta / max(1.0, comp_start) * 100, 2),
        "risk_delta": risk_delta,
        "capital_efficiency_delta": cap_delta,
        "hypothesis_profit_capture_rate": round(baseline_capture + 0.02 * confidence, 4),
        "hypothesis_capital_efficiency": round(_f((ctx.get("portfolio_gii") or {}).get("capital_efficiency")) + cap_delta, 2),
        "dpe_winner": winner,
    }


def score_maintenance() -> dict[str, float]:
    return {
        "expected_profit_delta_usd": 0.0,
        "expected_profit_delta_pct": 0.0,
        "risk_delta": 0.0,
        "capital_efficiency_delta": 0.0,
        "hypothesis_profit_capture_rate": 0.0,
        "hypothesis_capital_efficiency": 0.0,
    }


def assign_verdict(
    *,
    deltas: dict[str, float],
    confidence: float,
    has_data: bool,
    action: str,
) -> str:
    if not has_data or action in {"PAPER_MAINTENANCE_REFRESH", "PAPER_PATTERN_DISCOVERY"}:
        return "NEEDS_MORE_DATA"

    profit = _f(deltas.get("expected_profit_delta_usd"))
    risk = _f(deltas.get("risk_delta"))
    cap = _f(deltas.get("capital_efficiency_delta"))

    if profit < -1.0 and risk > 0:
        return "REJECT"

    composite = profit + cap * 2.0 - max(0.0, risk) * 50.0
    if profit >= 15.0 and risk <= 0 and confidence >= 0.6 and composite > 10:
        return "PROMISING"
    if profit >= 5.0 and composite > 0 and confidence >= 0.55:
        return "PROMISING"
    if profit < 0 or composite < -5:
        return "REJECT"
    if confidence < 0.45 or abs(profit) < 1.0:
        return "NEEDS_MORE_DATA"
    return "CONTINUE_TESTING"


def score_hypothesis(
    queue_item: dict[str, Any],
    hypothesis: dict[str, Any] | None,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    hypothesis_id = _s(queue_item.get("hypothesis_id"))
    hyp_type = _s(queue_item.get("hypothesis_type") or (hypothesis or {}).get("hypothesis_type"))
    action = _s(queue_item.get("paper_experiment_action") or (hypothesis or {}).get("paper_experiment", {}).get("action"))
    tickers = list(queue_item.get("affected_tickers") or (hypothesis or {}).get("affected_tickers") or [])
    confidence = _f(queue_item.get("confidence") or (hypothesis or {}).get("confidence"), 0.5)
    target_metric = _s((hypothesis or {}).get("target_metric"), "profit_capture_rate")

    isolated = isolated_ticker_state(tickers, ctx=ctx)
    baseline = baseline_metrics_for_tickers(tickers, ctx)
    has_ticker_data = bool(tickers) and any(
        isolated["positions"].get(_s(t).upper(), {}).get("gii")
        or isolated["positions"].get(_s(t).upper(), {}).get("shadow")
        for t in tickers
    )
    has_portfolio_data = not tickers and bool(ctx.get("portfolio_gii"))
    has_dpe_data = action == "PAPER_DPE_PHILOSOPHY_WEIGHT" and bool(ctx.get("dpe_competitive_totals"))
    has_data = has_ticker_data or has_portfolio_data or has_dpe_data

    if action in {"PAPER_LIFECYCLE_HOLD"}:
        deltas = score_lifecycle_hold(tickers, ctx, confidence)
    elif action in {"PAPER_LIFECYCLE_TRIM"}:
        deltas = score_lifecycle_trim(tickers, ctx, confidence)
    elif action.startswith("PAPER_TRAILING") or action.startswith("PAPER_PORTFOLIO_PROTECT") or action.startswith("PAPER_CONFIDENCE"):
        deltas = score_protection(tickers, ctx, confidence)
    elif action in {"PAPER_ROTATION_REDUCE", "PAPER_REALLOCATION"}:
        deltas = score_rotation(tickers, ctx, confidence)
    elif action == "PAPER_DPE_PHILOSOPHY_WEIGHT":
        deltas = score_dpe_philosophy(ctx, confidence)
        has_data = has_dpe_data
    elif action in {"PAPER_MAINTENANCE_REFRESH", "PAPER_PATTERN_DISCOVERY", "PAPER_DECISION_REPLAY"}:
        deltas = score_maintenance()
        has_data = False
    else:
        deltas = score_protection(tickers, ctx, confidence) if tickers else score_maintenance()

    verdict = assign_verdict(deltas=deltas, confidence=confidence, has_data=has_data, action=action)

    evidence = []
    if tickers and has_ticker_data:
        evidence.append("tae_growth_intelligence.json")
    if tickers and any(isolated["positions"].get(_s(t).upper(), {}).get("shadow") for t in tickers):
        evidence.append("tae_profit_protection_shadow.json")
    if has_dpe_data:
        evidence.extend(
            [
                "runtime_outputs/dpe/paper_competitive/metrics.json",
                "runtime_outputs/dpe/paper_collaborative/metrics.json",
                "runtime_outputs/dpe/result_evaluator/evaluation.json",
            ]
        )
    if ctx.get("sources_present", {}).get("live_portfolio"):
        evidence.append("portfolio.csv (read-only snapshot)")

    return {
        "experiment_id": f"EXP-{hypothesis_id}",
        "queue_id": _s(queue_item.get("queue_id")),
        "hypothesis_id": hypothesis_id,
        "hypothesis_type": hyp_type,
        "mode": MODE,
        "live_promotion_allowed": False,
        "paper_experiment_action": action,
        "affected_tickers": tickers,
        "target_metric": target_metric,
        "confidence": confidence,
        "verdict": verdict,
        "baseline": baseline,
        "hypothesis_arm": {
            "profit_capture_rate": deltas.get("hypothesis_profit_capture_rate"),
            "capital_efficiency": deltas.get("hypothesis_capital_efficiency"),
            "isolated_state": isolated,
        },
        "deltas": {
            "expected_profit_delta_usd": deltas.get("expected_profit_delta_usd"),
            "expected_profit_delta_pct": deltas.get("expected_profit_delta_pct"),
            "risk_delta": deltas.get("risk_delta"),
            "capital_efficiency_delta": deltas.get("capital_efficiency_delta"),
        },
        "validation_rule": _s(queue_item.get("validation_rule") or (hypothesis or {}).get("validation_rule")),
        "rejection_rule": _s(queue_item.get("rejection_rule") or (hypothesis or {}).get("rejection_rule")),
        "evidence_used": evidence,
        "scoring_method": "read_only_ssot_simulation",
        "created_at": _now(),
    }


def run_experiments(
    queue: list[dict[str, Any]],
    hypotheses_doc: dict[str, Any] | None,
    ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    hyp_by_id = {
        _s(h.get("hypothesis_id")): h for h in (hypotheses_doc or {}).get("hypotheses") or [] if h.get("hypothesis_id")
    }
    results: list[dict[str, Any]] = []
    for item in queue:
        hid = _s(item.get("hypothesis_id"))
        results.append(score_hypothesis(item, hyp_by_id.get(hid), ctx))
    results.sort(key=lambda r: (_f(r["deltas"]["expected_profit_delta_usd"]), r["confidence"]), reverse=True)
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    return results


def build_report_payload(
    queue: list[dict[str, Any]],
    results: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    verdict_counts: dict[str, int] = {}
    for row in results:
        v = row.get("verdict") or "NEEDS_MORE_DATA"
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_live_execution": True,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "queue_size": len(queue),
        "experiments_run": len(results),
        "verdict_summary": verdict_counts,
        "sources_present": ctx.get("sources_present") or {},
        "experiments": results,
        "summary": {
            "promising_count": verdict_counts.get("PROMISING", 0),
            "continue_testing_count": verdict_counts.get("CONTINUE_TESTING", 0),
            "reject_count": verdict_counts.get("REJECT", 0),
            "needs_more_data_count": verdict_counts.get("NEEDS_MORE_DATA", 0),
            "top_promising": [
                r["hypothesis_id"]
                for r in results
                if r.get("verdict") == "PROMISING"
            ][:5],
        },
        "safety": {
            "mode": MODE,
            "live_promotion_allowed": False,
            "portfolio_csv_modified": False,
            "live_bot_modified": False,
            "execution_enabled": False,
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    assert_safe_output_path(RESULTS_JSON)
    assert_safe_output_path(RESULTS_JSONL)
    assert_safe_output_path(REPORT_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    RESULTS_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with RESULTS_JSONL.open("w", encoding="utf-8") as handle:
        for row in report.get("experiments") or []:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    vs = report.get("verdict_summary") or {}
    lines = [
        "# TAE Paper Experiment Runner Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {MODE} — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE",
        f"**Live promotion allowed:** false",
        "",
        "> **PAPER_ONLY experiment scoring — read-only simulation from existing SSOT; no broker execution**",
        "",
        "## Executive summary",
        "",
        f"- Queue size: **{report.get('queue_size', 0)}**",
        f"- Experiments run: **{report.get('experiments_run', 0)}**",
        f"- PROMISING: **{vs.get('PROMISING', 0)}**",
        f"- CONTINUE_TESTING: **{vs.get('CONTINUE_TESTING', 0)}**",
        f"- REJECT: **{vs.get('REJECT', 0)}**",
        f"- NEEDS_MORE_DATA: **{vs.get('NEEDS_MORE_DATA', 0)}**",
        "",
        "## Top experiments",
        "",
        "| rank | hypothesis_id | type | verdict | profit Δ USD | risk Δ | cap eff Δ |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in (report.get("experiments") or [])[:15]:
        d = row.get("deltas") or {}
        lines.append(
            f"| {row.get('rank')} | `{row.get('hypothesis_id')}` | {row.get('hypothesis_type')} | "
            f"{row.get('verdict')} | {d.get('expected_profit_delta_usd')} | {d.get('risk_delta')} | "
            f"{d.get('capital_efficiency_delta')} |"
        )

    lines.extend(
        [
            "",
            "## Closed validation loop",
            "",
            "- Input: `runtime_outputs/learning_to_profit/paper_experiment_queue.jsonl`",
            "- Input: `runtime_outputs/learning_to_profit/hypotheses.json`",
            "- Output: `runtime_outputs/learning_to_profit/experiment_results.json`",
            "- Each hypothesis receives measurable baseline vs hypothesis deltas and a verdict.",
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| READ_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| NO_LIVE_CHANGE | ✅ |",
            "| live_promotion_allowed | **false** |",
            "| portfolio.csv modified | **false** |",
            "| live_bot.py modified | **false** |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return RESULTS_JSON, RESULTS_JSONL, REPORT_MD


def print_summary(report: dict[str, Any]) -> None:
    vs = report.get("verdict_summary") or {}
    print("===== TAE PAPER EXPERIMENT RUNNER =====")
    print(f"Mode: {MODE} — READ_ONLY — NO_BROKER — no live change")
    print("Experiments run:", report.get("experiments_run", 0))
    print(
        "Verdicts: PROMISING={} CONTINUE={} REJECT={} NEEDS_DATA={}".format(
            vs.get("PROMISING", 0),
            vs.get("CONTINUE_TESTING", 0),
            vs.get("REJECT", 0),
            vs.get("NEEDS_MORE_DATA", 0),
        )
    )
    for row in (report.get("experiments") or [])[:3]:
        d = row.get("deltas") or {}
        print(
            f"  #{row.get('rank')} {row['hypothesis_id']} [{row['verdict']}] "
            f"profitΔ=${d.get('expected_profit_delta_usd')}"
        )


def main() -> int:
    queue = load_jsonl(QUEUE_JSONL)
    hypotheses_doc = load_json(HYPOTHESES_JSON)
    if not queue:
        print("paper-experiment-runner: empty or missing queue — run learning-profit first", flush=True)
        return 1

    ctx = build_scoring_context()
    results = run_experiments(queue, hypotheses_doc, ctx)
    report = build_report_payload(queue, results, ctx)
    paths = write_outputs(report)
    print_summary(report)
    print("Wrote:", *paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
