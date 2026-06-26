"""
Evidence accumulator — Phase VI Sprint B2

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Aggregates evidence across TAE artifacts into per-candidate dossiers.
Tracking only — does not modify strategy or trading logic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.evidence_history.evidence_record import (
    ConfidenceTrend,
    EvidenceDossier,
    EvidenceHistoryReport,
    EvidenceHistoryStore,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceRecordType,
    ImplementationReadiness,
)

logger = logging.getLogger(__name__)

KNOWLEDGE_CANDIDATES_PATH = Path("tae_knowledge_candidates.json")
EXPERIMENT_RESULTS_PATH = Path("tae_experiment_results.json")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
LEARNING_PATH = Path("tae_learning_report.json")
PATCH_REVIEW_PATH = Path("tae_patch_review.json")
EVOLUTION_PLAN_PATH = Path("tae_strategy_evolution_plan.json")
IMPLEMENTATION_PATCH_PATH = Path("tae_implementation_patch.json")
STRATEGY_RECOMMENDATIONS_PATH = Path("tae_strategy_recommendations.json")
NOT_AVAILABLE = "NOT_AVAILABLE"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _list_items(payload: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not payload:
        return []
    items = payload.get(key, [])
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict)]


def _region_missing(validation: dict[str, Any] | None) -> bool:
    if not validation:
        return True
    region = validation.get("regional_consistency", NOT_AVAILABLE)
    if region == NOT_AVAILABLE or str(region) == NOT_AVAILABLE:
        return True
    for region_name in ("Europe", "UK"):
        slice_data = validation.get("region_slices", {}).get(region_name, {})
        if isinstance(slice_data, dict) and slice_data.get("status") != "EVALUATED":
            return True
    return False


class EvidenceAccumulator:
    """Builds and updates evidence dossiers for knowledge candidates."""

    def __init__(self, store: EvidenceHistoryStore | None = None) -> None:
        self._store = store or EvidenceHistoryStore()
        self._sources_loaded: dict[str, bool] = {}

    def accumulate(self) -> EvidenceHistoryReport:
        self._load_source_flags()

        kc_payload = _load_json(KNOWLEDGE_CANDIDATES_PATH)
        candidates = _list_items(kc_payload, "candidates")
        experiments_payload = _load_json(EXPERIMENT_RESULTS_PATH)
        validation_payload = _load_json(CROSS_VALIDATION_PATH)
        learning_payload = _load_json(LEARNING_PATH)
        patch_review_payload = _load_json(PATCH_REVIEW_PATH)
        evolution_payload = _load_json(EVOLUTION_PLAN_PATH)
        impl_patch_payload = _load_json(IMPLEMENTATION_PATCH_PATH)
        recommendations_payload = _load_json(STRATEGY_RECOMMENDATIONS_PATH)

        experiments = _list_items(experiments_payload, "results")
        validations = _list_items(validation_payload, "candidate_results")
        reviews = _list_items(patch_review_payload, "reviews")
        plans = _list_items(evolution_payload, "plans")
        patches = _list_items(impl_patch_payload, "patches")
        recommendations = _list_items(recommendations_payload, "recommendations")

        created = 0
        updated = 0
        dossiers: list[EvidenceDossier] = []

        for candidate in candidates:
            cid = str(candidate.get("candidate_id", ""))
            if not cid:
                continue
            hyp_id = str(candidate.get("source_hypothesis_id", ""))
            title = str(candidate.get("title", ""))

            prior = self._store.get(cid)
            prior_score = prior.current_evidence_score if prior else None

            records = self._gather_records(
                candidate,
                hyp_id,
                experiments,
                validations,
                learning_payload,
                recommendations,
                plans,
                patches,
                reviews,
            )

            score = self._compute_score(records, candidate)
            trend = self._compute_trend(prior_score, score)
            blockers, next_required = self._blockers_and_next(
                cid, validations, reviews, records
            )
            readiness = self._readiness(cid, reviews, blockers)

            dossier = EvidenceDossier(
                candidate_id=cid,
                source_hypothesis_id=hyp_id,
                title=title,
                evidence_records=records,
                total_evidence_count=len(records),
                positive_evidence_count=sum(
                    1 for r in records if r.polarity == EvidencePolarity.POSITIVE
                ),
                negative_evidence_count=sum(
                    1 for r in records if r.polarity == EvidencePolarity.NEGATIVE
                ),
                missing_evidence_count=sum(
                    1 for r in records if r.polarity == EvidencePolarity.MISSING
                ),
                current_evidence_score=score,
                confidence_trend=trend,
                implementation_readiness=readiness,
                blockers=blockers,
                next_required_evidence=next_required,
                last_updated=datetime.now(timezone.utc),
            )

            is_new = self._store.upsert_dossier(dossier, merge_records=True)
            if is_new:
                created += 1
            else:
                updated += 1
            dossiers.append(self._store.get(cid) or dossier)

        all_dossiers = self._store.list_all()
        scores = [d.current_evidence_score for d in all_dossiers]
        top_score = max(scores) if scores else 0.0
        weak_score = min(scores) if scores else 0.0
        sandbox_ready = sum(
            1 for d in all_dossiers
            if d.implementation_readiness == ImplementationReadiness.READY_FOR_SANDBOX_REVIEW
        )
        blocked = sum(
            1 for d in all_dossiers
            if d.implementation_readiness == ImplementationReadiness.NOT_READY
        )

        blocker_counts: dict[str, int] = {}
        for d in all_dossiers:
            for b in d.blockers:
                blocker_counts[b] = blocker_counts.get(b, 0) + 1
        main_blockers = sorted(blocker_counts, key=blocker_counts.get, reverse=True)[:5]

        report = EvidenceHistoryReport(
            candidates_analyzed=len(candidates),
            dossiers_created=created,
            dossiers_updated=updated,
            dossiers=all_dossiers,
            top_evidence_score=top_score,
            weakest_evidence_score=weak_score,
            sandbox_ready_count=sandbox_ready,
            blocked_count=blocked,
            main_blockers=main_blockers,
            sources_loaded=dict(self._sources_loaded),
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _load_source_flags(self) -> None:
        for name, path in (
            ("tae_knowledge_candidates.json", KNOWLEDGE_CANDIDATES_PATH),
            ("tae_experiment_results.json", EXPERIMENT_RESULTS_PATH),
            ("tae_cross_validation_report.json", CROSS_VALIDATION_PATH),
            ("tae_learning_report.json", LEARNING_PATH),
            ("tae_patch_review.json", PATCH_REVIEW_PATH),
            ("tae_strategy_evolution_plan.json", EVOLUTION_PLAN_PATH),
            ("tae_implementation_patch.json", IMPLEMENTATION_PATCH_PATH),
            ("tae_strategy_recommendations.json", STRATEGY_RECOMMENDATIONS_PATH),
        ):
            self._sources_loaded[name] = path.is_file()

    def _gather_records(
        self,
        candidate: dict[str, Any],
        hyp_id: str,
        experiments: list[dict[str, Any]],
        validations: list[dict[str, Any]],
        learning: dict[str, Any] | None,
        recommendations: list[dict[str, Any]],
        plans: list[dict[str, Any]],
        patches: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
    ) -> list[EvidenceRecord]:
        cid = str(candidate.get("candidate_id", ""))
        records: list[EvidenceRecord] = []
        now = datetime.now(timezone.utc)

        for exp in experiments:
            if str(exp.get("hypothesis_id", "")) != hyp_id:
                continue
            acc = float(exp.get("accuracy", 0))
            polarity = EvidencePolarity.POSITIVE if acc >= 0.55 else EvidencePolarity.NEGATIVE
            records.append(EvidenceRecord(
                record_id=f"ev_{exp.get('experiment_id', '')}",
                record_type=EvidenceRecordType.EXPERIMENT_RESULT,
                source_ref=str(exp.get("experiment_id", "")),
                summary=(
                    f"Experiment n={exp.get('sample_size', 0)}, "
                    f"accuracy={acc:.2%}, avg_return={exp.get('avg_forward_return', 0)}"
                ),
                polarity=polarity,
                score_contribution=min(100.0, acc * 100),
                recorded_at=now,
            ))

        quality = float(candidate.get("quality_score", 0))
        if quality > 0:
            records.append(EvidenceRecord(
                record_id=f"qual_{cid}",
                record_type=EvidenceRecordType.QUALITY_RANKING,
                source_ref=cid,
                summary=f"Knowledge candidate quality_score={quality:.2f}, robustness={candidate.get('robustness_label', '?')}",
                polarity=EvidencePolarity.POSITIVE if quality >= 60 else EvidencePolarity.NEUTRAL,
                score_contribution=quality,
                recorded_at=now,
            ))

        validation = next(
            (v for v in validations if str(v.get("candidate_id", "")) == cid),
            None,
        )
        if validation:
            robust = float(validation.get("robustness_score", 0))
            region_na = _region_missing(validation)
            polarity = EvidencePolarity.POSITIVE if not region_na and robust >= 70 else (
                EvidencePolarity.MISSING if region_na else EvidencePolarity.NEUTRAL
            )
            records.append(EvidenceRecord(
                record_id=f"xval_{cid}",
                record_type=EvidenceRecordType.CROSS_VALIDATION,
                source_ref=cid,
                summary=(
                    f"robustness={robust}, regime={validation.get('regime_consistency', '?')}, "
                    f"region={validation.get('regional_consistency', '?')}"
                ),
                polarity=polarity,
                score_contribution=robust,
                recorded_at=now,
            ))
            if region_na:
                records.append(EvidenceRecord(
                    record_id=f"missing_region_{cid}",
                    record_type=EvidenceRecordType.MISSING_EVIDENCE,
                    source_ref="europe_uk_regional",
                    summary="Europe/UK regional validation missing — blocks implementation readiness",
                    polarity=EvidencePolarity.MISSING,
                    score_contribution=-25.0,
                    recorded_at=now,
                ))

        if learning:
            lc = float(learning.get("learning_confidence", 0))
            records.append(EvidenceRecord(
                record_id=f"learn_{cid}",
                record_type=EvidenceRecordType.LEARNING_SUPPORT,
                source_ref="tae_learning_report",
                summary=(
                    f"Learning confidence={lc:.1f}, best_organism={learning.get('best_organism', '?')}"
                ),
                polarity=EvidencePolarity.POSITIVE if lc >= 70 else EvidencePolarity.NEUTRAL,
                score_contribution=lc * 0.5,
                recorded_at=now,
            ))

        rec = next(
            (r for r in recommendations if str(r.get("source_candidate_id", "")) == cid),
            None,
        )
        if rec:
            rec_type = str(rec.get("recommendation_type", ""))
            polarity = (
                EvidencePolarity.MISSING
                if rec_type == "REQUIRE_MORE_VALIDATION"
                else EvidencePolarity.POSITIVE
            )
            records.append(EvidenceRecord(
                record_id=f"strat_{rec.get('recommendation_id', cid)}",
                record_type=EvidenceRecordType.STRATEGY_RECOMMENDATION,
                source_ref=str(rec.get("recommendation_id", "")),
                summary=f"Strategy recommendation: {rec_type}, confidence={rec.get('confidence', 0)}",
                polarity=polarity,
                score_contribution=float(rec.get("confidence", 0)) * 0.5,
                recorded_at=now,
            ))

        plan = next(
            (p for p in plans if f"candidate={cid}" in str(p.get("proposed_target", ""))),
            None,
        )
        if plan is None:
            plan = next(
                (p for p in plans if str(p.get("source_recommendation_id", "")).endswith(cid)),
                None,
            )
        if plan:
            gate = str(plan.get("proposed_change_type", ""))
            records.append(EvidenceRecord(
                record_id=f"evo_{plan.get('plan_id', '')}",
                record_type=EvidenceRecordType.EVOLUTION_PLAN,
                source_ref=str(plan.get("plan_id", "")),
                summary=f"Evolution plan: {gate}, confidence={plan.get('confidence', 0)}",
                polarity=(
                    EvidencePolarity.MISSING
                    if gate == "VALIDATION_GATE"
                    else EvidencePolarity.NEUTRAL
                ),
                score_contribution=float(plan.get("confidence", 0)) * 0.4,
                recorded_at=now,
            ))

        patch = next(
            (p for p in patches if str(p.get("source_candidate_id", "")) == cid),
            None,
        )
        if patch:
            gate = str(patch.get("patch_gate_status", ""))
            records.append(EvidenceRecord(
                record_id=f"patch_{patch.get('patch_id', '')}",
                record_type=EvidenceRecordType.IMPLEMENTATION_PATCH,
                source_ref=str(patch.get("patch_id", "")),
                summary=f"Implementation patch: {gate}, confidence={patch.get('confidence', 0)}",
                polarity=(
                    EvidencePolarity.MISSING
                    if "BLOCKED" in gate
                    else EvidencePolarity.NEUTRAL
                ),
                score_contribution=float(patch.get("confidence", 0)) * 0.3,
                recorded_at=now,
            ))

        review = next(
            (r for r in reviews if str(r.get("source_candidate_id", "")) == cid),
            None,
        )
        if review:
            verdict = str(review.get("verdict", ""))
            records.append(EvidenceRecord(
                record_id=f"rev_{review.get('review_id', '')}",
                record_type=EvidenceRecordType.PATCH_REVIEW,
                source_ref=str(review.get("review_id", "")),
                summary=f"Patch review: {verdict}, score={review.get('review_score', 0)}",
                polarity=(
                    EvidencePolarity.POSITIVE
                    if verdict == "APPROVED_FOR_SANDBOX"
                    else EvidencePolarity.MISSING
                    if verdict == "REQUIRE_MORE_EVIDENCE"
                    else EvidencePolarity.NEGATIVE
                ),
                score_contribution=float(review.get("review_score", 0)) * 0.6,
                recorded_at=now,
            ))

        return records

    def _compute_score(self, records: list[EvidenceRecord], candidate: dict[str, Any]) -> float:
        if not records:
            return 0.0
        base = sum(r.score_contribution for r in records) / max(len(records), 1)
        quality = float(candidate.get("quality_score", 0))
        score = base * 0.6 + quality * 0.4
        missing_penalty = sum(
            5.0 for r in records if r.polarity == EvidencePolarity.MISSING
        )
        return max(0.0, min(100.0, score - missing_penalty))

    def _compute_trend(self, prior_score: float | None, current: float) -> ConfidenceTrend:
        if prior_score is None:
            return ConfidenceTrend.UNKNOWN
        delta = current - prior_score
        if delta >= 2.0:
            return ConfidenceTrend.IMPROVING
        if delta <= -2.0:
            return ConfidenceTrend.WEAKENING
        return ConfidenceTrend.STABLE

    def _validation_for_candidate(
        self,
        cid: str,
        validations: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return next(
            (v for v in validations if str(v.get("candidate_id", "")) == cid),
            None,
        )

    def _blockers_and_next(
        self,
        cid: str,
        validations: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        records: list[EvidenceRecord],
    ) -> tuple[list[str], list[str]]:
        blockers: list[str] = []
        next_required: list[str] = []

        validation = self._validation_for_candidate(cid, validations)
        if _region_missing(validation):
            blockers.append("Europe/UK regional validation missing")

        review = next(
            (r for r in reviews if str(r.get("source_candidate_id", "")) == cid),
            None,
        )
        if review:
            verdict = str(review.get("verdict", ""))
            if verdict == "REQUIRE_MORE_EVIDENCE":
                blockers.append("Patch review requires more evidence")
            if verdict == "REJECTED":
                blockers.append("Patch review rejected")
            for step in review.get("next_required_steps", [])[:3]:
                if isinstance(step, str):
                    next_required.append(step)

        for record in records:
            if record.record_type == EvidenceRecordType.MISSING_EVIDENCE:
                if record.summary not in next_required:
                    next_required.append(record.summary)

        if not next_required and blockers:
            next_required.append("Complete Europe/UK regional validation before sandbox review")

        seen_b: set[str] = set()
        unique_blockers: list[str] = []
        for b in blockers:
            if b not in seen_b:
                seen_b.add(b)
                unique_blockers.append(b)

        return unique_blockers, next_required[:6]

    def _readiness(
        self,
        cid: str,
        reviews: list[dict[str, Any]],
        blockers: list[str],
    ) -> ImplementationReadiness:
        if any("Europe/UK" in b for b in blockers):
            return ImplementationReadiness.NOT_READY

        review = next(
            (r for r in reviews if str(r.get("source_candidate_id", "")) == cid),
            None,
        )
        if review and str(review.get("verdict", "")) == "APPROVED_FOR_SANDBOX":
            return ImplementationReadiness.READY_FOR_SANDBOX_REVIEW

        if review and str(review.get("verdict", "")) == "REQUIRE_MORE_EVIDENCE":
            return ImplementationReadiness.NOT_READY

        if review:
            return ImplementationReadiness.READY_FOR_HUMAN_REVIEW

        return ImplementationReadiness.NOT_READY
