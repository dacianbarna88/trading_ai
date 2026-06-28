"""Integration adapter registry — Phase IX Sprint IX.3."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import SAFETY_BANNER
from research_core.integration_adapters.accounting_adapter import AccountingAdapter
from research_core.integration_adapters.base_adapter import BaseAdapter
from research_core.integration_adapters.evidence_adapter import EvidenceAdapter
from research_core.integration_adapters.integration_gate_adapter import IntegrationGateAdapter
from research_core.integration_adapters.orchestrator_adapter import OrchestratorAdapter
from research_core.integration_adapters.runtime_adapter import RuntimeAdapter
from research_core.integration_adapters.simulation_adapter import SimulationAdapter
from research_core.integration_adapters.strategy_adapter import StrategyAdapter

REGISTRY_JSON = "tae_adapter_registry.json"
REGISTRY_TXT = "tae_adapter_registry.txt"

INTEGRATION_RULE = (
    "Module A → Contract → Adapter → Canonical JSON → Adapter → Contract → Module B"
)


def all_adapters(root: Path | str = Path(".")) -> list[BaseAdapter]:
    return [
        AccountingAdapter(root),
        EvidenceAdapter(root),
        SimulationAdapter(root),
        StrategyAdapter(root),
        IntegrationGateAdapter(root),
        OrchestratorAdapter(root),
        RuntimeAdapter(root),
    ]


def adapter_by_id(adapter_id: str, root: Path | str = Path(".")) -> BaseAdapter | None:
    for adapter in all_adapters(root):
        if adapter.ADAPTER_ID == adapter_id:
            return adapter
    return None


def adapter_by_contract(contract_id: str, root: Path | str = Path(".")) -> BaseAdapter | None:
    for adapter in all_adapters(root):
        if adapter.CONTRACT_ID == contract_id:
            return adapter
    return None


@dataclass
class AdapterRegistryEntry:
    adapter_id: str
    version: str
    contract_id: str
    subsystem_name: str
    canonical_module: str
    canonical_reports: list[str]
    optional_reports: list[str]
    validation_status: str
    adapter_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "contract_id": self.contract_id,
            "subsystem_name": self.subsystem_name,
            "canonical_module": self.canonical_module,
            "canonical_reports": list(self.canonical_reports),
            "optional_reports": list(self.optional_reports),
            "validation_status": self.validation_status,
            "adapter_status": self.adapter_status,
        }


@dataclass
class AdapterRegistryReport:
    adapters: list[AdapterRegistryEntry]
    integration_rule: str
    adapter_count: int
    contract_coverage: int
    verdict: str = "ADAPTER_REGISTRY_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_adapter_registry",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "integration_rule": self.integration_rule,
            "adapter_count": self.adapter_count,
            "contract_coverage": self.contract_coverage,
            "adapters": [a.to_dict() for a in self.adapters],
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ADAPTER REGISTRY — SPRINT IX.3 =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            f"Integration rule: {self.integration_rule}",
            "",
            f"Adapters: {self.adapter_count} | Contract coverage: {self.contract_coverage}/7",
            "",
            "===== REGISTERED ADAPTERS =====",
        ]
        for entry in self.adapters:
            lines.append(
                f"  {entry.adapter_id} — {entry.subsystem_name} "
                f"(contract: {entry.contract_id})"
            )
            lines.append(f"    Module: {entry.canonical_module}")
            lines.append(f"    Reports: {', '.join(entry.canonical_reports)}")
            lines.append(
                f"    Status: {entry.adapter_status} | Validation: {entry.validation_status}"
            )
        lines.append("")
        return "\n".join(lines)


class AdapterRegistryBuilder:
    def build(self, root: Path | str = Path(".")) -> AdapterRegistryReport:
        entries: list[AdapterRegistryEntry] = []
        for adapter in all_adapters(root):
            validation = adapter.validate_contract_payload()
            desc = adapter.describe()
            entries.append(
                AdapterRegistryEntry(
                    adapter_id=desc.adapter_id,
                    version=desc.version,
                    contract_id=desc.contract_id,
                    subsystem_name=desc.subsystem_name,
                    canonical_module=desc.canonical_module,
                    canonical_reports=desc.canonical_reports,
                    optional_reports=desc.optional_reports,
                    validation_status=validation.get("compatibility_status", "UNKNOWN"),
                    adapter_status=adapter.adapter_status().value,
                )
            )

        contract_ids = {e.contract_id for e in entries}
        adapter_ids = [e.adapter_id for e in entries]
        dup_adapters = [aid for aid in adapter_ids if adapter_ids.count(aid) > 1]
        verdict = "ADAPTER_REGISTRY_READY"
        if len(entries) != 7 or len(contract_ids) != 7 or dup_adapters:
            verdict = "ADAPTER_REGISTRY_INCOMPLETE"

        return AdapterRegistryReport(
            adapters=entries,
            integration_rule=INTEGRATION_RULE,
            adapter_count=len(entries),
            contract_coverage=len(contract_ids),
            verdict=verdict,
        )


class AdapterRegistryStore:
    def persist(self, report: AdapterRegistryReport, root: Path | str = Path(".")) -> Path:
        path = Path(root) / REGISTRY_JSON
        path.write_text(
            __import__("json").dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def persist_txt(self, report: AdapterRegistryReport, root: Path | str = Path(".")) -> Path:
        path = Path(root) / REGISTRY_TXT
        path.write_text(report.format_text() + "\n", encoding="utf-8")
        return path
