#!/usr/bin/env python3
"""
TAE Investment Council — synthesis layer only.

PAPER_ONLY | NO_BROKER | NO_REAL_MONEY | NO_LIVE_PROMOTION

Aggregates decisions already produced by PDE, GII, DPE, PPG, APPE,
rule survival, hard risk, structural governance, and morning audit.
Does NOT decide independently or override hard rules.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODE = "PAPER_ONLY"

OUTPUT_DIR = Path("runtime_outputs/investment_council")
COUNCIL_JSON = OUTPUT_DIR / "council.json"
COUNCIL_PRIOR_JSON = OUTPUT_DIR / "council_prior.json"
REPORT_MD = Path("TAE_INVESTMENT_COUNCIL_REPORT.md")

GII_JSON = Path("tae_growth_intelligence.json")
DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
PAPER_PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
RULE_ATTRIBUTION_JSON = Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
RULE_LIFECYCLE_JSON = Path("runtime_outputs/paper_execution/rule_lifecycle.json")
HARD_RISK_JSON = Path("runtime_outputs/governance/hard_risk.json")
GOVERNANCE_JSON = Path("runtime_outputs/governance/structural_governance.json")
CYCLE_SUMMARY_JSON = Path("runtime_outputs/full_paper_cycle/summary.json")
DPE_ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
DPE_EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
CANONICAL_REPORT_MD = Path("TAE_CANONICAL_VS_PAPER_REPORT.md")

ACTION_BUCKETS = {
    "BUY_PAPER": "buy",
    "SELL_PAPER": "sell",
    "PROTECT_PAPER": "protect",
    "HOLD_PAPER": "hold",
    "ROTATE_PAPER": "rotate",
    "REDUCE_PAPER": "reduce",
    "SKIP_PAPER": "skip",
}


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


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _decision_row(dec: dict[str, Any]) -> dict[str, Any]:
    hard = dec.get("hard_risk_discipline") or {}
    return {
        "ticker": dec.get("ticker"),
        "action": dec.get("action"),
        "confidence": dec.get("confidence"),
        "risk_score": dec.get("risk_score"),
        "expected_profit_delta": dec.get("expected_profit_delta"),
        "expected_risk_delta": dec.get("expected_risk_delta"),
        "paper_position_held": dec.get("paper_position_held"),
        "hard_risk_override": bool(hard.get("override")),
        "hard_rule": hard.get("hard_rule"),
        "evidence": _s(dec.get("evidence"))[:240],
        "source": "tae_paper_decision_engine",
        "decision_id": dec.get("decision_id"),
    }


def _rank_decisions(decisions: list[dict[str, Any]], action: str, *, limit: int = 10) -> list[dict[str, Any]]:
    rows = [_decision_row(d) for d in decisions if d.get("action") == action]
    rows.sort(key=lambda r: (-_f(r.get("confidence")), _s(r.get("ticker"))))
    return rows[:limit]


def _gii_buy_candidates(gii: dict[str, Any] | None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in (gii or {}).get("top_growth_candidates") or []:
        if isinstance(row, dict):
            candidates.append(
                {
                    "ticker": row.get("ticker"),
                    "growth_score": row.get("growth_score"),
                    "lifecycle_stage": row.get("lifecycle_stage"),
                    "recommended_shadow_strategy": row.get("recommended_shadow_strategy"),
                    "source": "tae_growth_intelligence.json",
                }
            )
        elif row:
            candidates.append({"ticker": str(row).upper(), "source": "tae_growth_intelligence.json"})
    portfolio = (gii or {}).get("portfolio") or {}
    for ticker in portfolio.get("top_growth_candidates") or []:
        if not any(c.get("ticker") == ticker for c in candidates):
            candidates.append({"ticker": ticker, "source": "tae_growth_intelligence.json"})
    return candidates[:10]


def _merge_buy_candidates(pde_buys: list[dict[str, Any]], gii_buys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in pde_buys:
        ticker = _s(row.get("ticker")).upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            merged.append({**row, "pde_buy": True, "gii_top_growth": False})
    for row in gii_buys:
        ticker = _s(row.get("ticker")).upper()
        if not ticker:
            continue
        if ticker in seen:
            for m in merged:
                if m.get("ticker") == ticker:
                    m["gii_top_growth"] = True
                    m.setdefault("growth_score", row.get("growth_score"))
                    break
        else:
            seen.add(ticker)
            merged.append(
                {
                    "ticker": ticker,
                    "action": "BUY_PAPER",
                    "confidence": None,
                    "source": "tae_growth_intelligence.json",
                    "pde_buy": False,
                    "gii_top_growth": True,
                    "growth_score": row.get("growth_score"),
                    "lifecycle_stage": row.get("lifecycle_stage"),
                }
            )
    return merged[:10]


def _hard_risk_alerts(hard_risk: dict[str, Any] | None, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for row in (hard_risk or {}).get("breaches") or []:
        alerts.append(
            {
                "ticker": row.get("ticker"),
                "pnl_pct": row.get("pnl_pct"),
                "status": row.get("status"),
                "required_action": row.get("required_action"),
                "hard_rule": row.get("hard_rule"),
                "source": "hard_risk_guardian.json",
            }
        )
    for row in (hard_risk or {}).get("positions") or []:
        if row.get("status") not in {"OK", "NO_POSITION"} and not any(a.get("ticker") == row.get("ticker") for a in alerts):
            alerts.append(
                {
                    "ticker": row.get("ticker"),
                    "pnl_pct": row.get("pnl_pct"),
                    "status": row.get("status"),
                    "required_action": row.get("required_action"),
                    "hard_rule": row.get("hard_rule"),
                    "source": "hard_risk_guardian.json",
                }
            )
    for dec in decisions:
        hard = dec.get("hard_risk_discipline") or {}
        if hard.get("override"):
            ticker = dec.get("ticker")
            if not any(a.get("ticker") == ticker for a in alerts):
                alerts.append(
                    {
                        "ticker": ticker,
                        "pnl_pct": hard.get("pnl_pct"),
                        "status": hard.get("status"),
                        "required_action": hard.get("required_action"),
                        "hard_rule": hard.get("hard_rule"),
                        "pde_action": dec.get("action"),
                        "source": "paper_decisions.hard_risk_discipline",
                    }
                )
    return alerts


def _portfolio_rebuild_view(decisions: list[dict[str, Any]], gii: dict[str, Any] | None) -> dict[str, Any]:
    buys = [_decision_row(d) for d in decisions if d.get("action") == "BUY_PAPER"]
    sells = [_decision_row(d) for d in decisions if d.get("action") == "SELL_PAPER"]
    rotates = [_decision_row(d) for d in decisions if d.get("action") == "ROTATE_PAPER"]
    reduces = [_decision_row(d) for d in decisions if d.get("action") == "REDUCE_PAPER"]
    gii_strategy = _s(((gii or {}).get("portfolio") or {}).get("recommended_portfolio_shadow_strategy"))
    return {
        "source": "paper_decisions.json + tae_growth_intelligence.json",
        "would_buy": buys,
        "would_sell": sells,
        "would_rotate": rotates,
        "would_reduce": reduces,
        "gii_portfolio_strategy": gii_strategy or None,
        "note": "Synthesis only — reflects existing PDE/GII outputs, not new decisions.",
    }


def _rule_rankings(lifecycle: dict[str, Any] | None, attribution: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rules = dict((lifecycle or {}).get("rules") or {})
    if not rules and attribution:
        rules = dict((attribution or {}).get("rules") or {})

    ranked = []
    for rule_id, row in rules.items():
        if not isinstance(row, dict):
            continue
        ranked.append(
            {
                "rule_id": rule_id,
                "state": row.get("state"),
                "net_pnl_impact": _f(row.get("net_pnl_impact")),
                "avg_actual_pnl": _f(row.get("avg_actual_pnl")),
                "win_rate": _f(row.get("win_rate")),
                "influence_multiplier": _f(row.get("influence_multiplier"), 1.0),
                "reason": _s(row.get("reason"))[:120],
                "source": "rule_lifecycle.json",
            }
        )

    strongest = sorted(ranked, key=lambda r: (-r["net_pnl_impact"], -r["win_rate"]))[:8]
    weakest_states = {"DISABLED", "DEPRECATED", "WATCHLIST"}
    weakest = [r for r in ranked if _s(r.get("state")) in weakest_states]
    weakest.extend(sorted([r for r in ranked if r not in weakest], key=lambda r: r["net_pnl_impact"])[:8])
    seen: set[str] = set()
    weakest_dedup: list[dict[str, Any]] = []
    for row in weakest:
        rid = _s(row.get("rule_id"))
        if rid and rid not in seen:
            seen.add(rid)
            weakest_dedup.append(row)
    by_state = (lifecycle or {}).get("by_state") or {}
    disabled = [{"rule_id": rid, "state": "DISABLED", "source": "rule_lifecycle.json"} for rid in by_state.get("DISABLED") or []]
    deprecated = [{"rule_id": rid, "state": "DEPRECATED", "source": "rule_lifecycle.json"} for rid in by_state.get("DEPRECATED") or []]
    for row in disabled + deprecated:
        if row["rule_id"] not in seen:
            weakest_dedup.append(row)
    return strongest[:8], weakest_dedup[:8]


def _dpe_philosophy_view(adaptive: dict[str, Any] | None, evaluation: dict[str, Any] | None, policy: dict[str, Any] | None) -> dict[str, Any]:
    policy_ctx = policy or {}
    latest = (policy_ctx.get("latest_observation") or {}) if isinstance(policy_ctx.get("latest_observation"), dict) else {}
    if not latest and (policy_ctx.get("observations") or []):
        latest = (policy_ctx.get("observations") or [])[-1]
    return {
        "preferred_philosophy": _s(adaptive.get("preferred_philosophy")) if adaptive else _s(latest.get("preferred_philosophy")),
        "adaptive_recommendation": _s((adaptive or {}).get("recommendation")),
        "adaptive_confidence": _f((adaptive or {}).get("confidence")),
        "competitive_pct": _f((adaptive or {}).get("competitive_pct")),
        "collaborative_pct": _f((adaptive or {}).get("collaborative_pct")),
        "context_label": _s((adaptive or {}).get("context_label")),
        "evaluator_winner": _s((evaluation or {}).get("winner_philosophy") or (evaluation or {}).get("preferred_philosophy")),
        "evaluator_summary": _s((evaluation or {}).get("summary") or (evaluation or {}).get("recommendation"))[:300],
        "policy_state": _s(latest.get("policy_state")),
        "suggested_policy": _s(latest.get("suggested_shadow_policy") or latest.get("suggested_policy")),
        "source": "dpe/adaptive + dpe/evaluator + appe",
    }


def _capital_status(
    paper: dict[str, Any] | None,
    accounting: dict[str, Any] | None,
    ppg: dict[str, Any] | None,
    appe: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_appe = (appe or {}).get("latest_observation") or {}
    if not latest_appe and (appe or {}).get("observations"):
        latest_appe = (appe or {}).get("observations")[-1]
    return {
        "paper_cash": _f((paper or {}).get("cash")),
        "paper_total_value": _f((paper or {}).get("total_value")),
        "paper_realized_pnl": _f((paper or {}).get("realized_pnl")),
        "paper_unrealized_pnl": _f((paper or {}).get("unrealized_pnl")),
        "paper_total_pnl": _f((paper or {}).get("total_pnl")),
        "paper_open_positions": len((paper or {}).get("positions") or {}),
        "canonical_cash": _f((accounting or {}).get("cash_available")),
        "canonical_total_value": _f((accounting or {}).get("account_value_corrected") or (accounting or {}).get("total_account_value")),
        "ppg_portfolio_verdict": _s((ppg or {}).get("portfolio_verdict")),
        "appe_policy_state": _s(latest_appe.get("policy_state")),
        "broker_executed": bool((paper or {}).get("broker_executed")),
        "live_money": bool((paper or {}).get("live_money")),
        "live_promotion_allowed": False,
    }


def _canonical_vs_paper() -> dict[str, Any]:
    try:
        from tae_paper_execution import compare_canonical_vs_paper

        return compare_canonical_vs_paper(write_report_flag=False)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "compare_canonical_vs_paper"}


def _changes_since_last(current: dict[str, Any], prior: dict[str, Any] | None) -> list[str]:
    if not prior:
        return ["First council synthesis — no prior council.json for delta comparison."]
    changes: list[str] = []
    keys = (
        ("governance_verdict", "Governance verdict"),
        ("executive_recommendation", "Executive recommendation"),
        ("paper_portfolio_value", "PAPER portfolio value"),
        ("paper_cash", "PAPER cash"),
        ("action_plan_count", "Action plan items"),
    )
    cur_summary = current.get("summary") or {}
    pri_summary = prior.get("summary") or {}
    for key, label in keys:
        if cur_summary.get(key) != pri_summary.get(key):
            changes.append(f"{label}: {pri_summary.get(key)!r} → {cur_summary.get(key)!r}")
    cur_actions = {(_s(r.get("ticker")), _s(r.get("action"))) for r in (current.get("final_paper_action_plan") or [])}
    pri_actions = {(_s(r.get("ticker")), _s(r.get("action"))) for r in (prior.get("final_paper_action_plan") or [])}
    added = cur_actions - pri_actions
    removed = pri_actions - cur_actions
    if added:
        changes.append(f"New action plan entries: {sorted(added)}")
    if removed:
        changes.append(f"Removed action plan entries: {sorted(removed)}")
    if len(changes) == 1 and changes[0].startswith("First council"):
        return changes
    if not any(not c.startswith("First council") for c in changes):
        changes.append("No material council delta detected.")
    return changes[:12]


def _build_action_plan(
    decisions: list[dict[str, Any]],
    *,
    governance_blocked: bool,
) -> list[dict[str, Any]]:
    if governance_blocked:
        return [
            {
                "ticker": "_PORTFOLIO",
                "action": "NO_PAPER_ACTION",
                "reason": "Structural governance BLOCKED — observe only; resolve block reasons before execution.",
                "source": "tae_structural_governance",
            }
        ]
    actionable = {"BUY_PAPER", "SELL_PAPER", "PROTECT_PAPER", "HOLD_PAPER", "ROTATE_PAPER", "REDUCE_PAPER"}
    plan = [_decision_row(d) for d in decisions if d.get("action") in actionable]
    plan.sort(
        key=lambda r: (
            {"SELL_PAPER": 0, "ROTATE_PAPER": 1, "REDUCE_PAPER": 2, "PROTECT_PAPER": 3, "BUY_PAPER": 4, "HOLD_PAPER": 5}.get(
                _s(r.get("action")), 9
            ),
            -_f(r.get("confidence")),
        )
    )
    return plan


def _executive_recommendation(
    *,
    governance_verdict: str,
    block_reasons: list[str],
    morning_verdict: str,
    pde_summary: dict[str, Any],
    hard_alerts: list[dict[str, Any]],
    dpe_view: dict[str, Any],
    capital: dict[str, Any],
    action_plan: list[dict[str, Any]],
) -> str:
    if governance_verdict == "BLOCKED_WITH_REASONS":
        reason = "; ".join(block_reasons[:2]) or "governance block"
        return (
            f"PAPER BLOCKED by structural governance ({reason}). "
            "Do not execute PAPER actions until blockers clear. Observe only."
        )

    sells = [r for r in action_plan if r.get("action") == "SELL_PAPER"]
    buys = [r for r in action_plan if r.get("action") == "BUY_PAPER"]
    protects = [r for r in action_plan if r.get("action") == "PROTECT_PAPER"]

    parts = [f"PAPER cycle {governance_verdict}."]
    if hard_alerts:
        tickers = ", ".join(_s(a.get("ticker")) for a in hard_alerts[:4])
        parts.append(f"Hard risk active: {tickers}.")
    if sells:
        parts.append(f"PDE SELL: {', '.join(_s(r.get('ticker')) for r in sells[:5])}.")
    if protects:
        parts.append(f"PDE PROTECT: {', '.join(_s(r.get('ticker')) for r in protects[:5])}.")
    if buys:
        parts.append(f"PDE BUY: {', '.join(_s(r.get('ticker')) for r in buys[:5])}.")
    if not sells and not buys and not protects:
        parts.append(f"PDE summary: {pde_summary}.")
    parts.append(f"Policy {capital.get('appe_policy_state') or 'N/A'} / PPG {capital.get('ppg_portfolio_verdict') or 'N/A'}.")
    parts.append(f"DPE philosophy {dpe_view.get('preferred_philosophy') or 'N/A'}.")
    if morning_verdict:
        parts.append(f"Morning audit {morning_verdict}.")
    parts.append("live_promotion_allowed=false.")
    return " ".join(parts)


def build_council_synthesis(*, include_morning_audit: bool = True) -> dict[str, Any]:
    """Load upstream artifacts and produce synthesis payload — no independent decisions."""
    decisions_doc = _load_json(DECISIONS_JSON) or {}
    decisions = decisions_doc.get("decisions") or []
    gii = _load_json(GII_JSON)
    paper = _load_json(PAPER_PORTFOLIO_JSON)
    lifecycle = _load_json(RULE_LIFECYCLE_JSON)
    attribution = _load_json(RULE_ATTRIBUTION_JSON)
    hard_risk = _load_json(HARD_RISK_JSON)
    governance = _load_json(GOVERNANCE_JSON)
    cycle_summary = _load_json(CYCLE_SUMMARY_JSON)
    adaptive = _load_json(DPE_ADAPTIVE_JSON)
    evaluation = _load_json(DPE_EVAL_JSON)
    appe = _load_json(APPE_JSON)
    ppg = _load_json(PPG_JSON)
    accounting = _load_json(ACCOUNTING_JSON)

    morning: dict[str, Any] = {}
    if include_morning_audit:
        try:
            from tae_morning_operational_audit import run_audit

            morning = run_audit()
        except Exception as exc:
            morning = {"ok": False, "error": str(exc)}

    canonical = _canonical_vs_paper()
    governance_verdict = _s(
        (governance or {}).get("final_verdict")
        or (cycle_summary or {}).get("governance_verdict")
        or (cycle_summary or {}).get("final_verdict")
        or "UNKNOWN"
    )
    block_reasons = list((governance or {}).get("block_reasons") or (cycle_summary or {}).get("block_reasons") or [])

    pde_buys = _rank_decisions(decisions, "BUY_PAPER")
    top_buy = _merge_buy_candidates(pde_buys, _gii_buy_candidates(gii))
    top_sell = _rank_decisions(decisions, "SELL_PAPER")
    top_protect = _rank_decisions(decisions, "PROTECT_PAPER")
    top_hold = _rank_decisions(decisions, "HOLD_PAPER")
    hard_alerts = _hard_risk_alerts(hard_risk, decisions)
    rebuild = _portfolio_rebuild_view(decisions, gii)
    strongest, weakest = _rule_rankings(lifecycle, attribution)
    dpe_view = _dpe_philosophy_view(adaptive, evaluation, appe)
    capital = _capital_status(paper, accounting, ppg, appe)

    governance_blocked = governance_verdict == "BLOCKED_WITH_REASONS"
    action_plan = _build_action_plan(decisions, governance_blocked=governance_blocked)
    executive = _executive_recommendation(
        governance_verdict=governance_verdict,
        block_reasons=block_reasons,
        morning_verdict=_s(morning.get("verdict")),
        pde_summary=decisions_doc.get("action_summary") or {},
        hard_alerts=hard_alerts,
        dpe_view=dpe_view,
        capital=capital,
        action_plan=action_plan,
    )

    prior = _load_json(COUNCIL_JSON)
    if prior and COUNCIL_JSON.is_file():
        shutil.copy2(COUNCIL_JSON, COUNCIL_PRIOR_JSON)

    payload: dict[str, Any] = {
        "schema": "tae.investment_council.v1",
        "mode": MODE,
        "synthesis_only": True,
        "no_independent_decisions": True,
        "live_promotion_allowed": False,
        "broker_executed": False,
        "live_money": False,
        "generated_at": _now(),
        "governance_verdict": governance_verdict,
        "block_reasons": block_reasons,
        "executive_recommendation": executive,
        "top_buy_candidates": top_buy,
        "top_sell_candidates": top_sell,
        "top_protect_candidates": top_protect,
        "top_hold_candidates": top_hold,
        "hard_risk_alerts": hard_alerts,
        "portfolio_rebuild_view": rebuild,
        "strongest_rules": strongest,
        "weakest_rules": weakest,
        "dpe_philosophy_view": dpe_view,
        "canonical_vs_paper": canonical,
        "capital_status": capital,
        "morning_audit_summary": {
            "verdict": morning.get("verdict"),
            "global_score": morning.get("global_score"),
            "next_actions": morning.get("next_actions"),
            "outstanding_risks": morning.get("outstanding_risks"),
        },
        "final_paper_action_plan": action_plan,
        "sources_loaded": {
            "paper_decisions": DECISIONS_JSON.is_file(),
            "gii": GII_JSON.is_file(),
            "paper_portfolio": PAPER_PORTFOLIO_JSON.is_file(),
            "rule_lifecycle": RULE_LIFECYCLE_JSON.is_file(),
            "rule_attribution": RULE_ATTRIBUTION_JSON.is_file(),
            "hard_risk": HARD_RISK_JSON.is_file(),
            "governance": GOVERNANCE_JSON.is_file(),
            "cycle_summary": CYCLE_SUMMARY_JSON.is_file(),
            "dpe_adaptive": DPE_ADAPTIVE_JSON.is_file(),
            "dpe_evaluator": DPE_EVAL_JSON.is_file(),
            "appe": APPE_JSON.is_file(),
            "ppg": PPG_JSON.is_file(),
            "accounting": ACCOUNTING_JSON.is_file(),
            "canonical_report_md": CANONICAL_REPORT_MD.is_file(),
            "morning_audit": bool(morning.get("verdict")),
        },
        "summary": {
            "governance_verdict": governance_verdict,
            "executive_recommendation": executive,
            "paper_portfolio_value": capital.get("paper_total_value"),
            "paper_cash": capital.get("paper_cash"),
            "action_plan_count": len(action_plan),
            "hard_risk_alert_count": len(hard_alerts),
            "pde_action_summary": decisions_doc.get("action_summary"),
        },
    }
    payload["changes_since_last_cycle"] = _changes_since_last(payload, prior)
    return payload


def write_council_report(payload: dict[str, Any]) -> None:
    capital = payload.get("capital_status") or {}
    canonical = payload.get("canonical_vs_paper") or {}
    delta = canonical.get("delta") or {}
    dpe = payload.get("dpe_philosophy_view") or {}
    rebuild = payload.get("portfolio_rebuild_view") or {}

    def _rows(items: list[dict[str, Any]], cols: list[str]) -> list[str]:
        if not items:
            return ["- none"]
        lines = []
        for row in items:
            bits = [f"**{row.get('ticker', row.get('rule_id', '?'))}**"]
            for col in cols:
                if col in row and row[col] is not None:
                    bits.append(f"{col}={row[col]}")
            lines.append("- " + " | ".join(bits))
        return lines

    lines = [
        "# TAE Investment Council Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Mode:** {MODE} — SYNTHESIS ONLY — NO_BROKER — NO_LIVE_PROMOTION",
        f"**Governance verdict:** **{payload.get('governance_verdict')}**",
        "",
        "## 1. Executive recommendation",
        "",
        payload.get("executive_recommendation") or "",
        "",
        "## 2. Today's top BUY candidates",
        "",
        *_rows(payload.get("top_buy_candidates") or [], ["confidence", "growth_score", "pde_buy", "gii_top_growth"]),
        "",
        "## 3. Today's top SELL candidates",
        "",
        *_rows(payload.get("top_sell_candidates") or [], ["confidence", "hard_risk_override", "hard_rule"]),
        "",
        "## 4. Today's top PROTECT candidates",
        "",
        *_rows(payload.get("top_protect_candidates") or [], ["confidence", "expected_profit_delta"]),
        "",
        "## 5. Today's HOLD candidates",
        "",
        *_rows(payload.get("top_hold_candidates") or [], ["confidence"]),
        "",
        "## 6. Hard risk alerts",
        "",
        *_rows(payload.get("hard_risk_alerts") or [], ["pnl_pct", "status", "required_action", "hard_rule"]),
        "",
        "## 7. Portfolio rebuild view",
        "",
        f"- GII portfolio strategy: **{rebuild.get('gii_portfolio_strategy') or 'N/A'}**",
        f"- Would BUY: `{[r.get('ticker') for r in rebuild.get('would_buy') or []]}`",
        f"- Would SELL: `{[r.get('ticker') for r in rebuild.get('would_sell') or []]}`",
        f"- Would ROTATE: `{[r.get('ticker') for r in rebuild.get('would_rotate') or []]}`",
        f"- Would REDUCE: `{[r.get('ticker') for r in rebuild.get('would_reduce') or []]}`",
        f"- Note: {rebuild.get('note')}",
        "",
        "## 8. Strongest rules",
        "",
        *_rows(payload.get("strongest_rules") or [], ["state", "net_pnl_impact", "win_rate"]),
        "",
        "## 9. Weakest / disabled rules",
        "",
        *_rows(payload.get("weakest_rules") or [], ["state", "net_pnl_impact", "reason"]),
        "",
        "## 10. DPE philosophy view",
        "",
        f"- Preferred philosophy: **{dpe.get('preferred_philosophy') or 'N/A'}**",
        f"- Adaptive confidence: **{dpe.get('adaptive_confidence')}**",
        f"- Competitive / Collaborative: **{dpe.get('competitive_pct')}% / {dpe.get('collaborative_pct')}%**",
        f"- Context: **{dpe.get('context_label') or 'N/A'}**",
        f"- Evaluator winner: **{dpe.get('evaluator_winner') or 'N/A'}**",
        f"- Policy state: **{dpe.get('policy_state') or 'N/A'}** ({dpe.get('suggested_policy') or 'N/A'})",
        f"- Recommendation: {dpe.get('adaptive_recommendation') or 'N/A'}",
        "",
        "## 11. Canonical vs PAPER result",
        "",
        f"- Canonical value: **${ _f((canonical.get('canonical') or {}).get('total_value')):,.2f}**",
        f"- PAPER value: **${ _f((canonical.get('paper') or {}).get('total_value')):,.2f}**",
        f"- Delta: **${ _f(delta.get('total_value')):,.2f}**",
        f"- PAPER reconciliation: **{(canonical.get('paper') or {}).get('reconciliation_status') or 'N/A'}**",
        f"- Explanation: {(canonical.get('explanation') or 'N/A')[:300]}",
        "",
        "## 12. Capital / cash status",
        "",
        f"- PAPER cash: **${ _f(capital.get('paper_cash')):,.2f}**",
        f"- PAPER total value: **${ _f(capital.get('paper_total_value')):,.2f}**",
        f"- PAPER realized / unrealized PnL: **${ _f(capital.get('paper_realized_pnl')):,.2f}** / **${ _f(capital.get('paper_unrealized_pnl')):,.2f}**",
        f"- Open PAPER positions: **{capital.get('paper_open_positions')}**",
        f"- PPG verdict: **{capital.get('ppg_portfolio_verdict') or 'N/A'}**",
        f"- APPE policy: **{capital.get('appe_policy_state') or 'N/A'}**",
        "",
        "## 13. What changed since last cycle",
        "",
    ]
    for change in payload.get("changes_since_last_cycle") or ["none"]:
        lines.append(f"- {change}")
    lines.extend(
        [
            "",
            "## 14. Final PAPER action plan",
            "",
            "Synthesized from existing PDE decisions — council does not override hard rules.",
            "",
        ]
    )
    for row in payload.get("final_paper_action_plan") or []:
        lines.append(
            f"- **{row.get('ticker')}** → `{row.get('action')}` "
            f"(conf={row.get('confidence')}, hard_override={row.get('hard_risk_override')}) — {(_s(row.get('evidence'))[:120])}"
        )
    if not payload.get("final_paper_action_plan"):
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Operator command",
            "",
            "```bash",
            "python3 tae.py investment-council",
            "```",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_investment_council(*, write_outputs: bool = True, include_morning_audit: bool = True) -> dict[str, Any]:
    payload = build_council_synthesis(include_morning_audit=include_morning_audit)
    if write_outputs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        COUNCIL_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        write_council_report(payload)
    return payload


def main() -> int:
    print("===== TAE INVESTMENT COUNCIL — SYNTHESIS ONLY =====")
    print(f"Mode: {MODE} | NO_BROKER | NO_REAL_MONEY | NO_LIVE_PROMOTION")
    print("")
    payload = run_investment_council()
    print("Executive recommendation:")
    print(payload.get("executive_recommendation"))
    print("")
    print("Governance verdict:", payload.get("governance_verdict"))
    print("Action plan items:", len(payload.get("final_paper_action_plan") or []))
    print("Wrote:", COUNCIL_JSON, REPORT_MD)
    if payload.get("governance_verdict") == "BLOCKED_WITH_REASONS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
