"""
Simulation registry — Phase X Sprint X.3B

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Canonical simulation records linked to discovery candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from research_core.strategy_simulation.performance_metrics import (
    pending_performance_metrics,
    validate_performance_metrics_schema,
)
from research_core.strategy_simulation.simulation_queue import (
    QUEUE_STATUS_QUEUED,
    SimulationQueueEntry,
)

MARKETS: tuple[str, ...] = ("US", "EU", "UK", "ASIA")
TIME_HORIZONS: tuple[str, ...] = ("2Y", "5Y", "10Y", "20Y")


class ResearchState(str, Enum):
    DISCOVERY = "DISCOVERY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


FOUNDATION_RESEARCH_STATE = ResearchState.QUEUED.value
FOUNDATION_SIMULATION_STATUS = QUEUE_STATUS_QUEUED


@dataclass
class SimulationRecord:
    simulation_id: str
    strategy_id: str
    created_at: datetime
    simulation_status: str
    markets: list[str]
    time_horizons: list[str]
    performance_metrics: dict[str, str]
    research_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "strategy_id": self.strategy_id,
            "created_at": self.created_at.isoformat(),
            "simulation_status": self.simulation_status,
            "markets": list(self.markets),
            "time_horizons": list(self.time_horizons),
            "performance_metrics": dict(self.performance_metrics),
            "research_state": self.research_state,
        }


def build_simulation_registry(
    queue: list[SimulationQueueEntry],
    created_at: datetime | None = None,
) -> list[SimulationRecord]:
    timestamp = created_at or datetime.now(timezone.utc)
    records: list[SimulationRecord] = []

    for entry in queue:
        records.append(
            SimulationRecord(
                simulation_id=entry.simulation_id,
                strategy_id=entry.linked_strategy,
                created_at=timestamp,
                simulation_status=FOUNDATION_SIMULATION_STATUS,
                markets=list(MARKETS),
                time_horizons=list(TIME_HORIZONS),
                performance_metrics=pending_performance_metrics(),
                research_state=FOUNDATION_RESEARCH_STATE,
            )
        )

    return records


def validate_registry_completeness(
    strategy_ids: list[str],
    records: list[SimulationRecord],
) -> tuple[bool, list[str]]:
    warnings: list[str] = []

    if len(records) != len(strategy_ids):
        warnings.append(
            f"Registry count {len(records)} != discovery count {len(strategy_ids)}"
        )

    record_strategies = {record.strategy_id for record in records}
    for strategy_id in strategy_ids:
        if strategy_id not in record_strategies:
            warnings.append(f"Missing simulation record for {strategy_id}")

    simulation_ids = [record.simulation_id for record in records]
    if len(simulation_ids) != len(set(simulation_ids)):
        warnings.append("Duplicate simulation IDs in registry")

    for record in records:
        metrics_ok, metric_warnings = validate_performance_metrics_schema(
            record.performance_metrics
        )
        if not metrics_ok:
            warnings.extend(metric_warnings)

        if record.research_state != FOUNDATION_RESEARCH_STATE:
            warnings.append(
                f"{record.simulation_id} research_state expected "
                f"{FOUNDATION_RESEARCH_STATE}, got {record.research_state}"
            )

    return len(warnings) == 0, warnings
