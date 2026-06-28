"""Accounting integration adapter."""

from __future__ import annotations

from typing import Any

from research_core.contracts.accounting_contract import AccountingContract
from research_core.contracts.base_contract import BaseContract
from research_core.integration_adapters.base_adapter import BaseAdapter


class AccountingAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.accounting.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.accounting.v1"
    SUBSYSTEM_NAME = "Accounting"
    CANONICAL_MODULE = "research_core/accounting/independent_double_entry.py"
    PRIMARY_REPORT = "tae_independent_double_entry_verification.json"
    CANONICAL_REPORTS = (PRIMARY_REPORT,)
    OPTIONAL_REPORTS = (
        "tae_accounting_integration_report.json",
        "tae_accounting_dependency_map.json",
    )

    def _build_contract(self) -> BaseContract:
        return AccountingContract()

    @classmethod
    def load_accounting_state_for_auditor(cls, root: str | None = None) -> dict[str, Any]:
        """Read-only approved path for accounting integrity auditor consumption."""
        adapter = cls(root=root or ".")
        loaded = adapter.load_source()
        validation = adapter.validate_contract_payload()
        contract_payload = adapter.to_contract_payload()
        primary = loaded.sources.get(cls.PRIMARY_REPORT) or {}

        missing_optional = [
            name for name in cls.OPTIONAL_REPORTS if loaded.sources.get(name) is None
        ]

        if loaded.missing_reports:
            state_completeness = "DEGRADED"
        elif missing_optional:
            state_completeness = "PARTIAL"
        else:
            state_completeness = "FULL"

        contract_payload["contract_validation"] = validation
        contract_payload["accounting_state_completeness"] = state_completeness
        contract_payload["missing_optional_reports"] = missing_optional
        contract_payload["missing_primary_report"] = bool(loaded.missing_reports)
        contract_payload["primary_verdict"] = primary.get("verdict")
        contract_payload["integration_report"] = loaded.sources.get(
            "tae_accounting_integration_report.json"
        )
        contract_payload["dependency_map"] = loaded.sources.get(
            "tae_accounting_dependency_map.json"
        )
        contract_payload["adapter_path"] = "AccountingAdapter.load_accounting_state_for_auditor()"
        contract_payload["csv_validation_view_only"] = True
        return contract_payload
