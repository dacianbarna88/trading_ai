"""
Evolution proposal card — Phase V A4 human review communication

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Formats the highest-confidence evolution plan as a concise owner notification.
Does not modify live code — WAITING HUMAN APPROVAL only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.evolution.evolution_plan import (
    EvolutionPlanEntry,
    EvolutionPlanStore,
    ProposedChangeType,
)
from research_core.integration.strategy_recommendation import (
    DEFAULT_RECOMMENDATIONS_PATH,
    StrategyRecommendation,
    StrategyRecommendationsStore,
)

logger = logging.getLogger(__name__)

DEFAULT_PROPOSAL_PATH = Path("tae_evolution_proposal.txt")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
KNOWLEDGE_CANDIDATES_PATH = Path("tae_knowledge_candidates.json")
LEARNING_PATH = Path("tae_learning_report.json")
NOT_AVAILABLE = "NOT_AVAILABLE"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _candidate_for_plan(
    plan: EvolutionPlanEntry,
    candidates_payload: dict[str, Any] | None,
    recommendations_store: StrategyRecommendationsStore | None = None,
) -> dict[str, Any] | None:
    store = recommendations_store or StrategyRecommendationsStore()
    rec = store.get(plan.source_recommendation_id)
    if rec is None:
        return None
    if not candidates_payload:
        return None
    for item in candidates_payload.get("candidates", []):
        if isinstance(item, dict) and item.get("candidate_id") == rec.source_candidate_id:
            return item
    return None


def _validation_for_candidate(candidate_id: str) -> dict[str, Any] | None:
    payload = _load_json(CROSS_VALIDATION_PATH)
    if not payload:
        return None
    for item in payload.get("candidate_results", []):
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
            return item
    return None


def _slice_ok(slices: dict[str, Any] | None, label: str) -> bool:
    if not slices or not isinstance(slices, dict):
        return False
    slice_data = slices.get(label)
    if not isinstance(slice_data, dict):
        return False
    return slice_data.get("status") == "EVALUATED" and int(slice_data.get("sample_size", 0)) > 0


def _compute_confidence(
    plan: EvolutionPlanEntry,
    validation: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> float:
    score = plan.confidence * 0.25
    if validation:
        robust = float(validation.get("robustness_score", 0))
        score += robust * 0.35
        regime = validation.get("regime_consistency")
        if isinstance(regime, (int, float)):
            score += float(regime) * 0.15
        horizon = validation.get("horizon_consistency")
        if isinstance(horizon, (int, float)):
            score += float(horizon) * 0.15
        adj = validation.get("confidence_adjustment")
        if isinstance(adj, (int, float)):
            score += float(adj) * 0.05
    if candidate:
        sample = int(candidate.get("sample_size", 0))
        score += min(sample / 3000.0, 1.0) * 10.0
    return round(min(100.0, max(0.0, score)), 1)


def _estimated_benefit(validation: dict[str, Any] | None, learning: dict[str, Any] | None) -> str:
    if validation:
        adj = validation.get("confidence_adjustment")
        if isinstance(adj, (int, float)):
            return f"+{round(float(adj) * 0.8, 1)}%"
    if learning and validation:
        acc = validation.get("regime_slices", {}).get("BULL", {})
        if isinstance(acc, dict) and acc.get("accuracy") is not None:
            learning_acc = learning.get("average_accuracy")
            if isinstance(learning_acc, (int, float)):
                delta = (float(acc["accuracy"]) - float(learning_acc)) * 100
                return f"+{round(delta, 1)}%"
    return "under research review"


def _files_affected(plan: EvolutionPlanEntry) -> list[str]:
    if plan.proposed_change_type == ProposedChangeType.RESEARCH_WEIGHT_ADJUSTMENT:
        return [
            "core/entry_filter.py (human approval required before any change)",
            "research_weights.py (proposed research-only module — not live)",
        ]
    if plan.proposed_change_type == ProposedChangeType.VALIDATION_GATE:
        return [
            "core/entry_filter.py",
            "research_weights.py (proposed research module — not created yet)",
        ]
    return ["observation_registry — paper metrics only, no live execution files"]


def _build_evidence_lines(
    validation: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    learning: dict[str, Any] | None,
) -> list[str]:
    lines: list[str] = []
    if not validation:
        lines.append("✘ validare cross-regime indisponibilă")
        return lines

    sample = int(candidate.get("sample_size", 0)) if candidate else 0
    data_span = validation.get("validation_notes", "")
    years_note = "~9.7 years" if "9.7" in str(data_span) else "multi-year cohort"

    if _slice_ok(validation.get("horizon_slices"), "5Y"):
        lines.append(f"✔ 5 ani backtest ({years_note})")
    else:
        lines.append("✘ 5 ani backtest incomplet")

    if sample >= 500:
        lines.append(f"✔ {sample:,} exemple".replace(",", " "))
    else:
        lines.append(f"⚠ {sample} exemple (sample mic)")

    learning_acc = learning.get("average_accuracy") if learning else None
    cand_acc = candidate.get("accuracy") if candidate else None
    if learning_acc is not None and cand_acc is not None:
        if float(cand_acc) >= float(learning_acc):
            lines.append("✔ mai bun decât media learning actuală")
        else:
            lines.append("⚠ sub media learning — revizuire necesară")
    else:
        lines.append("⚠ comparație cu strategia actuală indisponibilă")

    if _slice_ok(validation.get("regime_slices"), "BULL"):
        lines.append("✔ validat BULL")
    else:
        lines.append("✘ validare BULL incompletă")

    if _slice_ok(validation.get("horizon_slices"), "10Y"):
        lines.append("✔ validat 10Y")
    else:
        lines.append("✘ validare 10Y incompletă")

    return lines


def _build_risk_lines(validation: dict[str, Any] | None) -> list[str]:
    risks: list[str] = []
    if not validation:
        return ["⚠ lipsă raport de validare"]

    region = validation.get("regional_consistency", NOT_AVAILABLE)
    if region == NOT_AVAILABLE or str(region) == NOT_AVAILABLE:
        risks.append("⚠ lipsă validare Europe")
        risks.append("⚠ lipsă validare UK")

    regime = validation.get("regime_consistency", NOT_AVAILABLE)
    if regime == NOT_AVAILABLE or str(regime) == NOT_AVAILABLE:
        risks.append("⚠ validare cross-regime incompletă")

    europe_slice = validation.get("region_slices", {}).get("Europe", {})
    if isinstance(europe_slice, dict) and europe_slice.get("status") != "EVALUATED":
        if "⚠ lipsă validare Europe" not in risks:
            risks.append("⚠ lipsă validare Europe")

    if not risks:
        risks.append("⚠ revizuire umană obligatorie înainte de implementare")
    return risks


def format_evolution_proposal_card(
    plan: EvolutionPlanEntry,
    recommendation: StrategyRecommendation | None = None,
) -> str:
    candidates_payload = _load_json(KNOWLEDGE_CANDIDATES_PATH)
    learning_payload = _load_json(LEARNING_PATH)
    candidate = _candidate_for_plan(plan, candidates_payload)
    candidate_id = candidate.get("candidate_id", "") if candidate else ""
    validation = _validation_for_candidate(candidate_id) if candidate_id else None

    confidence = _compute_confidence(plan, validation, candidate)
    evidence = _build_evidence_lines(validation, candidate, learning_payload)
    risks = _build_risk_lines(validation)
    benefit = _estimated_benefit(validation, learning_payload)
    files = _files_affected(plan)
    title = candidate.get("title", plan.rationale[:60]) if candidate else plan.plan_id

    border = "====================================="
    lines = [
        border,
        "",
        "NEW EVOLUTION PROPOSAL",
        "",
        f"Plan: {plan.plan_id}",
        f"Candidat: {candidate_id or 'NOT_AVAILABLE'}",
        f"Titlu: {title[:80]}",
        "",
        f"Confidence: {confidence}%",
        "",
        "Evidence:",
        "",
    ]
    for item in evidence:
        lines.append(item)
    lines.extend(["", "Risk:", "",])
    for item in risks:
        lines.append(item)
    lines.extend([
        "",
        "Estimated benefit:",
        "",
        benefit,
        "",
        "Files affected:",
        "",
    ])
    for f in files:
        lines.append(f)
    lines.extend([
        "",
        "Rollback:",
        "",
        f"git revert <commit-for-{plan.plan_id}> — sau abandonați planul; "
        "implementation_status rămâne NOT_IMPLEMENTED până la aprobare.",
        "",
        "Status:",
        "",
        "WAITING HUMAN APPROVAL",
        "",
        "NOT IMPLEMENTED — HUMAN APPROVAL REQUIRED",
        "No live trading files were modified",
        "",
        border,
        "",
    ])
    return "\n".join(lines)


def generate_evolution_proposal(
    plan_store: EvolutionPlanStore | None = None,
    output_path: Path | None = None,
) -> str:
    """Write proposal card for highest-confidence plan, or empty-state notice."""
    store = plan_store or EvolutionPlanStore()
    out = output_path or DEFAULT_PROPOSAL_PATH

    plans = store.list_all()
    if not plans:
        content = (
            "=====================================\n\n"
            "No strategy evolution is ready for implementation review.\n"
            "Nu există planuri de evoluție documentate.\n\n"
            "WAITING HUMAN APPROVAL\n"
            "NOT IMPLEMENTED — HUMAN APPROVAL REQUIRED\n"
            "No live trading files were modified\n\n"
            "=====================================\n"
        )
        out.write_text(content, encoding="utf-8")
        return content

    best = max(plans, key=lambda p: p.confidence)
    content = format_evolution_proposal_card(best)
    out.write_text(content + "\n", encoding="utf-8")
    return content
