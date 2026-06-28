"""Ecosystem Orchestrator subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class OrchestratorContract(BaseContract):
    CONTRACT_ID = "tae.contract.orchestrator.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Ecosystem Orchestrator"
    CANONICAL_MODULE = "research_core/orchestrator/ecosystem_orchestrator.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "steps",
        "subsystem_verdicts",
        "protected_files_unchanged",
    )
    OPTIONAL_FIELDS = (
        "top_ranked_strategy_id",
        "top_ranked_strategy_score",
        "promotion_review_candidate_id",
        "promotion_gate_summary",
        "paper_tracking_summary",
        "missing_connections",
        "do_not_rewrite",
        "final_ecosystem_recommendation",
    )
    OUTPUT_REPORTS = ("tae_ecosystem_orchestrator.json",)
    CONSUMED_REPORTS = (
        "tae_evidence_engine_report.json",
        "tae_strategy_evolution_daily_runner.json",
        "tae_evidence_integration_gate.json",
    )

    def _expected_schema(self) -> str | None:
        return "tae_ecosystem_orchestrator"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        if payload.get("do_not_rewrite") is not None and not isinstance(
            payload["do_not_rewrite"], list
        ):
            messages.append("do_not_rewrite must be a list")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
