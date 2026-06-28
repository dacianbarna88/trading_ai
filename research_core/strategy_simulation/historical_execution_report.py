"""
Historical Execution report — Phase X Sprint X.4

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.strategy_simulation.performance_metrics import METRIC_FIELDS

DEFAULT_JSON_PATH = Path("tae_historical_execution.json")
DEFAULT_TXT_PATH = Path("tae_historical_execution.txt")
CHECKPOINT_PATH = Path("tae_historical_execution_checkpoint.json")
RESEARCH_INPUT_PATH = Path("tae_historical_research.json")
DISCOVERY_INPUT_PATH = Path("tae_strategy_discovery.json")
SIMULATION_INPUT_PATH = Path("tae_strategy_simulation.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_historical_execution"
CHECKPOINT_SCHEMA = "tae_historical_execution_checkpoint"
EXECUTION_SAFETY_BANNER = (
    "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
)


class HistoricalExecutionVerdict(str, Enum):
    HISTORICAL_EXECUTION_READY = "HISTORICAL_EXECUTION_READY"
    HISTORICAL_EXECUTION_READY_WITH_WARNINGS = "HISTORICAL_EXECUTION_READY_WITH_WARNINGS"
    HISTORICAL_EXECUTION_BLOCKED = "HISTORICAL_EXECUTION_BLOCKED"


@dataclass
class ExecutionJobResult:
    research_job_id: str
    strategy_id: str
    simulation_id: str
    market: str
    time_horizon: str
    execution_status: str
    metrics: dict[str, float] | None = None
    block_reason: str | None = None
    trade_count: int = 0
    tickers_used: list[str] = field(default_factory=list)
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "research_job_id": self.research_job_id,
            "strategy_id": self.strategy_id,
            "simulation_id": self.simulation_id,
            "market": self.market,
            "time_horizon": self.time_horizon,
            "execution_status": self.execution_status,
            "trade_count": self.trade_count,
            "tickers_used": list(self.tickers_used),
            "executed_at": self.executed_at.isoformat(),
        }
        if self.metrics is not None:
            payload["metrics"] = dict(self.metrics)
        if self.block_reason:
            payload["block_reason"] = self.block_reason
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExecutionJobResult | None:
        if not isinstance(payload, dict) or not payload.get("research_job_id"):
            return None
        executed_raw = payload.get("executed_at")
        executed_at = datetime.now(timezone.utc)
        if isinstance(executed_raw, str):
            try:
                executed_at = datetime.fromisoformat(executed_raw)
            except ValueError:
                pass
        metrics = payload.get("metrics")
        return cls(
            research_job_id=str(payload["research_job_id"]),
            strategy_id=str(payload.get("strategy_id", "")),
            simulation_id=str(payload.get("simulation_id", "")),
            market=str(payload.get("market", "")),
            time_horizon=str(payload.get("time_horizon", "")),
            execution_status=str(payload.get("execution_status", "UNKNOWN")),
            metrics=dict(metrics) if isinstance(metrics, dict) else None,
            block_reason=str(payload["block_reason"]) if payload.get("block_reason") else None,
            trade_count=int(payload.get("trade_count", 0) or 0),
            tickers_used=list(payload.get("tickers_used") or []),
            executed_at=executed_at,
        )


@dataclass
class HistoricalExecutionReport:
    verdict: HistoricalExecutionVerdict
    jobs_total: int
    jobs_completed: int
    jobs_blocked: int
    jobs_failed: int
    jobs_pending: int
    jobs_processed_this_run: int
    batch_size: int
    batches_executed: int
    data_availability: dict[str, Any]
    results: list[ExecutionJobResult]
    schema_validation_passed: bool
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    input_files_unchanged: bool = True
    last_checkpoint_saved_at: str | None = None
    safety_mode: str = EXECUTION_SAFETY_BANNER
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
            "jobs_total": self.jobs_total,
            "jobs_completed": self.jobs_completed,
            "jobs_blocked": self.jobs_blocked,
            "jobs_failed": self.jobs_failed,
            "jobs_pending": self.jobs_pending,
            "jobs_processed_this_run": self.jobs_processed_this_run,
            "batch_size": self.batch_size,
            "batches_executed": self.batches_executed,
            "last_checkpoint_saved_at": self.last_checkpoint_saved_at,
            "data_availability": dict(self.data_availability),
            "schema_validation_passed": self.schema_validation_passed,
            "execution_results": [result.to_dict() for result in self.results],
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
            "input_files_unchanged": self.input_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE HISTORICAL EXECUTION ENGINE — SPRINT X.4 =====",
            "",
            f"Safety banner: {self.safety_mode}",
            "Mode: RESEARCH_ONLY | NO_BROKER | NO_PORTFOLIO_CHANGE",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            f"Input files unchanged: {self.input_files_unchanged}",
            "",
            "===== JOB SUMMARY =====",
            f"  Jobs total: {self.jobs_total}",
            f"  Jobs completed: {self.jobs_completed}",
            f"  Jobs blocked: {self.jobs_blocked}",
            f"  Jobs failed: {self.jobs_failed}",
            f"  Jobs pending: {self.jobs_pending}",
            f"  Jobs processed this run: {self.jobs_processed_this_run}",
            f"  Batch size: {self.batch_size}",
            f"  Batches executed this run: {self.batches_executed}",
        ]
        if self.last_checkpoint_saved_at:
            lines.append(f"  Last checkpoint saved: {self.last_checkpoint_saved_at}")
        lines.extend(
            [
                "",
                "===== DATA AVAILABILITY =====",
            ]
        )
        for key, value in self.data_availability.items():
            lines.append(f"  {key}: {value}")

        lines.extend(
            [
                "",
                "===== SCHEMA VALIDATION =====",
                f"  Metric fields expected: {len(METRIC_FIELDS)}",
                f"  Schema validation passed: {self.schema_validation_passed}",
                "",
                "===== SAMPLE RESULTS (first 5) =====",
            ]
        )

        for result in self.results[:5]:
            if result.execution_status == "COMPLETED" and result.metrics:
                lines.append(
                    f"  [{result.research_job_id}] {result.strategy_id} "
                    f"{result.market}/{result.time_horizon} → COMPLETED "
                    f"(trades={result.trade_count}, profit_pct={result.metrics.get('profit_pct')})"
                )
            else:
                lines.append(
                    f"  [{result.research_job_id}] {result.strategy_id} "
                    f"{result.market}/{result.time_horizon} → {result.execution_status}"
                    + (f" ({result.block_reason})" if result.block_reason else "")
                )

        if len(self.results) > 5:
            lines.append(f"  ... and {len(self.results) - 5} more results in report/checkpoint")

        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)


class HistoricalExecutionReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: HistoricalExecutionReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path


class HistoricalExecutionCheckpointStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or CHECKPOINT_PATH
        self._results: dict[str, ExecutionJobResult] = {}
        self._last_saved_at: str | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict) or payload.get("schema") != CHECKPOINT_SCHEMA:
            return False

        items = payload.get("completed_jobs", {})
        if not isinstance(items, dict):
            return False

        restored: dict[str, ExecutionJobResult] = {}
        for job_id, item in items.items():
            result = ExecutionJobResult.from_dict(item if isinstance(item, dict) else {})
            if result is not None:
                restored[job_id] = result
        self._results = restored
        self._last_saved_at = payload.get("saved_at") if isinstance(payload.get("saved_at"), str) else None
        return True

    def get(self, job_id: str) -> ExecutionJobResult | None:
        return self._results.get(job_id)

    def upsert(self, result: ExecutionJobResult) -> None:
        self._results[result.research_job_id] = result

    def all_results(self) -> list[ExecutionJobResult]:
        return sorted(self._results.values(), key=lambda item: item.research_job_id)

    def processed_ids(self) -> set[str]:
        """All job IDs already handled (completed, blocked, or failed)."""
        return set(self._results.keys())

    def completed_ids(self) -> set[str]:
        return self.processed_ids()

    @property
    def last_saved_at(self) -> str | None:
        return self._last_saved_at

    def persist(self) -> Path:
        saved_at = datetime.now(timezone.utc).isoformat()
        self._last_saved_at = saved_at
        payload = {
            "version": SCHEMA_VERSION,
            "schema": CHECKPOINT_SCHEMA,
            "saved_at": saved_at,
            "completed_count": len(self._results),
            "completed_jobs": {
                job_id: result.to_dict() for job_id, result in sorted(self._results.items())
            },
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path


def validate_completed_metrics(results: list[ExecutionJobResult]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    for result in results:
        if result.execution_status != "COMPLETED":
            continue
        if result.metrics is None:
            warnings.append(f"{result.research_job_id} COMPLETED without metrics")
            continue
        missing = [field for field in METRIC_FIELDS if field not in result.metrics]
        if missing:
            warnings.append(f"{result.research_job_id} missing metrics: {missing}")
        for field in METRIC_FIELDS:
            value = result.metrics.get(field)
            if isinstance(value, str) and value == "PENDING":
                warnings.append(f"{result.research_job_id} has placeholder metric {field}")
    return len(warnings) == 0, warnings
