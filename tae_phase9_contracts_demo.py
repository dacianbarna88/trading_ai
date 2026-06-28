#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.2D — Ecosystem Contracts & Interfaces Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.contracts.base_contract import SAFETY_BANNER
from research_core.contracts.contract_report import EcosystemContractsAudit, PROTECTED_PATHS
from research_core.contracts.contract_registry import all_contracts

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
    logger.info("TAE Phase IX Sprint IX.2D — Ecosystem Contracts & Interfaces")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = _protected_mtime_snapshot(root)
    protected_ok = _verify_protected_unchanged(root, before)

    audit = EcosystemContractsAudit(root)
    registry, dep_map, report = audit.run(protected_ok=protected_ok)
    paths = audit.persist_all(registry, dep_map, report)

    print()
    print("===== TAE ECOSYSTEM CONTRACTS — SPRINT IX.2D =====")
    print()
    print(f"Safety: {SAFETY_BANNER}")
    print(f"Contracts defined: {len(all_contracts())}")
    print(f"Verdict: {report.verdict}")
    print()
    print(f"Validation compliant: {report.validation_matrix.get('compliant_count', 0)}/"
          f"{report.validation_matrix.get('total_contracts', 0)}")
    print(f"Legacy direct links: {dep_map.legacy_direct_link_count}")
    print(f"Forbidden dependencies: {dep_map.forbidden_count}")
    print(f"Adapter recommendations: {len(dep_map.adapter_recommendations)}")
    print(f"Protected files unchanged: {report.protected_files_unchanged}")
    print()
    print("Reports written:")
    for key, path in sorted(paths.items()):
        print(f"  {path}")
    print()

    if report.verdict == "ECOSYSTEM_CONTRACTS_FAILED_PROTECTED_FILE_MODIFIED":
        return 2
    if report.verdict == "ECOSYSTEM_CONTRACTS_READY":
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
