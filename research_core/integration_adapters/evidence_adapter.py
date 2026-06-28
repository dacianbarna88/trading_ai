"""Evidence integration adapter."""

from __future__ import annotations

from research_core.contracts.base_contract import BaseContract
from research_core.contracts.evidence_contract import EvidenceContract
from research_core.integration_adapters.base_adapter import BaseAdapter


class EvidenceAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.evidence.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.evidence.v1"
    SUBSYSTEM_NAME = "Evidence Registry"
    CANONICAL_MODULE = "research_core/evidence_engine/evidence_registry.py"
    PRIMARY_REPORT = "tae_evidence_engine_report.json"
    CANONICAL_REPORTS = (PRIMARY_REPORT,)
    OPTIONAL_REPORTS = ("tae_evidence_integration_report.json",)

    def _build_contract(self) -> BaseContract:
        return EvidenceContract()
