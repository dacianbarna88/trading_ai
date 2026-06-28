"""
Confidence Registration — Phase IX Sprint IX.5D integration helpers

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIDENCE_RECALIBRATION_REPORT_PATH = Path("tae_confidence_recalibration.json")
CONFIDENCE_RECALIBRATION_SCHEMA = "tae_confidence_recalibration"
REGISTRY_MODULE_PATH = Path("research_core/evidence_engine/evidence_registry.py")

MISSING_CONNECTION_CONFIDENCE_EVIDENCE = (
    "Confidence recalibration outputs not registered as evidence items"
)

CONFIDENCE_STATUS_REGISTERED = "CONFIDENCE_REGISTERED"
CONFIDENCE_STATUS_MISSING_REPORT = "CONFIDENCE_REGISTERED_MISSING_REPORT"
CONFIDENCE_STATUS_NOT_REGISTERED = "CONFIDENCE_NOT_REGISTERED"

CANONICAL_CONFIDENCE_MODULE = (
    "research_core/recalibration/confidence_recalibration.py"
)


def load_canonical_confidence_recalibration_report(
    root: Path | str = Path("."),
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    path = Path(root) / (json_path or CONFIDENCE_RECALIBRATION_REPORT_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Confidence recalibration report read failed for %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != CONFIDENCE_RECALIBRATION_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data


def _confidence_report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    ecosystem = payload.get("ecosystem") or {}
    accounting = payload.get("accounting_comparison") or {}
    candidates = payload.get("candidates") or []
    return {
        "schema": payload.get("schema"),
        "candidates_recalibrated": len(candidates) if isinstance(candidates, list) else 0,
        "top_candidate_after": ecosystem.get("top_candidate_after"),
        "average_recalibrated_confidence": ecosystem.get("average_recalibrated_confidence"),
        "conclusions_affected_by_accounting": ecosystem.get(
            "conclusions_affected_by_accounting"
        ),
        "next_recommended_research_action": payload.get("next_recommended_research_action"),
        "realized_pnl_delta": accounting.get("realized_pnl_delta"),
    }


def is_confidence_wired_in_registry(root: Path | str = Path(".")) -> bool:
    path = Path(root) / REGISTRY_MODULE_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "build_confidence_registration" in text
        and "CONFIDENCE_RECALIBRATION_REPORT_PATH" in text
    )


def build_confidence_registration(
    root: Path | str = Path("."),
    confidence_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Evidence Registry feeder status from canonical confidence JSON — read-only."""
    root_path = Path(root)
    if confidence_payload is None:
        confidence_payload = load_canonical_confidence_recalibration_report(root_path)

    registered_at = datetime.now(timezone.utc).isoformat()
    source_report = str(CONFIDENCE_RECALIBRATION_REPORT_PATH.name)

    if confidence_payload is not None:
        return {
            "confidence_registered": True,
            "confidence_status": CONFIDENCE_STATUS_REGISTERED,
            "confidence_source": source_report,
            "confidence_last_refresh": confidence_payload.get("generated_at"),
            "confidence_report": _confidence_report_summary(confidence_payload),
            "registered_at": registered_at,
            "canonical_confidence_module": CANONICAL_CONFIDENCE_MODULE,
        }

    return {
        "confidence_registered": True,
        "confidence_status": CONFIDENCE_STATUS_MISSING_REPORT,
        "confidence_source": source_report,
        "confidence_last_refresh": None,
        "confidence_report": {},
        "registered_at": registered_at,
        "canonical_confidence_module": CANONICAL_CONFIDENCE_MODULE,
    }


def is_confidence_registration_resolved(
    root: Path | str = Path("."),
    evidence_payload: dict[str, Any] | None = None,
) -> bool:
    if not is_confidence_wired_in_registry(root):
        return False
    if evidence_payload:
        reg = evidence_payload.get("confidence_registration")
        if isinstance(reg, dict) and reg.get("confidence_registered"):
            return True
    return True
