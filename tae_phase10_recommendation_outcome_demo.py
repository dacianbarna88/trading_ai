#!/usr/bin/env python3
"""
TAE Phase X Sprint X.2C — Recommendation Outcome Learning Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | LEARNING_ONLY

Evaluates historical Meta Evolution recommendations against accumulated evidence.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.meta_intelligence.recommendation_outcome_engine import (
    RecommendationOutcomeEngine,
)
from research_core.meta_intelligence.recommendation_outcome_report import (
    RecommendationOutcomeReportStore,
    RecommendationOutcomeVerdict,
)
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
    logger.info("TAE Phase X Sprint X.2C — Recommendation Outcome Learning")
    logger.info("Safety: %s | LEARNING_ONLY", SAFETY_BANNER)

    before = _snapshot_mtimes(root)

    engine = RecommendationOutcomeEngine(root)
    report = engine.analyze()

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during analysis")

    json_path, txt_path = RecommendationOutcomeReportStore().persist(report)

    learning = report.learning_metrics
    logger.info("Sources loaded: %d/%d", report.sources_loaded_count, len(report.sources_loaded))
    logger.info("Registry cycles: %d", report.registry_evaluation_cycles)
    logger.info("Recommendations evaluated: %d", len(report.recommendation_history))
    logger.info("Historical score: %s", learning.get("historical_recommendation_score"))
    logger.info("False recommendations: %d", report.false_recommendation_count)
    logger.info("Improvement trend: %s", report.improvement_trend)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == RecommendationOutcomeVerdict.RECOMMENDATION_OUTCOME_INSUFFICIENT_HISTORY:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
