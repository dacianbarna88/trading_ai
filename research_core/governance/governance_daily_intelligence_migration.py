"""
Governance Daily Intelligence Migration — Phase IX Sprint IX.5G

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Connect-only: register Phase VIII/IX canonical strategy outputs as official
governance inputs; legacy JSON remains optional fallback only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DAILY_INTELLIGENCE_MODULE_PATH = Path("research_core/governance/daily_intelligence.py")
GOVERNANCE_REPORT_PATH = Path("tae_daily_intelligence_report.json")
CANONICAL_STRATEGY_SOURCE = Path("tae_strategy_evolution_daily_runner.json")

MODERN_CANONICAL_INPUT_PATHS: dict[str, Path] = {
    "tae_strategy_evolution_daily_runner.json": Path(
        "tae_strategy_evolution_daily_runner.json"
    ),
    "tae_candidate_strategy_registry.json": Path("tae_candidate_strategy_registry.json"),
    "tae_parallel_paper_validation.json": Path("tae_parallel_paper_validation.json"),
    "tae_continuous_strategy_ranking.json": Path("tae_continuous_strategy_ranking.json"),
    "tae_strategy_promotion_gate.json": Path("tae_strategy_promotion_gate.json"),
    "tae_paper_tracking_log.json": Path("tae_paper_tracking_log.json"),
    "tae_evidence_integration_gate.json": Path("tae_evidence_integration_gate.json"),
    "tae_performance_pipeline_report.json": Path("tae_performance_pipeline_report.json"),
}

LEGACY_JSON_INPUT_NAMES: tuple[str, ...] = (
    "tae_learning_report.json",
    "tae_discoveries.json",
    "tae_knowledge_candidates.json",
    "tae_strategy_recommendations.json",
    "tae_strategy_evolution_plan.json",
    "tae_cross_validation_report.json",
    "tae_research_priorities.json",
    "tae_roadmap_status.json",
    "process_health.json",
    "tae_hypothesis_registry.json",
)

MISSING_CONNECTION_GOVERNANCE_MODERN = (
    "Governance daily intelligence reads legacy JSON set; "
    "extend to Phase VIII strategy_evolution outputs"
)

GOVERNANCE_MIGRATION_STATUS_REGISTERED = "GOVERNANCE_MODERN_INPUTS_REGISTERED"
GOVERNANCE_MIGRATION_STATUS_LEGACY_ONLY = "GOVERNANCE_LEGACY_INPUTS_ONLY"


def _load_governance_report(root: Path) -> dict[str, Any] | None:
    path = root / GOVERNANCE_REPORT_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Governance report read failed for %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def is_governance_modern_inputs_wired(root: Path | str = Path(".")) -> bool:
    path = Path(root) / DAILY_INTELLIGENCE_MODULE_PATH
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        "MODERN_CANONICAL_INPUT_PATHS" in text
        and "build_governance_modern_inputs_registration" in text
        and "governance_modern_inputs" in text
    )


def build_governance_modern_inputs_registration(
    root: Path | str = Path("."),
    sources_loaded: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Document modern vs legacy governance input registration — read-only."""
    root_path = Path(root)
    loaded = dict(sources_loaded or {})
    if not loaded:
        for name, rel_path in MODERN_CANONICAL_INPUT_PATHS.items():
            loaded[name] = (root_path / rel_path).is_file()
        for name in LEGACY_JSON_INPUT_NAMES:
            loaded[name] = (root_path / name).is_file()

    modern_count = sum(
        1 for name in MODERN_CANONICAL_INPUT_PATHS if loaded.get(name)
    )
    legacy_count = sum(1 for name in LEGACY_JSON_INPUT_NAMES if loaded.get(name))

    if loaded.get(CANONICAL_STRATEGY_SOURCE.name):
        strategy_source = str(CANONICAL_STRATEGY_SOURCE.name)
    elif modern_count > 0:
        strategy_source = next(
            name
            for name in MODERN_CANONICAL_INPUT_PATHS
            if loaded.get(name)
        )
    else:
        strategy_source = "legacy_fallback"

    wired = is_governance_modern_inputs_wired(root_path)
    registered = wired and modern_count > 0
    legacy_fallback_only = modern_count > 0

    return {
        "governance_modern_inputs_registered": registered,
        "governance_modern_input_count": modern_count,
        "governance_legacy_input_count": legacy_count,
        "governance_legacy_fallback_only": legacy_fallback_only,
        "governance_strategy_evolution_source": strategy_source,
        "modern_inputs_loaded": {
            name: bool(loaded.get(name)) for name in MODERN_CANONICAL_INPUT_PATHS
        },
        "canonical_pipeline": "research_core/strategy_evolution/daily_runner.py",
        "governance_module": str(DAILY_INTELLIGENCE_MODULE_PATH),
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }


def is_governance_migration_resolved(
    root: Path | str = Path("."),
    governance_payload: dict[str, Any] | None = None,
) -> bool:
    if not is_governance_modern_inputs_wired(root):
        return False

    payload = governance_payload
    if payload is None:
        payload = _load_governance_report(Path(root))
    if not isinstance(payload, dict):
        return False

    registration = payload.get("governance_modern_inputs")
    if not isinstance(registration, dict):
        return False

    return (
        registration.get("governance_modern_inputs_registered") is True
        and int(registration.get("governance_modern_input_count") or 0) > 0
        and registration.get("governance_legacy_fallback_only") is True
    )
