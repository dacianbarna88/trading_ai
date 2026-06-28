#!/usr/bin/env python3
"""
TAE Phase X Sprint X.3B — Strategy Simulation Engine Demo

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Builds simulation queue and registry from discovery candidates.
No historical execution, backtesting, broker, or live market access.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_simulation.historical_simulation_engine import (
    HistoricalSimulationEngine,
)
from research_core.strategy_simulation.strategy_simulation_report import (
    SIMULATION_SAFETY_BANNER,
    StrategySimulationReportStore,
    StrategySimulationVerdict,
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
    logger.info("TAE Phase X Sprint X.3B — Strategy Simulation Engine")
    logger.info("Safety: %s | NO_HISTORICAL_EXECUTION", SIMULATION_SAFETY_BANNER)

    before = _snapshot_mtimes(root)

    engine = HistoricalSimulationEngine(root)
    report = engine.run()

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during simulation setup")

    json_path, txt_path = StrategySimulationReportStore().persist(report)

    logger.info("Discovery candidates loaded: %d", report.discovery_candidates_loaded)
    logger.info("Simulation records created: %d", report.simulation_records_created)
    logger.info("Schema validation: %s", report.schema_validation_passed)
    logger.info("Registry completeness: %s", report.registry_completeness_passed)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == StrategySimulationVerdict.STRATEGY_SIMULATION_INPUT_MISSING:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
