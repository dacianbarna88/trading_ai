#!/usr/bin/env python3
"""
TAE Phase X Sprint X.2A — Meta Intelligence Layer Demo

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only observer above the Full Ecosystem Run.
Consumes canonical JSON reports only — no trading logic, no execution.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.meta_intelligence import (
    MetaIntelligenceEngine,
    MetaIntelligenceReportStore,
    MetaIntelligenceVerdict,
    SAFETY_BANNER,
)
from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS

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
    logger.info("TAE Phase X Sprint X.2A — Meta Intelligence Layer")
    logger.info("Safety: %s", SAFETY_BANNER)

    before = _snapshot_mtimes(root)

    engine = MetaIntelligenceEngine(root)
    report = engine.analyze()

    if not _protected_unchanged(root, before):
        logger.warning("Protected files changed during analysis")

    json_path, txt_path = MetaIntelligenceReportStore().persist(report)

    obs = report.strategic_observations
    confidence = obs.get("overall_ecosystem_confidence") or {}
    logger.info("Sources loaded: %d/%d", report.sources_loaded_count, len(report.sources_loaded))
    logger.info(
        "Ecosystem confidence: %s (%s)",
        confidence.get("confidence_label"),
        confidence.get("composite_score"),
    )
    logger.info("Highest quality strategy: %s", (obs.get("highest_quality_strategy") or {}).get("candidate_id"))
    logger.info("System maturity: %s", (obs.get("system_maturity") or {}).get("maturity_level"))
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if report.verdict == MetaIntelligenceVerdict.META_INTELLIGENCE_INSUFFICIENT_DATA:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
