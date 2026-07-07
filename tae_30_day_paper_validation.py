#!/usr/bin/env python3
"""
TAE 30-Day PAPER Validation Start Package — Phase 8 baseline and operator docs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN_MD = Path("TAE_30_DAY_PAPER_VALIDATION_PLAN.md")
CHECKLIST_MD = Path("TAE_30_DAY_PAPER_DAILY_CHECKLIST.md")
CRITERIA_MD = Path("TAE_30_DAY_PAPER_SUCCESS_CRITERIA.md")
BASELINE_MD = Path("TAE_30_DAY_PAPER_DAY0_BASELINE.md")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def collect_baseline() -> dict[str, Any]:
    accounting = load_json(Path("tae_accounting_snapshot.json")) or {}
    summary = load_json(Path("runtime_outputs/full_paper_cycle/summary.json")) or {}
    validation = load_json(Path("runtime_outputs/paper_decisions/decision_validation_results.json")) or {}
    weights = load_json(Path("runtime_outputs/adaptive_weights/paper_action_weights.json")) or {}
    memory = load_json(Path("runtime_outputs/longitudinal_memory/memory_index.json")) or {}
    knowledge = load_json(Path("runtime_outputs/longitudinal_memory/knowledge.json")) or {}
    infra = load_json(Path("tae_infrastructure_health.json")) or {}
    adaptive = load_json(Path("runtime_outputs/dpe/adaptive/adaptive.json")) or {}
    evaluation = load_json(Path("runtime_outputs/dpe/result_evaluator/evaluation.json")) or {}
    gii = load_json(Path("tae_growth_intelligence.json")) or {}
    ppg = load_json(Path("tae_portfolio_profit_governor.json")) or {}
    appe = load_json(Path("tae_adaptive_profit_policy_engine.json")) or {}

    positions = accounting.get("open_positions") or []
    winners = sorted(positions, key=lambda p: -_f(p.get("pnl_pct")))[:3]
    losers = sorted(positions, key=lambda p: _f(p.get("pnl_pct")))[:3]

    action_weights = {
        action: row.get("new_weight")
        for action, row in (weights.get("weights") or {}).items()
    }

    return {
        "generated_at": _now(),
        "account_value": _f(accounting.get("account_value_corrected") or accounting.get("total_account_value")),
        "cash": _f(accounting.get("cash_available")),
        "open_positions": accounting.get("open_positions_count") or len(positions),
        "realized_pnl": _f(accounting.get("realized_pnl")),
        "unrealized_pnl": _f(accounting.get("unrealized_pnl")),
        "total_pnl": _f(accounting.get("total_pnl")),
        "top_winners": winners,
        "top_losers": losers,
        "dpe_winner": evaluation.get("winner") or evaluation.get("preferred_philosophy"),
        "adaptive_philosophy": adaptive.get("preferred_philosophy"),
        "adaptive_confidence": adaptive.get("confidence") or evaluation.get("confidence"),
        "action_weights": action_weights,
        "validation_summary": validation.get("verdict_summary") or {},
        "memory_records": memory.get("total_records"),
        "knowledge_rules": len((knowledge or {}).get("rules") or []),
        "infrastructure_status": infra.get("overall_status"),
        "autostart_readiness": infra.get("autostart_readiness"),
        "final_verdict": summary.get("final_verdict"),
        "capital_efficiency": (gii.get("portfolio") or {}).get("capital_efficiency"),
        "opportunity_cost": _f((gii.get("portfolio") or {}).get("opportunity_cost_total")),
        "ppg_verdict": (ppg or {}).get("portfolio_verdict"),
        "appe_policy": ((appe or {}).get("latest_observation") or {}).get("policy_state"),
        "horizon_conflicts": summary.get("horizon_conflicts"),
        "stale_sources": summary.get("stale_sources") or [],
        "blocked_jobs": summary.get("blocked_jobs"),
        "warnings": summary.get("failed_steps") or [],
        "live_promotion_allowed": False,
    }


def write_plan() -> None:
    PLAN_MD.write_text(
        "\n".join(
            [
                "# TAE 30-Day PAPER Validation Plan",
                "",
                f"**Created:** {_now()}",
                "**Mode:** PAPER_ONLY — NO_BROKER — NO_LIVE_EXECUTION — NO_LIVE_PROMOTION",
                "",
                "## Objective",
                "",
                "Run disciplined daily PAPER validation for 30 calendar days before any live promotion review.",
                "",
                "## Daily command",
                "",
                "```bash",
                "python3 tae.py full-paper-cycle",
                "```",
                "",
                "## Daily evidence to record",
                "",
                "- Portfolio value, cash, open positions",
                "- Realized / unrealized / total PnL",
                "- Top BUY_PAPER, SELL_PAPER, PROTECT_PAPER, HOLD_PAPER, ROTATE_PAPER",
                "- PROMISING / CONTINUE / REJECT / NEEDS_MORE_DATA counts",
                "- DPE winner, adaptive philosophy, adaptive confidence",
                "- Adaptive action weights (`runtime_outputs/adaptive_weights/paper_action_weights.json`)",
                "- Capital efficiency, opportunity cost",
                "- Profit protection / PPG / APPE state",
                "- Horizon conflicts, stale sources, blocked jobs",
                "- Infrastructure status and final verdict",
                "",
                "## Weekly review",
                "",
                "- `python3 tae.py outcome-memory`",
                "- `python3 tae.py strategy-survival`",
                "- `python3 tae.py long-term-learning`",
                "- `python3 tae.py philosophy-performance`",
                "",
                "## End-of-period gate",
                "",
                "After 30 days, operator may review `PROMOTE_TO_LIVE_CANDIDATE` recommendations only.",
                "Machine outputs remain `live_promotion_allowed=false` until manual approval outside TAE.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_checklist() -> None:
    CHECKLIST_MD.write_text(
        "\n".join(
            [
                "# TAE 30-Day PAPER Daily Checklist",
                "",
                "## Morning",
                "",
                "- [ ] Run `python3 tae.py full-paper-cycle`",
                "- [ ] Confirm `final_verdict` is READY_FOR_PAPER_DAY or READY_WITH_WARNINGS",
                "- [ ] Confirm forbidden files unchanged",
                "- [ ] Confirm `live_promotion_allowed=false`",
                "",
                "## Record",
                "",
                "- [ ] Portfolio value / cash / positions",
                "- [ ] PnL (realized, unrealized, total)",
                "- [ ] Top PAPER decisions by action",
                "- [ ] Validation verdict counts",
                "- [ ] DPE winner + adaptive philosophy/confidence",
                "- [ ] Adaptive action weights updated within caps",
                "- [ ] Longitudinal memory record count increased or stable",
                "- [ ] Infrastructure status",
                "",
                "## Blockers",
                "",
                "- [ ] No broker execution",
                "- [ ] No live promotion",
                "- [ ] No forbidden file edits",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_criteria() -> None:
    CRITERIA_MD.write_text(
        "\n".join(
            [
                "# TAE 30-Day PAPER Success Criteria",
                "",
                "1. Infrastructure PASS on at least 90% of days.",
                "2. Historical refresh successful on at least 90% of days.",
                "3. Decision validation generated every day.",
                "4. Longitudinal memory updated every day.",
                "5. Adaptive weights updated only within safe caps (±0.02/day, 0.85–1.15 range).",
                "6. No live execution.",
                "7. No broker usage.",
                "8. No live promotion (`live_promotion_allowed=false` always).",
                "9. Forbidden files remain untouched unless explicitly approved.",
                "10. PAPER decisions produce measurable improvement or clear rejection evidence.",
                "11. Collaborative vs Competitive comparison remains tracked.",
                "12. At least one decision class reaches enough evidence for promotion review or rejection.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_baseline(data: dict[str, Any]) -> None:
    lines = [
        "# TAE 30-Day PAPER Day 0 Baseline",
        "",
        f"**Generated:** {data['generated_at']}",
        f"**live_promotion_allowed:** false",
        "",
        "## Portfolio",
        "",
        f"- Account value: **${data['account_value']:,.2f}**",
        f"- Cash: **${data['cash']:,.2f}**",
        f"- Open positions: **{data['open_positions']}**",
        f"- Realized PnL: **${data['realized_pnl']:,.2f}**",
        f"- Unrealized PnL: **${data['unrealized_pnl']:,.2f}**",
        f"- Total PnL: **${data['total_pnl']:,.2f}**",
        "",
        "## Top open winners",
        "",
    ]
    for p in data.get("top_winners") or []:
        lines.append(f"- {p.get('ticker')}: ${_f(p.get('pnl')):.2f} ({_f(p.get('pnl_pct')):.1f}%)")
    lines.extend(["", "## Top open losers", ""])
    for p in data.get("top_losers") or []:
        lines.append(f"- {p.get('ticker')}: ${_f(p.get('pnl')):.2f} ({_f(p.get('pnl_pct')):.1f}%)")
    lines.extend(
        [
            "",
            "## DPE & adaptive",
            "",
            f"- DPE winner: **{data.get('dpe_winner')}**",
            f"- Adaptive philosophy: **{data.get('adaptive_philosophy')}**",
            f"- Adaptive confidence: **{data.get('adaptive_confidence')}**",
            "",
            "## Action weights",
            "",
            f"```json\n{json.dumps(data.get('action_weights') or {}, indent=2)}\n```",
            "",
            "## Validation summary",
            "",
            f"```json\n{json.dumps(data.get('validation_summary') or {}, indent=2)}\n```",
            "",
            "## Memory & knowledge",
            "",
            f"- Longitudinal records: **{data.get('memory_records')}**",
            f"- Knowledge rules: **{data.get('knowledge_rules')}**",
            "",
            "## Risk & protection",
            "",
            f"- Capital efficiency: **{data.get('capital_efficiency')}**",
            f"- Opportunity cost: **${_f(data.get('opportunity_cost')):,.2f}**",
            f"- PPG verdict: **{data.get('ppg_verdict')}**",
            f"- APPE policy: **{data.get('appe_policy')}**",
            f"- Horizon conflicts: **{data.get('horizon_conflicts')}**",
            "",
            "## Infrastructure",
            "",
            f"- Status: **{data.get('infrastructure_status')}**",
            f"- Autostart: **{data.get('autostart_readiness')}**",
            f"- Final verdict: **{data.get('final_verdict')}**",
            f"- Stale sources: {', '.join(data.get('stale_sources') or []) or 'none'}",
            f"- Blocked jobs: **{data.get('blocked_jobs')}**",
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = data.get("warnings") or []
    lines.extend(f"- {w}" for w in warnings) if warnings else lines.append("- none recorded")
    BASELINE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_30_day_package() -> dict[str, Any]:
    baseline = collect_baseline()
    write_plan()
    write_checklist()
    write_criteria()
    write_baseline(baseline)
    return {"ok": True, "baseline": baseline, "files": [str(p) for p in (PLAN_MD, CHECKLIST_MD, CRITERIA_MD, BASELINE_MD)]}


def main() -> int:
    print("===== TAE 30-DAY PAPER VALIDATION START PACKAGE =====")
    result = run_30_day_package()
    print("Wrote:", ", ".join(result["files"]))
    print("Day 0 account value:", result["baseline"]["account_value"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
