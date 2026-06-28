"""TAE Evidence Engine — Phase VII / IX.2B integration hub (read-only)."""

from research_core.evidence_engine.evidence_registry import (
    CANONICAL_REGISTRY_MODULE,
    CANONICAL_REPORT_PATH,
    EvidenceEngine,
    EvidenceRegistry,
    load_canonical_evidence_report,
)
from research_core.evidence_engine.evidence_report import (
    CANONICAL_REGISTRY_SOURCE,
    EvidenceContradiction,
    EvidenceEngineReport,
    EvidenceEngineVerdict,
    EvidenceItem,
    EvidenceReportStore,
    EvidenceRiskLevel,
    EvidenceStatus,
    ImplementationEligibility,
    SAFETY_BANNER,
)

__all__ = [
    "CANONICAL_REGISTRY_MODULE",
    "CANONICAL_REGISTRY_SOURCE",
    "CANONICAL_REPORT_PATH",
    "EvidenceContradiction",
    "EvidenceEngine",
    "EvidenceRegistry",
    "EvidenceEngineReport",
    "EvidenceEngineVerdict",
    "EvidenceItem",
    "EvidenceReportStore",
    "EvidenceRiskLevel",
    "EvidenceStatus",
    "ImplementationEligibility",
    "SAFETY_BANNER",
    "load_canonical_evidence_report",
]
