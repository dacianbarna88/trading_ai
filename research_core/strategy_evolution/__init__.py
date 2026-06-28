"""Strategy evolution — Phase VIII / IX.2C integration hub (read-only)."""

from research_core.strategy_evolution.candidate_registry import CandidateStrategyRegistry
from research_core.strategy_evolution.candidate_report import (
    CandidateRegistryReport,
    CandidateRegistryReportStore,
    CandidateStatus,
    PromotionReadiness,
    RegistryVerdict,
    SAFETY_BANNER,
    StrategyCandidate,
)
from research_core.strategy_evolution.continuous_ranking_engine import (
    ContinuousStrategyRankingEngine,
)
from research_core.strategy_evolution.continuous_ranking_report import (
    ContinuousStrategyRankingReport,
    ContinuousStrategyRankingReportStore,
    RankingDecision,
    RankingVerdict,
    StrategyRankingEntry,
)
from research_core.strategy_evolution.daily_runner import StrategyEvolutionDailyRunner
from research_core.strategy_evolution.daily_runner_report import (
    DailyRunnerReport,
    DailyRunnerReportStore,
    DailyRunnerStepResult,
    DailyRunnerVerdict,
    PaperTrackingNeed,
)
from research_core.strategy_evolution.parallel_paper_report import (
    ParallelPaperValidationReport,
    ParallelPaperValidationReportStore,
    PaperValidationResult,
    ValidationStatus,
    ValidatorVerdict,
)
from research_core.strategy_evolution.parallel_paper_validator import ParallelPaperValidator
from research_core.strategy_evolution.paper_tracking_log import PaperTrackingLog
from research_core.strategy_evolution.paper_tracking_report import (
    PaperTrackingEntry,
    PaperTrackingLogReport,
    PaperTrackingLogReportStore,
    PaperTrackingVerdict,
    TrackingStatus,
)
from research_core.strategy_evolution.pipeline_integration import (
    CANONICAL_PIPELINE_MODULE,
    CANONICAL_REPORT_PATH,
    load_canonical_daily_runner_report,
    pipeline_reference,
)
from research_core.strategy_evolution.promotion_gate import StrategyPromotionGate
from research_core.strategy_evolution.promotion_gate_report import (
    PromotionGateDecision,
    PromotionGateEntry,
    PromotionGateReport,
    PromotionGateReportStore,
    PromotionGateVerdict,
)

__all__ = [
    "CANONICAL_PIPELINE_MODULE",
    "CANONICAL_REPORT_PATH",
    "CandidateStrategyRegistry",
    "CandidateRegistryReport",
    "CandidateRegistryReportStore",
    "CandidateStatus",
    "PromotionReadiness",
    "RegistryVerdict",
    "SAFETY_BANNER",
    "StrategyCandidate",
    "ParallelPaperValidator",
    "ParallelPaperValidationReport",
    "ParallelPaperValidationReportStore",
    "PaperValidationResult",
    "ValidationStatus",
    "ValidatorVerdict",
    "ContinuousStrategyRankingEngine",
    "ContinuousStrategyRankingReport",
    "ContinuousStrategyRankingReportStore",
    "RankingDecision",
    "RankingVerdict",
    "StrategyRankingEntry",
    "StrategyPromotionGate",
    "PromotionGateReport",
    "PromotionGateReportStore",
    "PromotionGateEntry",
    "PromotionGateDecision",
    "PromotionGateVerdict",
    "PaperTrackingLog",
    "PaperTrackingLogReport",
    "PaperTrackingLogReportStore",
    "PaperTrackingEntry",
    "PaperTrackingVerdict",
    "TrackingStatus",
    "StrategyEvolutionDailyRunner",
    "DailyRunnerReport",
    "DailyRunnerReportStore",
    "DailyRunnerStepResult",
    "DailyRunnerVerdict",
    "PaperTrackingNeed",
    "load_canonical_daily_runner_report",
    "pipeline_reference",
]
