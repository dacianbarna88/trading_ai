#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.5C — Regional Validation → Promotion Gate Integration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_inventory.inventory_audit import EcosystemInventoryAudit
from research_core.ecosystem_inventory.inventory_report import EcosystemInventoryReportStore
from research_core.strategy_evolution.promotion_gate import StrategyPromotionGate
from research_core.strategy_evolution.promotion_gate_report import PromotionGateReportStore
from research_core.strategy_evolution.regional_validation_integration import (
    is_regional_validation_wired_in_promotion_gate,
)
from research_core.strategy_evolution.regional_validation_integration_report import (
    RegionalValidationIntegrationAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.5C — Regional Validation Integration")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    before_wired = is_regional_validation_wired_in_promotion_gate(root)

    gate = StrategyPromotionGate()
    promotion_report = gate.evaluate()
    store = PromotionGateReportStore()
    store.persist(promotion_report)
    store.persist_txt(promotion_report)

    audit = RegionalValidationIntegrationAudit(root)
    report = audit.run(
        before_wired=before_wired,
        protected_ok=verify_protected_unchanged(root, before),
    )
    paths = audit.persist(report)

    inv = EcosystemInventoryAudit(root).audit()
    inv_store = EcosystemInventoryReportStore()
    paths["inventory_json"] = inv_store.persist(inv)
    paths["inventory_txt"] = inv_store.persist_txt(inv)

    regional_reg = promotion_report.regional_validation_registration or {}
    logger.info("Promotion gate verdict: %s", promotion_report.verdict.value)
    logger.info(
        "Regional validation status: %s",
        regional_reg.get("regional_validation_status"),
    )
    logger.info("Reports:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    if report.verdict == "REGIONAL_VALIDATION_INTEGRATION_INCOMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
