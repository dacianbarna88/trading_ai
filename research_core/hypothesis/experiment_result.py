"""
Experiment result model — Sprint 5.1

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Structured outcome of testing a hypothesis against historical research data.
Not a trade signal or execution instruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from research_core.hypothesis.hypothesis_model import SAFETY_MODE


class ExperimentStatus(str, Enum):
    TESTED = "TESTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    ERROR = "ERROR"


@dataclass
class ExperimentResult:
    experiment_id: str
    hypothesis_id: str
    hypothesis_title: str
    sample_size: int
    wins: int
    losses: int
    neutral: int
    accuracy: float
    avg_forward_return: float
    horizon: str
    status: ExperimentStatus
    tested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""
    safety_mode: str = SAFETY_MODE

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_title": self.hypothesis_title,
            "sample_size": self.sample_size,
            "wins": self.wins,
            "losses": self.losses,
            "neutral": self.neutral,
            "accuracy": round(self.accuracy, 4),
            "avg_forward_return": round(self.avg_forward_return, 4),
            "horizon": self.horizon,
            "status": self.status.value,
            "tested_at": self.tested_at.isoformat(),
            "notes": self.notes,
            "safety_mode": self.safety_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentResult | None:
        try:
            tested = data.get("tested_at")
            if tested:
                dt = datetime.fromisoformat(str(tested).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            status_raw = str(data.get("status", ExperimentStatus.TESTED.value))
            try:
                status = ExperimentStatus(status_raw)
            except ValueError:
                status = ExperimentStatus.TESTED

            return cls(
                experiment_id=str(data["experiment_id"]),
                hypothesis_id=str(data.get("hypothesis_id", "")),
                hypothesis_title=str(data.get("hypothesis_title", "")),
                sample_size=int(data.get("sample_size", 0)),
                wins=int(data.get("wins", 0)),
                losses=int(data.get("losses", 0)),
                neutral=int(data.get("neutral", 0)),
                accuracy=float(data.get("accuracy", 0)),
                avg_forward_return=float(data.get("avg_forward_return", 0)),
                horizon=str(data.get("horizon", "")),
                status=status,
                tested_at=dt,
                notes=str(data.get("notes", "")),
                safety_mode=str(data.get("safety_mode", SAFETY_MODE)),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.experiment_id} | {self.hypothesis_id} | "
            f"n={self.sample_size} acc={self.accuracy:.2%} "
            f"avg_ret={self.avg_forward_return:.2f}% [{self.status.value}]"
        )
