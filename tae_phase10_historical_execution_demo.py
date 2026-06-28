#!/usr/bin/env python3
"""
TAE Phase X Sprint X.4 — Historical Execution Engine Demo

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Executes queued historical research jobs via real backtest logic.
Resumable batching — default 10 jobs per run.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_simulation.historical_execution_engine import (
    DEFAULT_BATCH_SIZE,
    HistoricalExecutionEngine,
)
from research_core.strategy_simulation.historical_execution_report import (
    EXECUTION_SAFETY_BANNER,
    HistoricalExecutionReportStore,
    HistoricalExecutionVerdict,
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
    parser = argparse.ArgumentParser(description="TAE Historical Execution Engine demo")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Jobs to execute this run (default {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    root = Path(".")
    logger.info("TAE Phase X Sprint X.4 — Historical Execution Engine")
    logger.info("Safety: %s", EXECUTION_SAFETY_BANNER)
    logger.info("Batch size: %d", args.batch_size)

    before = _snapshot_mtimes(root)

    engine = HistoricalExecutionEngine(root)
    report = engine.run(batch_size=args.batch_size)

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during historical execution")

    json_path, txt_path = HistoricalExecutionReportStore().persist(report)

    logger.info("Jobs total: %d", report.jobs_total)
    logger.info("Jobs completed: %d", report.jobs_completed)
    logger.info("Jobs blocked: %d", report.jobs_blocked)
    logger.info("Jobs pending: %d", report.jobs_pending)
    logger.info("Schema validation: %s", report.schema_validation_passed)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == HistoricalExecutionVerdict.HISTORICAL_EXECUTION_BLOCKED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
