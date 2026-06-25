"""
Capability registry — Sprint 5.5 Research Roadmap

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Catalog of TAE research capabilities grouped by roadmap phase.
Informational only — not execution or trading logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RoadmapPhase(str, Enum):
    FOUNDATION = "Foundation"
    RESEARCH = "Research"
    INTELLIGENCE = "Intelligence"
    SCIENTIFIC_DISCOVERY = "Scientific Discovery"
    DECISION_INTELLIGENCE = "Decision Intelligence"


class CapabilityStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PLANNED = "PLANNED"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    name: str
    phase: RoadmapPhase
    sprint: str
    description: str
    module_paths: tuple[str, ...] = ()
    demo_paths: tuple[str, ...] = ()
    default_status: CapabilityStatus = CapabilityStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "phase": self.phase.value,
            "sprint": self.sprint,
            "description": self.description,
            "module_paths": list(self.module_paths),
            "demo_paths": list(self.demo_paths),
            "default_status": self.default_status.value,
        }


@dataclass
class CapabilityRecord:
    capability_id: str
    name: str
    phase: str
    sprint: str
    description: str
    status: CapabilityStatus
    module_paths: list[str] = field(default_factory=list)
    demo_paths: list[str] = field(default_factory=list)
    artifacts_found: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "phase": self.phase,
            "sprint": self.sprint,
            "description": self.description,
            "status": self.status.value,
            "module_paths": list(self.module_paths),
            "demo_paths": list(self.demo_paths),
            "artifacts_found": list(self.artifacts_found),
            "missing_artifacts": list(self.missing_artifacts),
        }


# Implemented capabilities (Sprint 3–5)
IMPLEMENTED_CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id="life_system",
        name="Life System",
        phase=RoadmapPhase.FOUNDATION,
        sprint="3.5–3.7",
        description="Biography, timeline, milestones, and JSON persistence for TAE life state.",
        module_paths=(
            "research_core/life/life_manager.py",
            "research_core/life/life_storage.py",
        ),
        demo_paths=("tae_life_demo.py",),
    ),
    CapabilityDefinition(
        capability_id="cognitive_layer",
        name="Cognitive Layer",
        phase=RoadmapPhase.FOUNDATION,
        sprint="3.x / 4.x",
        description="Cognitive cycle orchestration and organism packet processing.",
        module_paths=(
            "research_core/ecosystem/cognitive_layer.py",
            "research_core/ecosystem/collective_intelligence.py",
        ),
        demo_paths=("ecosystem_cognitive_demo_v1.py",),
    ),
    CapabilityDefinition(
        capability_id="organisms",
        name="Organisms",
        phase=RoadmapPhase.RESEARCH,
        sprint="4.0–4.1",
        description="Evidence, context, and momentum research organisms on the communication bus.",
        module_paths=(
            "research_core/ecosystem/organisms/evidence_organism.py",
            "research_core/ecosystem/organisms/context_organism.py",
            "research_core/ecosystem/organisms/momentum_organism.py",
        ),
        demo_paths=(
            "tae_sprint4_real_organism_demo.py",
            "tae_sprint4_multi_organism_demo.py",
        ),
    ),
    CapabilityDefinition(
        capability_id="trust_calibration",
        name="Trust Calibration",
        phase=RoadmapPhase.RESEARCH,
        sprint="4.3",
        description="Conservative trust deltas from organism memory and participation.",
        module_paths=("research_core/ecosystem/trust_calibration.py",),
        demo_paths=("tae_sprint4_trust_calibration_demo.py",),
    ),
    CapabilityDefinition(
        capability_id="research_council",
        name="Research Council",
        phase=RoadmapPhase.RESEARCH,
        sprint="4.4–4.5",
        description="Trust-weighted collective decisions and council session reports.",
        module_paths=(
            "research_core/ecosystem/research_council_report.py",
            "research_core/ecosystem/collective_intelligence.py",
        ),
        demo_paths=(
            "tae_sprint4_trust_weighted_decision_demo.py",
            "tae_sprint4_research_council_report.py",
        ),
    ),
    CapabilityDefinition(
        capability_id="hypothesis_engine",
        name="Hypothesis Engine",
        phase=RoadmapPhase.INTELLIGENCE,
        sprint="5.0",
        description="Hypothesis model, registry, and council-driven hypothesis generation.",
        module_paths=(
            "research_core/hypothesis/hypothesis_model.py",
            "research_core/hypothesis/hypothesis_registry.py",
            "research_core/hypothesis/hypothesis_generator.py",
        ),
        demo_paths=("tae_sprint5_hypothesis_engine_demo.py",),
    ),
    CapabilityDefinition(
        capability_id="experiment_runner",
        name="Experiment Runner",
        phase=RoadmapPhase.INTELLIGENCE,
        sprint="5.1",
        description="Defensive historical cohort tests for UNTESTED hypotheses.",
        module_paths=(
            "research_core/hypothesis/experiment_runner.py",
            "research_core/hypothesis/experiment_result.py",
        ),
        demo_paths=("tae_sprint5_experiment_runner_demo.py",),
    ),
    CapabilityDefinition(
        capability_id="ranking_engine",
        name="Ranking Engine",
        phase=RoadmapPhase.INTELLIGENCE,
        sprint="5.2",
        description="Quality-ranked hypotheses with robustness and duplicate awareness.",
        module_paths=("research_core/hypothesis/hypothesis_ranking.py",),
        demo_paths=("tae_sprint5_hypothesis_ranking_demo.py",),
    ),
    CapabilityDefinition(
        capability_id="knowledge_candidates",
        name="Knowledge Candidates",
        phase=RoadmapPhase.INTELLIGENCE,
        sprint="5.3",
        description="Promote high-quality ranked hypotheses to knowledge candidate registry.",
        module_paths=("research_core/hypothesis/knowledge_candidate.py",),
        demo_paths=("tae_sprint5_knowledge_candidate_demo.py",),
    ),
    CapabilityDefinition(
        capability_id="learning_engine",
        name="Learning Engine",
        phase=RoadmapPhase.INTELLIGENCE,
        sprint="5.4",
        description="Meta-learning report from experiments, rankings, candidates, and memory.",
        module_paths=(
            "research_core/learning/learning_engine.py",
            "research_core/learning/learning_report.py",
        ),
        demo_paths=("tae_sprint5_learning_engine_demo.py",),
    ),
)

# Future roadmap — informational planned capabilities
PLANNED_CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id="cross_regime_experiments",
        name="Cross-Regime Experiment Matrix",
        phase=RoadmapPhase.SCIENTIFIC_DISCOVERY,
        sprint="6.x (planned)",
        description="Systematic hypothesis tests across BULL/BEAR/NEUTRAL regimes.",
        default_status=CapabilityStatus.PLANNED,
    ),
    CapabilityDefinition(
        capability_id="discovery_pipeline_integration",
        name="Automated Discovery Integration",
        phase=RoadmapPhase.SCIENTIFIC_DISCOVERY,
        sprint="6.x (planned)",
        description="Bridge discovery engine outputs into hypothesis and experiment pipeline.",
        module_paths=("research_core/discovery/engine.py",),
        default_status=CapabilityStatus.PLANNED,
    ),
    CapabilityDefinition(
        capability_id="multi_horizon_validation",
        name="Multi-Horizon Validation",
        phase=RoadmapPhase.SCIENTIFIC_DISCOVERY,
        sprint="6.x (planned)",
        description="Validate hypotheses across multiple forward-return horizons.",
        default_status=CapabilityStatus.PLANNED,
    ),
    CapabilityDefinition(
        capability_id="research_prioritization_loop",
        name="Research Prioritization Loop",
        phase=RoadmapPhase.DECISION_INTELLIGENCE,
        sprint="7.x (planned)",
        description="Closed loop from learning report to next hypothesis queue (research only).",
        default_status=CapabilityStatus.PLANNED,
    ),
    CapabilityDefinition(
        capability_id="human_review_workflow",
        name="Human Review Workflow",
        phase=RoadmapPhase.DECISION_INTELLIGENCE,
        sprint="7.x (planned)",
        description="Structured human review gate for knowledge candidates — no auto-execution.",
        default_status=CapabilityStatus.PLANNED,
    ),
    CapabilityDefinition(
        capability_id="production_candidate_gate",
        name="Production Candidate Gate",
        phase=RoadmapPhase.DECISION_INTELLIGENCE,
        sprint="7.x (planned)",
        description="Research-only production candidate labeling for human review — never auto-trade.",
        default_status=CapabilityStatus.PLANNED,
    ),
)

ALL_CAPABILITY_DEFINITIONS: tuple[CapabilityDefinition, ...] = (
    *IMPLEMENTED_CAPABILITIES,
    *PLANNED_CAPABILITIES,
)

PHASE_ORDER: tuple[RoadmapPhase, ...] = (
    RoadmapPhase.FOUNDATION,
    RoadmapPhase.RESEARCH,
    RoadmapPhase.INTELLIGENCE,
    RoadmapPhase.SCIENTIFIC_DISCOVERY,
    RoadmapPhase.DECISION_INTELLIGENCE,
)


class CapabilityRegistry:
    """Registry and artifact detection for roadmap capabilities."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(".")

    @property
    def root(self) -> Path:
        return self._root

    def all_definitions(self) -> list[CapabilityDefinition]:
        return list(ALL_CAPABILITY_DEFINITIONS)

    def detect_capability(self, definition: CapabilityDefinition) -> CapabilityRecord:
        artifacts = list(definition.module_paths) + list(definition.demo_paths)
        found: list[str] = []
        missing: list[str] = []

        for rel in artifacts:
            path = self._root / rel
            if path.is_file():
                found.append(rel)
            else:
                missing.append(rel)

        if definition.default_status == CapabilityStatus.PLANNED:
            status = CapabilityStatus.PLANNED
            if definition.demo_paths:
                if artifacts and not missing:
                    status = CapabilityStatus.COMPLETED
                elif found:
                    status = CapabilityStatus.PARTIAL
            elif artifacts and missing:
                status = CapabilityStatus.PARTIAL
        else:
            if not artifacts:
                status = CapabilityStatus.COMPLETED
            elif not missing:
                status = CapabilityStatus.COMPLETED
            elif found:
                status = CapabilityStatus.PARTIAL
            else:
                status = CapabilityStatus.PLANNED

        return CapabilityRecord(
            capability_id=definition.capability_id,
            name=definition.name,
            phase=definition.phase.value,
            sprint=definition.sprint,
            description=definition.description,
            status=status,
            module_paths=list(definition.module_paths),
            demo_paths=list(definition.demo_paths),
            artifacts_found=found,
            missing_artifacts=missing,
        )

    def detect_all(self) -> list[CapabilityRecord]:
        return [self.detect_capability(defn) for defn in self.all_definitions()]

    def by_phase(self, records: list[CapabilityRecord]) -> dict[str, list[CapabilityRecord]]:
        grouped: dict[str, list[CapabilityRecord]] = {
            phase.value: [] for phase in PHASE_ORDER
        }
        for record in records:
            grouped.setdefault(record.phase, []).append(record)
        return grouped
