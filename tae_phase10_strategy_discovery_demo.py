#!/usr/bin/env python3
"""
TAE Phase X Sprint X.3A — Strategy Discovery Engine Demo

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Generates new research-only strategy candidates. Does not modify existing
strategies or connect to a broker.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_discovery.strategy_discovery_report import (
    DISCOVERY_SAFETY_BANNER,
    StrategyDiscoveryReportStore,
    StrategyDiscoveryVerdict,
)
from research_core.strategy_discovery.strategy_candidate_builder import StrategyDiscoveryEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _snapshot_mtimes(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[str(rel)] = full.stat().st_mtime
    return snapshot


def _protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    after = _snapshot_mtimes(root)
    for key, mtime in before.items():
        if key not in after or after[key] != mtime:
            return False
    return True


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase X Sprint X.3A — Strategy Discovery Engine")
    logger.info("Safety: %s", DISCOVERY_SAFETY_BANNER)

    before = _snapshot_mtimes(root)

    engine = StrategyDiscoveryEngine(root)
    report = engine.discover()

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during discovery")

    json_path, txt_path = StrategyDiscoveryReportStore().persist(report)

    logger.info("Hypotheses generated: %d", report.hypothesis_count)
    logger.info("Candidates built: %d", report.candidate_count)
    logger.info("Average confidence seed: %.4f", report.average_confidence_seed)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == StrategyDiscoveryVerdict.STRATEGY_DISCOVERY_INSUFFICIENT_FEATURES:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
