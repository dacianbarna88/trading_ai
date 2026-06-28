"""
Strategy Evolution Daily Runner — Phase VIII B6 / IX.2C canonical pipeline

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Runs the full Strategy Evolution pipeline in order and produces
a consolidated daily summary. Single official entry point for strategy evolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from research_core.strategy_evolution.candidate_registry import CandidateStrategyRegistry
from research_core.strategy_evolution.candidate_report import (
    DEFAULT_JSON_PATH as REGISTRY_JSON,
    DEFAULT_TXT_PATH as REGISTRY_TXT,
    CandidateRegistryReportStore,
    RegistryVerdict,
)
from research_core.strategy_evolution.continuous_ranking_engine import (
    ContinuousStrategyRankingEngine,
)
from research_core.strategy_evolution.continuous_ranking_report import (
    DEFAULT_JSON_PATH as RANKING_JSON,
    DEFAULT_TXT_PATH as RANKING_TXT,
    ContinuousStrategyRankingReportStore,
    RankingVerdict,
)
from research_core.strategy_evolution.daily_runner_report import (
    DailyRunnerReport,
    DailyRunnerStepResult,
    DailyRunnerVerdict,
    PaperTrackingNeed,
)
from research_core.strategy_evolution.pipeline_integration import CANONICAL_PIPELINE_MODULE
from research_core.performance.performance_pipeline_integration import (
    DAILY_RUNNER_PERFORMANCE_STEP_NAME,
    INTEGRITY_REPORT_PATH,
    STRATEGIC_REPORT_PATH,
    daily_runner_performance_step_verdict,
    pipeline_reference,
    PERFORMANCE_PIPELINE_CONNECTED,
    PERFORMANCE_PIPELINE_PARTIAL,
)
from research_core.strategy_evolution.paper_tracking_log import PaperTrackingLog
from research_core.strategy_evolution.paper_tracking_report import (
    DEFAULT_JSON_PATH as TRACKING_JSON,
    DEFAULT_TXT_PATH as TRACKING_TXT,
    PaperTrackingLogReportStore,
    PaperTrackingVerdict,
    TrackingStatus,
)
from research_core.strategy_evolution.parallel_paper_report import (
    DEFAULT_JSON_PATH as VALIDATION_JSON,
    DEFAULT_TXT_PATH as VALIDATION_TXT,
    ParallelPaperValidationReportStore,
    ValidatorVerdict,
)
from research_core.strategy_evolution.parallel_paper_validator import ParallelPaperValidator
from research_core.strategy_evolution.promotion_gate import StrategyPromotionGate
from research_core.strategy_evolution.promotion_gate_report import (
    DEFAULT_JSON_PATH as GATE_JSON,
    DEFAULT_TXT_PATH as GATE_TXT,
    PromotionGateReportStore,
    PromotionGateVerdict,
)

logger = logging.getLogger(__name__)

__all__ = ["CANONICAL_PIPELINE_MODULE", "StrategyEvolutionDailyRunner"]

PROTECTED_PATHS = [
    Path("live_bot.py"),
    Path("dashboard_v2.py"),
    Path("config/settings.py"),
    Path("portfolio.csv"),
    Path("core/trades.py"),
    Path("core/portfolio_prices.py"),
]


@dataclass
class _StepDef:
    step_number: int
    step_name: str
    run: Callable[[], str]
    output_json: str
    output_txt: str
    expected_verdict: str


class StrategyEvolutionDailyRunner:
    def __init__(self, protected_paths: list[Path] | None = None) -> None:
        self._protected_paths = protected_paths or PROTECTED_PATHS
        self._ranking_report = None
        self._gate_report = None
        self._tracking_report = None

    def run(self) -> DailyRunnerReport:
        before_mtimes = self._snapshot_mtimes()
        steps: list[DailyRunnerStepResult] = []

        for step_def in self._step_definitions():
            steps.append(self._run_step(step_def))

        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)
        all_succeeded = all(step.succeeded for step in steps)

        top_id, top_score = self._top_ranked_strategy()
        review_candidate = (
            self._gate_report.review_candidate_id if self._gate_report else None
        )
        tracking_needs = self._paper_tracking_needs()
        perf_ref = pipeline_reference()

        from research_core.strategy_evolution.phase_v_legacy_retirement import (
            build_phase_v_legacy_status,
        )

        phase_v_legacy_status = build_phase_v_legacy_status(Path("."))

        return DailyRunnerReport(
            verdict=(
                DailyRunnerVerdict.STRATEGY_EVOLUTION_DAILY_RUNNER_READY
                if all_succeeded
                else DailyRunnerVerdict.STRATEGY_EVOLUTION_DAILY_RUNNER_PARTIAL_FAILURE
            ),
            steps=steps,
            top_ranked_strategy_id=top_id,
            top_ranked_strategy_score=top_score,
            promotion_review_candidate_id=review_candidate,
            paper_tracking_needs=tracking_needs,
            protected_files_unchanged=protected_ok,
            performance_pipeline_reference=perf_ref,
            phase_v_legacy_status=phase_v_legacy_status,
        )

    def _step_definitions(self) -> list[_StepDef]:
        return [
            _StepDef(
                step_number=1,
                step_name="Candidate Strategy Registry",
                run=self._run_registry,
                output_json=REGISTRY_JSON.name,
                output_txt=REGISTRY_TXT.name,
                expected_verdict=RegistryVerdict.CANDIDATE_STRATEGY_REGISTRY_READY.value,
            ),
            _StepDef(
                step_number=2,
                step_name="Parallel Paper Validator",
                run=self._run_validator,
                output_json=VALIDATION_JSON.name,
                output_txt=VALIDATION_TXT.name,
                expected_verdict=ValidatorVerdict.PARALLEL_PAPER_VALIDATOR_READY.value,
            ),
            _StepDef(
                step_number=3,
                step_name="Continuous Strategy Ranking Engine",
                run=self._run_ranking,
                output_json=RANKING_JSON.name,
                output_txt=RANKING_TXT.name,
                expected_verdict=RankingVerdict.CONTINUOUS_STRATEGY_RANKING_READY.value,
            ),
            _StepDef(
                step_number=4,
                step_name="Strategy Promotion Gate",
                run=self._run_promotion_gate,
                output_json=GATE_JSON.name,
                output_txt=GATE_TXT.name,
                expected_verdict=PromotionGateVerdict.STRATEGY_PROMOTION_GATE_READY.value,
            ),
            _StepDef(
                step_number=5,
                step_name="Paper Tracking Log",
                run=self._run_tracking_log,
                output_json=TRACKING_JSON.name,
                output_txt=TRACKING_TXT.name,
                expected_verdict=PaperTrackingVerdict.PAPER_TRACKING_LOG_READY.value,
            ),
            _StepDef(
                step_number=6,
                step_name=DAILY_RUNNER_PERFORMANCE_STEP_NAME,
                run=self._run_performance_pipeline,
                output_json=STRATEGIC_REPORT_PATH.name,
                output_txt=INTEGRITY_REPORT_PATH.name.replace(".json", ".txt"),
                expected_verdict=PERFORMANCE_PIPELINE_CONNECTED,
            ),
        ]

    def _run_step(self, step_def: _StepDef) -> DailyRunnerStepResult:
        try:
            verdict = step_def.run()
            if step_def.step_name == DAILY_RUNNER_PERFORMANCE_STEP_NAME:
                succeeded = verdict in {
                    PERFORMANCE_PIPELINE_CONNECTED,
                    PERFORMANCE_PIPELINE_PARTIAL,
                }
            else:
                succeeded = verdict == step_def.expected_verdict
            return DailyRunnerStepResult(
                step_name=step_def.step_name,
                step_number=step_def.step_number,
                verdict=verdict,
                succeeded=succeeded,
                output_json=step_def.output_json,
                output_txt=step_def.output_txt,
                error=None if succeeded else f"Unexpected verdict: {verdict}",
            )
        except Exception as exc:
            logger.exception("Step failed: %s", step_def.step_name)
            return DailyRunnerStepResult(
                step_name=step_def.step_name,
                step_number=step_def.step_number,
                verdict=None,
                succeeded=False,
                output_json=step_def.output_json,
                output_txt=step_def.output_txt,
                error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _run_registry() -> str:
        report = CandidateStrategyRegistry().build()
        store = CandidateRegistryReportStore()
        store.persist(report)
        store.persist_txt(report)
        return report.verdict.value

    @staticmethod
    def _run_validator() -> str:
        report = ParallelPaperValidator().validate()
        store = ParallelPaperValidationReportStore()
        store.persist(report)
        store.persist_txt(report)
        return report.verdict.value

    def _run_ranking(self) -> str:
        report = ContinuousStrategyRankingEngine().rank()
        store = ContinuousStrategyRankingReportStore()
        store.persist(report)
        store.persist_txt(report)
        self._ranking_report = report
        return report.verdict.value

    def _run_promotion_gate(self) -> str:
        report = StrategyPromotionGate().evaluate()
        store = PromotionGateReportStore()
        store.persist(report)
        store.persist_txt(report)
        self._gate_report = report
        return report.verdict.value

    def _run_tracking_log(self) -> str:
        report = PaperTrackingLog().build()
        store = PaperTrackingLogReportStore()
        store.persist(report)
        store.persist_txt(report)
        self._tracking_report = report
        return report.verdict.value

    @staticmethod
    def _run_performance_pipeline() -> str:
        return daily_runner_performance_step_verdict()

    def _top_ranked_strategy(self) -> tuple[str | None, float | None]:
        if not self._ranking_report or not self._ranking_report.rankings:
            return None, None
        top = min(self._ranking_report.rankings, key=lambda entry: entry.rank)
        return top.candidate_id, top.ranking_score

    def _paper_tracking_needs(self) -> list[PaperTrackingNeed]:
        if not self._tracking_report:
            return []
        needs: list[PaperTrackingNeed] = []
        for entry in self._tracking_report.entries:
            if entry.tracking_status == TrackingStatus.BASELINE_REFERENCE:
                continue
            needs.append(
                PaperTrackingNeed(
                    candidate_id=entry.candidate_id,
                    tracking_status=entry.tracking_status.value,
                    current_trades=entry.current_trades,
                    trades_needed=entry.trades_needed,
                    tracking_note=entry.tracking_note,
                )
            )
        return needs

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in self._protected_paths:
            if path.is_file():
                out[str(path)] = path.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
