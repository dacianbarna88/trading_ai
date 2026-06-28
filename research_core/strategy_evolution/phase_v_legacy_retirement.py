"""
Phase V Legacy Retirement — Phase IX Sprint IX.5F

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Connect-only: demote Phase V to LEGACY_COMPATIBILITY_ONLY;
canonical strategy state flows through Phase VIII daily runner.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PHASE_V_MODULE_PATH = Path("research_core/evolution/strategy_evolution.py")
CANONICAL_PIPELINE_PATH = Path("research_core/strategy_evolution/daily_runner.py")
DAILY_RUNNER_MODULE_PATH = CANONICAL_PIPELINE_PATH

RUNTIME_SCAN_DIRS = (
    Path("research_core/runtime"),
)

RUNTIME_FORBIDDEN_PATTERNS = (
    "research_core.evolution",
    "research_core/evolution/",
    "StrategyEvolutionManager",
    "tae_strategy_evolution_plan.json",
)

DOCUMENTED_NON_RUNTIME_CONSUMERS = [
    "research_core/governance/daily_intelligence.py — legacy plan JSON read-only",
    "research_core/evidence_gap/evidence_gap.py — planning context feeder",
    "research_core/recalibration/confidence_recalibration.py — recalibration input",
    "research_core/evidence_history/evidence_accumulator.py — dossier enrichment",
    "research_core/review/patch_review.py — patch review context",
]

MISSING_CONNECTION_PHASE_V_PARALLEL = (
    "Phase V evolution manager parallel to Phase VIII pipeline"
)

LEGACY_STATUS_COMPATIBILITY_ONLY = "LEGACY_COMPATIBILITY_ONLY"
LEGACY_STATUS_ACTIVE_PARALLEL = "ACTIVE_PARALLEL_PIPELINE"


def scan_phase_v_runtime_consumers(root: Path | str = Path(".")) -> list[str]:
    """Return runtime module paths that still reference Phase V (must be empty when retired)."""
    root_path = Path(root)
    hits: list[str] = []
    for rel_dir in RUNTIME_SCAN_DIRS:
        directory = root_path / rel_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(pattern in text for pattern in RUNTIME_FORBIDDEN_PATTERNS):
                hits.append(str(path.relative_to(root_path)))
    return hits


def is_phase_v_legacy_wired_in_daily_runner(root: Path | str = Path(".")) -> bool:
    path = Path(root) / DAILY_RUNNER_MODULE_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "build_phase_v_legacy_status" in text
        and "phase_v_legacy_status" in text
    )


def build_phase_v_legacy_status(root: Path | str = Path(".")) -> dict[str, Any]:
    """Canonical strategy state documents Phase V as legacy compatibility only."""
    root_path = Path(root)
    runtime_consumers = scan_phase_v_runtime_consumers(root_path)
    runtime_usage = bool(runtime_consumers)
    parallel_pipeline = runtime_usage

    if runtime_usage:
        status = LEGACY_STATUS_ACTIVE_PARALLEL
    else:
        status = LEGACY_STATUS_COMPATIBILITY_ONLY

    return {
        "legacy_phase_v_status": status,
        "legacy_phase_v_consumers": list(DOCUMENTED_NON_RUNTIME_CONSUMERS),
        "legacy_phase_v_runtime_usage": runtime_usage,
        "legacy_phase_v_runtime_consumer_paths": runtime_consumers,
        "legacy_phase_v_parallel_pipeline": parallel_pipeline,
        "canonical_pipeline": str(CANONICAL_PIPELINE_PATH),
        "phase_v_module": str(PHASE_V_MODULE_PATH),
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }


def is_phase_v_legacy_retirement_resolved(
    root: Path | str = Path("."),
    daily_runner_payload: dict[str, Any] | None = None,
) -> bool:
    if not is_phase_v_legacy_wired_in_daily_runner(root):
        return False
    status = build_phase_v_legacy_status(root)
    if status.get("legacy_phase_v_runtime_usage"):
        return False
    if status.get("legacy_phase_v_parallel_pipeline"):
        return False
    if daily_runner_payload:
        legacy = daily_runner_payload.get("phase_v_legacy_status")
        if isinstance(legacy, dict):
            return (
                legacy.get("legacy_phase_v_status") == LEGACY_STATUS_COMPATIBILITY_ONLY
                and not legacy.get("legacy_phase_v_runtime_usage")
                and not legacy.get("legacy_phase_v_parallel_pipeline")
            )
    return status.get("legacy_phase_v_status") == LEGACY_STATUS_COMPATIBILITY_ONLY
