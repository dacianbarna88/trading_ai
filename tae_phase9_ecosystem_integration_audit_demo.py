#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.1 — Ecosystem Integration Audit Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Produces:
  - tae_ecosystem_inventory.json / .txt
  - tae_dependency_graph.json / .txt
  - tae_integration_gap_report.json / .txt
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.ecosystem_audit.integration_gap_report import EcosystemIntegrationAudit
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def _verify_protected_unchanged(root: Path, before: dict[str, float]) -> None:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file():
            raise RuntimeError(f"Protected file missing after audit: {rel}")
        if full.stat().st_mtime != mtime:
            raise RuntimeError(f"Protected file modified during audit: {rel}")


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase IX Sprint IX.1 — Ecosystem Integration Audit")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = _protected_mtime_snapshot(root)
    audit = EcosystemIntegrationAudit(root)
    inventory, graph, gap = audit.run()
    paths = audit.persist_all(inventory, graph, gap)
    _verify_protected_unchanged(root, before)

    print()
    print("===== TAE ECOSYSTEM INTEGRATION AUDIT — SPRINT IX.1 =====")
    print()
    print(f"Safety: {SAFETY_BANNER}")
    print(f"Inventory verdict: {inventory.verdict}")
    print(f"Graph verdict: {graph.verdict}")
    print(f"Gap verdict: {gap.verdict}")
    print()
    print(f"Modules scanned: {inventory.total_modules}")
    print(f"Dependency nodes: {len(graph.nodes)} | edges: {len(graph.edges)}")
    print(f"Duplicate groups: {len(inventory.duplicate_groups)}")
    print(f"Competing runners: {len(gap.competing_runners)}")
    print(f"Integration gaps: {len(gap.integration_gaps)}")
    print(f"Connect recommendations: {len(gap.connect_recommendations)}")
    print(f"Unused modules: {len(gap.unused_modules)}")
    print(f"Unreferenced modules: {len(gap.unreferenced_modules)}")
    print(f"Disconnected modules: {len(gap.disconnected_modules)}")
    print()
    print("Reports written:")
    for key, path in sorted(paths.items()):
        print(f"  {path}")
    print()
    print("Protected files verified unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
