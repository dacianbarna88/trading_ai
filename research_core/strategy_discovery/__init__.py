"""Strategy Discovery Engine — Phase X Sprint X.3A (research-only candidate generation)."""

from research_core.strategy_discovery.strategy_candidate_builder import (
    StrategyDiscoveryEngine,
    build_candidates,
)
from research_core.strategy_discovery.strategy_discovery_report import (
    DEFAULT_JSON_PATH,
    DEFAULT_TXT_PATH,
    DISCOVERY_SAFETY_BANNER,
    DiscoveryCandidate,
    DiscoveryCandidateStatus,
    RiskProfile,
    StrategyDiscoveryReport,
    StrategyDiscoveryReportStore,
    StrategyDiscoveryVerdict,
)
from research_core.strategy_discovery.strategy_feature_library import (
    ENTRY_FEATURES,
    EXIT_FEATURES,
    FILTER_FEATURES,
    HOLDING_PERIODS,
    get_feature_library,
    validate_feature_library,
)
from research_core.strategy_discovery.strategy_hypothesis_generator import (
    TARGET_HYPOTHESIS_COUNT,
    StrategyHypothesis,
    generate_hypotheses,
)

__all__ = [
    "DEFAULT_JSON_PATH",
    "DEFAULT_TXT_PATH",
    "ENTRY_FEATURES",
    "EXIT_FEATURES",
    "FILTER_FEATURES",
    "HOLDING_PERIODS",
    "TARGET_HYPOTHESIS_COUNT",
    "DiscoveryCandidate",
    "DiscoveryCandidateStatus",
    "RiskProfile",
    "StrategyDiscoveryEngine",
    "StrategyDiscoveryReport",
    "StrategyDiscoveryReportStore",
    "StrategyDiscoveryVerdict",
    "StrategyHypothesis",
    "build_candidates",
    "generate_hypotheses",
    "get_feature_library",
    "validate_feature_library",
]
