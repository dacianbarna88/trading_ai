#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.5F — Phase V Legacy Retirement Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_inventory.inventory_audit import EcosystemInventoryAudit
from research_core.ecosystem_inventory.inventory_report import EcosystemInventoryReportStore
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER
from research_core.strategy_evolution.daily_runner import StrategyEvolutionDailyRunner
from research_core.strategy_evolution.daily_runner_report import DailyRunnerReportStore
from research_core.strategy_evolution.phase_v_legacy_retirement import (
    is_phase_v_legacy_wired_in_daily_runner,
)
from research_core.strategy_evolution.phase_v_legacy_retirement_report import (
    PhaseVLegacyRetirementAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.5F — Phase V Legacy Retirement")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    before_wired = is_phase_v_legacy_wired_in_daily_runner(root)

    runner = StrategyEvolutionDailyRunner()
    daily_report = runner.run()
    store = DailyRunnerReportStore()
    store.persist(daily_report)
    store.persist_txt(daily_report)

    audit = PhaseVLegacyRetirementAudit(root)
    report = audit.run(
        before_wired=before_wired,
        protected_ok=verify_protected_unchanged(root, before),
    )
    paths = audit.persist(report)

    inv = EcosystemInventoryAudit(root).audit()
    inv_store = EcosystemInventoryReportStore()
    paths["inventory_json"] = inv_store.persist(inv)
    paths["inventory_txt"] = inv_store.persist_txt(inv)

    legacy = daily_report.phase_v_legacy_status or {}
    logger.info("Daily runner verdict: %s", daily_report.verdict.value)
    logger.info("Phase V legacy status: %s", legacy.get("legacy_phase_v_status"))
    logger.info("Reports:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    if report.verdict == "PHASE_V_LEGACY_RETIREMENT_INCOMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
