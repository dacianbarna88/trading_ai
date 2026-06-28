"""Integration gate adapter."""

from __future__ import annotations

from research_core.contracts.base_contract import BaseContract
from research_core.contracts.integration_gate_contract import IntegrationGateContract
from research_core.integration_adapters.base_adapter import BaseAdapter


class IntegrationGateAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.integration_gate.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.integration_gate.v1"
    SUBSYSTEM_NAME = "Integration Gate"
    CANONICAL_MODULE = "integration_layer/evidence_gate.py"
    PRIMARY_REPORT = "tae_evidence_integration_gate.json"
    CANONICAL_REPORTS = (PRIMARY_REPORT,)
    OPTIONAL_REPORTS = ()

    def _build_contract(self) -> BaseContract:
        return IntegrationGateContract()
