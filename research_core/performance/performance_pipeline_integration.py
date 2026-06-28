"""
Performance pipeline integration — Phase IX Sprint IX.5A

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Read-only pipeline reference for canonical performance audit JSON outputs.
No new performance engine — connect only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.performance.performance_report import (
    DEFAULT_AUDIT_JSON_PATH as STRATEGIC_REPORT_PATH,
    SCHEMA_NAME as STRATEGIC_SCHEMA,
)
from research_core.performance.accounting_integrity_auditor import (
    DEFAULT_INTEGRITY_JSON_PATH as INTEGRITY_REPORT_PATH,
    SCHEMA_NAME as INTEGRITY_SCHEMA,
)

logger = logging.getLogger(__name__)

CANONICAL_STRATEGIC_MODULE = "research_core/performance/strategic_performance_auditor.py"
CANONICAL_INTEGRITY_MODULE = "research_core/performance/accounting_integrity_auditor.py"

PIPELINE_STAGE = "performance"
PIPELINE_ENTRY = "after_paper_tracking"
PIPELINE_EXIT = "before_evidence_registry"

PIPELINE_ORDER = [
    "evidence_engine",
    "simulation_lab",
    "strategy_evolution",
    "promotion_gate",
    "paper_tracking",
    PIPELINE_STAGE,
    "evidence_registry",
    "runtime",
    "quick_health",
]

DAILY_RUNNER_PERFORMANCE_STEP_NAME = "Performance Pipeline (Canonical JSON)"
MISSING_CONNECTION_PERFORMANCE_DAILY_RUNNER = (
    "Performance audit not invoked by daily runner"
)

PERFORMANCE_PIPELINE_CONNECTED = "PERFORMANCE_PIPELINE_CONNECTED"
PERFORMANCE_PIPELINE_PARTIAL = "PERFORMANCE_PIPELINE_PARTIAL"
PERFORMANCE_PIPELINE_DEGRADED = "PERFORMANCE_PIPELINE_DEGRADED"

DAILY_RUNNER_PATH = Path("research_core/strategy_evolution/daily_runner.py")


def load_canonical_strategic_performance(
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    path = json_path or STRATEGIC_REPORT_PATH
    return _load_report(path, STRATEGIC_SCHEMA)


def load_canonical_accounting_integrity(
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    path = json_path or INTEGRITY_REPORT_PATH
    return _load_report(path, INTEGRITY_SCHEMA)


def _load_report(path: Path, expected_schema: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Performance report read failed for %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema") != expected_schema:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data


def pipeline_reference(root: Path | str = Path(".")) -> dict[str, Any]:
    """Official performance pipeline stage reference — JSON boundary only."""
    root_path = Path(root)
    strategic = load_canonical_strategic_performance(root_path / STRATEGIC_REPORT_PATH.name)
    integrity = load_canonical_accounting_integrity(root_path / INTEGRITY_REPORT_PATH.name)

    ref: dict[str, Any] = {
        "pipeline_stage": PIPELINE_STAGE,
        "pipeline_entry": PIPELINE_ENTRY,
        "pipeline_exit": PIPELINE_EXIT,
        "pipeline_order": list(PIPELINE_ORDER),
        "canonical_strategic_module": CANONICAL_STRATEGIC_MODULE,
        "canonical_integrity_module": CANONICAL_INTEGRITY_MODULE,
        "strategic_report": STRATEGIC_REPORT_PATH.name,
        "integrity_report": INTEGRITY_REPORT_PATH.name,
        "strategic_report_available": strategic is not None,
        "integrity_report_available": integrity is not None,
    }

    if strategic:
        perf = strategic.get("performance") or {}
        ref.update(
            {
                "strategic_status": "STRATEGIC_PERFORMANCE_AUDIT_AVAILABLE",
                "strategic_schema": strategic.get("schema"),
                "all_history_realized_pnl": perf.get("all_history_realized_pnl"),
                "reference_date": perf.get("reference_date"),
            }
        )
    if integrity:
        ref.update(
            {
                "integrity_anomalies_found": integrity.get("anomalies_found"),
                "integrity_sells_audited": integrity.get("sells_audited"),
                "accounting_state_completeness": integrity.get("accounting_state_completeness"),
            }
        )
    return ref


def daily_runner_performance_step_verdict(root: Path | str = Path(".")) -> str:
    """Read-only daily-runner performance stage — consumes canonical JSON only."""
    ref = pipeline_reference(root)
    if ref.get("strategic_report_available") and ref.get("integrity_report_available"):
        return PERFORMANCE_PIPELINE_CONNECTED
    if ref.get("strategic_report_available"):
        return PERFORMANCE_PIPELINE_PARTIAL
    return PERFORMANCE_PIPELINE_DEGRADED


def is_daily_runner_performance_wired(root: Path | str = Path(".")) -> bool:
    path = Path(root) / DAILY_RUNNER_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "performance_pipeline_integration" in text
        and "daily_runner_performance_step_verdict" in text
    )


def is_performance_pipeline_resolved(
    root: Path | str = Path("."),
    daily_runner_payload: dict[str, Any] | None = None,
) -> bool:
    """True when daily runner is wired and canonical performance JSON is reachable."""
    if not is_daily_runner_performance_wired(root):
        return False
    ref = pipeline_reference(root)
    if not ref.get("strategic_report_available"):
        return False
    if daily_runner_payload:
        for step in daily_runner_payload.get("steps", []):
            if not isinstance(step, dict):
                continue
            if DAILY_RUNNER_PERFORMANCE_STEP_NAME in str(step.get("step_name", "")):
                return bool(step.get("succeeded"))
    return True
