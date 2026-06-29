#!/usr/bin/env python3
"""
TAE Shadow Validation Report — Phase X Sprint X.9

READ_ONLY | CONNECTED_SHADOW_VALIDATION | NO_EXECUTION

Aggregates tae_shadow_validation_events.csv into tae_shadow_validation_summary.json.
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.governance.shadow_validation_ledger import (
    CSV_FIELDNAMES,
    DEFAULT_EVENTS_PATH,
    EVENT_BUY_ALLOWED,
    EVENT_BUY_BLOCKED_BY_TAE,
    EVENT_BUY_SKIPPED_OTHER_REASON,
    LIVE_TRADING_IMPACT,
    MODE,
)

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY_PATH = Path("tae_shadow_validation_summary.json")
SCHEMA = "tae.shadow_validation_summary.v1"


def _parse_json_list(cell: str) -> list[str]:
    if not cell or not str(cell).strip():
        return []
    try:
        value = json.loads(cell)
    except json.JSONDecodeError:
        return [str(cell)]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _safe_float(value: str) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_int(value: str) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def load_events(path: Path | str | None = None) -> list[dict[str, Any]]:
    events_path = Path(path or DEFAULT_EVENTS_PATH)
    if not events_path.is_file():
        return []

    rows: list[dict[str, Any]] = []
    with events_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {key: raw.get(key, "") for key in CSV_FIELDNAMES}
            row["advisory_reasons"] = _parse_json_list(row.get("advisory_reasons", ""))
            row["advisory_blockers"] = _parse_json_list(row.get("advisory_blockers", ""))
            row["score"] = _safe_float(row.get("score", ""))
            row["price"] = _safe_float(row.get("price", ""))
            row["intended_trade_usd"] = _safe_float(row.get("intended_trade_usd", ""))
            row["shares"] = _safe_float(row.get("shares", ""))
            row["advisory_confidence"] = _safe_int(row.get("advisory_confidence", ""))
            block_raw = str(row.get("block_new_buy", "")).strip().lower()
            row["block_new_buy"] = block_raw in {"true", "1", "yes"}
            rows.append(row)
    return rows


def build_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    buy_allowed = sum(1 for e in events if e.get("event_type") == EVENT_BUY_ALLOWED)
    buy_blocked = sum(
        1 for e in events if e.get("event_type") == EVENT_BUY_BLOCKED_BY_TAE
    )
    buy_skipped = sum(
        1 for e in events if e.get("event_type") == EVENT_BUY_SKIPPED_OTHER_REASON
    )

    block_rate = round(buy_blocked / total, 4) if total else 0.0

    action_dist = Counter(str(e.get("advisory_action") or "UNKNOWN") for e in events)
    block_reasons = Counter(
        str(e.get("block_reason") or "UNKNOWN")
        for e in events
        if e.get("event_type") in {EVENT_BUY_BLOCKED_BY_TAE, EVENT_BUY_SKIPPED_OTHER_REASON}
    )

    confidences = [
        c
        for c in (e.get("advisory_confidence") for e in events)
        if isinstance(c, int)
    ]
    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    latest = events[-20:] if events else []

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": MODE,
        "live_trading_impact": LIVE_TRADING_IMPACT,
        "source_events_path": str(DEFAULT_EVENTS_PATH),
        "total_events": total,
        "buy_allowed": buy_allowed,
        "buy_blocked_by_tae": buy_blocked,
        "buy_skipped_other_reason": buy_skipped,
        "block_rate": block_rate,
        "advisory_action_distribution": dict(sorted(action_dist.items())),
        "average_advisory_confidence": avg_confidence,
        "top_block_reasons": dict(block_reasons.most_common(10)),
        "latest_20_events": latest,
        "outcome_tracking_status": "PENDING_NEXT_PHASE",
    }


def persist_summary(
    summary: dict[str, Any],
    path: Path | str | None = None,
) -> Path:
    out = Path(path or DEFAULT_SUMMARY_PATH)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    events = load_events()
    summary = build_summary(events)
    out_path = persist_summary(summary)

    logger.info("Events loaded: %d", summary["total_events"])
    logger.info("BUY allowed: %d", summary["buy_allowed"])
    logger.info("BUY blocked by TAE: %d", summary["buy_blocked_by_tae"])
    logger.info("BUY skipped other: %d", summary["buy_skipped_other_reason"])
    logger.info("Output: %s", out_path)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
