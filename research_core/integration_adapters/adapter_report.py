"""Integration adapter master report — Phase IX Sprint IX.3."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import CompatibilityStatus, SAFETY_BANNER
from research_core.integration_adapters.adapter_dependency_map import (
    AdapterDependencyMapBuilder,
    AdapterDependencyMapReport,
    AdapterDependencyMapStore,
)
from research_core.integration_adapters.adapter_registry import (
    REGISTRY_JSON,
    REGISTRY_TXT,
    AdapterRegistryBuilder,
    AdapterRegistryReport,
    AdapterRegistryStore,
    all_adapters,
)
from research_core.integration_adapters.base_adapter import AdapterStatus

REPORT_JSON = "tae_adapter_report.json"
REPORT_TXT = "tae_adapter_report.txt"

PROTECTED_PATHS = [
    "live_bot.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "config/settings.py",
    "core/trades.py",
    "core/portfolio_prices.py",
]

FORBIDDEN_ADAPTER_PATTERNS = [
    (re.compile(r"\bplace_order\b"), "broker call"),
    (re.compile(r"\blive_bot\b"), "live execution reference"),
    (re.compile(r"portfolio\.csv.*write|write.*portfolio\.csv", re.I), "portfolio mutation"),
    (re.compile(r"\b_process_fifo\b"), "accounting formula"),
    (re.compile(r"\brecompute_portfolio\b"), "accounting formula"),
    (re.compile(r'["\']BUY["\']|["\']SELL["\']'), "trading instruction"),
]

ADAPTER_SOURCE_FILES = [
    "research_core/integration_adapters/base_adapter.py",
    "research_core/integration_adapters/accounting_adapter.py",
    "research_core/integration_adapters/evidence_adapter.py",
    "research_core/integration_adapters/simulation_adapter.py",
    "research_core/integration_adapters/strategy_adapter.py",
    "research_core/integration_adapters/integration_gate_adapter.py",
    "research_core/integration_adapters/orchestrator_adapter.py",
    "research_core/integration_adapters/runtime_adapter.py",
]


@dataclass
class AdapterValidationRow:
    adapter_id: str
    contract_id: str
    adapter_status: str
    valid: bool
    compatibility_status: str
    missing_required: list[str]
    primary_report_present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "contract_id": self.contract_id,
            "adapter_status": self.adapter_status,
            "valid": self.valid,
            "compatibility_status": self.compatibility_status,
            "missing_required": list(self.missing_required),
            "primary_report_present": self.primary_report_present,
        }


@dataclass
class AdapterLayerReport:
    safety_banner: str
    adapter_registry: dict[str, Any]
    adapter_validation_matrix: list[dict[str, Any]]
    contract_compatibility_matrix: list[dict[str, Any]]
    dependency_map: dict[str, Any]
    direct_dependency_warnings: list[dict[str, Any]]
    adapter_migration_recommendations: list[str]
    missing_canonical_reports: list[dict[str, str]]
    forbidden_dependencies: list[dict[str, str]]
    duplicate_adapter_check: list[str]
    read_only_verification: dict[str, Any]
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_adapter_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "adapter_registry": self.adapter_registry,
            "adapter_validation_matrix": list(self.adapter_validation_matrix),
            "contract_compatibility_matrix": list(self.contract_compatibility_matrix),
            "dependency_map_summary": {
                "adapter_compliant_count": self.dependency_map.get("adapter_compliant_count", 0),
                "needs_migration_count": self.dependency_map.get("needs_migration_count", 0),
                "legacy_direct_link_count": self.dependency_map.get("legacy_direct_link_count", 0),
                "forbidden_count": self.dependency_map.get("forbidden_count", 0),
            },
            "direct_dependency_warnings": list(self.direct_dependency_warnings),
            "adapter_migration_recommendations": list(self.adapter_migration_recommendations),
            "missing_canonical_reports": list(self.missing_canonical_reports),
            "forbidden_dependencies": list(self.forbidden_dependencies),
            "duplicate_adapter_check": list(self.duplicate_adapter_check),
            "read_only_verification": dict(self.read_only_verification),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE INTEGRATION ADAPTER LAYER REPORT — SPRINT IX.3 =====",
            "",
            f"1. Safety banner: {self.safety_banner}",
            "",
            "2. Adapter registry",
        ]
        for entry in self.adapter_registry.get("adapters", []):
            lines.append(
                f"   {entry['adapter_id']} — {entry['subsystem_name']} "
                f"[{entry['adapter_status']}] contract={entry['contract_id']}"
            )
        lines.extend(["", "3. Adapter validation matrix"])
        for row in self.adapter_validation_matrix:
            lines.append(
                f"   {row['adapter_id']}: {row['adapter_status']} "
                f"valid={row['valid']} report={row['primary_report_present']}"
            )
        lines.extend(["", "4. Contract compatibility matrix"])
        for row in self.contract_compatibility_matrix:
            lines.append(
                f"   {row['contract_id']}: {row['compatibility_status']} "
                f"(adapter: {row['adapter_id']})"
            )
        lines.extend(["", "5. Direct dependency warnings"])
        for warn in self.direct_dependency_warnings[:25]:
            lines.append(
                f"   [{warn['classification']}] {warn['source_subsystem']} → "
                f"{warn['target_subsystem']}: {warn['source_module']}"
            )
        lines.extend(["", "6. Adapter migration recommendations"])
        for rec in self.adapter_migration_recommendations[:20]:
            lines.append(f"   • {rec}")
        lines.extend(["", "7. Missing canonical report list"])
        if self.missing_canonical_reports:
            for item in self.missing_canonical_reports:
                lines.append(f"   {item['adapter_id']}: {item['report']}")
        else:
            lines.append("   None — all primary reports present")
        lines.extend(["", "8. Forbidden dependency list"])
        if self.forbidden_dependencies:
            for item in self.forbidden_dependencies:
                lines.append(
                    f"   {item.get('source_module', '?')} → "
                    f"{item.get('target_module', '?')}"
                )
        else:
            lines.append("   None detected")
        lines.extend(["", "9. Protected files unchanged"])
        lines.append(f"   {self.protected_files_unchanged}")
        lines.extend(["", "10. Read-only verification"])
        lines.append(f"   Adapters scanned: {self.read_only_verification.get('files_scanned', 0)}")
        lines.append(f"   Forbidden patterns: {self.read_only_verification.get('violations', [])}")
        lines.append("")
        lines.append(f"Final verdict: {self.verdict}")
        lines.append("")
        return "\n".join(lines)


def _verify_read_only_adapters(root: Path) -> dict[str, Any]:
    violations: list[str] = []
    for rel in ADAPTER_SOURCE_FILES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in FORBIDDEN_ADAPTER_PATTERNS:
            if pattern.search(text):
                violations.append(f"{rel}: {label}")
        if ".write_text(" in text and "adapter" not in rel:
            violations.append(f"{rel}: file write detected")
    return {
        "files_scanned": len(ADAPTER_SOURCE_FILES),
        "violations": violations,
        "read_only": len(violations) == 0,
    }


def _validation_matrix(root: Path) -> tuple[list[dict], list[dict]]:
    adapter_rows: list[dict] = []
    contract_rows: list[dict] = []
    for adapter in all_adapters(root):
        validation = adapter.validate_contract_payload()
        loaded = adapter.load_source()
        primary_present = loaded.sources.get(adapter.PRIMARY_REPORT) is not None
        row = AdapterValidationRow(
            adapter_id=adapter.ADAPTER_ID,
            contract_id=adapter.CONTRACT_ID,
            adapter_status=adapter.adapter_status().value,
            valid=bool(validation.get("valid")),
            compatibility_status=str(validation.get("compatibility_status", "UNKNOWN")),
            missing_required=list(validation.get("missing_required") or []),
            primary_report_present=primary_present,
        )
        adapter_rows.append(row.to_dict())
        contract_rows.append(
            {
                "contract_id": adapter.CONTRACT_ID,
                "adapter_id": adapter.ADAPTER_ID,
                "compatibility_status": row.compatibility_status,
                "valid": row.valid,
            }
        )
    return adapter_rows, contract_rows


class EcosystemAdapterAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(self, protected_ok: bool) -> tuple[
        AdapterRegistryReport,
        AdapterDependencyMapReport,
        AdapterLayerReport,
    ]:
        registry = AdapterRegistryBuilder().build(self._root)
        dep_map = AdapterDependencyMapBuilder(self._root).build()
        adapter_matrix, contract_matrix = _validation_matrix(self._root)
        read_only = _verify_read_only_adapters(self._root)

        warnings = [
            e.to_dict()
            for e in dep_map.edges
            if e.classification != AdapterStatus.ADAPTER_COMPLIANT
        ]

        all_adapters_ok = (
            len(all_adapters(self._root)) == 7
            and not dep_map.duplicate_adapter_check
            and not dep_map.missing_adapter_coverage
            and read_only["read_only"]
        )

        has_migration_backlog = (
            dep_map.needs_migration_count > 0
            or dep_map.legacy_direct_link_count > 0
            or dep_map.forbidden_count > 0
        )

        if not protected_ok:
            verdict = "ECOSYSTEM_ADAPTER_LAYER_FAILED_PROTECTED_FILE_MODIFIED"
        elif all_adapters_ok and not has_migration_backlog:
            verdict = "ECOSYSTEM_ADAPTER_LAYER_READY"
        elif all_adapters_ok:
            verdict = "ECOSYSTEM_ADAPTER_LAYER_READY_WITH_MIGRATION_BACKLOG"
        else:
            verdict = "ECOSYSTEM_ADAPTER_LAYER_READY_WITH_MIGRATION_BACKLOG"

        report = AdapterLayerReport(
            safety_banner=SAFETY_BANNER,
            adapter_registry=registry.to_dict(),
            adapter_validation_matrix=adapter_matrix,
            contract_compatibility_matrix=contract_matrix,
            dependency_map=dep_map.to_dict(),
            direct_dependency_warnings=warnings,
            adapter_migration_recommendations=dep_map.adapter_migration_recommendations,
            missing_canonical_reports=dep_map.missing_canonical_reports,
            forbidden_dependencies=dep_map.forbidden_dependencies,
            duplicate_adapter_check=dep_map.duplicate_adapter_check,
            read_only_verification=read_only,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )
        return registry, dep_map, report

    def persist_all(
        self,
        registry: AdapterRegistryReport,
        dep_map: AdapterDependencyMapReport,
        report: AdapterLayerReport,
    ) -> dict[str, Path]:
        reg_store = AdapterRegistryStore()
        dep_store = AdapterDependencyMapStore()
        paths = {
            "registry_json": reg_store.persist(registry, self._root),
            "registry_txt": reg_store.persist_txt(registry, self._root),
            "dependency_map_json": dep_store.persist(dep_map, self._root),
            "dependency_map_txt": dep_store.persist_txt(dep_map, self._root),
            "report_json": self._root / REPORT_JSON,
            "report_txt": self._root / REPORT_TXT,
        }
        paths["report_json"].write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        paths["report_txt"].write_text(report.format_text() + "\n", encoding="utf-8")
        return paths
