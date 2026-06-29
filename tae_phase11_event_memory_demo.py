#!/usr/bin/env python3
"""
TAE Phase X Sprint X.6A — Event Schema + Memory Scaffold Demo

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Schema support only: empty event memory registry, validation, round-trip.
No ingestion, models, or wiring.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.market_intelligence.event_memory_report import (
    EVENT_MEMORY_SAFETY_BANNER,
    EventMemoryReport,
    EventMemoryReportStore,
    EventMemoryVerdict,
)
from research_core.market_intelligence.event_memory_store import EventMemoryStore
from research_core.market_intelligence.event_schema import CURRENT_SCHEMA_VERSION

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROTECTED_PATHS = (
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("config/settings.py"),
)


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
    logger.info("TAE Phase X Sprint X.6A — Event Schema + Memory Scaffold")
    logger.info("Safety: %s", EVENT_MEMORY_SAFETY_BANNER)

    before = _snapshot_mtimes(root)
    store = EventMemoryStore(root / "tae_event_memory.json")
    registry = store.create_empty_registry()

    valid, errors = store.validate(registry)
    round_trip_ok, round_trip_errors = store.round_trip(registry)
    all_errors = errors + round_trip_errors

    warnings: list[str] = []
    if not _protected_unchanged(root, before):
        warnings.append("Protected files changed during scaffold demo")

    if valid and round_trip_ok and not warnings:
        verdict = EventMemoryVerdict.EVENT_MEMORY_SCAFFOLD_READY
    elif valid and round_trip_ok:
        verdict = EventMemoryVerdict.EVENT_MEMORY_SCAFFOLD_READY_WITH_WARNINGS
    else:
        verdict = EventMemoryVerdict.EVENT_MEMORY_SCHEMA_FAILED

    report = EventMemoryReport(
        verdict=verdict,
        event_count=int(registry.get("event_count", 0)),
        schema_validation_passed=valid,
        round_trip_passed=round_trip_ok,
        schema_version=CURRENT_SCHEMA_VERSION,
        registry=store.load(),
        validation_errors=all_errors,
        warnings=warnings,
    )

    json_path, txt_path = EventMemoryReportStore(
        json_path=root / "tae_event_memory.json",
        txt_path=root / "tae_event_memory.txt",
    ).persist(report)

    logger.info("Events stored: %d", report.event_count)
    logger.info("Schema validation: %s", report.schema_validation_passed)
    logger.info("Round-trip: %s", report.round_trip_passed)
    logger.info("Reports: %s, %s", json_path, txt_path)
    logger.info("Final verdict: %s", report.verdict.value)

    print(report.format_text())

    if verdict == EventMemoryVerdict.EVENT_MEMORY_SCHEMA_FAILED:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
