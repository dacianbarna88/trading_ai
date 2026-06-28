"""Canonical contract registry — Phase IX Sprint IX.2D."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_core.contracts.accounting_contract import AccountingContract
from research_core.contracts.base_contract import BaseContract, SAFETY_BANNER
from research_core.contracts.evidence_contract import EvidenceContract
from research_core.contracts.integration_gate_contract import IntegrationGateContract
from research_core.contracts.orchestrator_contract import OrchestratorContract
from research_core.contracts.runtime_contract import RuntimeContract
from research_core.contracts.simulation_contract import SimulationContract
from research_core.contracts.strategy_contract import StrategyContract

REGISTRY_JSON = "tae_contract_registry.json"
REGISTRY_TXT = "tae_contract_registry.txt"


def all_contracts() -> list[BaseContract]:
    return [
        AccountingContract(),
        EvidenceContract(),
        SimulationContract(),
        StrategyContract(),
        IntegrationGateContract(),
        OrchestratorContract(),
        RuntimeContract(),
    ]


def contract_by_id(contract_id: str) -> BaseContract | None:
    for contract in all_contracts():
        if contract.CONTRACT_ID == contract_id:
            return contract
    return None


@dataclass
class ContractRegistryEntry:
    contract_id: str
    version: str
    subsystem_name: str
    canonical_module: str
    output_reports: list[str]
    consumed_reports: list[str]
    validation_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "subsystem_name": self.subsystem_name,
            "canonical_module": self.canonical_module,
            "output_reports": list(self.output_reports),
            "consumed_reports": list(self.consumed_reports),
            "validation_status": self.validation_status,
        }


@dataclass
class ContractRegistryReport:
    contracts: list[ContractRegistryEntry]
    integration_rule: str
    boundary_rule: str
    verdict: str = "CONTRACT_REGISTRY_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_contract_registry",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "integration_rule": self.integration_rule,
            "boundary_rule": self.boundary_rule,
            "contract_count": len(self.contracts),
            "contracts": [c.to_dict() for c in self.contracts],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE CONTRACT REGISTRY — SPRINT IX.2D =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Integration rule: {self.integration_rule}",
            f"Boundary rule: {self.boundary_rule}",
            "",
            "===== CONTRACTS =====",
        ]
        for entry in self.contracts:
            lines.append(
                f"  {entry.contract_id} v{entry.version} — {entry.subsystem_name}"
            )
            lines.append(f"    module: {entry.canonical_module}")
            lines.append(f"    outputs: {', '.join(entry.output_reports)}")
            if entry.consumed_reports:
                lines.append(f"    consumes: {', '.join(entry.consumed_reports)}")
            lines.append(f"    validation: {entry.validation_status}")
        lines.append("")
        return "\n".join(lines)


class ContractRegistryBuilder:
    BOUNDARY_RULE = (
        "Orchestrator and Runtime must consume subsystem outputs only via "
        "contract-shaped JSON — never internal implementation imports."
    )

    def build(self, validation_status_by_id: dict[str, str] | None = None) -> ContractRegistryReport:
        statuses = validation_status_by_id or {}
        entries: list[ContractRegistryEntry] = []
        for contract in all_contracts():
            desc = contract.describe()
            entries.append(
                ContractRegistryEntry(
                    contract_id=desc.contract_id,
                    version=desc.version,
                    subsystem_name=desc.subsystem_name,
                    canonical_module=desc.canonical_module,
                    output_reports=desc.output_reports,
                    consumed_reports=desc.consumed_reports,
                    validation_status=statuses.get(
                        desc.contract_id, "NOT_VALIDATED"
                    ),
                )
            )
        return ContractRegistryReport(
            contracts=entries,
            integration_rule="Module A → Contract → Module B",
            boundary_rule=self.BOUNDARY_RULE,
        )
