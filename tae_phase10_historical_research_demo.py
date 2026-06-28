#!/usr/bin/env python3
"""
TAE Phase X Sprint X.3C — Historical Research Engine Demo

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Expands queued simulation records into historical research evaluation jobs.
No live data, broker, or portfolio execution.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_simulation.historical_research_engine import HistoricalResearchEngine
from research_core.strategy_simulation.historical_research_report import (
    RESEARCH_SAFETY_BANNER,
    HistoricalResearchReportStore,
    HistoricalResearchVerdict,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _snapshot_mtimes(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[str(rel)] = full.stat().st_mtime
    return snapshot


def _protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    after = _snapshot_mtimes(root)
    for key, mtime in before.items():
        if key not in after or after[key] != mtime:
            return False
    return True


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase X Sprint X.3C — Historical Research Engine")
    logger.info("Safety: %s | NO_LIVE_DATA", RESEARCH_SAFETY_BANNER)

    before = _snapshot_mtimes(root)

    engine = HistoricalResearchEngine(root)
    report = engine.run()

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during historical research setup")

    json_path, txt_path = HistoricalResearchReportStore().persist(report)

    logger.info("Simulation records loaded: %d", report.simulation_records_loaded)
    logger.info("Research jobs created: %d", report.research_jobs_created)
    logger.info("Metrics pending: %d", report.metrics_pending_count)
    logger.info("Schema validation: %s", report.schema_validation_passed)
    logger.info("Input files unchanged: %s", report.input_files_unchanged)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict in (
        HistoricalResearchVerdict.HISTORICAL_RESEARCH_INPUT_MISSING,
        HistoricalResearchVerdict.HISTORICAL_RESEARCH_SCHEMA_FAILED,
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
