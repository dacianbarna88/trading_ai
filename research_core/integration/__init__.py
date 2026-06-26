"""TAE Knowledge Integration — Phase V Sprint A3."""

from research_core.integration.knowledge_integration import KnowledgeIntegrator
from research_core.integration.strategy_recommendation import (
    DEFAULT_RECOMMENDATIONS_PATH,
    ImplementationStatus,
    IntegrationResult,
    RecommendationType,
    StrategyRecommendation,
    StrategyRecommendationsStore,
)

__all__ = [
    "DEFAULT_RECOMMENDATIONS_PATH",
    "ImplementationStatus",
    "IntegrationResult",
    "KnowledgeIntegrator",
    "RecommendationType",
    "StrategyRecommendation",
    "StrategyRecommendationsStore",
]
