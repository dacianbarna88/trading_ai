#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.5D — Confidence Recalibration Registration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_inventory.inventory_audit import EcosystemInventoryAudit
from research_core.ecosystem_inventory.inventory_report import EcosystemInventoryReportStore
from research_core.evidence_engine import EvidenceEngine, EvidenceReportStore
from research_core.evidence_engine.confidence_registration import (
    is_confidence_wired_in_registry,
)
from research_core.evidence_engine.confidence_registration_report import (
    ConfidenceRegistrationAudit,
    protected_mtime_snapshot,
    verify_protected_unchanged,
)
from research_core.evidence_engine.evidence_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.5D — Confidence Registration")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = protected_mtime_snapshot(root)
    before_wired = is_confidence_wired_in_registry(root)

    engine = EvidenceEngine()
    evidence_report = engine.initialize()
    store = EvidenceReportStore()
    store.persist(evidence_report)
    store.persist_txt(evidence_report)

    audit = ConfidenceRegistrationAudit(root)
    report = audit.run(
        before_wired=before_wired,
        protected_ok=verify_protected_unchanged(root, before),
    )
    paths = audit.persist(report)

    inv = EcosystemInventoryAudit(root).audit()
    inv_store = EcosystemInventoryReportStore()
    paths["inventory_json"] = inv_store.persist(inv)
    paths["inventory_txt"] = inv_store.persist_txt(inv)

    confidence_reg = evidence_report.confidence_registration or {}
    logger.info("Evidence engine verdict: %s", evidence_report.verdict.value)
    logger.info("Confidence status: %s", confidence_reg.get("confidence_status"))
    logger.info("Reports:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)
    logger.info("Final verdict: %s", report.verdict)

    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    if report.verdict == "CONFIDENCE_REGISTRATION_INCOMPLETE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
