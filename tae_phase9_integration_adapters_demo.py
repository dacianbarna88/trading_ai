#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.3 — Integration Adapter Layer Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.integration_adapters.adapter_registry import all_adapters
from research_core.integration_adapters.adapter_report import EcosystemAdapterAudit, PROTECTED_PATHS
from research_core.integration_adapters.base_adapter import ADAPTER_RULE, SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def _verify_protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file() or full.stat().st_mtime != mtime:
            return False
    return True


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.3 — Integration Adapter Layer")
    logger.info("Safety: %s", SAFETY_BANNER)
    logger.info("Architecture: %s", ADAPTER_RULE)

    before = _protected_mtime_snapshot(root)
    protected_ok = _verify_protected_unchanged(root, before)

    audit = EcosystemAdapterAudit(root)
    registry, dep_map, report = audit.run(protected_ok=protected_ok)
    paths = audit.persist_all(registry, dep_map, report)

    logger.info("Adapters registered: %d", registry.adapter_count)
    logger.info("Contract coverage: %d/7", registry.contract_coverage)

    for adapter in all_adapters(root):
        desc = adapter.describe()
        status = adapter.adapter_status().value
        logger.info(
            "  %s — %s [%s]",
            desc.adapter_id,
            desc.subsystem_name,
            status,
        )

    logger.info("Migration backlog: needs_migration=%d legacy=%d forbidden=%d",
                dep_map.needs_migration_count,
                dep_map.legacy_direct_link_count,
                dep_map.forbidden_count)
    logger.info("Reports written:")
    for name, path in paths.items():
        logger.info("  %s: %s", name, path)

    logger.info("Final verdict: %s", report.verdict)
    print(report.format_text())

    if report.verdict.endswith("FAILED_PROTECTED_FILE_MODIFIED"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
