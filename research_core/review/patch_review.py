"""
Patch review engine — Phase VI Sprint B1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Reviews implementation patch proposals before any sandbox stage.
Documentation only — does not apply patches or alter live code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.evolution.implementation_patch import (
    DEFAULT_PATCH_JSON_PATH,
    PatchGateStatus,
    PatchProposal,
)
from research_core.review.patch_review_report import (
    CategoryScores,
    ImplementationStatus,
    OperationalImpact,
    PatchReviewEntry,
    PatchReviewReport,
    PatchReviewStore,
    ReviewVerdict,
)

logger = logging.getLogger(__name__)

IMPLEMENTATION_PATCH_PATH = DEFAULT_PATCH_JSON_PATH
EVOLUTION_PLAN_PATH = Path("tae_strategy_evolution_plan.json")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
LEARNING_PATH = Path("tae_learning_report.json")
DAILY_INTELLIGENCE_PATH = Path("tae_daily_intelligence_report.json")
NOT_AVAILABLE = "NOT_AVAILABLE"
REGIMES = ("BULL", "BEAR", "NEUTRAL")
REGIONS = ("US", "Europe", "UK")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _load_patches(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    items = payload.get("patches", [])
    return [i for i in items if isinstance(i, dict)]


def _validation_for_candidate(
    candidate_id: str,
    validation_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not validation_payload or not candidate_id:
        return None
    for item in validation_payload.get("candidate_results", []):
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
            return item
    return None


def _candidate_from_knowledge(candidate_id: str, kc_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not kc_payload:
        return None
    for item in kc_payload.get("candidates", []):
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
            return item
    return None


def _slice_evaluated(slices: dict[str, Any] | None, label: str) -> bool:
    if not slices or not isinstance(slices, dict):
        return False
    s = slices.get(label)
    if not isinstance(s, dict):
        return False
    return s.get("status") == "EVALUATED" and int(s.get("sample_size", 0)) > 0


class PatchReviewCenter:
    """Formal review layer for implementation patch proposals."""

    def __init__(self, store: PatchReviewStore | None = None) -> None:
        self._store = store or PatchReviewStore()
        self._sources_loaded: dict[str, bool] = {}

    def review_all(self) -> PatchReviewReport:
        self._load_sources()

        patch_payload = _load_json(IMPLEMENTATION_PATCH_PATH)
        patches = _load_patches(patch_payload)
        validation_payload = _load_json(CROSS_VALIDATION_PATH)
        learning_payload = _load_json(LEARNING_PATH)
        daily_payload = _load_json(DAILY_INTELLIGENCE_PATH)
        kc_payload = _load_json(Path("tae_knowledge_candidates.json"))

        new_reviews: list[PatchReviewEntry] = []
        for patch_dict in patches:
            new_reviews.append(
                self._review_patch(
                    patch_dict,
                    validation_payload,
                    learning_payload,
                    daily_payload,
                    kc_payload,
                )
            )

        added, skipped = self._store.merge_new(new_reviews)
        all_reviews = self._store.list_all()

        approved = sum(1 for r in all_reviews if r.verdict == ReviewVerdict.APPROVED_FOR_SANDBOX)
        more_evidence = sum(1 for r in all_reviews if r.verdict == ReviewVerdict.REQUIRE_MORE_EVIDENCE)
        rejected = sum(1 for r in all_reviews if r.verdict == ReviewVerdict.REJECTED)
        highest = max(all_reviews, key=lambda r: r.review_score) if all_reviews else None

        blocker_counts: dict[str, int] = {}
        for r in all_reviews:
            for b in r.blockers:
                blocker_counts[b] = blocker_counts.get(b, 0) + 1
        biggest_blocker = (
            max(blocker_counts, key=blocker_counts.get) if blocker_counts else "none identified"
        )

        next_work = self._next_recommended_work(daily_payload, all_reviews)

        report = PatchReviewReport(
            patches_reviewed=len(patches),
            approved_for_sandbox=approved,
            require_more_evidence=more_evidence,
            rejected=rejected,
            reviews_generated=added,
            reviews_skipped_duplicate=skipped,
            reviews=all_reviews,
            highest_quality_review=highest,
            biggest_blocker=biggest_blocker,
            next_recommended_work=next_work,
            sources_loaded=dict(self._sources_loaded),
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _load_sources(self) -> None:
        for name, path in (
            ("tae_implementation_patch.json", IMPLEMENTATION_PATCH_PATH),
            ("tae_strategy_evolution_plan.json", EVOLUTION_PLAN_PATH),
            ("tae_cross_validation_report.json", CROSS_VALIDATION_PATH),
            ("tae_learning_report.json", LEARNING_PATH),
            ("tae_daily_intelligence_report.json", DAILY_INTELLIGENCE_PATH),
        ):
            self._sources_loaded[name] = path.is_file()

    def _next_recommended_work(
        self,
        daily_payload: dict[str, Any] | None,
        reviews: list[PatchReviewEntry],
    ) -> str:
        if daily_payload:
            priorities = daily_payload.get("research_priorities", [])
            if isinstance(priorities, list) and priorities:
                top = priorities[0]
                if isinstance(top, dict):
                    action = str(top.get("suggested_next_action", ""))
                    if action:
                        return action[:200]
        for review in reviews:
            if review.next_required_steps:
                return review.next_required_steps[0]
        return "Complete Europe/UK regional validation and cross-regime matrix before sandbox."

    def _compute_scores(
        self,
        patch: dict[str, Any],
        validation: dict[str, Any] | None,
        candidate: dict[str, Any] | None,
        learning: dict[str, Any] | None,
    ) -> tuple[CategoryScores, list[str], list[str]]:
        missing: list[str] = []
        blockers: list[str] = []

        patch_confidence = float(patch.get("confidence", 0))
        gate = str(patch.get("patch_gate_status", ""))

        robustness = 0.0
        sample_size = int(candidate.get("sample_size", 0)) if candidate else 0
        accuracy = float(candidate.get("accuracy", 0)) if candidate else 0.0

        if validation:
            robustness = float(validation.get("robustness_score", 0))
        else:
            missing.append("Cross-validation record missing for candidate")

        research_evidence = min(
            100.0,
            patch_confidence * 0.4 + robustness * 0.4 + min(sample_size / 3000.0, 1.0) * 20.0,
        )

        learning_conf = float(learning.get("learning_confidence", 0)) if learning else 0.0
        statistical_confidence = min(
            100.0,
            accuracy * 100 * 0.5 + min(sample_size / 2000.0, 1.0) * 30.0 + learning_conf * 0.2,
        )

        validation_completeness = 100.0
        if validation:
            for key in ("regime_consistency", "horizon_consistency", "regional_consistency"):
                val = validation.get(key, NOT_AVAILABLE)
                if val == NOT_AVAILABLE or str(val) == NOT_AVAILABLE:
                    validation_completeness -= 25.0
                    if "regional" in key:
                        missing.append("Regional consistency NOT_AVAILABLE")
                    elif "regime" in key:
                        missing.append("Regime consistency NOT_AVAILABLE")
                    else:
                        missing.append("Horizon consistency NOT_AVAILABLE")
        else:
            validation_completeness = 20.0

        regime_evaluated = 0
        if validation:
            regime_slices = validation.get("regime_slices", {})
            if isinstance(regime_slices, dict):
                for regime in REGIMES:
                    if _slice_evaluated(regime_slices, regime):
                        regime_evaluated += 1
                    else:
                        missing.append(f"Cross-regime slice {regime} not evaluated")
        cross_regime = (regime_evaluated / len(REGIMES)) * 100.0

        region_evaluated = 0
        if validation:
            region_slices = validation.get("region_slices", {})
            if isinstance(region_slices, dict):
                for region in REGIONS:
                    if _slice_evaluated(region_slices, region):
                        region_evaluated += 1
                    elif region in ("Europe", "UK"):
                        missing.append(f"{region} validation missing")
        cross_region = (region_evaluated / len(REGIONS)) * 100.0

        if cross_region < 50:
            blockers.append("Europe/UK regional validation incomplete")

        if cross_regime < 70:
            blockers.append("Cross-regime coverage insufficient (BEAR/NEUTRAL gaps)")

        if gate == PatchGateStatus.BLOCKED_BY_VALIDATION_GAP.value:
            blockers.append("Patch blocked by validation gate")

        learning_support = min(100.0, learning_conf * 0.7 + (research_evidence * 0.3))

        implementation_risk = 30.0
        if gate == PatchGateStatus.BLOCKED_BY_VALIDATION_GAP.value:
            implementation_risk += 35.0
        if cross_region < 40:
            implementation_risk += 20.0
        if cross_regime < 50:
            implementation_risk += 15.0
        implementation_risk = min(100.0, implementation_risk)

        rollback_text = str(patch.get("rollback_procedure", ""))
        rollback_readiness = 85.0 if "NOT_IMPLEMENTED" in rollback_text and "revert" in rollback_text.lower() else 60.0

        operational_impact = OperationalImpact.LOW
        if gate == PatchGateStatus.BLOCKED_BY_VALIDATION_GAP.value:
            operational_impact = OperationalImpact.MEDIUM

        scores = CategoryScores(
            research_evidence_score=research_evidence,
            statistical_confidence_score=statistical_confidence,
            validation_completeness_score=max(0.0, validation_completeness),
            cross_regime_coverage_score=cross_regime,
            cross_region_coverage_score=cross_region,
            learning_support_score=learning_support,
            implementation_risk_score=implementation_risk,
            rollback_readiness_score=rollback_readiness,
            operational_impact=operational_impact,
        )

        # Deduplicate missing
        seen: set[str] = set()
        unique_missing: list[str] = []
        for m in missing:
            if m not in seen:
                seen.add(m)
                unique_missing.append(m)

        return scores, unique_missing, blockers

    def _determine_verdict(
        self,
        scores: CategoryScores,
        patch: dict[str, Any],
        blockers: list[str],
    ) -> ReviewVerdict:
        gate = str(patch.get("patch_gate_status", ""))

        if gate == PatchGateStatus.BLOCKED_BY_VALIDATION_GAP.value:
            return ReviewVerdict.REQUIRE_MORE_EVIDENCE

        review_score = self._composite_review_score(scores)

        if review_score < 35 or scores.research_evidence_score < 30:
            return ReviewVerdict.REJECTED

        if (
            review_score >= 72
            and scores.validation_completeness_score >= 70
            and scores.cross_region_coverage_score >= 50
            and scores.cross_regime_coverage_score >= 60
            and scores.implementation_risk_score <= 45
            and not blockers
        ):
            return ReviewVerdict.APPROVED_FOR_SANDBOX

        return ReviewVerdict.REQUIRE_MORE_EVIDENCE

    def _composite_review_score(self, scores: CategoryScores) -> float:
        positive = (
            scores.research_evidence_score * 0.2
            + scores.statistical_confidence_score * 0.15
            + scores.validation_completeness_score * 0.2
            + scores.cross_regime_coverage_score * 0.15
            + scores.cross_region_coverage_score * 0.15
            + scores.learning_support_score * 0.1
            + scores.rollback_readiness_score * 0.05
        )
        risk_penalty = scores.implementation_risk_score * 0.15
        return max(0.0, min(100.0, positive - risk_penalty))

    def _review_patch(
        self,
        patch: dict[str, Any],
        validation_payload: dict[str, Any] | None,
        learning_payload: dict[str, Any] | None,
        daily_payload: dict[str, Any] | None,
        kc_payload: dict[str, Any] | None,
    ) -> PatchReviewEntry:
        patch_id = str(patch.get("patch_id", ""))
        candidate_id = str(patch.get("source_candidate_id", ""))
        validation = _validation_for_candidate(candidate_id, validation_payload)
        candidate = _candidate_from_knowledge(candidate_id, kc_payload)

        scores, missing, blockers = self._compute_scores(
            patch, validation, candidate, learning_payload
        )
        verdict = self._determine_verdict(scores, patch, blockers)
        review_score = self._composite_review_score(scores)

        next_steps = self._build_next_steps(verdict, missing, blockers, candidate_id)

        rationale = (
            f"Patch {patch_id} reviewed for sandbox readiness only (not implementation). "
            f"Gate status: {patch.get('patch_gate_status', '?')}. "
            f"Validation completeness {scores.validation_completeness_score:.0f}/100, "
            f"cross-region {scores.cross_region_coverage_score:.0f}/100, "
            f"cross-regime {scores.cross_regime_coverage_score:.0f}/100. "
            f"Verdict: {verdict.value} — no APPROVED_FOR_IMPLEMENTATION in Sprint B1."
        )

        sandbox_required = verdict == ReviewVerdict.APPROVED_FOR_SANDBOX

        return PatchReviewEntry(
            review_id=f"review_{patch_id}",
            patch_id=patch_id,
            source_candidate_id=candidate_id,
            verdict=verdict,
            review_score=review_score,
            scores=scores,
            missing_evidence=missing,
            blockers=blockers,
            rationale=rationale,
            next_required_steps=next_steps,
            human_approval_required=True,
            sandbox_required=sandbox_required,
            implementation_status=ImplementationStatus.NOT_IMPLEMENTED,
        )

    def _build_next_steps(
        self,
        verdict: ReviewVerdict,
        missing: list[str],
        blockers: list[str],
        candidate_id: str,
    ) -> list[str]:
        steps: list[str] = []
        if verdict == ReviewVerdict.APPROVED_FOR_SANDBOX:
            steps.append("Human approval required before sandbox experiment.")
            steps.append(f"Run paper-only sandbox for candidate {candidate_id}.")
        elif verdict == ReviewVerdict.REJECTED:
            steps.append("Do not advance to sandbox — archive or re-derive research evidence.")
        else:
            steps.append("Close validation gaps before sandbox review.")
            if any("Europe" in m for m in missing):
                steps.append("Add Europe hypothesis-linked regional signal CSVs.")
            if any("UK" in m for m in missing):
                steps.append("Add UK hypothesis-linked regional signal CSVs.")
            if any("regime" in m.lower() or "BEAR" in m or "NEUTRAL" in m for m in missing):
                steps.append("Run cross-regime experiment matrix (BULL/BEAR/NEUTRAL).")
            for b in blockers[:3]:
                steps.append(f"Resolve blocker: {b}")
        return steps[:6]
