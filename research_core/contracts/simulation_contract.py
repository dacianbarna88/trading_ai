"""Simulation Lab subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class SimulationContract(BaseContract):
    CONTRACT_ID = "tae.contract.simulation.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Simulation Lab"
    CANONICAL_MODULE = "research_core/simulation_lab/strategy_simulation_lab.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "best_strategy_by_total_pnl",
        "strategies",
    )
    OPTIONAL_FIELDS = (
        "best_strategy_by_profit_factor",
        "strategy_rankings",
        "baseline_total_pnl",
        "buy_rows_total",
        "pipeline_reference",
    )
    OUTPUT_REPORTS = ("tae_continuous_strategy_simulation_lab.json",)
    CONSUMED_REPORTS = ("tae_independent_double_entry_verification.json",)

    def _expected_schema(self) -> str | None:
        return "tae_continuous_strategy_simulation_lab"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        if payload.get("strategies") is not None and not isinstance(payload["strategies"], list):
            messages.append("strategies must be a list")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
