"""TAE Strategy Evolution — Phase V Sprint A4."""

from research_core.evolution.evolution_plan import (
    DEFAULT_EVOLUTION_PLAN_PATH,
    DEFAULT_EVOLUTION_NOTICE_PATH,
    EvolutionPlanEntry,
    EvolutionPlanResult,
    EvolutionPlanStore,
    ImplementationStatus,
    ProposedChangeType,
)
from research_core.evolution.strategy_evolution import StrategyEvolutionManager
from research_core.evolution.evolution_proposal import (
    DEFAULT_PROPOSAL_PATH,
    generate_evolution_proposal,
)

__all__ = [
    "DEFAULT_EVOLUTION_NOTICE_PATH",
    "DEFAULT_EVOLUTION_PLAN_PATH",
    "DEFAULT_PROPOSAL_PATH",
    "EvolutionPlanEntry",
    "EvolutionPlanResult",
    "EvolutionPlanStore",
    "ImplementationStatus",
    "ProposedChangeType",
    "StrategyEvolutionManager",
    "generate_evolution_proposal",
]
