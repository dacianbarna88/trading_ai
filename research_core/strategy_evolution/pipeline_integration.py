"""
Strategy Evolution pipeline integration — Phase IX Sprint IX.2C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.strategy_evolution.daily_runner_report import (
    DEFAULT_JSON_PATH as CANONICAL_REPORT_PATH,
    SCHEMA_NAME as CANONICAL_SCHEMA,
)

logger = logging.getLogger(__name__)

CANONICAL_PIPELINE_MODULE = "research_core/strategy_evolution/daily_runner.py"


def load_canonical_daily_runner_report(
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load canonical daily runner JSON — read-only, no pipeline re-execution."""
    path = json_path or CANONICAL_REPORT_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Canonical daily runner read failed: %s", exc)
        return None
    if data.get("schema") != CANONICAL_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data


def pipeline_reference() -> dict[str, Any]:
    """Reference for pipeline steps — official conclusions via daily runner only."""
    data = load_canonical_daily_runner_report()
    base: dict[str, Any] = {
        "canonical_pipeline": CANONICAL_PIPELINE_MODULE,
        "official_entry_point": CANONICAL_PIPELINE_MODULE,
        "daily_runner_report_available": data is not None,
    }
    if data is None:
        return base
    base.update(
        {
            "schema": data.get("schema"),
            "verdict": data.get("verdict"),
            "top_ranked_strategy_id": data.get("top_ranked_strategy_id"),
            "top_ranked_strategy_score": data.get("top_ranked_strategy_score"),
            "promotion_review_candidate_id": data.get("promotion_review_candidate_id"),
        }
    )
    return base
