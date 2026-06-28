"""Integration adapter layer — Phase IX Sprint IX.3."""

from research_core.integration_adapters.base_adapter import (
    ADAPTER_RULE,
    AdapterDescription,
    AdapterLoadResult,
    AdapterStatus,
    BaseAdapter,
    SAFETY_BANNER,
    read_json_report,
)
from research_core.integration_adapters.accounting_adapter import AccountingAdapter
from research_core.integration_adapters.evidence_adapter import EvidenceAdapter
from research_core.integration_adapters.simulation_adapter import SimulationAdapter
from research_core.integration_adapters.strategy_adapter import StrategyAdapter
from research_core.integration_adapters.integration_gate_adapter import IntegrationGateAdapter
from research_core.integration_adapters.orchestrator_adapter import OrchestratorAdapter
from research_core.integration_adapters.runtime_adapter import RuntimeAdapter
from research_core.integration_adapters.adapter_registry import (
    all_adapters,
    adapter_by_id,
    adapter_by_contract,
    AdapterRegistryBuilder,
    AdapterRegistryReport,
)
from research_core.integration_adapters.adapter_dependency_map import (
    AdapterDependencyMapBuilder,
    AdapterDependencyMapReport,
)
from research_core.integration_adapters.adapter_report import (
    EcosystemAdapterAudit,
    AdapterLayerReport,
    PROTECTED_PATHS,
)

__all__ = [
    "ADAPTER_RULE",
    "AdapterDescription",
    "AdapterLoadResult",
    "AdapterStatus",
    "BaseAdapter",
    "AccountingAdapter",
    "EvidenceAdapter",
    "SimulationAdapter",
    "StrategyAdapter",
    "IntegrationGateAdapter",
    "OrchestratorAdapter",
    "RuntimeAdapter",
    "all_adapters",
    "adapter_by_id",
    "adapter_by_contract",
    "AdapterRegistryBuilder",
    "AdapterRegistryReport",
    "AdapterDependencyMapBuilder",
    "AdapterDependencyMapReport",
    "EcosystemAdapterAudit",
    "AdapterLayerReport",
    "PROTECTED_PATHS",
    "read_json_report",
]
