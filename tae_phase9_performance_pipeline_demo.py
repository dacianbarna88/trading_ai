#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.5A — Performance Pipeline Integration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_inventory.inventory_audit import EcosystemInventoryAudit
from research_core.ecosystem_inventory.inventory_report import EcosystemInventoryReportStore
from research_core.performance.performance_pipeline_report import (
    PerformancePipelineAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.5A — Performance Pipeline Integration")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    audit = PerformancePipelineAudit(root)
    dep_map, report = audit.run(protected_ok=verify_protected_unchanged(root, before))
    paths = audit.persist_all(dep_map, report)

    inv = EcosystemInventoryAudit(root).audit()
    inv_store = EcosystemInventoryReportStore()
    paths["inventory_json"] = inv_store.persist(inv)
    paths["inventory_txt"] = inv_store.persist_txt(inv)

    logger.info("Dependency map: %s", dep_map.verdict)
    logger.info("Strategic JSON: %s", report.strategic_json_exists)
    logger.info("Integrity JSON: %s", report.integrity_json_exists)
    logger.info("Runtime connected: %s", report.runtime_connected)
    logger.info("Quick health connected: %s", report.quick_health_connected)
    logger.info("Reports:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
