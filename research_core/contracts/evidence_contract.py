"""Evidence Registry subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class EvidenceContract(BaseContract):
    CONTRACT_ID = "tae.contract.evidence.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Evidence Registry"
    CANONICAL_MODULE = "research_core/evidence_engine/evidence_registry.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "registry_item_count",
        "evidence_items",
    )
    OPTIONAL_FIELDS = (
        "confirmed_count",
        "inconclusive_count",
        "rejected_count",
        "data_source_flags",
        "contradictions",
        "sources_loaded",
        "canonical_registry_source",
    )
    OUTPUT_REPORTS = ("tae_evidence_engine_report.json",)
    CONSUMED_REPORTS = (
        "tae_closed_freeze_statistical_audit.json",
        "tae_score_decomposition_anomaly.json",
        "tae_independent_double_entry_verification.json",
    )

    def _expected_schema(self) -> str | None:
        return "tae_evidence_engine_report"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        items = payload.get("evidence_items")
        if items is not None and not isinstance(items, list):
            messages.append("evidence_items must be a list")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
