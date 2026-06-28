"""
Accounting Adapter Migration Report — Phase IX Sprint IX.3B

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Validates that Accounting Integrity Auditor consumes canonical accounting state
exclusively via AccountingAdapter (no direct independent_double_entry imports).
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.contracts.base_contract import SAFETY_BANNER
from research_core.integration_adapters.accounting_adapter import AccountingAdapter

REPORT_JSON = Path("tae_accounting_adapter_migration.json")
REPORT_TXT = Path("tae_accounting_adapter_migration.txt")

AUDITOR_PATH = Path("research_core/performance/accounting_integrity_auditor.py")
KERNEL_PATH = Path("research_core/accounting/independent_double_entry.py")
DIRECT_IMPORT_BEFORE = "research_core.accounting.independent_double_entry"
ADAPTER_METHOD = "load_accounting_state_for_auditor"

PROTECTED_PATHS = [
    "live_bot.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "config/settings.py",
    "core/trades.py",
    "core/portfolio_prices.py",
]

ACCOUNTING_MODULES_PROTECTED = [
    "research_core/accounting/independent_double_entry.py",
    "research_core/accounting/ledger_audit.py",
    "research_core/accounting/ledger_report.py",
]


@dataclass
class AccountingAdapterMigrationReport:
    safety_banner: str
    direct_dependency_before: str
    direct_dependency_after: str
    adapter_path_used: str
    accounting_contract_validation: dict[str, Any]
    accounting_auditor_canonical_state_source: str
    csv_validation_view_only: bool
    missing_canonical_accounting_reports: list[str]
    protected_files_unchanged: bool
    auditor_uses_adapter: bool
    direct_kernel_import_remains: bool
    kernel_module_unmodified: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_accounting_adapter_migration",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "direct_dependency_before": self.direct_dependency_before,
            "direct_dependency_after": self.direct_dependency_after,
            "adapter_path_used": self.adapter_path_used,
            "accounting_contract_validation": self.accounting_contract_validation,
            "accounting_auditor_canonical_state_source": (
                self.accounting_auditor_canonical_state_source
            ),
            "csv_validation_view_only": self.csv_validation_view_only,
            "missing_canonical_accounting_reports": list(
                self.missing_canonical_accounting_reports
            ),
            "protected_files_unchanged": self.protected_files_unchanged,
            "auditor_uses_adapter": self.auditor_uses_adapter,
            "direct_kernel_import_remains": self.direct_kernel_import_remains,
            "kernel_module_unmodified": self.kernel_module_unmodified,
        }

    def format_text(self) -> str:
        validation = self.accounting_contract_validation
        lines = [
            "===== TAE ACCOUNTING ADAPTER MIGRATION — SPRINT IX.3B =====",
            "",
            f"1. Safety banner: {self.safety_banner}",
            "",
            "2. Direct dependency before/after",
            f"   Before: {self.direct_dependency_before}",
            f"   After:  {self.direct_dependency_after}",
            "",
            "3. Adapter path used",
            f"   {self.adapter_path_used}",
            "",
            "4. Accounting contract validation status",
            f"   valid={validation.get('valid')} "
            f"status={validation.get('compatibility_status')} "
            f"payload_available={validation.get('payload_available')}",
            "",
            "5. Accounting auditor canonical state source",
            f"   {self.accounting_auditor_canonical_state_source}",
            "",
            "6. CSV validation remains view-only",
            f"   {self.csv_validation_view_only}",
            "",
            "7. Missing canonical accounting reports",
        ]
        if self.missing_canonical_accounting_reports:
            for report in self.missing_canonical_accounting_reports:
                lines.append(f"   - {report}")
        else:
            lines.append("   None — primary accounting report present")
        lines.extend([
            "",
            "8. Protected files unchanged",
            f"   {self.protected_files_unchanged}",
            "",
            f"9. Final verdict: {self.verdict}",
            "",
        ])
        return "\n".join(lines)


class AccountingAdapterMigrationAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(self, protected_ok: bool) -> AccountingAdapterMigrationReport:
        auditor_text = self._read_auditor_source()
        direct_import_remains = self._has_direct_kernel_import(auditor_text)
        uses_adapter = self._uses_accounting_adapter(auditor_text)

        adapter = AccountingAdapter(self._root)
        validation = adapter.validate_contract_payload()
        accounting_state = AccountingAdapter.load_accounting_state_for_auditor(str(self._root))

        missing_reports: list[str] = []
        loaded = adapter.load_source()
        missing_reports.extend(loaded.missing_reports)
        for name in accounting_state.get("missing_optional_reports") or []:
            if name not in missing_reports:
                missing_reports.append(name)

        kernel_ok = all((self._root / rel).is_file() for rel in ACCOUNTING_MODULES_PROTECTED)

        if direct_import_remains:
            verdict = "ACCOUNTING_ADAPTER_MIGRATION_FAILED_DIRECT_IMPORT_REMAINS"
        elif not protected_ok:
            verdict = "ACCOUNTING_ADAPTER_MIGRATION_FAILED_PROTECTED_FILE_MODIFIED"
        elif not uses_adapter:
            verdict = "ACCOUNTING_ADAPTER_MIGRATION_FAILED_DIRECT_IMPORT_REMAINS"
        elif accounting_state.get("accounting_state_completeness") in {"PARTIAL", "DEGRADED"}:
            verdict = "ACCOUNTING_ADAPTER_MIGRATION_READY_WITH_PARTIAL_STATE"
        else:
            verdict = "ACCOUNTING_ADAPTER_MIGRATION_READY"

        after_dependency = (
            f"{AUDITOR_PATH} → AccountingAdapter.{ADAPTER_METHOD}() → "
            f"tae.contract.accounting.v1"
            if not direct_import_remains
            else f"{AUDITOR_PATH} → {DIRECT_IMPORT_BEFORE} (UNMIGRATED)"
        )

        return AccountingAdapterMigrationReport(
            safety_banner=SAFETY_BANNER,
            direct_dependency_before=(
                f"{AUDITOR_PATH} → {DIRECT_IMPORT_BEFORE}.load_canonical_verification"
            ),
            direct_dependency_after=after_dependency,
            adapter_path_used=f"AccountingAdapter.{ADAPTER_METHOD}()",
            accounting_contract_validation=validation,
            accounting_auditor_canonical_state_source=accounting_state.get(
                "adapter_path",
                f"AccountingAdapter.{ADAPTER_METHOD}()",
            ),
            csv_validation_view_only=bool(accounting_state.get("csv_validation_view_only", True)),
            missing_canonical_accounting_reports=missing_reports,
            protected_files_unchanged=protected_ok,
            auditor_uses_adapter=uses_adapter,
            direct_kernel_import_remains=direct_import_remains,
            kernel_module_unmodified=kernel_ok,
            verdict=verdict,
        )

    def persist(self, report: AccountingAdapterMigrationReport) -> dict[str, Path]:
        json_path = self._root / REPORT_JSON
        txt_path = self._root / REPORT_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"json": json_path, "txt": txt_path}

    def _read_auditor_source(self) -> str:
        return (self._root / AUDITOR_PATH).read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _has_direct_kernel_import(source: str) -> bool:
        if DIRECT_IMPORT_BEFORE not in source:
            return False
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return DIRECT_IMPORT_BEFORE in source
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == DIRECT_IMPORT_BEFORE or node.module.startswith(
                    f"{DIRECT_IMPORT_BEFORE}."
                ):
                    return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == DIRECT_IMPORT_BEFORE or alias.name.startswith(
                        f"{DIRECT_IMPORT_BEFORE}."
                    ):
                        return True
        return False

    @staticmethod
    def _uses_accounting_adapter(source: str) -> bool:
        if "AccountingAdapter" not in source:
            return False
        return ADAPTER_METHOD in source


def protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def verify_protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file() or full.stat().st_mtime != mtime:
            return False
    return True
