#!/usr/bin/env python3
"""
TAE DPE-4 — Collaborative Paper Executor — PAPER_ONLY / SHADOW_ONLY.

Consumes COLLABORATIVE + READY jobs from execution_jobs.jsonl.
Collaborative philosophy: profit protection, drawdown reduction, faster exits,
exposure reduction, capital preservation. Does NOT touch live paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tae_dpe_paper_executor_infra import (
    ExecutorConfig,
    _f,
    _s,
    run_executor,
)

EXECUTOR = "COLLABORATIVE"
SOURCE = "tae_dpe_collaborative_executor"
OUTPUT_DIR = Path("runtime_outputs/dpe/paper_collaborative")

COLLAPSED_STAGES = frozenset({"COLLAPSED", "COLLAPSE"})
DECAY_STAGES = frozenset({"PROFIT_DECAY", "DECAY"})
STRONG_WINNER_STAGES = frozenset({"SURVIVED", "EARLY_WINNER", "MATURE_WINNER", "MATURE"})

CONFIG = ExecutorConfig(
    executor=EXECUTOR,
    source=SOURCE,
    output_dir=OUTPUT_DIR,
    report_title="# TAE DPE-4 Collaborative Paper Executor Report",
    report_tagline="Collaborative paper portfolio — market-following, capital preservation, no live execution",
    root_report_path=Path("TAE_DPE4_COLLABORATIVE_EXECUTOR_REPORT.md"),
    next_sprint="TAE DPE-5 — Result Evaluator",
)


def resolve_paper_action_collaborative(
    job: dict[str, Any],
    position: dict[str, Any] | None,
) -> tuple[str, float, str]:
    """Collaborative policy — conservative, profit-protecting, faster exits."""
    if position is None or _f(position.get("shares")) <= 0:
        return "PAPER_SKIP", 0.0, "NO_OPEN_POSITION"

    growth = job.get("growth_snapshot") or {}
    target = job.get("target_snapshot") or {}
    policy = job.get("policy_snapshot") or {}
    market = job.get("market_snapshot") or {}
    candidate = (_s(job.get("action_candidate")) or "UNKNOWN").upper()

    growth_score = _f(growth.get("growth_score"))
    lifecycle = (_s(growth.get("lifecycle_stage")) or "").upper()
    urgency = (_s(target.get("exit_window_urgency")) or "").upper()
    partial_pct = _f(target.get("suggested_partial_size_pct"), 25.0)
    policy_state = (_s(policy.get("policy_state")) or "").upper()
    portfolio_verdict = (_s(policy.get("portfolio_verdict")) or "").upper()
    shadow_policy = (_s(policy.get("suggested_shadow_policy")) or "").upper()
    drawdown_pct = _f(market.get("drawdown_pct"))
    position_pct = _f(position.get("current_pct"))

    # Collaborative: collapsed positions — exit exposure quickly
    if lifecycle in COLLAPSED_STAGES:
        return "PAPER_TRIM", 50.0, "COLLAPSED_COLLABORATIVE_EXIT"

    # Profit decay — trim more aggressively than competitive
    if lifecycle in DECAY_STAGES:
        return "PAPER_TRIM", 33.0, "PROFIT_DECAY_COLLABORATIVE_TRIM"

    # Drawdown protection — reduce exposure when underwater
    if drawdown_pct <= -1.5 or position_pct < -1.0:
        return "PAPER_TRIM", max(partial_pct, 30.0), "DRAWDOWN_COLLABORATIVE_TRIM"

    # Critical exit window — always trim (no strong-winner override)
    if urgency == "CRITICAL":
        return "PAPER_TRIM", max(partial_pct, 30.0), "CRITICAL_COLLABORATIVE_EXIT"

    if urgency == "HIGH":
        return "PAPER_PROTECT", max(partial_pct, 25.0), "HIGH_URGENCY_COLLABORATIVE_PROTECT"

    # High portfolio risk — capital preservation bias
    if policy_state == "HIGH_RISK" or "HIGH_RISK" in portfolio_verdict:
        if growth_score < 75:
            return "PAPER_TRIM", max(partial_pct, 30.0), "HIGH_RISK_COLLABORATIVE_REDUCE"
        return "PAPER_PROTECT", partial_pct, "HIGH_RISK_COLLABORATIVE_PROTECT"

    if "CAPITAL_PRESERVATION" in shadow_policy:
        if candidate in {"PROTECT", "TRIM_TRAIL", "REDUCE", "REDUCE_EXPOSURE"}:
            return "PAPER_PROTECT", partial_pct, "CAPITAL_PRESERVATION_PROTECT"
        if growth_score < 70:
            return "PAPER_TRIM", max(partial_pct, 25.0), "CAPITAL_PRESERVATION_TRIM"

    # Collaborative base mapping — less hold bias
    if candidate == "HOLD_WINNER":
        if growth_score >= 85 and lifecycle in STRONG_WINNER_STAGES and position_pct > 0:
            return "HOLD", 0.0, "STRONG_WINNER_COLLABORATIVE_HOLD"
        return "PAPER_PROTECT", partial_pct, "HOLD_WINNER_COLLABORATIVE_PROTECT"

    if candidate == "MONITOR":
        if growth_score >= 70 and position_pct > 0:
            return "PAPER_PROTECT", partial_pct, "MONITOR_COLLABORATIVE_PROTECT"
        return "PAPER_TRIM", max(partial_pct, 25.0), "MONITOR_COLLABORATIVE_TRIM"

    if candidate == "PROTECT":
        return "PAPER_PROTECT", max(partial_pct, 25.0), "PROTECT_COLLABORATIVE"

    if candidate in {"TRIM_TRAIL", "REDUCE", "REDUCE_EXPOSURE"}:
        return "PAPER_TRIM", max(partial_pct, 30.0), "EXPOSURE_COLLABORATIVE_TRIM"

    if candidate == "UNKNOWN":
        return "PAPER_SKIP", 0.0, "UNKNOWN_COLLABORATIVE_SKIP"

    return "PAPER_SKIP", 0.0, f"UNMAPPED_{candidate}"


def main() -> int:
    return run_executor(
        config=CONFIG,
        resolve_action=resolve_paper_action_collaborative,
        banner="===== TAE DPE-4 COLLABORATIVE PAPER EXECUTOR =====",
    )


if __name__ == "__main__":
    raise SystemExit(main())
