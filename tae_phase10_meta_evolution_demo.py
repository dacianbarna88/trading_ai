#!/usr/bin/env python3
"""
TAE Phase X Sprint X.2B — Meta Intelligence Evolution Engine Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | RECOMMENDATION_ONLY

Evidence-based evolution advisor — advisory output for human review only.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.meta_intelligence.meta_evolution_engine import MetaEvolutionEngine
from research_core.meta_intelligence.meta_evolution_report import (
    MetaEvolutionReportStore,
    MetaEvolutionVerdict,
)
from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_evolution.candidate_report import SAFETY_BANNER

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
    logger.info("TAE Phase X Sprint X.2B — Meta Intelligence Evolution Engine")
    logger.info("Safety: %s | RECOMMENDATION_ONLY", SAFETY_BANNER)

    before = _snapshot_mtimes(root)

    engine = MetaEvolutionEngine(root)
    report = engine.analyze()

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during analysis")

    json_path, txt_path = MetaEvolutionReportStore().persist(report)

    logger.info("Sources loaded: %d/%d", report.sources_loaded_count, len(report.sources_loaded))
    logger.info("Meta Intelligence verdict: %s", report.meta_intelligence_verdict)
    logger.info("Recommendations: %d", len(report.recommendations))
    for category, count in sorted(report.recommendation_summary.items()):
        logger.info("  %s: %d", category, count)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == MetaEvolutionVerdict.META_EVOLUTION_INSUFFICIENT_DATA:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
