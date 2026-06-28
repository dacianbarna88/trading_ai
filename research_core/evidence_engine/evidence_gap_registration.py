"""
Evidence Gap Registration — Phase IX Sprint IX.5B integration helpers

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EVIDENCE_GAP_REPORT_PATH = Path("tae_evidence_gap_report.json")
EVIDENCE_GAP_SCHEMA = "tae_evidence_gap_report"
REGISTRY_MODULE_PATH = Path("research_core/evidence_engine/evidence_registry.py")

MISSING_CONNECTION_EVIDENCE_GAP_REGISTRY = (
    "Evidence gap analyzer not wired to evidence_registry refresh"
)

EVIDENCE_GAP_STATUS_REGISTERED = "EVIDENCE_GAP_REGISTERED"
EVIDENCE_GAP_STATUS_MISSING_REPORT = "EVIDENCE_GAP_REGISTERED_MISSING_REPORT"
EVIDENCE_GAP_STATUS_NOT_REGISTERED = "EVIDENCE_GAP_NOT_REGISTERED"

CANONICAL_GAP_MODULE = "research_core/evidence_gap/evidence_gap.py"


def load_canonical_evidence_gap_report(
    root: Path | str = Path("."),
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    path = Path(root) / (json_path or EVIDENCE_GAP_REPORT_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Evidence gap report read failed for %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != EVIDENCE_GAP_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data


def is_evidence_gap_wired_in_registry(root: Path | str = Path(".")) -> bool:
    path = Path(root) / REGISTRY_MODULE_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "build_evidence_gap_registration" in text
        and "EVIDENCE_GAP_REPORT_PATH" in text
    )


def build_evidence_gap_registration(
    root: Path | str = Path("."),
    gap_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Evidence Registry feeder status from canonical gap JSON — read-only."""
    root_path = Path(root)
    if gap_payload is None:
        gap_payload = load_canonical_evidence_gap_report(root_path)

    registered_at = datetime.now(timezone.utc).isoformat()
    source_report = str(EVIDENCE_GAP_REPORT_PATH.name)

    if gap_payload is not None:
        return {
            "evidence_gap_registered": True,
            "evidence_gap_status": EVIDENCE_GAP_STATUS_REGISTERED,
            "evidence_gap_source_report": source_report,
            "evidence_gap_last_loaded": gap_payload.get("generated_at"),
            "evidence_gap_warning_count": int(gap_payload.get("total_gaps", 0)),
            "candidates_analyzed": int(gap_payload.get("candidates_analyzed", 0)),
            "registered_at": registered_at,
            "canonical_gap_module": CANONICAL_GAP_MODULE,
        }

    return {
        "evidence_gap_registered": True,
        "evidence_gap_status": EVIDENCE_GAP_STATUS_MISSING_REPORT,
        "evidence_gap_source_report": source_report,
        "evidence_gap_last_loaded": None,
        "evidence_gap_warning_count": 0,
        "candidates_analyzed": 0,
        "registered_at": registered_at,
        "canonical_gap_module": CANONICAL_GAP_MODULE,
    }


def is_evidence_gap_registration_resolved(
    root: Path | str = Path("."),
    evidence_payload: dict[str, Any] | None = None,
) -> bool:
    if not is_evidence_gap_wired_in_registry(root):
        return False
    if evidence_payload:
        reg = evidence_payload.get("evidence_gap_registration")
        if isinstance(reg, dict) and reg.get("evidence_gap_registered"):
            return True
    return True
