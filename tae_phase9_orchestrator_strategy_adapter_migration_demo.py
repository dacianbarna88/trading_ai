#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.3A — Orchestrator Strategy Adapter Migration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.contracts.base_contract import SAFETY_BANNER
from research_core.integration_adapters.strategy_adapter import StrategyAdapter
from research_core.orchestrator.orchestrator_adapter_migration_report import (
    OrchestratorStrategyAdapterMigrationAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.3A — Orchestrator Strategy Adapter Migration")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    audit = OrchestratorStrategyAdapterMigrationAudit(root)
    report = audit.run(protected_ok=verify_protected_unchanged(root, before))
    paths = audit.persist(report)

    state = StrategyAdapter.load_strategy_state_for_orchestrator(str(root))
    logger.info("Adapter path: %s", state.get("adapter_path"))
    logger.info("State completeness: %s", state.get("strategy_state_completeness"))
    logger.info("Direct daily_runner import remains: %s", report.direct_daily_runner_import_remains)
    logger.info("Uses StrategyAdapter: %s", report.orchestrator_uses_adapter)
    logger.info("Reports written: %s, %s", paths["json"], paths["txt"])
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_DIRECT_IMPORT_REMAINS"):
        return 1
    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
