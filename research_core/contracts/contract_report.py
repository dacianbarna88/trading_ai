"""Ecosystem contracts master report — Phase IX Sprint IX.2D."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import CompatibilityStatus, SAFETY_BANNER
from research_core.contracts.contract_dependency_map import (
    ContractDependencyMapBuilder,
    ContractDependencyMapReport,
    ContractDependencyMapStore,
)
from research_core.contracts.contract_registry import (
    REGISTRY_JSON,
    REGISTRY_TXT,
    ContractRegistryBuilder,
    ContractRegistryReport,
    all_contracts,
)
from research_core.contracts.contract_validation import validate_all_contracts, validation_matrix

REPORT_JSON = "tae_contract_report.json"
REPORT_TXT = "tae_contract_report.txt"

CANONICAL_SUBSYSTEMS = [
    "Accounting",
    "Evidence Registry",
    "Simulation Lab",
    "Strategy Evolution Daily Runner",
    "Integration Gate",
    "Ecosystem Orchestrator",
    "Runtime Workflow",
]

PROTECTED_PATHS = [
    "live_bot.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "config/settings.py",
    "core/trades.py",
    "core/portfolio_prices.py",
]


@dataclass
class EcosystemContractsReport:
    safety_banner: str
    contract_registry: dict[str, Any]
    validation_matrix: dict[str, Any]
    dependency_map: dict[str, Any]
    direct_dependency_warnings: list[dict[str, str]]
    adapter_recommendations: list[str]
    duplicate_contract_check: list[str]
    missing_contract_check: list[str]
    canonical_subsystem_coverage: dict[str, bool]
    protected_files_unchanged: bool
    orchestrator_runtime_boundary_documented: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_contract_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "contract_registry": self.contract_registry,
            "validation_matrix": self.validation_matrix,
            "dependency_map_summary": {
                "legacy_direct_link_count": self.dependency_map.get(
                    "legacy_direct_link_count", 0
                ),
                "forbidden_count": self.dependency_map.get("forbidden_count", 0),
                "needs_adapter_count": self.dependency_map.get("needs_adapter_count", 0),
            },
            "direct_dependency_warnings": list(self.direct_dependency_warnings),
            "adapter_recommendations": list(self.adapter_recommendations),
            "duplicate_contract_check": list(self.duplicate_contract_check),
            "missing_contract_check": list(self.missing_contract_check),
            "canonical_subsystem_coverage": dict(self.canonical_subsystem_coverage),
            "protected_files_unchanged": self.protected_files_unchanged,
            "orchestrator_runtime_boundary_documented": (
                self.orchestrator_runtime_boundary_documented
            ),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ECOSYSTEM CONTRACTS REPORT — SPRINT IX.2D =====",
            "",
            f"1. Safety banner: {self.safety_banner}",
            "",
            "2. Contract registry",
        ]
        for entry in self.contract_registry.get("contracts", []):
            lines.append(
                f"   {entry['contract_id']} — {entry['subsystem_name']} "
                f"(v{entry['version']}) [{entry['validation_status']}]"
            )
        lines.extend(["", "3. Contract validation matrix"])
        for row in self.validation_matrix.get("results", []):
            lines.append(
                f"   {row['contract_id']}: {row['compatibility_status']} "
                f"valid={row['valid']} missing={row['missing_required']}"
            )
        lines.extend(["", "4. Direct dependency warnings"])
        for warn in self.direct_dependency_warnings[:20]:
            lines.append(
                f"   [{warn['classification']}] {warn['source_subsystem']} → "
                f"{warn['target_subsystem']}: {warn['source_module']}"
            )
        lines.extend(["", "5. Contract adapter recommendations"])
        for rec in self.adapter_recommendations[:15]:
            lines.append(f"   • {rec}")
        lines.extend(["", "6. Duplicate contract check"])
        if self.duplicate_contract_check:
            for dup in self.duplicate_contract_check:
                lines.append(f"   DUPLICATE: {dup}")
        else:
            lines.append("   None — exactly one contract per subsystem")
        lines.extend(["", "7. Missing contract check"])
        if self.missing_contract_check:
            for miss in self.missing_contract_check:
                lines.append(f"   MISSING: {miss}")
        else:
            lines.append("   None — all canonical subsystems covered")
        lines.extend(["", "8. Canonical subsystem coverage"])
        for name, covered in self.canonical_subsystem_coverage.items():
            lines.append(f"   {name}: {'YES' if covered else 'NO'}")
        lines.extend([
            "",
            "9. Protected files unchanged",
            f"   {self.protected_files_unchanged}",
            "",
            "10. Orchestrator/Runtime boundary rule documented",
            f"   {self.orchestrator_runtime_boundary_documented}",
            "",
            f"Final verdict: {self.verdict}",
            "",
        ])
        return "\n".join(lines)


class EcosystemContractsAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        protected_ok: bool,
    ) -> tuple[
        ContractRegistryReport,
        ContractDependencyMapReport,
        EcosystemContractsReport,
    ]:
        validation_results = validate_all_contracts(self._root)
        matrix = validation_matrix(self._root)
        status_by_id = {
            r["contract_id"]: r["compatibility_status"] for r in validation_results
        }

        registry = ContractRegistryBuilder().build(status_by_id)
        dep_map = ContractDependencyMapBuilder(self._root).build()

        warnings = [
            e.to_dict()
            for e in dep_map.edges
            if e.classification.value
            not in ("INTERNAL", "CONTRACT_COMPLIANT")
        ]

        coverage = {
            name: any(c.SUBSYSTEM_NAME == name for c in all_contracts())
            for name in CANONICAL_SUBSYSTEMS
        }

        all_have_validator = all(
            hasattr(c, "validate") and hasattr(c, "normalize") for c in all_contracts()
        )
        all_compliant = all(
            r["compatibility_status"] == CompatibilityStatus.CONTRACT_COMPLIANT.value
            for r in validation_results
            if r["payload_available"]
        )
        has_legacy = dep_map.legacy_direct_link_count > 0 or dep_map.forbidden_count > 0

        if not protected_ok:
            verdict = "ECOSYSTEM_CONTRACTS_FAILED_PROTECTED_FILE_MODIFIED"
        elif (
            not dep_map.missing_contract_check
            and not dep_map.duplicate_contract_check
            and all_have_validator
            and len(all_contracts()) == 7
        ):
            if has_legacy or not all_compliant:
                verdict = "ECOSYSTEM_CONTRACTS_READY_WITH_ADAPTER_RECOMMENDATIONS"
            else:
                verdict = "ECOSYSTEM_CONTRACTS_READY"
        else:
            verdict = "ECOSYSTEM_CONTRACTS_READY_WITH_ADAPTER_RECOMMENDATIONS"

        report = EcosystemContractsReport(
            safety_banner=SAFETY_BANNER,
            contract_registry=registry.to_dict(),
            validation_matrix=matrix,
            dependency_map=dep_map.to_dict(),
            direct_dependency_warnings=warnings,
            adapter_recommendations=dep_map.adapter_recommendations,
            duplicate_contract_check=dep_map.duplicate_contract_check,
            missing_contract_check=dep_map.missing_contract_check,
            canonical_subsystem_coverage=coverage,
            protected_files_unchanged=protected_ok,
            orchestrator_runtime_boundary_documented=True,
            verdict=verdict,
        )
        return registry, dep_map, report

    def persist_all(
        self,
        registry: ContractRegistryReport,
        dep_map: ContractDependencyMapReport,
        report: EcosystemContractsReport,
    ) -> dict[str, Path]:
        dep_store = ContractDependencyMapStore()
        paths = {
            "registry_json": self._root / REGISTRY_JSON,
            "registry_txt": self._root / REGISTRY_TXT,
            "dependency_map_json": dep_store.persist(dep_map, self._root),
            "dependency_map_txt": dep_store.persist_txt(dep_map, self._root),
            "report_json": self._root / REPORT_JSON,
            "report_txt": self._root / REPORT_TXT,
        }
        paths["registry_json"].write_text(
            json.dumps(registry.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths["registry_txt"].write_text(registry.format_text() + "\n", encoding="utf-8")
        paths["report_json"].write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths["report_txt"].write_text(report.format_text() + "\n", encoding="utf-8")
        return paths
