"""
Historical Execution Engine — Phase X Sprint X.4

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Executes queued historical research jobs via real backtest logic with resumable batching.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_simulation.historical_backtest_runner import (
    StrategyBacktestRunner,
    check_data_availability,
)
from research_core.strategy_simulation.historical_execution_report import (
    DISCOVERY_INPUT_PATH,
    ExecutionJobResult,
    HistoricalExecutionCheckpointStore,
    HistoricalExecutionReport,
    HistoricalExecutionVerdict,
    RESEARCH_INPUT_PATH,
    SIMULATION_INPUT_PATH,
    validate_completed_metrics,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10
INPUT_PATHS = (RESEARCH_INPUT_PATH, DISCOVERY_INPUT_PATH, SIMULATION_INPUT_PATH)


class HistoricalExecutionEngine:
    """Turns RESEARCH_QUEUED jobs into completed or clearly blocked backtest results."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._warnings: list[str] = []

    def run(self, batch_size: int = DEFAULT_BATCH_SIZE) -> HistoricalExecutionReport:
        if batch_size <= 0:
            batch_size = DEFAULT_BATCH_SIZE

        before_protected = self._snapshot_protected_mtimes()
        before_inputs = self._snapshot_input_mtimes()

        research_payload = self._load_json(RESEARCH_INPUT_PATH)
        discovery_payload = self._load_json(DISCOVERY_INPUT_PATH)
        simulation_payload = self._load_json(SIMULATION_INPUT_PATH)

        if research_payload is None:
            return self._blocked_report(
                batch_size=batch_size,
                before_protected=before_protected,
                after_protected=self._snapshot_protected_mtimes(),
                before_inputs=before_inputs,
                after_inputs=self._snapshot_input_mtimes(),
                reason="Missing tae_historical_research.json",
            )

        jobs = self._extract_research_jobs(research_payload)
        strategy_map = self._build_strategy_map(discovery_payload)
        if simulation_payload is None:
            self._warnings.append("Simulation input missing; proceeding with research + discovery only.")

        data = check_data_availability(self._root)
        if not data.available:
            return self._blocked_report(
                batch_size=batch_size,
                before_protected=before_protected,
                after_protected=self._snapshot_protected_mtimes(),
                before_inputs=before_inputs,
                after_inputs=self._snapshot_input_mtimes(),
                reason=data.block_reason or "Historical data unavailable",
                jobs_total=len(jobs),
                data=data,
            )

        checkpoint = HistoricalExecutionCheckpointStore()
        checkpoint.load()
        processed_ids = checkpoint.processed_ids()

        pending_jobs = sorted(
            (
                job
                for job in jobs
                if str(job.get("research_job_id", "")) not in processed_ids
                and str(job.get("research_status", "")) == "RESEARCH_QUEUED"
            ),
            key=lambda item: str(item.get("research_job_id", "")),
        )

        batch_jobs = pending_jobs[:batch_size]
        runner = StrategyBacktestRunner(self._root)
        batches_executed = 0
        jobs_processed_this_run = 0

        if batch_jobs:
            batches_executed = 1
            for job in batch_jobs:
                job_id = str(job.get("research_job_id", ""))
                strategy_id = str(job.get("strategy_id", ""))
                try:
                    result = self._execute_job(job, strategy_map, runner, data)
                except Exception as exc:
                    logger.exception("Job %s failed with exception", job_id)
                    result = ExecutionJobResult(
                        research_job_id=job_id,
                        strategy_id=strategy_id,
                        simulation_id=str(job.get("simulation_id", "")),
                        market=str(job.get("market", "")),
                        time_horizon=str(job.get("time_horizon", "")),
                        execution_status="FAILED",
                        block_reason=f"Execution exception: {exc}",
                    )

                checkpoint.upsert(result)
                checkpoint.persist()
                jobs_processed_this_run += 1
        elif pending_jobs:
            self._warnings.append(
                f"No jobs processed despite {len(pending_jobs)} pending — batch_size={batch_size}"
            )
        elif len(processed_ids) < len(jobs):
            self._warnings.append("All jobs appear processed but counts mismatch — verify checkpoint.")

        all_results = checkpoint.all_results()
        completed = [r for r in all_results if r.execution_status == "COMPLETED"]
        blocked = [r for r in all_results if r.execution_status == "BLOCKED"]
        failed = [r for r in all_results if r.execution_status == "FAILED"]
        pending_count = max(0, len(jobs) - len(all_results))

        schema_ok, schema_warnings = validate_completed_metrics(completed)
        self._warnings.extend(schema_warnings)

        after_protected = self._snapshot_protected_mtimes()
        after_inputs = self._snapshot_input_mtimes()
        protected_ok = self._mtimes_unchanged(before_protected, after_protected)
        input_ok = self._mtimes_unchanged(before_inputs, after_inputs)

        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during historical execution")
        if not input_ok:
            self._warnings.append("Input file mtimes changed during historical execution")

        verdict = self._determine_verdict(
            jobs_total=len(jobs),
            pending_count=pending_count,
            completed_count=len(completed),
            blocked_count=len(blocked),
            schema_ok=schema_ok,
        )

        return HistoricalExecutionReport(
            verdict=verdict,
            jobs_total=len(jobs),
            jobs_completed=len(completed),
            jobs_blocked=len(blocked),
            jobs_failed=len(failed),
            jobs_pending=pending_count,
            jobs_processed_this_run=jobs_processed_this_run,
            batch_size=batch_size,
            batches_executed=batches_executed,
            last_checkpoint_saved_at=checkpoint.last_saved_at,
            data_availability={
                "available": data.available,
                "ohlcv_available": data.ohlcv_available,
                "csv_available": data.csv_available,
                "ohlcv_probe_rows": data.ohlcv_probe_rows,
                "csv_row_count": data.csv_row_count,
                "block_reason": data.block_reason,
            },
            results=all_results,
            schema_validation_passed=schema_ok,
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
            input_files_unchanged=input_ok,
        )

    def _blocked_report(
        self,
        *,
        batch_size: int,
        before_protected: dict[str, float],
        after_protected: dict[str, float],
        before_inputs: dict[str, float],
        after_inputs: dict[str, float],
        reason: str,
        jobs_total: int = 0,
        data: Any | None = None,
    ) -> HistoricalExecutionReport:
        self._warnings.append(reason)
        data_payload = {
            "available": False,
            "ohlcv_available": False,
            "csv_available": False,
            "block_reason": reason,
        }
        if data is not None:
            data_payload = {
                "available": data.available,
                "ohlcv_available": data.ohlcv_available,
                "csv_available": data.csv_available,
                "ohlcv_probe_rows": data.ohlcv_probe_rows,
                "csv_row_count": data.csv_row_count,
                "block_reason": reason,
            }

        return HistoricalExecutionReport(
            verdict=HistoricalExecutionVerdict.HISTORICAL_EXECUTION_BLOCKED,
            jobs_total=jobs_total,
            jobs_completed=0,
            jobs_blocked=0,
            jobs_failed=0,
            jobs_pending=jobs_total,
            jobs_processed_this_run=0,
            batch_size=batch_size,
            batches_executed=0,
            last_checkpoint_saved_at=None,
            data_availability=data_payload,
            results=[],
            schema_validation_passed=False,
            warnings=list(self._warnings),
            protected_files_unchanged=self._mtimes_unchanged(before_protected, after_protected),
            input_files_unchanged=self._mtimes_unchanged(before_inputs, after_inputs),
        )

    def _load_json(self, rel_path: Path) -> dict[str, Any] | None:
        path = self._root / rel_path
        if not path.is_file():
            self._warnings.append(f"Missing input: {rel_path.name}")
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._warnings.append(f"Could not read {rel_path.name}: {exc}")
            return None
        return payload if isinstance(payload, dict) else None

    def _extract_research_jobs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        jobs = payload.get("research_jobs")
        if not isinstance(jobs, list):
            self._warnings.append("research_jobs missing or invalid")
            return []
        return [job for job in jobs if isinstance(job, dict) and job.get("research_job_id")]

    def _build_strategy_map(self, payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        if not payload:
            self._warnings.append("Discovery input missing; cannot map strategy definitions.")
            return {}

        registry = payload.get("discovery_registry")
        if not isinstance(registry, list):
            self._warnings.append("discovery_registry missing or invalid")
            return {}

        mapping: dict[str, dict[str, Any]] = {}
        for item in registry:
            if isinstance(item, dict):
                discovery_id = str(item.get("discovery_id", "")).strip()
                if discovery_id:
                    mapping[discovery_id] = item
        return mapping

    def _execute_job(
        self,
        job: dict[str, Any],
        strategy_map: dict[str, dict[str, Any]],
        runner: StrategyBacktestRunner,
        data: Any,
    ) -> ExecutionJobResult:
        job_id = str(job.get("research_job_id", ""))
        strategy_id = str(job.get("strategy_id", ""))
        strategy = strategy_map.get(strategy_id)
        if strategy is None:
            return ExecutionJobResult(
                research_job_id=job_id,
                strategy_id=strategy_id,
                simulation_id=str(job.get("simulation_id", "")),
                market=str(job.get("market", "")),
                time_horizon=str(job.get("time_horizon", "")),
                execution_status="BLOCKED",
                block_reason=f"Strategy definition missing for {strategy_id}",
            )

        outcome = runner.run_job(
            market=str(job.get("market", "")),
            time_horizon=str(job.get("time_horizon", "")),
            strategy=strategy,
            data=data,
        )

        if outcome.status == "COMPLETED" and outcome.metrics:
            return ExecutionJobResult(
                research_job_id=job_id,
                strategy_id=strategy_id,
                simulation_id=str(job.get("simulation_id", "")),
                market=str(job.get("market", "")),
                time_horizon=str(job.get("time_horizon", "")),
                execution_status="COMPLETED",
                metrics=outcome.metrics,
                trade_count=outcome.trade_count,
                tickers_used=outcome.tickers_used,
            )

        return ExecutionJobResult(
            research_job_id=job_id,
            strategy_id=strategy_id,
            simulation_id=str(job.get("simulation_id", "")),
            market=str(job.get("market", "")),
            time_horizon=str(job.get("time_horizon", "")),
            execution_status="BLOCKED",
            block_reason=outcome.block_reason or "Backtest blocked",
            trade_count=outcome.trade_count,
            tickers_used=outcome.tickers_used,
        )

    def _determine_verdict(
        self,
        *,
        jobs_total: int,
        pending_count: int,
        completed_count: int,
        blocked_count: int,
        schema_ok: bool,
    ) -> HistoricalExecutionVerdict:
        if jobs_total == 0:
            return HistoricalExecutionVerdict.HISTORICAL_EXECUTION_BLOCKED

        if completed_count == 0 and blocked_count == 0:
            return HistoricalExecutionVerdict.HISTORICAL_EXECUTION_BLOCKED

        if not schema_ok:
            return HistoricalExecutionVerdict.HISTORICAL_EXECUTION_READY_WITH_WARNINGS

        if pending_count > 0 or self._warnings:
            return HistoricalExecutionVerdict.HISTORICAL_EXECUTION_READY_WITH_WARNINGS

        if completed_count + blocked_count >= jobs_total:
            return HistoricalExecutionVerdict.HISTORICAL_EXECUTION_READY

        return HistoricalExecutionVerdict.HISTORICAL_EXECUTION_READY_WITH_WARNINGS

    def _snapshot_protected_mtimes(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for rel in PROTECTED_PATHS:
            full = self._root / rel
            if full.is_file():
                snapshot[str(rel)] = full.stat().st_mtime
        return snapshot

    def _snapshot_input_mtimes(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for rel in INPUT_PATHS:
            full = self._root / rel
            if full.is_file():
                snapshot[str(rel)] = full.stat().st_mtime
        return snapshot

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
