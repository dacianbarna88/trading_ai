"""
Strategy Simulation report — Phase X Sprint X.3B

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_simulation.performance_metrics import METRIC_FIELDS
from research_core.strategy_simulation.simulation_queue import SimulationQueueEntry
from research_core.strategy_simulation.simulation_registry import (
    MARKETS,
    TIME_HORIZONS,
    SimulationRecord,
)

DEFAULT_JSON_PATH = Path("tae_strategy_simulation.json")
DEFAULT_TXT_PATH = Path("tae_strategy_simulation.txt")
DISCOVERY_INPUT_PATH = Path("tae_strategy_discovery.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategy_simulation"
SIMULATION_SAFETY_BANNER = "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class StrategySimulationVerdict(str, Enum):
    STRATEGY_SIMULATION_ENGINE_READY = "STRATEGY_SIMULATION_ENGINE_READY"
    STRATEGY_SIMULATION_READY_WITH_WARNINGS = "STRATEGY_SIMULATION_READY_WITH_WARNINGS"
    STRATEGY_SIMULATION_INPUT_MISSING = "STRATEGY_SIMULATION_INPUT_MISSING"


@dataclass
class StrategySimulationReport:
    verdict: StrategySimulationVerdict
    discovery_candidates_loaded: int
    simulation_records_created: int
    queue: list[SimulationQueueEntry]
    registry: list[SimulationRecord]
    markets: list[str]
    time_horizons: list[str]
    schema_validation_passed: bool
    registry_completeness_passed: bool
    performance_metric_fields: list[str]
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    safety_mode: str = SIMULATION_SAFETY_BANNER
    research_only: bool = True
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "research_only": self.research_only,
            "verdict": self.verdict.value,
            "discovery_candidates_loaded": self.discovery_candidates_loaded,
            "simulation_records_created": self.simulation_records_created,
            "markets": list(self.markets),
            "time_horizons": list(self.time_horizons),
            "performance_metric_fields": list(self.performance_metric_fields),
            "schema_validation_passed": self.schema_validation_passed,
            "registry_completeness_passed": self.registry_completeness_passed,
            "simulation_queue": [entry.to_dict() for entry in self.queue],
            "simulation_registry": [record.to_dict() for record in self.registry],
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE STRATEGY SIMULATION ENGINE — SPRINT X.3B =====",
            "",
            f"Safety banner: {self.safety_mode}",
            "Mode: RESEARCH_ONLY | NO_HISTORICAL_EXECUTION",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== INPUT =====",
            f"  Discovery input: {DISCOVERY_INPUT_PATH.name}",
            f"  Discovery candidates loaded: {self.discovery_candidates_loaded}",
            f"  Simulation records created: {self.simulation_records_created}",
            "",
            "===== MARKETS =====",
        ]
        for market in self.markets:
            lines.append(f"  • {market}")

        lines.extend(["", "===== TIME HORIZONS ====="])
        for horizon in self.time_horizons:
            lines.append(f"  • {horizon}")

        lines.extend(
            [
                "",
                "===== SCHEMA VALIDATION =====",
                f"  Performance metric fields: {len(self.performance_metric_fields)}",
                f"  Schema validation passed: {self.schema_validation_passed}",
                f"  Registry completeness passed: {self.registry_completeness_passed}",
                "",
                "===== SAMPLE QUEUE (first 5) =====",
            ]
        )

        for entry in self.queue[:5]:
            lines.append(
                f"  [{entry.simulation_id}] → {entry.linked_strategy} | status: {entry.status}"
            )

        if len(self.queue) > 5:
            lines.append(f"  ... and {len(self.queue) - 5} more queued simulations")

        lines.extend(["", "===== SAMPLE REGISTRY (first 3) ====="])
        for record in self.registry[:3]:
            lines.extend(
                [
                    f"  [{record.simulation_id}] strategy: {record.strategy_id}",
                    f"    Status: {record.simulation_status} | Research: {record.research_state}",
                    f"    Metrics: all PENDING ({len(record.performance_metrics)} fields)",
                    "",
                ]
            )

        if self.warnings:
            lines.extend(["===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)


class StrategySimulationReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: StrategySimulationReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
