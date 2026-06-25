"""TAE ecosystem organisms — live research module wrappers."""

from research_core.ecosystem.organisms.context_organism import ContextOrganism, ORGANISM_NAME as CONTEXT_ORGANISM_NAME
from research_core.ecosystem.organisms.evidence_organism import EvidenceOrganism, ORGANISM_NAME as EVIDENCE_ORGANISM_NAME
from research_core.ecosystem.organisms.momentum_organism import MomentumOrganism, ORGANISM_NAME as MOMENTUM_ORGANISM_NAME

__all__ = [
    "ContextOrganism",
    "CONTEXT_ORGANISM_NAME",
    "EvidenceOrganism",
    "EVIDENCE_ORGANISM_NAME",
    "MomentumOrganism",
    "MOMENTUM_ORGANISM_NAME",
]
