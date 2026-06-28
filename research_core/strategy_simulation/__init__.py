"""Strategy Simulation Engine — Phase X Sprint X.3B/X.3C (infrastructure + historical research)."""

from research_core.strategy_simulation.historical_research_engine import (
    HistoricalResearchEngine,
    build_coverage_matrix,
    build_research_jobs,
    default_data_requirement,
    research_job_id_for_index,
    validate_research_jobs_schema,
)
from research_core.strategy_simulation.historical_research_report import (
    DATA_REQUIREMENT_FIELDS,
    HistoricalResearchJob,
    HistoricalResearchReport,
    HistoricalResearchReportStore,
    HistoricalResearchVerdict,
    RESEARCH_SAFETY_BANNER,
)
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
    "DATA_REQUIREMENT_FIELDS",
    "DEFAULT_JSON_PATH",
    "DEFAULT_TXT_PATH",
    "DISCOVERY_INPUT_PATH",
    "FOUNDATION_RESEARCH_STATE",
    "FOUNDATION_SIMULATION_STATUS",
    "HistoricalResearchEngine",
    "HistoricalResearchJob",
    "HistoricalResearchReport",
    "HistoricalResearchReportStore",
    "HistoricalResearchVerdict",
    "HistoricalSimulationEngine",
    "MARKETS",
    "METRIC_FIELDS",
    "PENDING_VALUE",
    "RESEARCH_SAFETY_BANNER",
    "ResearchState",
    "SIMULATION_SAFETY_BANNER",
    "SimulationQueueEntry",
    "SimulationRecord",
    "StrategySimulationReport",
    "StrategySimulationReportStore",
    "StrategySimulationVerdict",
    "TIME_HORIZONS",
    "build_coverage_matrix",
    "build_research_jobs",
    "build_simulation_queue",
    "build_simulation_registry",
    "default_data_requirement",
    "pending_performance_metrics",
    "research_job_id_for_index",
    "simulation_id_for_index",
    "validate_performance_metrics_schema",
    "validate_registry_completeness",
    "validate_research_jobs_schema",
]
