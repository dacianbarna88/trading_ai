"""
Knowledge integration engine — Phase V Sprint A3

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Bridges research knowledge artifacts to human-review strategy recommendations.
Does not modify live bot, config, portfolio, or execution paths.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from research_core.autonomy.prioritization_report import DEFAULT_PRIORITIES_PATH
from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.discovery_registry import DEFAULT_REGISTRY_PATH, DiscoveryRegistry
from research_core.hypothesis.knowledge_candidate import (
    DEFAULT_CANDIDATES_PATH,
    KnowledgeCandidate,
    KnowledgeCandidateRegistry,
)
from research_core.integration.strategy_recommendation import (
    ImplementationStatus,
    IntegrationResult,
    RecommendationType,
    StrategyRecommendation,
    StrategyRecommendationsStore,
)
from research_core.learning.learning_report import DEFAULT_REPORT_PATH as LEARNING_PATH
from research_core.learning.learning_report import LearningReport, LearningReportStore
from research_core.validation.validation_report import DEFAULT_REPORT_PATH as VALIDATION_PATH
from research_core.validation.validation_report import NOT_AVAILABLE

logger = logging.getLogger(__name__)

MIN_SAMPLE_FOR_PROMOTE = 400
MIN_QUALITY_FOR_PROMOTE = 62.0
MIN_ROBUSTNESS_FOR_PROMOTE = 80.0


def _metric_unavailable(value: Any) -> bool:
    return value is None or value == NOT_AVAILABLE


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _validation_by_candidate(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    results = payload.get("candidate_results", [])
    if not isinstance(results, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in results:
        if isinstance(item, dict) and item.get("candidate_id"):
            out[str(item["candidate_id"])] = item
    return out


def _priority_by_candidate(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    priorities = payload.get("priorities", [])
    if not isinstance(priorities, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in priorities:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id", ""))
        source_type = str(item.get("source_type", ""))
        if source_type == "VALIDATION_GAP" and source_id.startswith("kn_"):
            out[source_id] = item
    return out


class KnowledgeIntegrator:
    """
    Generates strategy recommendations from research knowledge artifacts.
    Sprint A3 — human approval required; no automatic trading changes.
    """

    def __init__(
        self,
        candidates_registry: KnowledgeCandidateRegistry | None = None,
        learning_store: LearningReportStore | None = None,
        recommendations_store: StrategyRecommendationsStore | None = None,
        discoveries_registry: DiscoveryRegistry | None = None,
    ) -> None:
        self._candidates = candidates_registry or KnowledgeCandidateRegistry()
        self._learning = learning_store or LearningReportStore()
        self._store = recommendations_store or StrategyRecommendationsStore()
        self._discoveries = discoveries_registry or DiscoveryRegistry()
        self._sources_loaded: dict[str, bool] = {}

    def integrate(self) -> IntegrationResult:
        self._load_sources()

        candidates = self._candidates.list_all()
        validation_map = _validation_by_candidate(
            _load_json(VALIDATION_PATH)
        )
        priority_map = _priority_by_candidate(_load_json(DEFAULT_PRIORITIES_PATH))
        learning = self._learning.report

        new_recommendations: list[StrategyRecommendation] = []
        for candidate in candidates:
            validation = validation_map.get(candidate.candidate_id)
            priority = priority_map.get(candidate.candidate_id)
            rec = self._build_recommendation(candidate, validation, priority, learning)
            new_recommendations.append(rec)

        added, skipped = self._store.merge_new(new_recommendations)
        all_recs = self._store.list_all()

        highest = max(all_recs, key=lambda r: r.confidence) if all_recs else None
        blocked_or_validation = [
            r for r in all_recs
            if r.recommendation_type in (
                RecommendationType.BLOCK_FROM_TRADING,
                RecommendationType.REQUIRE_MORE_VALIDATION,
            )
        ]

        result = IntegrationResult(
            candidates_analyzed=len(candidates),
            recommendations_generated=added,
            recommendations_skipped_duplicate=skipped,
            recommendations=all_recs,
            highest_confidence=highest,
            blocked_or_validation=blocked_or_validation,
            sources_loaded=dict(self._sources_loaded),
        )
        self._store.persist(result)
        return result

    def _load_sources(self) -> None:
        if not self._candidates.loaded_at_startup:
            self._candidates.load()
        self._sources_loaded[str(DEFAULT_CANDIDATES_PATH)] = self._candidates.count() > 0

        if not self._learning.loaded_at_startup:
            self._learning.load()
        self._sources_loaded[str(LEARNING_PATH)] = self._learning.report is not None

        self._sources_loaded[str(VALIDATION_PATH)] = VALIDATION_PATH.is_file()
        self._sources_loaded[str(DEFAULT_PRIORITIES_PATH)] = DEFAULT_PRIORITIES_PATH.is_file()

        if not self._discoveries.loaded_at_startup:
            self._discoveries.load()
        self._sources_loaded[str(DEFAULT_REGISTRY_PATH)] = self._discoveries.count() > 0

    def _build_recommendation(
        self,
        candidate: KnowledgeCandidate,
        validation: dict[str, Any] | None,
        priority: dict[str, Any] | None,
        learning: LearningReport | None,
    ) -> StrategyRecommendation:
        rec_type = self._classify_type(candidate, validation, priority)
        confidence = self._compute_confidence(candidate, validation, priority, learning)
        validation_summary = self._validation_summary(candidate, validation)
        risk_notes = self._risk_notes(candidate, validation, priority, rec_type)

        return StrategyRecommendation(
            recommendation_id=f"rec_{candidate.candidate_id}",
            source_candidate_id=candidate.candidate_id,
            source_hypothesis_id=candidate.source_hypothesis_id,
            title=f"Strategy review: {candidate.title}",
            recommendation_type=rec_type,
            confidence=confidence,
            evidence_summary=candidate.evidence_summary,
            validation_summary=validation_summary,
            risk_notes=risk_notes,
            human_approval_required=True,
            implementation_status=ImplementationStatus.NOT_IMPLEMENTED,
        )

    def _classify_type(
        self,
        candidate: KnowledgeCandidate,
        validation: dict[str, Any] | None,
        priority: dict[str, Any] | None,
    ) -> RecommendationType:
        if candidate.sample_size < 100 or candidate.quality_score < 45:
            return RecommendationType.BLOCK_FROM_TRADING

        regime_na = validation is None or _metric_unavailable(validation.get("regime_consistency"))
        regional_na = validation is None or _metric_unavailable(validation.get("regional_consistency"))
        robustness = float(validation.get("robustness_score", 0)) if validation else 0.0

        if priority is not None:
            rank = int(priority.get("rank", 99))
            if rank <= 2 and (regional_na or regime_na):
                return RecommendationType.REQUIRE_MORE_VALIDATION

        if regime_na and regional_na:
            return RecommendationType.REQUIRE_MORE_VALIDATION

        if regional_na or regime_na:
            if robustness >= MIN_ROBUSTNESS_FOR_PROMOTE and candidate.quality_score >= MIN_QUALITY_FOR_PROMOTE:
                return RecommendationType.KEEP_UNDER_OBSERVATION
            return RecommendationType.REQUIRE_MORE_VALIDATION

        if (
            robustness >= MIN_ROBUSTNESS_FOR_PROMOTE
            and candidate.quality_score >= MIN_QUALITY_FOR_PROMOTE
            and candidate.sample_size >= MIN_SAMPLE_FOR_PROMOTE
        ):
            return RecommendationType.PROMOTE_RESEARCH_WEIGHT

        if candidate.quality_score >= 55:
            return RecommendationType.KEEP_UNDER_OBSERVATION

        return RecommendationType.REQUIRE_MORE_VALIDATION

    def _compute_confidence(
        self,
        candidate: KnowledgeCandidate,
        validation: dict[str, Any] | None,
        priority: dict[str, Any] | None,
        learning: LearningReport | None,
    ) -> float:
        score = (candidate.quality_score / 100.0) * 40.0
        if validation:
            score += (float(validation.get("robustness_score", 0)) / 100.0) * 35.0
        score += min(candidate.sample_size / 3000.0, 1.0) * 15.0
        if learning:
            score += (learning.learning_confidence / 100.0) * 10.0

        if validation:
            if _metric_unavailable(validation.get("regime_consistency")):
                score -= 8.0
            if _metric_unavailable(validation.get("regional_consistency")):
                score -= 8.0
        if priority is not None:
            score -= 5.0

        return max(0.0, min(100.0, score))

    def _validation_summary(
        self,
        candidate: KnowledgeCandidate,
        validation: dict[str, Any] | None,
    ) -> str:
        if validation is None:
            return (
                f"No cross-validation record for {candidate.candidate_id}. "
                "Run Phase IV D6 cross-validation before strategy integration."
            )

        regime = validation.get("regime_consistency", NOT_AVAILABLE)
        horizon = validation.get("horizon_consistency", NOT_AVAILABLE)
        regional = validation.get("regional_consistency", NOT_AVAILABLE)
        robustness = validation.get("robustness_score", NOT_AVAILABLE)
        notes = str(validation.get("validation_notes", ""))

        parts = [
            f"robustness={robustness}",
            f"regime_consistency={regime}",
            f"horizon_consistency={horizon}",
            f"regional_consistency={regional}",
        ]
        if notes:
            parts.append(f"notes={notes[:160]}")
        return "Cross-validation: " + "; ".join(parts)

    def _risk_notes(
        self,
        candidate: KnowledgeCandidate,
        validation: dict[str, Any] | None,
        priority: dict[str, Any] | None,
        rec_type: RecommendationType,
    ) -> str:
        notes: list[str] = [
            "Human approval required before any live strategy, threshold, or execution change.",
            "Recommendation is research-to-review only — not a trading signal.",
        ]

        if validation:
            if _metric_unavailable(validation.get("regional_consistency")):
                notes.append(
                    "Regional validation NOT_AVAILABLE — Europe/UK hypothesis-linked CSVs "
                    "required before trading weight changes."
                )
            if _metric_unavailable(validation.get("regime_consistency")):
                notes.append(
                    "Regime consistency NOT_AVAILABLE — insufficient multi-regime samples."
                )

        if priority is not None:
            action = str(priority.get("suggested_next_action", ""))
            if action:
                notes.append(f"Research priority follow-up: {action[:140]}")

        if candidate.candidate_id.startswith("kn_d5_"):
            notes.append(
                "Discovery-derived candidate — validate discovery pipeline evidence "
                "before production promotion."
            )

        if rec_type == RecommendationType.BLOCK_FROM_TRADING:
            notes.append(
                "BLOCK_FROM_TRADING: do not auto-apply to live bot or portfolio logic."
            )
        elif rec_type == RecommendationType.REQUIRE_MORE_VALIDATION:
            notes.append(
                "REQUIRE_MORE_VALIDATION: close validation gaps before strategy weighting."
            )
        elif rec_type == RecommendationType.PROMOTE_RESEARCH_WEIGHT:
            notes.append(
                "PROMOTE_RESEARCH_WEIGHT: candidate for paper/research weight review only "
                "after human sign-off."
            )

        return " ".join(notes)
