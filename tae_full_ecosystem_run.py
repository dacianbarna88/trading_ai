#!/usr/bin/env python3
"""
TAE Phase X Sprint X.1 — Full Ecosystem Run

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Single daily operating command chaining all canonical TAE modules.
Read-only / paper-only — no broker, no BUY/SELL, no portfolio mutation.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.full_ecosystem import (
    FullEcosystemRunner,
    FullEcosystemRunReportStore,
    FullEcosystemRunVerdict,
    SAFETY_BANNER,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase X Sprint X.1 — Full Ecosystem Run")
    logger.info("Safety: %s", SAFETY_BANNER)

    runner = FullEcosystemRunner(root)
    report = runner.run()

    json_path, txt_path = FullEcosystemRunReportStore().persist(report)

    succeeded = sum(1 for step in report.steps if step.succeeded)
    logger.info("Steps succeeded: %d/%d", succeeded, len(report.steps))
    logger.info("Quick Health pre:  %s", report.quick_health_pre_verdict)
    logger.info("Quick Health post: %s", report.quick_health_post_verdict)
    logger.info("Integration backlog: %s", report.integration_health.get("integration_backlog"))
    logger.info("Protected files unchanged: %s", report.protected_files_unchanged)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == FullEcosystemRunVerdict.FULL_ECOSYSTEM_RUN_BLOCKED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
