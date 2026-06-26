"""
Implementation patch proposal generator — Phase V Sprint A7

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Generates auditable patch documentation from evolution artifacts.
Does not apply patches, edit live files, or run git.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.evolution.evolution_plan import (
    DEFAULT_EVOLUTION_PLAN_PATH,
    EvolutionPlanEntry,
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

logger = logging.getLogger(__name__)

DEFAULT_PATCH_JSON_PATH = Path("tae_implementation_patch.json")
DEFAULT_PATCH_TXT_PATH = Path("tae_implementation_patch.txt")
DEFAULT_PROPOSAL_TXT_PATH = Path("tae_evolution_proposal.txt")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
LEARNING_PATH = Path("tae_learning_report.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_implementation_patch"
NOT_AVAILABLE = "NOT_AVAILABLE"

PROTECTED_PATHS = frozenset({
    "live_bot.py",
    "config/settings.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "core/entry_filter.py",
})


class PatchGateStatus(str, Enum):
    BLOCKED_BY_VALIDATION_GAP = "BLOCKED_BY_VALIDATION_GAP"
    WAITING_VALIDATION = "WAITING_VALIDATION"
    PROPOSAL_FOR_HUMAN_REVIEW = "PROPOSAL_FOR_HUMAN_REVIEW"


@dataclass
class PatchProposal:
    patch_id: str
    source_recommendation_id: str
    source_plan_id: str
    source_candidate_id: str
    title: str
    confidence: float
    files_affected: list[str]
    functions_affected: list[str]
    current_behavior: str
    proposed_behavior: str
    suggested_code_change_description: str
    estimated_benefit: str
    risk_assessment: str
    validation_status: str
    rollback_procedure: str
    patch_gate_status: PatchGateStatus
    human_approval_required: bool = True
    implementation_status: ImplementationStatus = ImplementationStatus.NOT_IMPLEMENTED
    safety_mode: str = RESEARCH_SAFETY_BANNER
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.patch_gate_status, str):
            self.patch_gate_status = PatchGateStatus(self.patch_gate_status)
        if isinstance(self.implementation_status, str):
            self.implementation_status = ImplementationStatus(self.implementation_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "source_recommendation_id": self.source_recommendation_id,
            "source_plan_id": self.source_plan_id,
            "source_candidate_id": self.source_candidate_id,
            "title": self.title,
            "confidence": round(self.confidence, 2),
            "files_affected": list(self.files_affected),
            "functions_affected": list(self.functions_affected),
            "current_behavior": self.current_behavior,
            "proposed_behavior": self.proposed_behavior,
            "suggested_code_change_description": self.suggested_code_change_description,
            "estimated_benefit": self.estimated_benefit,
            "risk_assessment": self.risk_assessment,
            "validation_status": self.validation_status,
            "rollback_procedure": self.rollback_procedure,
            "patch_gate_status": self.patch_gate_status.value,
            "human_approval_required": self.human_approval_required,
            "implementation_status": self.implementation_status.value,
            "safety_mode": self.safety_mode,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatchProposal | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            gate = str(data.get("patch_gate_status", PatchGateStatus.WAITING_VALIDATION.value))
            try:
                patch_gate_status = PatchGateStatus(gate)
            except ValueError:
                patch_gate_status = PatchGateStatus.WAITING_VALIDATION

            impl = str(data.get("implementation_status", ImplementationStatus.NOT_IMPLEMENTED.value))
            try:
                implementation_status = ImplementationStatus(impl)
            except ValueError:
                implementation_status = ImplementationStatus.NOT_IMPLEMENTED

            files = data.get("files_affected", [])
            funcs = data.get("functions_affected", [])
            if not isinstance(files, list):
                files = []
            if not isinstance(funcs, list):
                funcs = []

            return cls(
                patch_id=str(data["patch_id"]),
                source_recommendation_id=str(data.get("source_recommendation_id", "")),
                source_plan_id=str(data.get("source_plan_id", "")),
                source_candidate_id=str(data.get("source_candidate_id", "")),
                title=str(data.get("title", "")),
                confidence=float(data.get("confidence", 0)),
                files_affected=[str(f) for f in files],
                functions_affected=[str(f) for f in funcs],
                current_behavior=str(data.get("current_behavior", "")),
                proposed_behavior=str(data.get("proposed_behavior", "")),
                suggested_code_change_description=str(
                    data.get("suggested_code_change_description", "")
                ),
                estimated_benefit=str(data.get("estimated_benefit", "")),
                risk_assessment=str(data.get("risk_assessment", "")),
                validation_status=str(data.get("validation_status", "")),
                rollback_procedure=str(data.get("rollback_procedure", "")),
                patch_gate_status=patch_gate_status,
                human_approval_required=bool(data.get("human_approval_required", True)),
                implementation_status=implementation_status,
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                created_at=dt,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.patch_id} | {self.patch_gate_status.value} | "
            f"confidence={self.confidence:.1f} | {self.source_candidate_id}"
        )


@dataclass
class PatchGenerationResult:
    recommendations_loaded: int
    plans_loaded: int
    patches_generated: int
    patches_skipped_duplicate: int
    patches: list[PatchProposal]
    highest_confidence_patch: PatchProposal | None
    blocked_patches: list[PatchProposal]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "recommendations_loaded": self.recommendations_loaded,
            "plans_loaded": self.plans_loaded,
            "patches_generated": self.patches_generated,
            "patches_skipped_duplicate": self.patches_skipped_duplicate,
            "highest_confidence_patch_id": (
                self.highest_confidence_patch.patch_id
                if self.highest_confidence_patch
                else ""
            ),
            "blocked_patch_count": len(self.blocked_patches),
            "sources_loaded": dict(self.sources_loaded),
            "patches": [p.to_dict() for p in self.patches],
        }


class ImplementationPatchStore:
    """JSON persistence for patch proposals — stdlib only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_PATCH_JSON_PATH
        self._patches: dict[str, PatchProposal] = {}
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    def list_all(self) -> list[PatchProposal]:
        return sorted(self._patches.values(), key=lambda p: p.created_at)

    def has_plan(self, source_plan_id: str) -> bool:
        return any(p.source_plan_id == source_plan_id for p in self._patches.values())

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Patch store unreadable (%s): %s", self._path, exc)
            return False
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return False
        items = payload.get("patches", [])
        if not isinstance(items, list):
            return False
        self._patches.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            patch = PatchProposal.from_dict(item)
            if patch is not None:
                self._patches[patch.patch_id] = patch
        return True

    def merge_new(self, patches: list[PatchProposal]) -> tuple[int, int]:
        added = 0
        skipped = 0
        for patch in patches:
            if patch.patch_id in self._patches or self.has_plan(patch.source_plan_id):
                skipped += 1
                continue
            self._patches[patch.patch_id] = patch
            added += 1
        return added, skipped

    def persist(self, result: PatchGenerationResult) -> Path:
        payload = result.to_dict()
        payload["patches"] = [p.to_dict() for p in self.list_all()]
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _validation_for_candidate(candidate_id: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    for item in payload.get("candidate_results", []):
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
            return item
    return None


def _missing_validation_evidence(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return ["Cross-validation report missing for candidate"]
    missing: list[str] = []
    region = validation.get("regional_consistency", NOT_AVAILABLE)
    regime = validation.get("regime_consistency", NOT_AVAILABLE)
    if region == NOT_AVAILABLE or str(region) == NOT_AVAILABLE:
        missing.append("Europe/UK regional validation NOT_AVAILABLE")
    if regime == NOT_AVAILABLE or str(regime) == NOT_AVAILABLE:
        missing.append("Cross-regime consistency incomplete for candidate")
    europe = validation.get("region_slices", {}).get("Europe", {})
    if isinstance(europe, dict) and europe.get("status") != "EVALUATED":
        if "Europe validation missing" not in missing:
            missing.append("Europe validation missing")
    uk = validation.get("region_slices", {}).get("UK", {})
    if isinstance(uk, dict) and uk.get("status") != "EVALUATED":
        if "UK validation missing" not in missing:
            missing.append("UK validation missing")
    return missing


def _gate_status(
    plan: EvolutionPlanEntry,
    recommendation: StrategyRecommendation | None,
) -> PatchGateStatus:
    if plan.proposed_change_type == ProposedChangeType.VALIDATION_GATE:
        return PatchGateStatus.BLOCKED_BY_VALIDATION_GAP
    if recommendation and recommendation.recommendation_type == RecommendationType.REQUIRE_MORE_VALIDATION:
        return PatchGateStatus.WAITING_VALIDATION
    if recommendation and recommendation.recommendation_type == RecommendationType.BLOCK_FROM_TRADING:
        return PatchGateStatus.BLOCKED_BY_VALIDATION_GAP
    return PatchGateStatus.PROPOSAL_FOR_HUMAN_REVIEW


def _proposal_files_only(plan: EvolutionPlanEntry) -> list[str]:
    """Proposal-only paths — protected live files are not listed as editable."""
    if plan.proposed_change_type == ProposedChangeType.VALIDATION_GATE:
        return [
            "research_weights.py (proposed new module — documentation only)",
            "research_core/integration/knowledge_integration.py (review only)",
        ]
    if plan.proposed_change_type == ProposedChangeType.RESEARCH_WEIGHT_ADJUSTMENT:
        return [
            "research_weights.py (proposed new module — not live_bot or entry_filter)",
        ]
    return ["research_core/evolution/observation_registry.py (proposed paper-only)"]


def _functions_affected(plan: EvolutionPlanEntry) -> list[str]:
    if plan.proposed_change_type == ProposedChangeType.VALIDATION_GATE:
        return [
            "CrossRegimeValidator.validate_candidate_by_id (run validation first)",
            "KnowledgeIntegrator.integrate (research review only)",
        ]
    if plan.proposed_change_type == ProposedChangeType.RESEARCH_WEIGHT_ADJUSTMENT:
        return [
            "research_weights.apply_candidate_weight (proposed — not implemented)",
        ]
    return ["observation_registry.track_candidate (proposed paper-only)"]


class ImplementationPatchGenerator:
    """
    Generates patch documentation from evolution artifacts.
    Sprint A7 — no file writes to live trading code.
    """

    def __init__(
        self,
        recommendations_store: StrategyRecommendationsStore | None = None,
        plan_store: EvolutionPlanStore | None = None,
        patch_store: ImplementationPatchStore | None = None,
    ) -> None:
        self._recommendations = recommendations_store or StrategyRecommendationsStore()
        self._plans = plan_store or EvolutionPlanStore()
        self._patches = patch_store or ImplementationPatchStore()
        self._sources_loaded: dict[str, bool] = {}
        self._proposal_text: str = ""

    def generate(self) -> PatchGenerationResult:
        self._load_sources()

        recs = self._recommendations.list_all()
        plans = self._plans.list_all()
        validation_payload = _load_json(CROSS_VALIDATION_PATH)
        learning_payload = _load_json(LEARNING_PATH)

        new_patches: list[PatchProposal] = []
        for plan in plans:
            rec = self._recommendations.get(plan.source_recommendation_id)
            new_patches.append(
                self._build_patch(plan, rec, validation_payload, learning_payload)
            )

        added, skipped = self._patches.merge_new(new_patches)
        all_patches = self._patches.list_all()
        highest = max(all_patches, key=lambda p: p.confidence) if all_patches else None
        blocked = [
            p for p in all_patches
            if p.patch_gate_status in (
                PatchGateStatus.BLOCKED_BY_VALIDATION_GAP,
                PatchGateStatus.WAITING_VALIDATION,
            )
        ]

        result = PatchGenerationResult(
            recommendations_loaded=len(recs),
            plans_loaded=len(plans),
            patches_generated=added,
            patches_skipped_duplicate=skipped,
            patches=all_patches,
            highest_confidence_patch=highest,
            blocked_patches=blocked,
            sources_loaded=dict(self._sources_loaded),
        )
        self._patches.persist(result)
        return result

    def _load_sources(self) -> None:
        if not self._recommendations.loaded_at_startup:
            self._recommendations.load()
        self._sources_loaded[str(DEFAULT_RECOMMENDATIONS_PATH)] = len(
            self._recommendations.list_all()
        ) > 0

        if not self._plans.loaded_at_startup:
            self._plans.load()
        self._sources_loaded[str(DEFAULT_EVOLUTION_PLAN_PATH)] = len(
            self._plans.list_all()
        ) > 0

        proposal_path = DEFAULT_PROPOSAL_TXT_PATH
        if proposal_path.is_file():
            try:
                self._proposal_text = proposal_path.read_text(encoding="utf-8")
                self._sources_loaded[str(proposal_path)] = True
            except OSError:
                self._sources_loaded[str(proposal_path)] = False
        else:
            self._sources_loaded[str(proposal_path)] = False

        self._sources_loaded[str(CROSS_VALIDATION_PATH)] = CROSS_VALIDATION_PATH.is_file()
        self._sources_loaded[str(LEARNING_PATH)] = LEARNING_PATH.is_file()

    def _build_patch(
        self,
        plan: EvolutionPlanEntry,
        rec: StrategyRecommendation | None,
        validation_payload: dict[str, Any] | None,
        learning_payload: dict[str, Any] | None,
    ) -> PatchProposal:
        candidate_id = rec.source_candidate_id if rec else ""
        validation = _validation_for_candidate(candidate_id, validation_payload) if candidate_id else None
        missing = _missing_validation_evidence(validation)
        gate = _gate_status(plan, rec)

        title = rec.title if rec else plan.rationale[:80]
        confidence = plan.confidence
        if validation and isinstance(validation.get("robustness_score"), (int, float)):
            confidence = round(
                (plan.confidence * 0.5) + float(validation["robustness_score"]) * 0.5,
                2,
            )

        estimated = plan.expected_benefit[:120] if plan.expected_benefit else "under research review"
        if validation and isinstance(validation.get("confidence_adjustment"), (int, float)):
            estimated = f"+{round(float(validation['confidence_adjustment']) * 0.8, 1)}% (research estimate)"

        validation_status = "VALIDATED_PARTIAL"
        if missing:
            validation_status = "WAITING_VALIDATION — " + "; ".join(missing[:3])
        elif validation:
            validation_status = (
                f"robustness={validation.get('robustness_score', '?')}; "
                f"regime={validation.get('regime_consistency', '?')}; "
                f"region={validation.get('regional_consistency', '?')}"
            )

        current_behavior = (
            "Live strategy unchanged. Research candidate documented in evolution plan "
            "with implementation_status=NOT_IMPLEMENTED. No threshold or entry_filter "
            "changes applied."
        )
        if learning_payload:
            current_behavior += (
                f" Learning baseline: accuracy={learning_payload.get('average_accuracy', '?')}, "
                f"confidence={learning_payload.get('learning_confidence', '?')}."
            )

        if gate == PatchGateStatus.BLOCKED_BY_VALIDATION_GAP:
            proposed_behavior = (
                "Complete validation gaps before any code change. "
                "Proposed future behavior: paper-only research weight review for candidate "
                f"{candidate_id} after human approval — not live execution."
            )
            code_desc = (
                "NO direct threshold or config patch ready to apply. "
                "Suggested preparatory work only: extend cross-regime/regional validation "
                f"for {candidate_id}. Missing: " + ", ".join(missing[:4])
            )
        elif gate == PatchGateStatus.WAITING_VALIDATION:
            proposed_behavior = (
                "Hold implementation until validation requirements are satisfied. "
                "Document observation metrics in research layer only."
            )
            code_desc = (
                "Documentation-only patch proposal. Do not modify core/entry_filter.py, "
                "live_bot.py, or config/settings.py until validation complete."
            )
        else:
            proposed_behavior = (
                "After human approval: add research_weights module entry for candidate "
                f"{candidate_id} — paper/research scoring only."
            )
            code_desc = (
                "Proposed new function in research_weights.py (file does not exist yet) "
                "to record approved research weight — not auto-applied to live bot."
            )

        risk = plan.risk_assessment[:500] if plan.risk_assessment else "Standard research-only risk."
        if missing:
            risk += " Validation gaps: " + "; ".join(missing[:3])

        rollback = (
            f"Discard patch {plan.plan_id} without applying. "
            "implementation_status remains NOT_IMPLEMENTED. "
            "If ever applied in future after approval: git revert <commit> for research-only module only. "
            "Protected files (live_bot.py, core/entry_filter.py, portfolio.csv) must not be patched without separate review."
        )

        return PatchProposal(
            patch_id=f"patch_{plan.plan_id}",
            source_recommendation_id=plan.source_recommendation_id,
            source_plan_id=plan.plan_id,
            source_candidate_id=candidate_id,
            title=title,
            confidence=confidence,
            files_affected=_proposal_files_only(plan),
            functions_affected=_functions_affected(plan),
            current_behavior=current_behavior,
            proposed_behavior=proposed_behavior,
            suggested_code_change_description=code_desc,
            estimated_benefit=estimated,
            risk_assessment=risk[:600],
            validation_status=validation_status,
            rollback_procedure=rollback,
            patch_gate_status=gate,
            human_approval_required=True,
            implementation_status=ImplementationStatus.NOT_IMPLEMENTED,
        )


def format_patch_txt(result: PatchGenerationResult, live_files_unchanged: bool) -> str:
    lines = [
        "===== TAE IMPLEMENTATION PATCH PROPOSAL =====",
        "",
        f"Safety: {result.safety_mode}",
        f"Generated: {result.generated_at.isoformat()}",
        "",
        f"Recommendations loaded: {result.recommendations_loaded}",
        f"Plans loaded: {result.plans_loaded}",
        f"Patches generated (this run): {result.patches_generated}",
        f"Duplicates skipped (this run): {result.patches_skipped_duplicate}",
        f"Total patches in store: {len(result.patches)}",
        "",
    ]

    if result.highest_confidence_patch:
        hc = result.highest_confidence_patch
        lines.extend([
            "Highest-confidence patch:",
            f"  {hc.summary_line()}",
            f"  title: {hc.title[:100]}",
            "",
        ])

    lines.append(f"Blocked / waiting validation: {len(result.blocked_patches)}")
    for patch in result.blocked_patches:
        lines.append(f"  - {patch.patch_id}: {patch.patch_gate_status.value}")
    lines.append("")

    for patch in result.patches:
        lines.extend([
            "----------------------------------------",
            f"Patch: {patch.patch_id}",
            f"Gate status: {patch.patch_gate_status.value}",
            f"Confidence: {patch.confidence:.1f}%",
            f"Candidate: {patch.source_candidate_id}",
            "",
            "Files affected (proposal only — not modified):",
        ])
        for f in patch.files_affected:
            lines.append(f"  - {f}")
        lines.append("")
        lines.append("Functions affected (documentation):")
        for fn in patch.functions_affected:
            lines.append(f"  - {fn}")
        lines.extend([
            "",
            f"Current behavior: {patch.current_behavior[:300]}",
            "",
            f"Proposed behavior: {patch.proposed_behavior[:300]}",
            "",
            f"Suggested change: {patch.suggested_code_change_description[:400]}",
            "",
            f"Validation: {patch.validation_status[:300]}",
            "",
            f"Estimated benefit: {patch.estimated_benefit}",
            "",
            f"Risk: {patch.risk_assessment[:300]}",
            "",
            f"Rollback: {patch.rollback_procedure[:250]}",
            "",
            f"human_approval_required: {patch.human_approval_required}",
            f"implementation_status: {patch.implementation_status.value}",
            "",
        ])

    lines.extend([
        "===== AVERTISMENT =====",
        "NOT IMPLEMENTED — HUMAN APPROVAL REQUIRED",
        "",
        "===== CONFIRMARE SIGURANȚĂ =====",
    ])
    if live_files_unchanged:
        lines.append("No live trading files were modified")
        lines.append(
            "(live_bot.py, config/settings.py, dashboard_v2.py, portfolio.csv, "
            "core/entry_filter.py — neatinse)"
        )
    else:
        lines.append("Verificare necesară: fișiere protejate posibil modificate.")
    lines.extend([
        "",
        "Documentație only — nu se aplică patch-uri automat.",
        "",
    ])
    return "\n".join(lines)


def persist_patch_txt(result: PatchGenerationResult, live_files_unchanged: bool) -> Path:
    text = format_patch_txt(result, live_files_unchanged)
    DEFAULT_PATCH_TXT_PATH.write_text(text + "\n", encoding="utf-8")
    return DEFAULT_PATCH_TXT_PATH
