"""Accounting integration adapter."""

from __future__ import annotations

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
    OPTIONAL_REPORTS = ("tae_accounting_integration_report.json",)

    def _build_contract(self) -> BaseContract:
        return AccountingContract()
