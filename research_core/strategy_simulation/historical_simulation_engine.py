"""
Historical Simulation Engine — Phase X Sprint X.3B

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Simulation infrastructure only. No historical execution, backtesting, or broker access.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from research_core.meta_intelligence.meta_intelligence_constants import PROTECTED_PATHS
from research_core.strategy_simulation.performance_metrics import METRIC_FIELDS
from research_core.strategy_simulation.simulation_queue import build_simulation_queue
from research_core.strategy_simulation.simulation_registry import (
    MARKETS,
    TIME_HORIZONS,
    build_simulation_registry,
    validate_registry_completeness,
)
from research_core.strategy_simulation.strategy_simulation_report import (
    DISCOVERY_INPUT_PATH,
    StrategySimulationReport,
    StrategySimulationVerdict,
)

logger = logging.getLogger(__name__)

DISCOVERY_ID_PATTERN = re.compile(r"^DISCOVERY_\d{4}$")


class HistoricalSimulationEngine:
    """Builds simulation queue and registry from discovery candidates — no execution."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._warnings: list[str] = []

    def run(self) -> StrategySimulationReport:
        before_mtimes = self._snapshot_mtimes()

        discovery_payload = self._load_discovery()
        strategy_ids = self._extract_strategy_ids(discovery_payload)

        if not strategy_ids:
            after_mtimes = self._snapshot_mtimes()
            protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)
            return StrategySimulationReport(
                verdict=StrategySimulationVerdict.STRATEGY_SIMULATION_INPUT_MISSING,
                discovery_candidates_loaded=0,
                simulation_records_created=0,
                queue=[],
                registry=[],
                markets=list(MARKETS),
                time_horizons=list(TIME_HORIZONS),
                schema_validation_passed=False,
                registry_completeness_passed=False,
                performance_metric_fields=list(METRIC_FIELDS),
                warnings=list(self._warnings),
                protected_files_unchanged=protected_ok,
            )

        queue = build_simulation_queue(strategy_ids)
        registry = build_simulation_registry(queue)

        registry_ok, registry_warnings = validate_registry_completeness(strategy_ids, registry)
        self._warnings.extend(registry_warnings)

        schema_ok = registry_ok and all(
            set(record.performance_metrics.keys()) == set(METRIC_FIELDS) for record in registry
        )
        if not schema_ok:
            self._warnings.append("Performance metrics schema validation failed")

        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)
        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during simulation setup")

        verdict = self._determine_verdict(strategy_ids, registry_ok, schema_ok)

        return StrategySimulationReport(
            verdict=verdict,
            discovery_candidates_loaded=len(strategy_ids),
            simulation_records_created=len(registry),
            queue=queue,
            registry=registry,
            markets=list(MARKETS),
            time_horizons=list(TIME_HORIZONS),
            schema_validation_passed=schema_ok,
            registry_completeness_passed=registry_ok,
            performance_metric_fields=list(METRIC_FIELDS),
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
        )

    def _load_discovery(self) -> dict[str, Any] | None:
        path = self._root / DISCOVERY_INPUT_PATH
        if not path.is_file():
            self._warnings.append(f"Missing discovery input: {DISCOVERY_INPUT_PATH.name}")
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._warnings.append(f"Could not read {DISCOVERY_INPUT_PATH.name}: {exc}")
            return None

        if not isinstance(payload, dict):
            self._warnings.append(f"Invalid discovery payload in {DISCOVERY_INPUT_PATH.name}")
            return None

        return payload

    def _extract_strategy_ids(self, payload: dict[str, Any] | None) -> list[str]:
        if not payload:
            return []

        registry = payload.get("discovery_registry")
        if not isinstance(registry, list):
            self._warnings.append("discovery_registry missing or invalid in discovery input")
            return []

        strategy_ids: list[str] = []
        for item in registry:
            if not isinstance(item, dict):
                self._warnings.append("Skipping invalid discovery registry entry")
                continue

            discovery_id = str(item.get("discovery_id", "")).strip()
            if not discovery_id:
                self._warnings.append("Discovery entry missing discovery_id")
                continue

            if not DISCOVERY_ID_PATTERN.match(discovery_id):
                self._warnings.append(f"Non-canonical discovery ID skipped: {discovery_id}")
                continue

            strategy_ids.append(discovery_id)

        if not strategy_ids:
            self._warnings.append("No DISCOVERY_xxxx candidates found in discovery input")

        return strategy_ids

    def _determine_verdict(
        self,
        strategy_ids: list[str],
        registry_ok: bool,
        schema_ok: bool,
    ) -> StrategySimulationVerdict:
        if not strategy_ids:
            return StrategySimulationVerdict.STRATEGY_SIMULATION_INPUT_MISSING

        if self._warnings or not registry_ok or not schema_ok:
            return StrategySimulationVerdict.STRATEGY_SIMULATION_READY_WITH_WARNINGS

        return StrategySimulationVerdict.STRATEGY_SIMULATION_ENGINE_READY

    def _snapshot_mtimes(self) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for rel in PROTECTED_PATHS:
            full = self._root / rel
            if full.is_file():
                snapshot[str(rel)] = full.stat().st_mtime
        return snapshot

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
