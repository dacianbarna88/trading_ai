#!/usr/bin/env python3
"""
TAE Phase X Sprint X.5 — Historical Results Analysis Demo

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Read-only analysis of completed historical execution results.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.strategy_simulation.historical_results_analysis import (
    HistoricalResultsAnalysisEngine,
)
from research_core.strategy_simulation.historical_results_analysis_report import (
    ANALYSIS_SAFETY_BANNER,
    HistoricalResultsAnalysisReportStore,
    HistoricalResultsAnalysisVerdict,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase X Sprint X.5 — Historical Results Analysis")
    logger.info("Safety: %s", ANALYSIS_SAFETY_BANNER)

    engine = HistoricalResultsAnalysisEngine(root)
    report = engine.analyze()

    json_path, txt_path = HistoricalResultsAnalysisReportStore().persist(report)

    logger.info("Jobs completed: %d", report.jobs_completed)
    logger.info("Jobs blocked: %d", report.jobs_blocked)
    logger.info("Robust strategies: %d", len(report.robust_strategy_shortlist))
    logger.info("Weak strategies: %d", len(report.weak_strategy_shortlist))
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == HistoricalResultsAnalysisVerdict.HISTORICAL_RESULTS_ANALYSIS_INPUT_MISSING:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
