"""Strategy Simulation Engine — Phase X Sprint X.3B (infrastructure only)."""

from research_core.strategy_simulation.historical_simulation_engine import (
    HistoricalSimulationEngine,
)
from research_core.strategy_simulation.performance_metrics import (
    METRIC_FIELDS,
    PENDING_VALUE,
    pending_performance_metrics,
    validate_performance_metrics_schema,
)
from research_core.strategy_simulation.simulation_queue import (
    SimulationQueueEntry,
    build_simulation_queue,
    simulation_id_for_index,
)
from research_core.strategy_simulation.simulation_registry import (
    MARKETS,
    TIME_HORIZONS,
    FOUNDATION_RESEARCH_STATE,
    FOUNDATION_SIMULATION_STATUS,
    ResearchState,
    SimulationRecord,
    build_simulation_registry,
    validate_registry_completeness,
)
from research_core.strategy_simulation.strategy_simulation_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    DISCOVERY_INPUT_PATH,
    SIMULATION_SAFETY_BANNER,
    StrategySimulationReport,
    StrategySimulationReportStore,
    StrategySimulationVerdict,
)

__all__ = [
    "DEFAULT_JSON_PATH",
    "DEFAULT_TXT_PATH",
    "DISCOVERY_INPUT_PATH",
    "FOUNDATION_RESEARCH_STATE",
    "FOUNDATION_SIMULATION_STATUS",
    "HistoricalSimulationEngine",
    "MARKETS",
    "METRIC_FIELDS",
    "PENDING_VALUE",
    "ResearchState",
    "SIMULATION_SAFETY_BANNER",
    "SimulationQueueEntry",
    "SimulationRecord",
    "StrategySimulationReport",
    "StrategySimulationReportStore",
    "StrategySimulationVerdict",
    "TIME_HORIZONS",
    "build_simulation_queue",
    "build_simulation_registry",
    "pending_performance_metrics",
    "simulation_id_for_index",
    "validate_performance_metrics_schema",
    "validate_registry_completeness",
]
