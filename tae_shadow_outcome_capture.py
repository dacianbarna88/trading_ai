#!/usr/bin/env python3
"""
TAE Shadow Outcome Capture — Phase X Sprint X.10

SHADOW_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_AUTO_POLICY_CHANGE

Batch CLI for BUY_BLOCKED_BY_TAE counterfactual outcome attribution.
Implements TAE_X10_EVIDENCE_MODEL.md — extends X.9 shadow validation chain only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from research_core.governance.shadow_outcome_attribution import (
    DEFAULT_OUTCOMES_MD_PATH,
    DEFAULT_OUTCOMES_PATH,
    run_outcome_attribution,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TAE X.10 shadow outcome attribution for BUY_BLOCKED_BY_TAE events"
    )
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--events", default="tae_shadow_validation_events.csv")
    parser.add_argument("--portfolio", default="portfolio.csv")
    parser.add_argument("--signals", default="live_signals.csv")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTCOMES_PATH))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTCOMES_MD_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Compute without writing files")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    report = run_outcome_attribution(
        root=args.root,
        events_path=args.events,
        portfolio_path=args.portfolio,
        signals_path=args.signals,
        json_path=args.output_json,
        md_path=args.output_md,
        dry_run=args.dry_run,
    )

    logging.info("Eligible blocked events: %s", report.get("eligible_events"))
    logging.info("Outcome tracking status: %s", report.get("outcome_tracking_status"))
    if not args.dry_run:
        logging.info("Wrote %s", args.output_json)
        logging.info("Wrote %s", args.output_md)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
