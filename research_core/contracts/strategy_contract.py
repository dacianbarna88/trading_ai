"""Strategy Evolution Daily Runner subsystem contract."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract, ContractValidationResult


class StrategyContract(BaseContract):
    CONTRACT_ID = "tae.contract.strategy_evolution.v1"
    VERSION = "1"
    SUBSYSTEM_NAME = "Strategy Evolution Daily Runner"
    CANONICAL_MODULE = "research_core/strategy_evolution/daily_runner.py"
    REQUIRED_FIELDS = (
        "version",
        "schema",
        "generated_at",
        "safety_mode",
        "verdict",
        "steps",
        "protected_files_unchanged",
    )
    OPTIONAL_FIELDS = (
        "top_ranked_strategy_id",
        "top_ranked_strategy_score",
        "promotion_review_candidate_id",
        "paper_tracking_needs",
        "canonical_pipeline",
    )
    OUTPUT_REPORTS = ("tae_strategy_evolution_daily_runner.json",)
    CONSUMED_REPORTS = (
        "tae_candidate_strategy_registry.json",
        "tae_parallel_paper_validation.json",
        "tae_continuous_strategy_ranking.json",
        "tae_strategy_promotion_gate.json",
        "tae_paper_tracking_log.json",
        "tae_evidence_engine_report.json",
        "tae_continuous_strategy_simulation_lab.json",
    )

    def _expected_schema(self) -> str | None:
        return "tae_strategy_evolution_daily_runner"

    def _extra_validation(self, payload: dict[str, Any]) -> ContractValidationResult:
        messages: list[str] = []
        valid = True
        steps = payload.get("steps")
        if steps is not None and not isinstance(steps, list):
            messages.append("steps must be a list")
            valid = False
        return ContractValidationResult(
            contract_id=self.CONTRACT_ID,
            subsystem_name=self.SUBSYSTEM_NAME,
            report_path=self.OUTPUT_REPORTS[0],
            payload_available=True,
            valid=valid,
            messages=messages,
        )
