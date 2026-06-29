#!/usr/bin/env python3
"""
TAE Phase X Sprint X.7B — Read-Only Advisory Index Demo

READ_ONLY | REPORT_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Builds tae_advisory_index.json from canonical tae_*.json reports in project root.
Does not modify existing tae reports or connect to live trading.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.governance.advisory_index import ADVISORY_INDEX_SAFETY_BANNER
from research_core.governance.advisory_index_report import AdvisoryIndexReportStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase X Sprint X.7B — Read-Only Advisory Index")
    logger.info("Safety: %s", ADVISORY_INDEX_SAFETY_BANNER)

    store = AdvisoryIndexReportStore()
    report, json_path = store.build_and_persist(root)

    logger.info("Total reports indexed: %d", report.total_reports)
    logger.info("Valid: %d | Invalid: %d", report.valid_reports, report.invalid_reports)
    logger.info("Output: %s", json_path)

    populated = [
        (category, len(files))
        for category, files in report.reports_by_category.items()
        if files
    ]
    for category, count in sorted(populated, key=lambda item: (-item[1], item[0])):
        latest = report.latest_timestamp_by_category.get(category)
        logger.info("  %s: %d (latest=%s)", category, count, latest or "n/a")

    print(store.format_text(report))
    return 0 if report.invalid_reports == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
