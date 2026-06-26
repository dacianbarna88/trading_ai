"""Evidence gap analysis — Phase VI Sprint B3 (research roadmap only)."""

from research_core.evidence_gap.evidence_gap import EvidenceGapAnalyzer
from research_core.evidence_gap.evidence_gap_report import (
    CandidateGapAnalysis,
    DEFAULT_GAP_JSON_PATH,
    DEFAULT_GAP_TXT_PATH,
    EvidenceGapReport,
    EvidenceGapStore,
    GapCategory,
    MissingEvidenceItem,
    ResearchAction,
)

__all__ = [
    "CandidateGapAnalysis",
    "DEFAULT_GAP_JSON_PATH",
    "DEFAULT_GAP_TXT_PATH",
    "EvidenceGapAnalyzer",
    "EvidenceGapReport",
    "EvidenceGapStore",
    "GapCategory",
    "MissingEvidenceItem",
    "ResearchAction",
]
