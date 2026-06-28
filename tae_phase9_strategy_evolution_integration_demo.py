#!/usr/bin/env python3
"""
TAE Phase IX Sprint IX.2C — Strategy Evolution Pipeline Integration Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.ecosystem_audit.audit_constants import PROTECTED_PATHS
from research_core.strategy_evolution.pipeline_integration import (
    CANONICAL_PIPELINE_MODULE,
    CANONICAL_REPORT_PATH,
)
from research_core.strategy_evolution.strategy_integration_report import StrategyIntegrationAudit
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
    logger.info("TAE Phase IX Sprint IX.2C — Strategy Evolution Pipeline Integration")
    logger.info("Safety: %s", SAFETY_BANNER)
    logger.info("Canonical runner: %s", CANONICAL_PIPELINE_MODULE)

    before = _protected_mtime_snapshot(root)
    audit = StrategyIntegrationAudit()
    dep_map, report = audit.run()
    paths = audit.persist_all(dep_map, report)
    _verify_protected_unchanged(root, before)

    print()
    print("===== TAE STRATEGY EVOLUTION PIPELINE INTEGRATION — SPRINT IX.2C =====")
    print()
    print(f"Safety: {SAFETY_BANNER}")
    print(f"Canonical runner: {CANONICAL_PIPELINE_MODULE}")
    print(f"Canonical JSON: {CANONICAL_REPORT_PATH} (exists={CANONICAL_REPORT_PATH.is_file()})")
    print()
    print(f"Dependency map verdict: {dep_map.verdict}")
    print(f"Integration verdict: {report.verdict}")
    print()
    print(f"Runner count: {dep_map.runner_count} (required: 1)")
    print(f"Single runner verified: {report.single_runner_verified}")
    print(f"Promotion gate review-only: {report.promotion_gate_review_only_verified}")
    print(f"Paper tracking paper-only: {report.paper_tracking_paper_only_verified}")
    print(f"Competing step demos: {len(report.competing_demos)}")
    print()
    print("Integration targets:")
    for target in report.integration_targets:
        print(f"  [{target.status.value}] {target.module_path} ({target.pipeline_role})")
    print()
    print("Reports written:")
    for key, path in sorted(paths.items()):
        print(f"  {path}")
    print()
    print("Protected files verified unchanged.")
    return 0 if report.verdict == "STRATEGY_EVOLUTION_INTEGRATION_READY" else 1


if __name__ == "__main__":
    sys.exit(main())
