"""Simulation integration adapter."""

from __future__ import annotations

from research_core.contracts.base_contract import BaseContract
from research_core.contracts.simulation_contract import SimulationContract
from research_core.integration_adapters.base_adapter import BaseAdapter


class SimulationAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.simulation.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.simulation.v1"
    SUBSYSTEM_NAME = "Simulation Lab"
    CANONICAL_MODULE = "research_core/simulation_lab/strategy_simulation_lab.py"
    PRIMARY_REPORT = "tae_continuous_strategy_simulation_lab.json"
    CANONICAL_REPORTS = (PRIMARY_REPORT,)
    OPTIONAL_REPORTS = ("tae_strategy_dependency_map.json",)

    def _build_contract(self) -> BaseContract:
        return SimulationContract()
