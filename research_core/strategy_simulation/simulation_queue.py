"""
Simulation queue — Phase X Sprint X.3B

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

One queued simulation object per discovered strategy candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

QUEUE_STATUS_QUEUED = "QUEUED"


@dataclass
class SimulationQueueEntry:
    simulation_id: str
    linked_strategy: str
    status: str = QUEUE_STATUS_QUEUED

    def to_dict(self) -> dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "linked_strategy": self.linked_strategy,
            "status": self.status,
        }


def simulation_id_for_index(index: int) -> str:
    return f"SIM_{index + 1:06d}"


def build_simulation_queue(strategy_ids: list[str]) -> list[SimulationQueueEntry]:
    queue: list[SimulationQueueEntry] = []
    for index, strategy_id in enumerate(strategy_ids):
        queue.append(
            SimulationQueueEntry(
                simulation_id=simulation_id_for_index(index),
                linked_strategy=strategy_id,
                status=QUEUE_STATUS_QUEUED,
            )
        )
    return queue
