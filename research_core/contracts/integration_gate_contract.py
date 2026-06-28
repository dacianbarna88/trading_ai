"""Integration Gate subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class IntegrationGateContract(BaseContract):
    CONTRACT_ID = "tae.contract.integration_gate.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Integration Gate"
    CANONICAL_MODULE = "integration_layer/evidence_gate.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "decisions",
    )
    OPTIONAL_FIELDS = (
        "engine_aligned",
        "allowed_count",
        "blocked_count",
        "status_counts",
        "source_report",
    )
    OUTPUT_REPORTS = ("tae_evidence_integration_gate.json",)
    CONSUMED_REPORTS = ("tae_evidence_engine_report.json",)

    def _expected_schema(self) -> str | None:
        return "tae_evidence_integration_gate"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        if payload.get("decisions") is not None and not isinstance(payload["decisions"], list):
            messages.append("decisions must be a list")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
