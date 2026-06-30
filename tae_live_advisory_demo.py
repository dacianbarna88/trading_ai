#!/usr/bin/env python3
"""
TAE Phase X Sprint X.7C — Live Advisory Signal Bridge Demo

PAPER_ONLY | ADVISORY_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Produces tae_live_advisory.json from advisory index, live CSV snapshots, and
selected TAE reports. Does not modify live_bot.py, portfolio.csv, or live_signals.csv.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from research_core.governance.live_advisory_bridge import (
    LIVE_ADVISORY_SAFETY_BANNER,
    LIVE_BOT_PATH,
    LiveAdvisoryBridge,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    root = Path(".")
    logger.info("TAE Phase X Sprint X.7C — Live Advisory Signal Bridge")
    logger.info("Safety: %s", LIVE_ADVISORY_SAFETY_BANNER)

    live_bot_mtime = None
    live_bot_path = root / LIVE_BOT_PATH
    if live_bot_path.is_file():
        live_bot_mtime = live_bot_path.stat().st_mtime

    bridge = LiveAdvisoryBridge(root)
    report, json_path = bridge.build_and_persist(live_bot_mtime_before=live_bot_mtime)

    logger.info("Output: %s", json_path)
    logger.info("Action: %s", report.action)
    logger.info("block_new_buy: %s", report.block_new_buy)
    logger.info("Confidence: %d", report.confidence)
    logger.info("Blocking warnings: %d", len(report.blocking_warnings))
    logger.info("Stale false positives: %d", len(report.stale_false_positive_warnings))
    logger.info("Blockers: %d", len(report.blockers))
    logger.info("live_bot_not_modified: %s", report.live_bot_not_modified)

    print(bridge.format_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
