"""
Evidence gap analyzer — Phase VI Sprint B3 / IX.2B view layer

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Transforms evidence history into an actionable research roadmap — planning only.
Phase IX.2B: reads canonical Evidence Registry; does not compete as source of truth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evidence_engine.evidence_registry import (
    CANONICAL_REPORT_PATH,
    load_canonical_evidence_report,
)
from research_core.evidence_gap.evidence_gap_report import (
    CandidateGapAnalysis,
    EvidenceGapReport,
    EvidenceGapStore,
    GapCategory,
    MissingEvidenceItem,
    ResearchAction,
)
from research_core.evidence_history.evidence_record import (
    EvidenceHistoryStore,
    ImplementationReadiness,
)

logger = logging.getLogger(__name__)

EVIDENCE_HISTORY_PATH = Path("tae_evidence_history.json")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
RESEARCH_PRIORITIES_PATH = Path("tae_research_priorities.json")
PATCH_REVIEW_PATH = Path("tae_patch_review.json")
EVOLUTION_PLAN_PATH = Path("tae_strategy_evolution_plan.json")
IMPLEMENTATION_PATCH_PATH = Path("tae_implementation_patch.json")
KNOWLEDGE_CANDIDATES_PATH = Path("tae_knowledge_candidates.json")

NOT_AVAILABLE = "NOT_AVAILABLE"
REGIMES = ("BULL", "BEAR", "NEUTRAL")
REGIONS = ("US", "Europe", "UK")
HORIZONS = ("2Y", "5Y", "10Y", "20Y")

REGIONAL_GAP_GAIN = 0.9
REGIME_GAP_GAIN = 1.2
HORIZON_GAP_GAIN = 0.5
PATCH_REVIEW_GAP_GAIN = 2.0
LEARNING_GAP_GAIN = 1.5
SANDBOX_GAP_GAIN = 1.0


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _slice_evaluated(slice_data: dict[str, Any] | None) -> bool:
    if not slice_data or not isinstance(slice_data, dict):
        return False
    status = str(slice_data.get("status", ""))
    sample = int(slice_data.get("sample_size", 0))
    return status == "EVALUATED" and sample > 0


def _compute_confidence(
    plan_confidence: float,
    validation: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> float:
    score = plan_confidence * 0.25
    if validation:
        robust = validation.get("robustness_score")
        if isinstance(robust, (int, float)):
            score += float(robust) * 0.35
        regime = validation.get("regime_consistency")
        if isinstance(regime, (int, float)):
            score += float(regime) * 0.15
        horizon = validation.get("horizon_consistency")
        if isinstance(horizon, (int, float)):
            score += float(horizon) * 0.15
        adj = validation.get("confidence_adjustment")
        if isinstance(adj, (int, float)):
            score += float(adj) * 0.05
        regional = validation.get("regional_consistency")
        if isinstance(regional, (int, float)):
            score += float(regional) * 0.10
    if candidate:
        sample = int(candidate.get("sample_size", 0))
        score += min(sample / 3000.0, 1.0) * 10.0
    return round(min(100.0, max(0.0, score)), 1)


class EvidenceGapAnalyzer:
    """Analyze evidence gaps per knowledge candidate — research planning only."""

    def __init__(
        self,
        history_store: EvidenceHistoryStore | None = None,
        gap_store: EvidenceGapStore | None = None,
    ) -> None:
        self._history_store = history_store or EvidenceHistoryStore()
        self._gap_store = gap_store or EvidenceGapStore()
        self._sources_loaded: dict[str, bool] = {}

    def analyze(self) -> EvidenceGapReport:
        now = datetime.now(timezone.utc)

        canonical_reference = self._load_canonical_reference()
        self._sources_loaded[str(CANONICAL_REPORT_PATH)] = canonical_reference is not None

        history_payload = _load_json(EVIDENCE_HISTORY_PATH)
        self._sources_loaded["tae_evidence_history.json"] = history_payload is not None

        cross_val = _load_json(CROSS_VALIDATION_PATH)
        self._sources_loaded["tae_cross_validation_report.json"] = cross_val is not None

        priorities_payload = _load_json(RESEARCH_PRIORITIES_PATH)
        self._sources_loaded["tae_research_priorities.json"] = priorities_payload is not None

        patch_review_payload = _load_json(PATCH_REVIEW_PATH)
        self._sources_loaded["tae_patch_review.json"] = patch_review_payload is not None

        evolution_payload = _load_json(EVOLUTION_PLAN_PATH)
        self._sources_loaded["tae_strategy_evolution_plan.json"] = evolution_payload is not None

        patch_payload = _load_json(IMPLEMENTATION_PATCH_PATH)
        self._sources_loaded["tae_implementation_patch.json"] = patch_payload is not None

        candidates_payload = _load_json(KNOWLEDGE_CANDIDATES_PATH)
        self._sources_loaded["tae_knowledge_candidates.json"] = candidates_payload is not None

        dossiers = self._history_store.list_all()
        if not dossiers and history_payload:
            for item in history_payload.get("dossiers", []):
                if isinstance(item, dict):
                    from research_core.evidence_history.evidence_record import EvidenceDossier

                    dossier = EvidenceDossier.from_dict(item)
                    if dossier is not None:
                        dossiers.append(dossier)

        priority_map = self._build_priority_map(priorities_payload)
        validation_map = self._build_validation_map(cross_val)
        candidate_map = self._build_candidate_map(candidates_payload)
        review_map = self._build_review_map(patch_review_payload)
        plan_map = self._build_plan_map(evolution_payload)
        patch_map = self._build_patch_map(patch_payload)

        gaps_created = 0
        gaps_updated = 0
        analyses: list[CandidateGapAnalysis] = []

        for dossier in dossiers:
            cid = dossier.candidate_id
            validation = validation_map.get(cid)
            candidate = candidate_map.get(cid)
            review = review_map.get(cid)
            plan = plan_map.get(cid)
            patch = patch_map.get(cid)
            priority_info = priority_map.get(cid, {})

            plan_confidence = float(plan.get("confidence", 0)) if plan else 0.0
            current_confidence = _compute_confidence(plan_confidence, validation, candidate)

            gaps, actions = self._identify_gaps(
                cid,
                validation,
                review,
                plan,
                patch,
                dossier,
                priority_info,
            )

            confidence_gain = 0.0
            for gap in gaps:
                if gap.category == GapCategory.REGIONAL_VALIDATION:
                    confidence_gain += REGIONAL_GAP_GAIN
                elif gap.category == GapCategory.REGIME_VALIDATION:
                    confidence_gain += REGIME_GAP_GAIN * 0.5
                elif gap.category == GapCategory.HORIZON_VALIDATION:
                    confidence_gain += HORIZON_GAP_GAIN * 0.3
                elif gap.category == GapCategory.PATCH_REVIEW:
                    confidence_gain += PATCH_REVIEW_GAP_GAIN * 0.2
                elif gap.category == GapCategory.SANDBOX_PREPARATION:
                    confidence_gain += SANDBOX_GAP_GAIN * 0.1
            estimated_confidence_after = round(
                min(100.0, current_confidence + confidence_gain),
                1,
            )

            has_regime_gap = any(
                g.category == GapCategory.REGIME_VALIDATION and g.blocks_readiness
                for g in gaps
            )
            has_regional_gap = any(
                g.category == GapCategory.REGIONAL_VALIDATION and g.blocks_readiness
                for g in gaps
            )
            if not has_regime_gap and not has_regional_gap:
                est_readiness = ImplementationReadiness.READY_FOR_SANDBOX_REVIEW
            elif not has_regime_gap:
                est_readiness = ImplementationReadiness.READY_FOR_SANDBOX_REVIEW
            else:
                est_readiness = ImplementationReadiness.NOT_READY

            info_gain = float(priority_info.get("expected_information_gain", 0))
            if info_gain <= 0:
                info_gain = sum(g.estimated_information_gain for g in gaps)

            blocking_items = list(dossier.blockers)
            for gap in gaps:
                if gap.blocks_readiness and gap.label not in blocking_items:
                    blocking_items.append(gap.label)

            remaining_parts: list[str] = []
            gap_counts: dict[str, int] = {}
            for gap in gaps:
                gap_counts[gap.category.value] = gap_counts.get(gap.category.value, 0) + 1
            for cat, count in sorted(gap_counts.items()):
                remaining_parts.append(f"{count} {cat.replace('_', ' ').lower()}")

            remaining_work = (
                "; ".join(remaining_parts) if remaining_parts else "No outstanding gaps"
            )

            recommended = priority_info.get("suggested_next_action", "")
            if not recommended and dossier.next_required_evidence:
                recommended = dossier.next_required_evidence[0]
            if not recommended and actions:
                recommended = actions[0].action

            analysis = CandidateGapAnalysis(
                candidate_id=cid,
                title=dossier.title,
                current_score=dossier.current_evidence_score,
                current_readiness=dossier.implementation_readiness,
                current_confidence=current_confidence,
                missing_evidence=gaps,
                research_actions=actions,
                estimated_information_gain=round(info_gain, 2),
                estimated_confidence_after_completion=estimated_confidence_after,
                estimated_readiness_after_completion=est_readiness,
                blocking_items=blocking_items,
                recommended_next_step=recommended,
                priority=int(priority_info.get("rank", 99)),
                human_review_required=True,
                implementation_allowed=False,
                remaining_work_summary=remaining_work,
                safety_mode=RESEARCH_SAFETY_BANNER,
                last_analyzed=now,
            )

            is_new, added, skipped = self._gap_store.upsert_analysis(analysis)
            if is_new:
                gaps_created += added
            else:
                gaps_updated += 1
                gaps_created += added
            analyses.append(self._gap_store.get(cid) or analysis)

        total_gaps = sum(len(a.missing_evidence) for a in analyses)

        if analyses:
            highest_info = max(analyses, key=lambda a: a.estimated_information_gain)
            most_blocked = max(analyses, key=lambda a: len(a.missing_evidence))
            easiest = min(
                analyses,
                key=lambda a: (len(a.missing_evidence), -a.current_score),
            )
            ready_after = sum(
                1
                for a in analyses
                if a.estimated_readiness_after_completion
                == ImplementationReadiness.READY_FOR_SANDBOX_REVIEW
            )
            research_order = sorted(analyses, key=lambda a: a.priority)
            top_blocked = max(
                analyses,
                key=lambda a: (len(a.blocking_items), -a.current_score),
            )
        else:
            highest_info = None
            most_blocked = None
            easiest = None
            ready_after = 0
            research_order = []
            top_blocked = None

        report = EvidenceGapReport(
            candidates_analyzed=len(analyses),
            total_gaps=total_gaps,
            analyses=analyses,
            highest_information_gain_candidate_id=(
                highest_info.candidate_id if highest_info else ""
            ),
            highest_information_gain=(
                highest_info.estimated_information_gain if highest_info else 0.0
            ),
            most_blocked_candidate_id=most_blocked.candidate_id if most_blocked else "",
            most_blocked_gap_count=len(most_blocked.missing_evidence) if most_blocked else 0,
            easiest_unblock_candidate_id=easiest.candidate_id if easiest else "",
            candidates_ready_after_closure=ready_after,
            recommended_research_order=[a.candidate_id for a in research_order],
            top_blocked_candidate_id=top_blocked.candidate_id if top_blocked else "",
            sources_loaded=dict(self._sources_loaded),
            canonical_reference=canonical_reference,
            gaps_created=gaps_created,
            gaps_updated=gaps_updated,
            safety_mode=RESEARCH_SAFETY_BANNER,
            generated_at=now,
        )

        self._gap_store.persist(report)
        self._gap_store.persist_txt(report)
        return report

    def _load_canonical_reference(self) -> dict[str, Any] | None:
        data = load_canonical_evidence_report()
        if data is None:
            return None
        items = data.get("evidence_items", [])
        return {
            "schema": data.get("schema"),
            "verdict": data.get("verdict"),
            "registry_item_count": data.get("registry_item_count"),
            "confirmed_count": data.get("confirmed_count"),
            "rejected_count": data.get("rejected_count"),
            "contradictions_count": len(data.get("contradictions", [])),
            "source_module": "research_core/evidence_engine/evidence_registry.py",
            "evidence_ids": [
                str(item.get("evidence_id", ""))
                for item in items
                if isinstance(item, dict)
            ][:20],
        }

    def _build_priority_map(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not payload:
            return out
        for item in payload.get("priorities", []):
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id", ""))
            if source_id.startswith("kn_"):
                out[source_id] = item
        return out

    def _build_validation_map(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not payload:
            return out
        for item in payload.get("candidate_results", []):
            if isinstance(item, dict) and item.get("candidate_id"):
                out[str(item["candidate_id"])] = item
        return out

    def _build_candidate_map(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not payload:
            return out
        for item in payload.get("candidates", []):
            if isinstance(item, dict) and item.get("candidate_id"):
                out[str(item["candidate_id"])] = item
        return out

    def _build_review_map(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not payload:
            return out
        for item in payload.get("reviews", []):
            if isinstance(item, dict) and item.get("source_candidate_id"):
                out[str(item["source_candidate_id"])] = item
        return out

    def _build_plan_map(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not payload:
            return out
        for item in payload.get("plans", []):
            if not isinstance(item, dict):
                continue
            target = str(item.get("proposed_target", ""))
            cid = ""
            if "candidate=" in target:
                cid = target.split("candidate=", 1)[1].split()[0].strip()
            if not cid:
                rec_id = str(item.get("source_recommendation_id", ""))
                if rec_id.startswith("rec_"):
                    cid = rec_id[4:]
            if cid:
                out[cid] = item
        return out

    def _build_patch_map(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not payload:
            return out
        for item in payload.get("patches", []):
            if isinstance(item, dict) and item.get("source_candidate_id"):
                out[str(item["source_candidate_id"])] = item
        return out

    def _identify_gaps(
        self,
        candidate_id: str,
        validation: dict[str, Any] | None,
        review: dict[str, Any] | None,
        plan: dict[str, Any] | None,
        patch: dict[str, Any] | None,
        dossier: Any,
        priority_info: dict[str, Any],
    ) -> tuple[list[MissingEvidenceItem], list[ResearchAction]]:
        gaps: list[MissingEvidenceItem] = []
        actions: list[ResearchAction] = []
        action_rank = 1

        regime_slices = (
            validation.get("regime_slices", {}) if validation else {}
        )
        if not isinstance(regime_slices, dict):
            regime_slices = {}

        for regime in REGIMES:
            slice_data = regime_slices.get(regime)
            if not _slice_evaluated(slice_data if isinstance(slice_data, dict) else None):
                label = regime
                if regime in ("BULL", "BEAR", "NEUTRAL"):
                    label = f"{regime} regime validation"
                gaps.append(
                    MissingEvidenceItem(
                        gap_id=f"gap_regime_{candidate_id}_{regime}",
                        category=GapCategory.REGIME_VALIDATION,
                        label=label,
                        description=(
                            f"Cross-regime validation for {regime} not complete — "
                            f"research-only experiment required."
                        ),
                        estimated_information_gain=REGIME_GAP_GAIN * 10,
                        blocks_readiness=True,
                    )
                )
                actions.append(
                    ResearchAction(
                        action_id=f"act_regime_{candidate_id}_{regime}",
                        category=GapCategory.REGIME_VALIDATION,
                        action=f"Run cross-regime validation experiment for {regime} "
                        f"(candidate {candidate_id}).",
                        priority_rank=action_rank,
                        estimated_effort=str(
                            priority_info.get("estimated_effort", "MEDIUM")
                        ),
                        expected_information_gain=REGIME_GAP_GAIN * 10,
                    )
                )
                action_rank += 1

        region_slices = validation.get("region_slices", {}) if validation else {}
        if not isinstance(region_slices, dict):
            region_slices = {}

        for region in REGIONS:
            if region == "US":
                continue
            slice_data = region_slices.get(region)
            region_missing = not _slice_evaluated(
                slice_data if isinstance(slice_data, dict) else None
            )
            if region_missing:
                for regime in REGIMES:
                    label = f"{region} {regime}"
                    gaps.append(
                        MissingEvidenceItem(
                            gap_id=f"gap_region_{candidate_id}_{region}_{regime}",
                            category=GapCategory.REGIONAL_VALIDATION,
                            label=label,
                            description=(
                                f"Regional validation for {region}/{regime} missing — "
                                f"add hypothesis-linked regional signal CSVs (research only)."
                            ),
                            estimated_information_gain=REGIONAL_GAP_GAIN * 10,
                            blocks_readiness=True,
                        )
                    )
                actions.append(
                    ResearchAction(
                        action_id=f"act_region_{candidate_id}_{region}",
                        category=GapCategory.REGIONAL_VALIDATION,
                        action=f"Add {region} hypothesis-linked regional signal CSVs "
                        f"and run regional validation for {candidate_id}.",
                        priority_rank=action_rank,
                        estimated_effort=str(
                            priority_info.get("estimated_effort", "MEDIUM")
                        ),
                        expected_information_gain=REGIONAL_GAP_GAIN * 10 * 3,
                    )
                )
                action_rank += 1

        horizon_slices = validation.get("horizon_slices", {}) if validation else {}
        if not isinstance(horizon_slices, dict):
            horizon_slices = {}

        for horizon in HORIZONS:
            slice_data = horizon_slices.get(horizon)
            if not _slice_evaluated(slice_data if isinstance(slice_data, dict) else None):
                gaps.append(
                    MissingEvidenceItem(
                        gap_id=f"gap_horizon_{candidate_id}_{horizon}",
                        category=GapCategory.HORIZON_VALIDATION,
                        label=f"{horizon} horizon validation",
                        description=(
                            f"Horizon slice {horizon} not evaluated — "
                            f"extend multi-horizon backtest coverage."
                        ),
                        estimated_information_gain=HORIZON_GAP_GAIN * 10,
                        blocks_readiness=horizon in ("10Y", "20Y"),
                    )
                )
                actions.append(
                    ResearchAction(
                        action_id=f"act_horizon_{candidate_id}_{horizon}",
                        category=GapCategory.HORIZON_VALIDATION,
                        action=f"Extend horizon validation to {horizon} for {candidate_id}.",
                        priority_rank=action_rank,
                        estimated_effort="LOW",
                        expected_information_gain=HORIZON_GAP_GAIN * 10,
                    )
                )
                action_rank += 1

        regional_consistency = (
            validation.get("regional_consistency") if validation else None
        )
        if regional_consistency == NOT_AVAILABLE or regional_consistency is None:
            if not any(g.category == GapCategory.REGIONAL_VALIDATION for g in gaps):
                gaps.append(
                    MissingEvidenceItem(
                        gap_id=f"gap_region_meta_{candidate_id}",
                        category=GapCategory.REGIONAL_VALIDATION,
                        label="Europe/UK regional validation",
                        description="Europe/UK regional validation missing — blocks readiness.",
                        estimated_information_gain=REGIONAL_GAP_GAIN * 10,
                        blocks_readiness=True,
                    )
                )

        regime_consistency = validation.get("regime_consistency") if validation else None
        if regime_consistency == NOT_AVAILABLE:
            if not any(g.category == GapCategory.REGIME_VALIDATION for g in gaps):
                gaps.append(
                    MissingEvidenceItem(
                        gap_id=f"gap_regime_meta_{candidate_id}",
                        category=GapCategory.REGIME_VALIDATION,
                        label="Cross-regime consistency",
                        description="Cross-regime consistency NOT_AVAILABLE — insufficient samples.",
                        estimated_information_gain=REGIME_GAP_GAIN * 10,
                        blocks_readiness=True,
                    )
                )

        if review:
            verdict = str(review.get("verdict", ""))
            if verdict == "REQUIRE_MORE_EVIDENCE":
                gaps.append(
                    MissingEvidenceItem(
                        gap_id=f"gap_patch_review_{candidate_id}",
                        category=GapCategory.PATCH_REVIEW,
                        label="Patch review requires more evidence",
                        description=(
                            f"Patch review verdict: {verdict} — "
                            f"score={review.get('review_score', 0)}."
                        ),
                        estimated_information_gain=PATCH_REVIEW_GAP_GAIN * 10,
                        blocks_readiness=True,
                    )
                )
                for step in review.get("next_required_steps", [])[:3]:
                    if isinstance(step, str):
                        actions.append(
                            ResearchAction(
                                action_id=f"act_review_{candidate_id}_{action_rank}",
                                category=GapCategory.PATCH_REVIEW,
                                action=step,
                                priority_rank=action_rank,
                                estimated_effort="MEDIUM",
                                expected_information_gain=PATCH_REVIEW_GAP_GAIN * 5,
                            )
                        )
                        action_rank += 1

        if patch:
            gate = str(patch.get("patch_gate_status", ""))
            if gate == "BLOCKED_BY_VALIDATION_GAP":
                gaps.append(
                    MissingEvidenceItem(
                        gap_id=f"gap_sandbox_{candidate_id}",
                        category=GapCategory.SANDBOX_PREPARATION,
                        label="Sandbox blocked by validation gap",
                        description=(
                            f"Implementation patch gate: {gate} — "
                            f"sandbox review not available until gaps closed."
                        ),
                        estimated_information_gain=SANDBOX_GAP_GAIN * 10,
                        blocks_readiness=True,
                    )
                )
                actions.append(
                    ResearchAction(
                        action_id=f"act_sandbox_{candidate_id}",
                        category=GapCategory.SANDBOX_PREPARATION,
                        action="Close validation gaps before sandbox review preparation.",
                        priority_rank=action_rank,
                        estimated_effort="MEDIUM",
                        expected_information_gain=SANDBOX_GAP_GAIN * 10,
                    )
                )
                action_rank += 1

        learning_missing = any(
            r.record_type.value == "LEARNING_SUPPORT"
            and r.polarity.value == "MISSING"
            for r in dossier.evidence_records
        )
        if learning_missing:
            gaps.append(
                MissingEvidenceItem(
                    gap_id=f"gap_learning_{candidate_id}",
                    category=GapCategory.LEARNING_CONFIRMATION,
                    label="Learning confirmation incomplete",
                    description="Learning support evidence incomplete — confirm with learning report.",
                    estimated_information_gain=LEARNING_GAP_GAIN * 10,
                    blocks_readiness=False,
                )
            )
            actions.append(
                ResearchAction(
                    action_id=f"act_learning_{candidate_id}",
                    category=GapCategory.LEARNING_CONFIRMATION,
                    action=f"Confirm learning support alignment for {candidate_id}.",
                    priority_rank=action_rank,
                    estimated_effort="LOW",
                    expected_information_gain=LEARNING_GAP_GAIN * 10,
                )
            )
            action_rank += 1

        if plan and str(plan.get("proposed_change_type", "")) == "VALIDATION_GATE":
            actions.insert(
                0,
                ResearchAction(
                    action_id=f"act_plan_{candidate_id}",
                    category=GapCategory.EXPERIMENT_REPEAT,
                    action=str(plan.get("proposed_change", ""))[:200],
                    priority_rank=0,
                    estimated_effort=str(priority_info.get("estimated_effort", "MEDIUM")),
                    expected_information_gain=float(
                        priority_info.get("expected_information_gain", 0)
                    ),
                ),
            )

        actions = sorted(actions, key=lambda a: a.priority_rank)
        return gaps, actions
