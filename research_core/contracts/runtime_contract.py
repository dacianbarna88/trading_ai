"""Runtime Workflow subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class RuntimeContract(BaseContract):
    CONTRACT_ID = "tae.contract.runtime.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Runtime Workflow"
    CANONICAL_MODULE = "research_core/runtime/workflow_engine.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "loaded_state_sources",
        "health_status",
        "protected_files_unchanged",
    )
    OPTIONAL_FIELDS = (
        "workflow_steps",
        "health_checks",
        "health_issues",
        "health_issue_count",
        "learning_memory_summary",
        "top_ranked_strategy_id",
        "promotion_review_candidate_id",
        "paper_tracking_needs",
        "missing_connections",
        "conflict_warnings",
        "events_emitted",
    )
    OUTPUT_REPORTS = ("tae_runtime_foundation.json",)
    CONSUMED_REPORTS = (
        "tae_ecosystem_orchestrator.json",
        "tae_evidence_engine_report.json",
        "tae_strategy_evolution_daily_runner.json",
    )

    def _expected_schema(self) -> str | None:
        return "tae_runtime_foundation"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        sources = payload.get("loaded_state_sources")
        if sources is not None and not isinstance(sources, dict):
            messages.append("loaded_state_sources must be a dict")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
