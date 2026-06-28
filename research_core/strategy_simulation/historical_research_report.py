"""
Historical Research report — Phase X Sprint X.3C

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DEFAULT_JSON_PATH = Path("tae_historical_research.json")
DEFAULT_TXT_PATH = Path("tae_historical_research.txt")
SIMULATION_INPUT_PATH = Path("tae_strategy_simulation.json")
DISCOVERY_INPUT_PATH = Path("tae_strategy_discovery.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_historical_research"
RESEARCH_SAFETY_BANNER = (
    "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE"
)

DATA_REQUIREMENT_FIELDS: tuple[str, ...] = (
    "price_history_required",
    "volume_history_required",
    "benchmark_required",
    "corporate_actions_required",
    "currency_normalization_required",
)


class HistoricalResearchVerdict(str, Enum):
    HISTORICAL_RESEARCH_ENGINE_READY = "HISTORICAL_RESEARCH_ENGINE_READY"
    HISTORICAL_RESEARCH_READY_WITH_WARNINGS = "HISTORICAL_RESEARCH_READY_WITH_WARNINGS"
    HISTORICAL_RESEARCH_INPUT_MISSING = "HISTORICAL_RESEARCH_INPUT_MISSING"
    HISTORICAL_RESEARCH_SCHEMA_FAILED = "HISTORICAL_RESEARCH_SCHEMA_FAILED"


@dataclass
class HistoricalResearchJob:
    research_job_id: str
    strategy_id: str
    simulation_id: str
    market: str
    time_horizon: str
    research_status: str
    metrics_status: str
    data_requirement: dict[str, bool]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_job_id": self.research_job_id,
            "strategy_id": self.strategy_id,
            "simulation_id": self.simulation_id,
            "market": self.market,
            "time_horizon": self.time_horizon,
            "research_status": self.research_status,
            "metrics_status": self.metrics_status,
            "data_requirement": dict(self.data_requirement),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HistoricalResearchReport:
    verdict: HistoricalResearchVerdict
    simulation_records_loaded: int
    research_jobs_created: int
    markets: list[str]
    horizons: list[str]
    data_requirements_summary: dict[str, bool]
    metrics_pending_count: int
    coverage_matrix: dict[str, dict[str, int]]
    schema_validation_passed: bool
    research_jobs: list[HistoricalResearchJob]
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    input_files_unchanged: bool = True
    safety_mode: str = RESEARCH_SAFETY_BANNER
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
            "simulation_records_loaded": self.simulation_records_loaded,
            "research_jobs_created": self.research_jobs_created,
            "markets": list(self.markets),
            "horizons": list(self.horizons),
            "data_requirements_summary": dict(self.data_requirements_summary),
            "metrics_pending_count": self.metrics_pending_count,
            "coverage_matrix": {
                market: dict(horizons) for market, horizons in self.coverage_matrix.items()
            },
            "schema_validation_passed": self.schema_validation_passed,
            "research_jobs": [job.to_dict() for job in self.research_jobs],
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
            "input_files_unchanged": self.input_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE HISTORICAL RESEARCH ENGINE — SPRINT X.3C =====",
            "",
            f"Safety banner: {self.safety_mode}",
            "Mode: RESEARCH_ONLY | NO_LIVE_DATA | NO_BROKER",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            f"Input files unchanged: {self.input_files_unchanged}",
            "",
            "===== INPUTS (READ-ONLY) =====",
            f"  Simulation input: {SIMULATION_INPUT_PATH.name}",
            f"  Discovery input: {DISCOVERY_INPUT_PATH.name}",
            f"  Simulation records loaded: {self.simulation_records_loaded}",
            f"  Research jobs created: {self.research_jobs_created}",
            "",
            "===== MARKETS =====",
        ]
        for market in self.markets:
            lines.append(f"  • {market}")

        lines.extend(["", "===== HORIZONS ====="])
        for horizon in self.horizons:
            lines.append(f"  • {horizon}")

        lines.extend(
            [
                "",
                "===== DATA REQUIREMENTS =====",
            ]
        )
        for key, required in self.data_requirements_summary.items():
            lines.append(f"  {key}: {required}")

        lines.extend(
            [
                "",
                "===== METRICS =====",
                f"  Metrics pending count: {self.metrics_pending_count}",
                f"  Schema validation passed: {self.schema_validation_passed}",
                "",
                "===== COVERAGE MATRIX =====",
            ]
        )
        for market in self.markets:
            horizon_counts = self.coverage_matrix.get(market, {})
            counts = ", ".join(f"{h}={horizon_counts.get(h, 0)}" for h in self.horizons)
            lines.append(f"  {market}: {counts}")

        lines.extend(["", "===== SAMPLE RESEARCH JOBS (first 5) ====="])
        for job in self.research_jobs[:5]:
            lines.extend(
                [
                    f"  [{job.research_job_id}] {job.simulation_id} → {job.strategy_id}",
                    f"    Market: {job.market} | Horizon: {job.time_horizon}",
                    f"    Status: {job.research_status} | Metrics: {job.metrics_status}",
                    "",
                ]
            )

        if len(self.research_jobs) > 5:
            lines.append(f"  ... and {len(self.research_jobs) - 5} more research jobs")

        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)


class HistoricalResearchReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: HistoricalResearchReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
