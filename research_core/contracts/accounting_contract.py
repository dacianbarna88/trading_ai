"""Accounting subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class AccountingContract(BaseContract):
    CONTRACT_ID = "tae.contract.accounting.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Accounting"
    CANONICAL_MODULE = "research_core/accounting/independent_double_entry.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "independent_account_value",
        "independent_realized_pnl",
        "independent_total_pnl",
    )
    OPTIONAL_FIELDS = (
        "independent_cash",
        "independent_open_market_value",
        "independent_open_unrealized_pnl",
        "internal_reconciliation_delta",
        "delta_vs_existing_ledger",
        "delta_vs_dashboard_expected",
        "open_positions",
        "transaction_count",
    )
    OUTPUT_REPORTS = ("tae_independent_double_entry_verification.json",)
    CONSUMED_REPORTS = ()

    def _expected_schema(self) -> str | None:
        return "tae_independent_double_entry_verification"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        if "safety_mode" in payload and "NO_EXECUTION" not in str(payload["safety_mode"]):
            messages.append("safety_mode must include NO_EXECUTION banner")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
