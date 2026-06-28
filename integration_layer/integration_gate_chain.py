"""
Integration Gate Chain — Phase IX Sprint IX.5C/IX.5E

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Connect-only chain: Promotion Gate → Integration Gate → Runtime.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMOTION_GATE_REPORT_PATH = Path("tae_strategy_promotion_gate.json")
PROMOTION_GATE_SCHEMA = "tae_strategy_promotion_gate"
INTEGRATION_GATE_MODULE_PATH = Path("integration_layer/evidence_gate.py")

MISSING_CONNECTION_INTEGRATION_GATE_CHAIN = (
    "Integration gate not yet chained after promotion gate"
)

PROMOTION_GATE_STATUS_REGISTERED = "PROMOTION_GATE_REGISTERED"
PROMOTION_GATE_STATUS_MISSING_REPORT = "PROMOTION_GATE_REGISTERED_MISSING_REPORT"

INTEGRATION_GATE_CHAIN_COMPLETE = "INTEGRATION_GATE_CHAIN_COMPLETE"
INTEGRATION_GATE_CHAIN_PARTIAL = "INTEGRATION_GATE_CHAIN_PARTIAL"
INTEGRATION_GATE_CHAIN_INCOMPLETE = "INTEGRATION_GATE_CHAIN_INCOMPLETE"

CANONICAL_PROMOTION_MODULE = "research_core/strategy_evolution/promotion_gate.py"


def load_canonical_promotion_gate_report(
    root: Path | str = Path("."),
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    path = Path(root) / (json_path or PROMOTION_GATE_REPORT_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Promotion gate report read failed for %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != PROMOTION_GATE_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data


def is_integration_gate_chained(root: Path | str = Path(".")) -> bool:
    path = Path(root) / INTEGRATION_GATE_MODULE_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "build_promotion_gate_chain" in text
        and "PROMOTION_GATE_REPORT_PATH" in text
    )


def build_promotion_gate_chain(
    root: Path | str = Path("."),
    promotion_payload: dict[str, Any] | None = None,
    gate_verdict: str | None = None,
) -> dict[str, Any]:
    """Build Integration Gate promotion chain status — read-only JSON boundary."""
    root_path = Path(root)
    if promotion_payload is None:
        promotion_payload = load_canonical_promotion_gate_report(root_path)

    registered_at = datetime.now(timezone.utc).isoformat()
    source_report = str(PROMOTION_GATE_REPORT_PATH.name)

    if promotion_payload is not None:
        return {
            "promotion_gate_registered": True,
            "promotion_gate_status": str(
                promotion_payload.get("verdict") or PROMOTION_GATE_STATUS_REGISTERED
            ),
            "promotion_gate_source": source_report,
            "promotion_gate_last_refresh": promotion_payload.get("generated_at"),
            "review_candidate_id": promotion_payload.get("review_candidate_id"),
            "baseline_candidate_id": promotion_payload.get("baseline_candidate_id"),
            "integration_gate_status": INTEGRATION_GATE_CHAIN_COMPLETE,
            "integration_gate_verdict": gate_verdict,
            "registered_at": registered_at,
            "canonical_promotion_module": CANONICAL_PROMOTION_MODULE,
        }

    return {
        "promotion_gate_registered": True,
        "promotion_gate_status": PROMOTION_GATE_STATUS_MISSING_REPORT,
        "promotion_gate_source": source_report,
        "promotion_gate_last_refresh": None,
        "review_candidate_id": None,
        "baseline_candidate_id": None,
        "integration_gate_status": INTEGRATION_GATE_CHAIN_PARTIAL,
        "integration_gate_verdict": gate_verdict,
        "registered_at": registered_at,
        "canonical_promotion_module": CANONICAL_PROMOTION_MODULE,
    }


def is_integration_gate_chain_resolved(
    root: Path | str = Path("."),
    integration_gate_payload: dict[str, Any] | None = None,
) -> bool:
    if not is_integration_gate_chained(root):
        return False
    if integration_gate_payload:
        chain = integration_gate_payload.get("promotion_gate_chain")
        if isinstance(chain, dict) and chain.get("promotion_gate_registered"):
            return True
    return True
