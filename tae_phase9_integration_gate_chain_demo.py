#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.5E — Integration Gate Chain Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from integration_layer import EvidenceIntegrationGate, IntegrationReportStore
from integration_layer.integration_gate_chain import is_integration_gate_chained
from integration_layer.integration_gate_chain_report import (
    IntegrationGateChainAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)
from integration_layer.integration_report import SAFETY_BANNER
from research_core.ecosystem_inventory.inventory_audit import EcosystemInventoryAudit
from research_core.ecosystem_inventory.inventory_report import EcosystemInventoryReportStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.5E — Integration Gate Chain")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    before_wired = is_integration_gate_chained(root)

    gate = EvidenceIntegrationGate()
    integration_report = gate.evaluate()
    store = IntegrationReportStore()
    store.persist(integration_report)
    store.persist_txt(integration_report)

    audit = IntegrationGateChainAudit(root)
    report = audit.run(
        before_wired=before_wired,
        protected_ok=verify_protected_unchanged(root, before),
    )
    paths = audit.persist(report)

    inv = EcosystemInventoryAudit(root).audit()
    inv_store = EcosystemInventoryReportStore()
    paths["inventory_json"] = inv_store.persist(inv)
    paths["inventory_txt"] = inv_store.persist_txt(inv)

    chain = integration_report.promotion_gate_chain or {}
    logger.info("Integration gate verdict: %s", integration_report.verdict.value)
    logger.info("Chain status: %s", chain.get("integration_gate_status"))
    logger.info("Reports:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    if report.verdict == "INTEGRATION_GATE_CHAIN_INCOMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
