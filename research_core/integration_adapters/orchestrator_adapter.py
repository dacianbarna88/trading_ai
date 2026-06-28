"""Orchestrator integration adapter."""

from __future__ import annotations

from research_core.contracts.base_contract import BaseContract
from research_core.contracts.orchestrator_contract import OrchestratorContract
from research_core.integration_adapters.base_adapter import BaseAdapter


class OrchestratorAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.orchestrator.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.orchestrator.v1"
    SUBSYSTEM_NAME = "Ecosystem Orchestrator"
    CANONICAL_MODULE = "research_core/orchestrator/ecosystem_orchestrator.py"
    PRIMARY_REPORT = "tae_ecosystem_orchestrator.json"
    CANONICAL_REPORTS = (PRIMARY_REPORT,)
    OPTIONAL_REPORTS = ("tae_ecosystem_inventory.json",)

    def _build_contract(self) -> BaseContract:
        return OrchestratorContract()
