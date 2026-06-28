"""
Historical Research Engine — Phase X Sprint X.3C

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Expands queued simulation records into historical research job records.
No live data fetch, broker access, or portfolio changes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_simulation.historical_research_report import (
    DATA_REQUIREMENT_FIELDS,
    DISCOVERY_INPUT_PATH,
    HistoricalResearchJob,
    HistoricalResearchReport,
    HistoricalResearchVerdict,
    SIMULATION_INPUT_PATH,
)
from research_core.strategy_simulation.performance_metrics import PENDING_VALUE
from research_core.strategy_simulation.simulation_registry import MARKETS, TIME_HORIZONS

logger = logging.getLogger(__name__)

RESEARCH_STATUS_QUEUED = "RESEARCH_QUEUED"
EXPECTED_JOBS_PER_SIMULATION = len(MARKETS) * len(TIME_HORIZONS)


def default_data_requirement() -> dict[str, bool]:
    return {field: True for field in DATA_REQUIREMENT_FIELDS}


def research_job_id_for_index(index: int) -> str:
    return f"HRJ_{index + 1:06d}"


def build_research_jobs(
    simulation_records: list[dict[str, Any]],
    created_at: datetime | None = None,
) -> list[HistoricalResearchJob]:
    timestamp = created_at or datetime.now(timezone.utc)
    jobs: list[HistoricalResearchJob] = []
    job_index = 0

    sorted_records = sorted(simulation_records, key=lambda item: item.get("simulation_id", ""))

    for record in sorted_records:
        simulation_id = str(record.get("simulation_id", ""))
        strategy_id = str(record.get("strategy_id", ""))

        for market in MARKETS:
            for horizon in TIME_HORIZONS:
                jobs.append(
                    HistoricalResearchJob(
                        research_job_id=research_job_id_for_index(job_index),
                        strategy_id=strategy_id,
                        simulation_id=simulation_id,
                        market=market,
                        time_horizon=horizon,
                        research_status=RESEARCH_STATUS_QUEUED,
                        metrics_status=PENDING_VALUE,
                        data_requirement=default_data_requirement(),
                        created_at=timestamp,
                    )
                )
                job_index += 1

    return jobs


def build_coverage_matrix(jobs: list[HistoricalResearchJob]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {market: {horizon: 0 for horizon in TIME_HORIZONS} for market in MARKETS}
    for job in jobs:
        matrix[job.market][job.time_horizon] += 1
    return matrix


def validate_research_jobs_schema(jobs: list[HistoricalResearchJob]) -> tuple[bool, list[str]]:
    warnings: list[str] = []

    for job in jobs:
        if job.research_status != RESEARCH_STATUS_QUEUED:
            warnings.append(f"{job.research_job_id} research_status expected RESEARCH_QUEUED")

        if job.metrics_status != PENDING_VALUE:
            warnings.append(f"{job.research_job_id} metrics_status expected PENDING")

        for field in DATA_REQUIREMENT_FIELDS:
            if field not in job.data_requirement:
                warnings.append(f"{job.research_job_id} missing data requirement: {field}")
            elif not job.data_requirement[field]:
                warnings.append(f"{job.research_job_id} data requirement {field} must be required")

        required_keys = {
            "research_job_id",
            "strategy_id",
            "simulation_id",
            "market",
            "time_horizon",
            "research_status",
            "metrics_status",
            "data_requirement",
            "created_at",
        }
        payload = job.to_dict()
        missing = required_keys - set(payload.keys())
        if missing:
            warnings.append(f"{job.research_job_id} missing fields: {sorted(missing)}")

    return len(warnings) == 0, warnings


class HistoricalResearchEngine:
    """Builds historical research jobs from simulation registry — no execution."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._warnings: list[str] = []

    def run(self) -> HistoricalResearchReport:
        before_protected = self._snapshot_protected_mtimes()
        before_inputs = self._snapshot_input_mtimes()

        simulation_payload = self._load_json(SIMULATION_INPUT_PATH)
        discovery_payload = self._load_json(DISCOVERY_INPUT_PATH)

        if simulation_payload is None or discovery_payload is None:
            after_protected = self._snapshot_protected_mtimes()
            after_inputs = self._snapshot_input_mtimes()
            return HistoricalResearchReport(
                verdict=HistoricalResearchVerdict.HISTORICAL_RESEARCH_INPUT_MISSING,
                simulation_records_loaded=0,
                research_jobs_created=0,
                markets=list(MARKETS),
                horizons=list(TIME_HORIZONS),
                data_requirements_summary=default_data_requirement(),
                metrics_pending_count=0,
                coverage_matrix=build_coverage_matrix([]),
                schema_validation_passed=False,
                research_jobs=[],
                warnings=list(self._warnings),
                protected_files_unchanged=self._mtimes_unchanged(before_protected, after_protected),
                input_files_unchanged=self._mtimes_unchanged(before_inputs, after_inputs),
            )

        simulation_records = self._extract_simulation_records(simulation_payload)
        discovery_ids = self._extract_discovery_ids(discovery_payload)

        if not simulation_records:
            self._warnings.append("No simulation records found in simulation input")

        self._cross_validate_strategies(simulation_records, discovery_ids)

        jobs = build_research_jobs(simulation_records)
        expected_jobs = len(simulation_records) * EXPECTED_JOBS_PER_SIMULATION

        if len(jobs) != expected_jobs:
            self._warnings.append(
                f"Research job count {len(jobs)} != expected {expected_jobs}"
            )

        schema_ok, schema_warnings = validate_research_jobs_schema(jobs)
        self._warnings.extend(schema_warnings)

        coverage_matrix = build_coverage_matrix(jobs)
        metrics_pending_count = sum(1 for job in jobs if job.metrics_status == PENDING_VALUE)

        after_protected = self._snapshot_protected_mtimes()
        after_inputs = self._snapshot_input_mtimes()
        protected_ok = self._mtimes_unchanged(before_protected, after_protected)
        input_ok = self._mtimes_unchanged(before_inputs, after_inputs)

        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during historical research setup")
        if not input_ok:
            self._warnings.append("Input file mtimes changed during historical research setup")

        verdict = self._determine_verdict(simulation_records, jobs, schema_ok, expected_jobs)

        return HistoricalResearchReport(
            verdict=verdict,
            simulation_records_loaded=len(simulation_records),
            research_jobs_created=len(jobs),
            markets=list(MARKETS),
            horizons=list(TIME_HORIZONS),
            data_requirements_summary=default_data_requirement(),
            metrics_pending_count=metrics_pending_count,
            coverage_matrix=coverage_matrix,
            schema_validation_passed=schema_ok,
            research_jobs=jobs,
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
            input_files_unchanged=input_ok,
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

        if not isinstance(payload, dict):
            self._warnings.append(f"Invalid payload in {rel_path.name}")
            return None

        return payload

    def _extract_simulation_records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        registry = payload.get("simulation_registry")
        if not isinstance(registry, list):
            self._warnings.append("simulation_registry missing or invalid in simulation input")
            return []

        records: list[dict[str, Any]] = []
        for item in registry:
            if isinstance(item, dict) and item.get("simulation_id") and item.get("strategy_id"):
                records.append(item)
            else:
                self._warnings.append("Skipping invalid simulation registry entry")

        return records

    def _extract_discovery_ids(self, payload: dict[str, Any]) -> set[str]:
        registry = payload.get("discovery_registry")
        if not isinstance(registry, list):
            self._warnings.append("discovery_registry missing or invalid in discovery input")
            return set()

        ids: set[str] = set()
        for item in registry:
            if isinstance(item, dict):
                discovery_id = str(item.get("discovery_id", "")).strip()
                if discovery_id:
                    ids.add(discovery_id)
        return ids

    def _cross_validate_strategies(
        self,
        simulation_records: list[dict[str, Any]],
        discovery_ids: set[str],
    ) -> None:
        if not discovery_ids:
            self._warnings.append("No discovery IDs available for cross-validation")
            return

        for record in simulation_records:
            strategy_id = str(record.get("strategy_id", ""))
            if strategy_id and strategy_id not in discovery_ids:
                self._warnings.append(
                    f"Strategy {strategy_id} in simulation not found in discovery input"
                )

    def _determine_verdict(
        self,
        simulation_records: list[dict[str, Any]],
        jobs: list[HistoricalResearchJob],
        schema_ok: bool,
        expected_jobs: int,
    ) -> HistoricalResearchVerdict:
        if not simulation_records:
            return HistoricalResearchVerdict.HISTORICAL_RESEARCH_INPUT_MISSING

        if not schema_ok:
            return HistoricalResearchVerdict.HISTORICAL_RESEARCH_SCHEMA_FAILED

        if self._warnings or len(jobs) != expected_jobs:
            return HistoricalResearchVerdict.HISTORICAL_RESEARCH_READY_WITH_WARNINGS

        return HistoricalResearchVerdict.HISTORICAL_RESEARCH_ENGINE_READY

    def _snapshot_protected_mtimes(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for rel in PROTECTED_PATHS:
            full = self._root / rel
            if full.is_file():
                snapshot[str(rel)] = full.stat().st_mtime
        return snapshot

    def _snapshot_input_mtimes(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for rel in (SIMULATION_INPUT_PATH, DISCOVERY_INPUT_PATH):
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
