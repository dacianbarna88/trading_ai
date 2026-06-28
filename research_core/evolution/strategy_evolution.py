"""
Strategy evolution manager — Phase V Sprint A4 / IX.2C LEGACY_PLANNING_ONLY

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Converts eligible strategy recommendations into auditable evolution plans.
Legacy Phase V planning — superseded by Phase VIII Strategy Evolution Daily Runner.
Does not modify live bot, config, portfolio, or execution paths.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from research_core.autonomy.prioritization_report import DEFAULT_PRIORITIES_PATH
from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evolution.evolution_plan import (
    EvolutionPlanEntry,
    EvolutionPlanResult,
    EvolutionPlanStore,
    ImplementationStatus,
    ProposedChangeType,
)
from research_core.integration.strategy_recommendation import (
    DEFAULT_RECOMMENDATIONS_PATH,
    RecommendationType,
    StrategyRecommendation,
    StrategyRecommendationsStore,
)
from research_core.learning.learning_report import DEFAULT_REPORT_PATH as LEARNING_PATH
from research_core.learning.learning_report import LearningReportStore
from research_core.validation.validation_report import DEFAULT_REPORT_PATH as VALIDATION_PATH

logger = logging.getLogger(__name__)

PIPELINE_ROLE = "LEGACY_PLANNING_ONLY"
CANONICAL_PIPELINE = "research_core/strategy_evolution/daily_runner.py"


def _load_json(path) -> dict[str, Any] | None:
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", p, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _priority_action_for_candidate(candidate_id: str, priorities_payload: dict[str, Any] | None) -> str:
    if not priorities_payload:
        return ""
    items = priorities_payload.get("priorities", [])
    if not isinstance(items, list):
        return ""
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("source_id", "")) == candidate_id:
            return str(item.get("suggested_next_action", ""))
    return ""


class StrategyEvolutionManager:
    """
    Generates evolution plans from strategy recommendations.
    Sprint A4 — human approval required; no automatic implementation.
    """

    def __init__(
        self,
        recommendations_store: StrategyRecommendationsStore | None = None,
        plan_store: EvolutionPlanStore | None = None,
        learning_store: LearningReportStore | None = None,
    ) -> None:
        self._recommendations = recommendations_store or StrategyRecommendationsStore()
        self._plans = plan_store or EvolutionPlanStore()
        self._learning = learning_store or LearningReportStore()
        self._sources_loaded: dict[str, bool] = {}

    def generate_plans(self) -> EvolutionPlanResult:
        self._load_sources()

        all_recs = self._recommendations.list_all()
        blocked = [
            r for r in all_recs
            if r.recommendation_type == RecommendationType.BLOCK_FROM_TRADING
        ]
        eligible = [
            r for r in all_recs
            if r.recommendation_type != RecommendationType.BLOCK_FROM_TRADING
        ]

        validation_payload = _load_json(VALIDATION_PATH)
        priorities_payload = _load_json(DEFAULT_PRIORITIES_PATH)
        learning = self._learning.report

        new_plans: list[EvolutionPlanEntry] = []
        for rec in eligible:
            new_plans.append(
                self._build_plan(rec, validation_payload, priorities_payload, learning)
            )

        added, skipped = self._plans.merge_new(new_plans)
        all_plans = self._plans.list_all()

        highest = max(all_plans, key=lambda p: p.confidence) if all_plans else None
        validation_gated = [
            p for p in all_plans
            if p.proposed_change_type == ProposedChangeType.VALIDATION_GATE
        ]

        result = EvolutionPlanResult(
            recommendations_loaded=len(all_recs),
            recommendations_eligible=len(eligible),
            recommendations_blocked=len(blocked),
            plans_generated=added,
            plans_skipped_duplicate=skipped,
            plans=all_plans,
            highest_confidence_plan=highest,
            validation_gated_plans=validation_gated,
            sources_loaded=dict(self._sources_loaded),
        )
        self._plans.persist(result)
        return result

    def _load_sources(self) -> None:
        if not self._recommendations.loaded_at_startup:
            self._recommendations.load()
        self._sources_loaded[str(DEFAULT_RECOMMENDATIONS_PATH)] = len(
            self._recommendations.list_all()
        ) > 0

        self._sources_loaded[str(VALIDATION_PATH)] = VALIDATION_PATH.is_file()

        if not self._learning.loaded_at_startup:
            self._learning.load()
        self._sources_loaded[str(LEARNING_PATH)] = self._learning.report is not None

        self._sources_loaded[str(DEFAULT_PRIORITIES_PATH)] = DEFAULT_PRIORITIES_PATH.is_file()

    def _build_plan(
        self,
        rec: StrategyRecommendation,
        validation_payload: dict[str, Any] | None,
        priorities_payload: dict[str, Any] | None,
        learning: Any,
    ) -> EvolutionPlanEntry:
        change_type, target, change = self._map_change(rec)
        priority_action = _priority_action_for_candidate(rec.source_candidate_id, priorities_payload)

        rationale = (
            f"{rec.title}. Recommendation type: {rec.recommendation_type.value}. "
            f"{rec.evidence_summary[:200]}"
        )
        expected = self._expected_benefit(rec, learning)
        risk = rec.risk_notes[:500] if rec.risk_notes else "Standard research-only evolution risk."
        rollback = (
            "No live changes applied (implementation_status=NOT_IMPLEMENTED). "
            "If approved later: revert proposed target to prior research baseline; "
            "discard plan entry without touching live_bot.py, config/settings.py, "
            "portfolio.csv, or execution logic."
        )

        if priority_action:
            rationale += f" Priority follow-up: {priority_action[:120]}"

        return EvolutionPlanEntry(
            plan_id=f"evo_{rec.recommendation_id}",
            source_recommendation_id=rec.recommendation_id,
            proposed_change_type=change_type,
            proposed_target=target,
            proposed_change=change,
            rationale=rationale,
            expected_benefit=expected,
            risk_assessment=risk,
            rollback_plan=rollback,
            human_approval_required=True,
            implementation_status=ImplementationStatus.NOT_IMPLEMENTED,
            confidence=rec.confidence,
        )

    def _map_change(self, rec: StrategyRecommendation) -> tuple[ProposedChangeType, str, str]:
        candidate = rec.source_candidate_id
        hypothesis = rec.source_hypothesis_id

        if rec.recommendation_type == RecommendationType.PROMOTE_RESEARCH_WEIGHT:
            return (
                ProposedChangeType.RESEARCH_WEIGHT_ADJUSTMENT,
                f"research_scoring_layer / candidate={candidate}",
                (
                    f"Paper-only review: increase research weight for hypothesis {hypothesis} "
                    f"in scoring committee simulation — not live_bot thresholds."
                ),
            )

        if rec.recommendation_type == RecommendationType.KEEP_UNDER_OBSERVATION:
            return (
                ProposedChangeType.OBSERVATION_TRACKING,
                f"observation_registry / candidate={candidate}",
                (
                    f"Track candidate {candidate} in paper observation dashboard metrics "
                    "without altering live signals or execution."
                ),
            )

        if rec.recommendation_type == RecommendationType.REQUIRE_MORE_VALIDATION:
            return (
                ProposedChangeType.VALIDATION_GATE,
                f"validation_pipeline / candidate={candidate}",
                (
                    f"Complete cross-regime and regional validation for {candidate} "
                    f"(hypothesis {hypothesis}) before any research-weight or live strategy change."
                ),
            )

        return (
            ProposedChangeType.PAPER_ONLY_TRIAL,
            f"paper_trial / candidate={candidate}",
            f"Hold {candidate} in paper-only trial queue pending further review.",
        )

    def _expected_benefit(self, rec: StrategyRecommendation, learning: Any) -> str:
        parts = [
            f"Improved research-to-strategy alignment for {rec.source_candidate_id} "
            f"with confidence={rec.confidence:.1f}.",
        ]
        if learning is not None:
            parts.append(
                f"Learning context: best_organism={learning.best_organism}, "
                f"learning_confidence={learning.learning_confidence:.1f}."
            )
        if rec.recommendation_type == RecommendationType.PROMOTE_RESEARCH_WEIGHT:
            parts.append("Potential paper/research weight uplift after human approval.")
        elif rec.recommendation_type == RecommendationType.REQUIRE_MORE_VALIDATION:
            parts.append("Reduced strategy risk by closing validation gaps before any change.")
        elif rec.recommendation_type == RecommendationType.KEEP_UNDER_OBSERVATION:
            parts.append("Continued monitoring without premature production exposure.")
        return " ".join(parts)
