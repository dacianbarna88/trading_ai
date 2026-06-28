"""Strategy evolution integration adapter — approved orchestrator consumption path."""

from __future__ import annotations

from typing import Any

from research_core.contracts.base_contract import BaseContract
from research_core.contracts.strategy_contract import StrategyContract
from research_core.integration_adapters.base_adapter import AdapterLoadResult, BaseAdapter


class StrategyAdapter(BaseAdapter):
    ADAPTER_ID = "tae.adapter.strategy_evolution.v1"
    VERSION = "1"
    CONTRACT_ID = "tae.contract.strategy_evolution.v1"
    SUBSYSTEM_NAME = "Strategy Evolution Daily Runner"
    CANONICAL_MODULE = "research_core/strategy_evolution/daily_runner.py"
    PRIMARY_REPORT = "tae_strategy_evolution_daily_runner.json"
    CANONICAL_REPORTS = (
        PRIMARY_REPORT,
        "tae_candidate_strategy_registry.json",
        "tae_parallel_paper_validation.json",
        "tae_continuous_strategy_ranking.json",
        "tae_strategy_promotion_gate.json",
        "tae_paper_tracking_log.json",
    )
    OPTIONAL_REPORTS = ("tae_strategy_integration_report.json",)

    def _build_contract(self) -> BaseContract:
        return StrategyContract()

    def load_source(self) -> AdapterLoadResult:
        loaded = super().load_source()
        if loaded.missing_reports:
            return loaded
        return loaded

    def to_contract_payload(self) -> dict[str, Any]:
        payload = super().to_contract_payload()
        loaded = self.load_source()
        payload["pipeline_step_reports"] = {
            name: name in loaded.sources and loaded.sources[name] is not None
            for name in self.CANONICAL_REPORTS
            if name != self.PRIMARY_REPORT
        }
        payload["approved_orchestrator_path"] = True
        return payload

    @classmethod
    def load_strategy_state_for_orchestrator(cls, root: str | None = None) -> dict[str, Any]:
        """Read-only approved path for orchestrator to consume strategy evolution state."""
        adapter = cls(root=root or ".")
        loaded = adapter.load_source()
        validation = adapter.validate_contract_payload()
        contract_payload = adapter.to_contract_payload()
        primary = loaded.sources.get(cls.PRIMARY_REPORT) or {}

        missing_step_reports = [
            name
            for name in cls.CANONICAL_REPORTS
            if name != cls.PRIMARY_REPORT and loaded.sources.get(name) is None
        ]

        if loaded.missing_reports:
            state_completeness = "DEGRADED"
        elif missing_step_reports:
            state_completeness = "PARTIAL"
        else:
            state_completeness = "FULL"

        daily_runner_verdict = primary.get("verdict") if primary else None
        if not daily_runner_verdict and loaded.missing_reports:
            daily_runner_verdict = "STRATEGY_EVOLUTION_STATE_DEGRADED"

        contract_payload["contract_validation"] = validation
        contract_payload["strategy_state_completeness"] = state_completeness
        contract_payload["missing_step_reports"] = missing_step_reports
        contract_payload["missing_primary_report"] = bool(loaded.missing_reports)
        contract_payload["daily_runner_verdict"] = daily_runner_verdict
        contract_payload["promotion_gate"] = loaded.sources.get("tae_strategy_promotion_gate.json")
        contract_payload["paper_tracking"] = loaded.sources.get("tae_paper_tracking_log.json")
        contract_payload["adapter_path"] = (
            "StrategyAdapter.load_strategy_state_for_orchestrator()"
        )
        return contract_payload
