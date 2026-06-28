#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.5G — Governance Daily Intelligence Migration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_inventory.inventory_audit import EcosystemInventoryAudit
from research_core.ecosystem_inventory.inventory_report import EcosystemInventoryReportStore
from research_core.governance.daily_intelligence import DailyIntelligenceCollector
from research_core.governance.governance_daily_intelligence_migration import (
    is_governance_modern_inputs_wired,
)
from research_core.governance.governance_daily_intelligence_migration_report import (
    GovernanceDailyIntelligenceMigrationAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.5G — Governance Daily Intelligence Migration")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    before_wired = is_governance_modern_inputs_wired(root)

    collector = DailyIntelligenceCollector()
    daily_report = collector.generate_and_persist()

    audit = GovernanceDailyIntelligenceMigrationAudit(root)
    report = audit.run(
        before_wired=before_wired,
        protected_ok=verify_protected_unchanged(root, before),
        sources_loaded=daily_report.sources_loaded,
    )
    paths = audit.persist(report)

    inv = EcosystemInventoryAudit(root).audit()
    inv_store = EcosystemInventoryReportStore()
    paths["inventory_json"] = inv_store.persist(inv)
    paths["inventory_txt"] = inv_store.persist_txt(inv)

    modern = daily_report.governance_modern_inputs or {}
    logger.info("Governance report date: %s", daily_report.report_date)
    logger.info(
        "Modern inputs registered: %s (%s loaded)",
        modern.get("governance_modern_inputs_registered"),
        modern.get("governance_modern_input_count"),
    )
    logger.info("Strategy evolution source: %s", modern.get("governance_strategy_evolution_source"))
    logger.info("Reports:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    if report.verdict == "GOVERNANCE_DAILY_INTELLIGENCE_MIGRATION_INCOMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
