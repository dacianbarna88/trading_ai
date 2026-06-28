"""
Regional Validation Integration — Phase IX Sprint IX.5C

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Connect-only registration of Regional Validation as Promotion Gate feeder.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REGIONAL_VALIDATION_REPORT_PATH = Path("tae_regional_validation_kn_d5_00002.json")
REGIONAL_VALIDATION_SCHEMA = "tae_regional_validation"
PROMOTION_GATE_MODULE_PATH = Path("research_core/strategy_evolution/promotion_gate.py")

MISSING_CONNECTION_REGIONAL_PROMOTION_GATE = (
    "Regional validation not connected to promotion gate"
)

REGIONAL_VALIDATION_STATUS_REGISTERED = "REGIONAL_VALIDATION_REGISTERED"
REGIONAL_VALIDATION_STATUS_MISSING_REPORT = (
    "REGIONAL_VALIDATION_REGISTERED_MISSING_REPORT"
)
REGIONAL_VALIDATION_STATUS_NOT_REGISTERED = "REGIONAL_VALIDATION_NOT_REGISTERED"

CANONICAL_REGIONAL_MODULE = (
    "research_core/regional_validation/regional_gap_closure.py"
)


def load_canonical_regional_validation_report(
    root: Path | str = Path("."),
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    path = Path(root) / (json_path or REGIONAL_VALIDATION_REPORT_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Regional validation report read failed for %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != REGIONAL_VALIDATION_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data


def is_regional_validation_wired_in_promotion_gate(root: Path | str = Path(".")) -> bool:
    path = Path(root) / PROMOTION_GATE_MODULE_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "build_regional_validation_registration" in text
        and "REGIONAL_VALIDATION_REPORT_PATH" in text
    )


def build_regional_validation_registration(
    root: Path | str = Path("."),
    regional_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Promotion Gate feeder status from canonical regional JSON — read-only."""
    root_path = Path(root)
    if regional_payload is None:
        regional_payload = load_canonical_regional_validation_report(root_path)

    registered_at = datetime.now(timezone.utc).isoformat()
    source_report = str(REGIONAL_VALIDATION_REPORT_PATH.name)

    if regional_payload is not None:
        return {
            "regional_validation_registered": True,
            "regional_validation_status": REGIONAL_VALIDATION_STATUS_REGISTERED,
            "regional_validation_source": source_report,
            "regional_validation_last_refresh": regional_payload.get("generated_at"),
            "readiness_projection": regional_payload.get("readiness_projection"),
            "validations_not_available": int(
                regional_payload.get("validations_not_available", 0)
            ),
            "registered_at": registered_at,
            "canonical_regional_module": CANONICAL_REGIONAL_MODULE,
        }

    return {
        "regional_validation_registered": True,
        "regional_validation_status": REGIONAL_VALIDATION_STATUS_MISSING_REPORT,
        "regional_validation_source": source_report,
        "regional_validation_last_refresh": None,
        "readiness_projection": None,
        "validations_not_available": 0,
        "registered_at": registered_at,
        "canonical_regional_module": CANONICAL_REGIONAL_MODULE,
    }


def is_regional_validation_integration_resolved(
    root: Path | str = Path("."),
    promotion_payload: dict[str, Any] | None = None,
) -> bool:
    if not is_regional_validation_wired_in_promotion_gate(root):
        return False
    if promotion_payload:
        reg = promotion_payload.get("regional_validation_registration")
        if isinstance(reg, dict) and reg.get("regional_validation_registered"):
            return True
    return True
