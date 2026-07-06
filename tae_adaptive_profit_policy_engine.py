#!/usr/bin/env python3
"""
TAE Adaptive Profit Policy Engine v1 — SHADOW_ONLY / NO_BROKER.

Records portfolio-level protection policy observations and evaluates whether
prior policy states were predictive. Does NOT affect live or advisory behavior.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PORTFOLIO_GOV_JSON = Path("tae_portfolio_profit_governor.json")
PDG_JSON = Path("tae_profit_decision_governor.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
LEARNING_JSON = Path("tae_profit_committee_learning.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")

OUTPUT_JSON = Path("tae_adaptive_profit_policy_engine.json")
OUTPUT_MD = Path("tae_adaptive_profit_policy_engine.md")

POLICY_MAP: dict[str, tuple[str, str]] = {
    "PORTFOLIO_KEEP": ("OFFENSIVE", "OBSERVE_ONLY"),
    "PORTFOLIO_NORMAL": ("NORMAL", "OBSERVE_ONLY"),
    "PORTFOLIO_WATCH": ("WATCH", "REDUCE_NEW_BUY_AGGRESSION_SHADOW"),
    "PORTFOLIO_DEFENSIVE": ("DEFENSIVE", "TIGHTEN_TRAILING_SHADOW"),
    "PORTFOLIO_LOCK_PROFITS": ("LOCK_PROFITS", "LOCK_PROFIT_SHADOW"),
    "PORTFOLIO_HIGH_RISK": ("HIGH_RISK", "CAPITAL_PRESERVATION_SHADOW"),
}

EVALUATION_OUTCOMES = frozenset({"VALIDATED", "FALSE_POSITIVE", "UNKNOWN", "PENDING"})


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def observation_key(obs: dict[str, Any]) -> str:
    """Stable dedupe key — no timestamp."""
    return "|".join(
        [
            str(obs.get("portfolio_verdict", "UNKNOWN")),
            str(obs.get("total_positions", 0)),
            str(round(_f(obs.get("aggregate_missed_usd")), 1)),
            str(round(_f(obs.get("profit_quality_score")), 1)),
            str(round(_f(obs.get("profit_at_risk_score")), 1)),
            str(round(_f(obs.get("concentration_risk_score")), 1)),
        ]
    )


def ticker_list(rows: list[dict[str, Any]] | None) -> list[str]:
    return [str(r.get("ticker", "")).upper() for r in (rows or []) if r.get("ticker")]


def build_observation(ppg: dict[str, Any], *, timestamp: str) -> dict[str, Any]:
    metrics = ppg.get("metrics") or {}
    verdict = str(ppg.get("portfolio_verdict") or "PORTFOLIO_NORMAL")
    policy_state, suggested_policy = POLICY_MAP.get(verdict, ("NORMAL", "OBSERVE_ONLY"))

    obs = {
        "timestamp": timestamp,
        "portfolio_verdict": verdict,
        "final_status": str(ppg.get("final_status") or "UNKNOWN"),
        "total_positions": int(metrics.get("total_positions") or 0),
        "profitable_positions": int(metrics.get("profitable_positions") or 0),
        "losing_positions": int(metrics.get("losing_positions") or 0),
        "keep_winner_count": int(metrics.get("keep_winner_count") or 0),
        "protect_shadow_count": int(metrics.get("protect_shadow_count") or 0),
        "trail_shadow_count": int(metrics.get("trail_shadow_count") or 0),
        "watch_shadow_count": int(metrics.get("watch_shadow_count") or 0),
        "aggregate_missed_usd": round(_f(metrics.get("aggregate_missed_usd")), 2),
        "profit_quality_score": round(_f(metrics.get("portfolio_profit_quality_score")), 1),
        "profit_at_risk_score": round(_f(metrics.get("portfolio_profit_at_risk_score")), 1),
        "concentration_risk_score": round(_f(metrics.get("concentration_risk_score")), 1),
        "top_risky_tickers": ticker_list(ppg.get("top_5_risky_tickers")),
        "top_keep_tickers": ticker_list(ppg.get("top_5_keep_winners")),
        "policy_state": policy_state,
        "suggested_shadow_policy": suggested_policy,
        "outcome_evaluation": "PENDING",
        "evaluated_at": None,
        "evaluation_detail": None,
    }
    obs["observation_key"] = observation_key(obs)
    return obs


def evaluate_prior_observation(prior: dict[str, Any], current: dict[str, Any]) -> tuple[str, str]:
    """Compare prior policy state against current metrics (next observation)."""
    prior_state = str(prior.get("policy_state") or "UNKNOWN")
    prev_missed = _f(prior.get("aggregate_missed_usd"))
    prev_quality = _f(prior.get("profit_quality_score"))
    prev_at_risk = _f(prior.get("profit_at_risk_score"))

    curr_missed = _f(current.get("aggregate_missed_usd"))
    curr_quality = _f(current.get("profit_quality_score"))
    curr_at_risk = _f(current.get("profit_at_risk_score"))

    missed_increased = curr_missed > prev_missed + 0.01
    missed_decreased = curr_missed < prev_missed - 0.01
    quality_degraded = curr_quality < prev_quality - 0.5
    quality_improved = curr_quality > prev_quality + 0.5
    quality_stable_or_improved = curr_quality >= prev_quality - 0.5
    at_risk_increased = curr_at_risk > prev_at_risk + 0.5
    at_risk_decreased = curr_at_risk < prev_at_risk - 0.5

    detail_parts = [
        f"prior={prior_state}",
        f"missed {prev_missed:.2f}→{curr_missed:.2f}",
        f"quality {prev_quality:.1f}→{curr_quality:.1f}",
        f"at_risk {prev_at_risk:.1f}→{curr_at_risk:.1f}",
    ]

    if prior_state in {"HIGH_RISK", "LOCK_PROFITS"}:
        if missed_increased or quality_degraded or at_risk_increased:
            detail_parts.append("warning metrics worsened")
            return "VALIDATED", "; ".join(detail_parts)
        if quality_improved and missed_decreased and at_risk_decreased:
            detail_parts.append("metrics improved despite warning")
            return "FALSE_POSITIVE", "; ".join(detail_parts)
        return "UNKNOWN", "; ".join(detail_parts)

    if prior_state in {"OFFENSIVE", "NORMAL"}:
        if quality_stable_or_improved and not quality_degraded:
            detail_parts.append("stable/improved quality")
            return "VALIDATED", "; ".join(detail_parts)
        if quality_degraded or missed_increased:
            detail_parts.append("deterioration despite calm posture")
            return "UNKNOWN", "; ".join(detail_parts)
        return "UNKNOWN", "; ".join(detail_parts)

    if prior_state in {"WATCH", "DEFENSIVE"}:
        if missed_increased or quality_degraded:
            detail_parts.append("elevated posture followed deterioration")
            return "VALIDATED", "; ".join(detail_parts)
        if quality_improved and missed_decreased:
            detail_parts.append("metrics improved")
            return "FALSE_POSITIVE", "; ".join(detail_parts)

    return "UNKNOWN", "; ".join(detail_parts)


def count_evaluations(observations: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"VALIDATED": 0, "FALSE_POSITIVE": 0, "UNKNOWN": 0, "PENDING": 0}
    for obs in observations:
        outcome = str(obs.get("outcome_evaluation") or "PENDING")
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def policy_accuracy(counts: dict[str, int]) -> float | None:
    evaluated = counts.get("VALIDATED", 0) + counts.get("FALSE_POSITIVE", 0)
    if evaluated < 1:
        return None
    return round(counts.get("VALIDATED", 0) / evaluated, 3)


def final_verdict(*, ppg_ok: bool, memory_count: int, evaluated_count: int) -> str:
    if not ppg_ok:
        return "APPE_NOT_READY"
    if memory_count >= 2 and evaluated_count >= 1:
        return "APPE_SHADOW_READY_FOR_OBSERVATION"
    return "APPE_NEEDS_MORE_DATA"


def build_policy_report() -> dict[str, Any]:
    source_paths = {
        "tae_portfolio_profit_governor.json": PORTFOLIO_GOV_JSON,
        "tae_profit_decision_governor.json": PDG_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_committee_learning.json": LEARNING_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
    }

    sources_loaded: dict[str, bool] = {}
    for key, path in source_paths.items():
        _, ok = load_json(path)
        sources_loaded[key] = ok

    ppg, ppg_ok = load_json(PORTFOLIO_GOV_JSON)

    prior_artifact, _ = load_json(OUTPUT_JSON)
    observations: list[dict[str, Any]] = list((prior_artifact or {}).get("observations") or [])

    now = datetime.now().isoformat(timespec="seconds")
    new_observation: dict[str, Any] | None = None
    evaluation_of_prior: dict[str, Any] | None = None

    if ppg_ok and ppg:
        candidate = build_observation(ppg, timestamp=now)
        key = candidate["observation_key"]
        existing_keys = {str(o.get("observation_key")) for o in observations}

        if observations and key not in existing_keys:
            prior = observations[-1]
            if prior.get("outcome_evaluation") == "PENDING":
                outcome, detail = evaluate_prior_observation(prior, candidate)
                prior["outcome_evaluation"] = outcome
                prior["evaluated_at"] = now
                prior["evaluation_detail"] = detail
                evaluation_of_prior = {
                    "observation_key": prior.get("observation_key"),
                    "policy_state": prior.get("policy_state"),
                    "outcome": outcome,
                    "detail": detail,
                }

        if key not in existing_keys:
            observations.append(candidate)
            new_observation = candidate

    counts = count_evaluations(observations)
    evaluated_count = counts["VALIDATED"] + counts["FALSE_POSITIVE"] + counts["UNKNOWN"]
    accuracy = policy_accuracy(counts)
    latest = observations[-1] if observations else {}

    report = {
        "schema": "tae_adaptive_profit_policy_engine",
        "version": "v1",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "no_execution": True,
        "no_advisory_change": True,
        "generated_at": now,
        "sources_loaded": sources_loaded,
        "safety_mode": {
            "shadow_only": True,
            "no_broker": True,
            "no_live_execution_change": True,
            "no_advisory_change": True,
            "portfolio_csv_modified": False,
        },
        "observations": observations,
        "latest_observation": latest or None,
        "new_observation_added": new_observation is not None,
        "evaluation_of_prior": evaluation_of_prior,
        "summary": {
            "policy_memory_count": len(observations),
            "latest_policy_state": latest.get("policy_state"),
            "latest_suggested_shadow_policy": latest.get("suggested_shadow_policy"),
            "latest_portfolio_verdict": latest.get("portfolio_verdict"),
            "validated_warnings_count": counts["VALIDATED"],
            "false_positive_count": counts["FALSE_POSITIVE"],
            "unknown_count": counts["UNKNOWN"],
            "pending_count": counts["PENDING"],
            "policy_accuracy": accuracy,
            "final_verdict": final_verdict(
                ppg_ok=ppg_ok,
                memory_count=len(observations),
                evaluated_count=evaluated_count,
            ),
        },
        "policy_mapping": {
            verdict: {"policy_state": state, "suggested_shadow_policy": policy}
            for verdict, (state, policy) in POLICY_MAP.items()
        },
    }
    return report


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["summary"]
    latest = report.get("latest_observation") or {}
    lines = [
        "# TAE Adaptive Profit Policy Engine v1",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY policy memory and evaluation**",
        "",
        "## Safety confirmation",
        "",
        "- SHADOW_ONLY: **true**",
        "- NO_BROKER: **true**",
        "- NO_LIVE_EXECUTION_CHANGE: **true**",
        "- NO advisory change: **true**",
        "- portfolio.csv modified: **false**",
        "",
        "## Latest portfolio policy",
        "",
        f"- Portfolio verdict: **{latest.get('portfolio_verdict', 'N/A')}**",
        f"- Policy state: **{summary.get('latest_policy_state', 'N/A')}**",
        f"- Suggested shadow policy: **{summary.get('latest_suggested_shadow_policy', 'N/A')}**",
        f"- PPG status: **{latest.get('final_status', 'N/A')}**",
        f"- Positions: **{latest.get('total_positions', 0)}** "
        f"(profitable {latest.get('profitable_positions', 0)}, losing {latest.get('losing_positions', 0)})",
        f"- Missed USD: **{latest.get('aggregate_missed_usd', 0)}**",
        f"- Quality / at-risk / concentration: "
        f"**{latest.get('profit_quality_score')} / {latest.get('profit_at_risk_score')} / "
        f"{latest.get('concentration_risk_score')}**",
        "",
        "## Policy memory summary",
        "",
        f"- Observations stored: **{summary['policy_memory_count']}**",
        f"- New observation this run: **{report.get('new_observation_added')}**",
        f"- Validated warnings: **{summary['validated_warnings_count']}**",
        f"- False positives: **{summary['false_positive_count']}**",
        f"- Unknown: **{summary['unknown_count']}**",
        f"- Pending: **{summary['pending_count']}**",
        f"- Policy accuracy: **{summary.get('policy_accuracy', 'insufficient data')}**",
        "",
        "## Suggested shadow policy",
        "",
        f"**{summary.get('latest_suggested_shadow_policy', 'N/A')}** — derived from "
        f"`{summary.get('latest_policy_state', 'N/A')}` / `{latest.get('portfolio_verdict', 'N/A')}`",
        "",
        "## Policy mapping",
        "",
        "| portfolio verdict | policy state | suggested shadow policy |",
        "| --- | --- | --- |",
    ]
    for verdict, mapping in (report.get("policy_mapping") or {}).items():
        lines.append(
            f"| {verdict} | {mapping['policy_state']} | {mapping['suggested_shadow_policy']} |"
        )

    eval_prior = report.get("evaluation_of_prior")
    lines.extend(["", "## Evaluation of prior observation", ""])
    if eval_prior:
        lines.append(
            f"- Prior key `{eval_prior.get('observation_key')}` "
            f"({eval_prior.get('policy_state')}) → **{eval_prior.get('outcome')}**"
        )
        lines.append(f"- Detail: {eval_prior.get('detail')}")
    else:
        lines.append("- No prior observation evaluated this run (duplicate snapshot or first run).")

    lines.extend(["", "## Observation history", ""])
    if not report.get("observations"):
        lines.append("_No observations recorded yet._")
    else:
        lines.append("| # | timestamp | verdict | policy state | missed USD | quality | evaluation |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for idx, obs in enumerate(report["observations"], start=1):
            lines.append(
                f"| {idx} | {obs.get('timestamp')} | {obs.get('portfolio_verdict')} | "
                f"{obs.get('policy_state')} | {obs.get('aggregate_missed_usd')} | "
                f"{obs.get('profit_quality_score')} | {obs.get('outcome_evaluation')} |"
            )

    lines.extend(["", "## Sources loaded", ""])
    for key, loaded in sorted((report.get("sources_loaded") or {}).items()):
        mark = "✅" if loaded else "❌"
        lines.append(f"- {mark} {key}")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("===== TAE ADAPTIVE PROFIT POLICY ENGINE v1 =====")
    print("Mode: SHADOW_ONLY — no live or advisory change")
    print("Final verdict:", summary["final_verdict"])
    print("Policy memory count:", summary["policy_memory_count"])
    print("Latest policy state:", summary.get("latest_policy_state"))
    print("Suggested shadow policy:", summary.get("latest_suggested_shadow_policy"))
    print(
        "Validated / false positive / unknown:",
        summary["validated_warnings_count"],
        summary["false_positive_count"],
        summary["unknown_count"],
    )
    if summary.get("policy_accuracy") is not None:
        print("Policy accuracy:", summary["policy_accuracy"])


def main() -> int:
    report = build_policy_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
