#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.4 — Official Quick Health Check

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Canonical read-only daily health entry point.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.runtime.quick_health_report import QuickHealthVerdict
from research_core.runtime.quick_health_wrapper import QuickHealthWrapper
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Official Quick Health Check — Sprint IX.4")
    logger.info("Safety: %s", SAFETY_BANNER)

    wrapper = QuickHealthWrapper(root)
    report = wrapper.run()
    paths = wrapper.persist(report)

    logger.info("Runtime health: %s", report.runtime_health_status)
    logger.info("Orchestrator: %s", report.orchestrator_verdict or "N/A")
    logger.info("Git: %s", report.git_status)
    logger.info("Warnings: %d", len(report.warnings))
    logger.info("Reports: %s, %s", paths["json"], paths["txt"])
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == QuickHealthVerdict.TAE_QUICK_HEALTH_NOT_READY:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
