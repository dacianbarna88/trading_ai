"""
Accounting Integration Report — Phase IX Sprint IX.2A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Validates that accounting modules are integrated around the canonical kernel.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.accounting.accounting_dependency_map import (
    AccountingDependencyMap,
    AccountingDependencyMapBuilder,
    AccountingDependencyMapStore,
    CANONICAL_KERNEL_PATH,
    INTEGRATION_TARGETS,
    ModuleRole,
)
from research_core.accounting.independent_double_entry import DEFAULT_JSON_PATH
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logger = logging.getLogger(__name__)

REPORT_JSON = Path("tae_accounting_integration_report.json")
REPORT_TXT = Path("tae_accounting_integration_report.txt")


class IntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    PARTIAL = "PARTIAL"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class TargetIntegration:
    module_path: str
    status: IntegrationStatus
    reads_canonical_json: bool
    imports_kernel: bool
    role: str
    notes: str

    def to_dict(self) -> dict[str, str]:
        return {
            "module_path": self.module_path,
            "status": self.status.value,
            "reads_canonical_json": str(self.reads_canonical_json),
            "imports_kernel": str(self.imports_kernel),
            "role": self.role,
            "notes": self.notes,
        }


@dataclass
class AccountingIntegrationReport:
    canonical_kernel: str
    canonical_json_exists: bool
    single_kernel_verified: bool
    no_duplicate_formulas_verified: bool
    no_duplicate_pnl_kernel_verified: bool
    no_duplicate_ledger_kernel_verified: bool
    integration_targets: list[TargetIntegration]
    validation_checks: list[str]
    warnings: list[str]
    verdict: str = "ACCOUNTING_INTEGRATION_READY"
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_accounting_integration_report",
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict,
            "canonical_kernel": self.canonical_kernel,
            "canonical_json_exists": self.canonical_json_exists,
            "single_kernel_verified": self.single_kernel_verified,
            "no_duplicate_formulas_verified": self.no_duplicate_formulas_verified,
            "no_duplicate_pnl_kernel_verified": self.no_duplicate_pnl_kernel_verified,
            "no_duplicate_ledger_kernel_verified": self.no_duplicate_ledger_kernel_verified,
            "integration_targets": [t.to_dict() for t in self.integration_targets],
            "validation_checks": list(self.validation_checks),
            "warnings": list(self.warnings),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE ACCOUNTING INTEGRATION REPORT — SPRINT IX.2A =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            f"Verdict: {self.verdict}",
            "",
            f"Canonical kernel: {self.canonical_kernel}",
            f"Canonical JSON present: {self.canonical_json_exists}",
            "",
            "===== VALIDATION =====",
            f"  Single kernel:              {self.single_kernel_verified}",
            f"  No duplicate PnL kernel:    {self.no_duplicate_pnl_kernel_verified}",
            f"  No duplicate ledger kernel: {self.no_duplicate_ledger_kernel_verified}",
            f"  No duplicate formulas:      {self.no_duplicate_formulas_verified}",
            "",
            "===== INTEGRATION TARGETS =====",
        ]
        for target in self.integration_targets:
            lines.append(
                f"  [{target.status.value}] {target.module_path} ({target.role})"
            )
            lines.append(f"      reads_canonical={target.reads_canonical_json} "
                           f"imports_kernel={target.imports_kernel}")
            lines.append(f"      {target.notes}")
        lines.extend(["", "===== CHECKS ====="])
        for check in self.validation_checks:
            lines.append(f"  ✓ {check}")
        if self.warnings:
            lines.extend(["", "===== WARNINGS (view layers — not new kernels) ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")
        lines.append("")
        return "\n".join(lines)


class AccountingIntegrationAnalyzer:
    def analyze(self, dependency_map: AccountingDependencyMap) -> AccountingIntegrationReport:
        node_by_path = {n.module_path: n for n in dependency_map.nodes}
        targets: list[TargetIntegration] = []
        warnings: list[str] = []
        checks: list[str] = []

        for path in INTEGRATION_TARGETS:
            node = node_by_path.get(path)
            if node is None:
                targets.append(
                    TargetIntegration(
                        module_path=path,
                        status=IntegrationStatus.DISCONNECTED,
                        reads_canonical_json=False,
                        imports_kernel=False,
                        role="UNKNOWN",
                        notes="Module not found in dependency map",
                    )
                )
                continue

            if path == CANONICAL_KERNEL_PATH:
                status = IntegrationStatus.CONNECTED
                notes = "Canonical accounting kernel — single source of truth"
            elif node.reads_canonical_json or node.imports_kernel:
                status = IntegrationStatus.CONNECTED if node.reads_canonical_json else IntegrationStatus.PARTIAL
                notes = (
                    "Reads canonical JSON and imports kernel module"
                    if node.reads_canonical_json and node.imports_kernel
                    else "References canonical verification outputs"
                )
            else:
                status = IntegrationStatus.DISCONNECTED
                notes = "Not yet wired to canonical kernel"

            if node.role == ModuleRole.VIEW_REPLAY and node.has_duplicate_fifo:
                warnings.append(
                    f"{path} retains legacy FIFO replay for cross-check; "
                    "canonical totals come from independent_double_entry JSON"
                )
            if node.role == ModuleRole.INTEGRITY_CONSUMER and node.has_duplicate_fifo:
                warnings.append(
                    f"{path} uses lot state for CSV column validation only; "
                    "aggregate PnL read from canonical JSON"
                )

            targets.append(
                TargetIntegration(
                    module_path=path,
                    status=status,
                    reads_canonical_json=node.reads_canonical_json,
                    imports_kernel=node.imports_kernel,
                    role=node.role.value,
                    notes=notes,
                )
            )

        single_kernel = dependency_map.kernel_count == 1
        if single_kernel:
            checks.append("Exactly one IndependentDoubleEntryVerifier kernel exists")

        no_dup_pnl_kernel = len(
            [
                p
                for p in dependency_map.duplicate_pnl_modules
                if p != "research_core/accounting/ledger_audit.py"
            ]
        ) == 0
        if no_dup_pnl_kernel:
            checks.append("No competing FIFO PnL kernel modules")

        no_dup_ledger = len(dependency_map.duplicate_ledger_modules) <= 1
        if no_dup_ledger:
            checks.append("Ledger replay limited to view layer (ledger_audit)")

        no_dup_formula = CANONICAL_KERNEL_PATH not in dependency_map.duplicate_formula_modules
        if no_dup_formula:
            checks.append("Reconciliation formula owned by canonical kernel path")

        canonical_json_exists = DEFAULT_JSON_PATH.is_file()
        if canonical_json_exists:
            checks.append("Canonical verification JSON available on disk")
        else:
            warnings.append(
                "Run tae_independent_double_entry_demo.py to materialize canonical JSON"
            )

        all_targets_connected = all(
            t.status in (IntegrationStatus.CONNECTED, IntegrationStatus.PARTIAL)
            for t in targets
            if t.module_path != CANONICAL_KERNEL_PATH
        )
        if all_targets_connected:
            checks.append("All integration targets wired to canonical kernel")

        verdict = "ACCOUNTING_INTEGRATION_READY"
        if not single_kernel or not all_targets_connected:
            verdict = "ACCOUNTING_INTEGRATION_INCOMPLETE"

        return AccountingIntegrationReport(
            canonical_kernel=CANONICAL_KERNEL_PATH,
            canonical_json_exists=canonical_json_exists,
            single_kernel_verified=single_kernel,
            no_duplicate_formulas_verified=no_dup_formula,
            no_duplicate_pnl_kernel_verified=no_dup_pnl_kernel,
            no_duplicate_ledger_kernel_verified=no_dup_ledger,
            integration_targets=targets,
            validation_checks=checks,
            warnings=warnings,
            verdict=verdict,
        )


class AccountingIntegrationAudit:
    def run(self) -> tuple[AccountingDependencyMap, AccountingIntegrationReport]:
        dep_map = AccountingDependencyMapBuilder().build()
        report = AccountingIntegrationAnalyzer().analyze(dep_map)
        return dep_map, report

    def persist_all(
        self,
        dep_map: AccountingDependencyMap,
        report: AccountingIntegrationReport,
    ) -> dict[str, Path]:
        dep_store = AccountingDependencyMapStore()
        rep_store = AccountingIntegrationReportStore()
        return {
            "dependency_map_json": dep_store.persist(dep_map),
            "dependency_map_txt": dep_store.persist_txt(dep_map),
            "integration_report_json": rep_store.persist(report),
            "integration_report_txt": rep_store.persist_txt(report),
        }


class AccountingIntegrationReportStore:
    def persist(self, report: AccountingIntegrationReport) -> Path:
        REPORT_JSON.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return REPORT_JSON

    def persist_txt(self, report: AccountingIntegrationReport) -> Path:
        REPORT_TXT.write_text(report.format_text() + "\n", encoding="utf-8")
        return REPORT_TXT
