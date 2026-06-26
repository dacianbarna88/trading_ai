"""TAE Evidence Integration Gate — paper-only integration layer."""

from integration_layer.evidence_gate import (
    ELIGIBILITY_TO_GATE,
    ENGINE_ALIGNED_VERDICT,
    EVIDENCE_ENGINE_REPORT_PATH,
    IMPLEMENTATION_ALLOWLIST,
    EvidenceIntegrationGate,
)
from integration_layer.integration_report import (
    IntegrationGateReport,
    IntegrationGateVerdict,
    IntegrationReportStore,
    GateDecision,
    GateStatus,
    SAFETY_BANNER,
)

__all__ = [
    "ELIGIBILITY_TO_GATE",
    "ENGINE_ALIGNED_VERDICT",
    "EVIDENCE_ENGINE_REPORT_PATH",
    "IMPLEMENTATION_ALLOWLIST",
    "EvidenceIntegrationGate",
    "GateDecision",
    "GateStatus",
    "IntegrationGateReport",
    "IntegrationGateVerdict",
    "IntegrationReportStore",
    "SAFETY_BANNER",
]
