"""Runtime workflow integration adapter."""

from __future__ import annotations

from research_core.contracts.base_contract import BaseContract
from research_core.contracts.runtime_contract import RuntimeContract
from research_core.integration_adapters.base_adapter import BaseAdapter


class RuntimeAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.runtime.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.runtime.v1"
    SUBSYSTEM_NAME = "Runtime Workflow"
    CANONICAL_MODULE = "research_core/runtime/workflow_engine.py"
    PRIMARY_REPORT = "tae_runtime_foundation.json"
    CANONICAL_REPORTS = (PRIMARY_REPORT,)
    OPTIONAL_REPORTS = ("tae_runtime_learning_memory.json",)

    def _build_contract(self) -> BaseContract:
        return RuntimeContract()
