"""
Parallel Paper Validator — Phase VIII B2 / IX.2C pipeline step 2

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Validates each candidate strategy from the Candidate Strategy Registry.
Pipeline step — not an official entry point; use Strategy Evolution Daily Runner.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from research_core.strategy_evolution.candidate_registry import CandidateStrategyRegistry
from research_core.strategy_evolution.candidate_report import (
    CandidateMetrics,
    CandidateStatus,
    PromotionReadiness,
    StrategyCandidate,
)
from research_core.strategy_evolution.parallel_paper_report import (
    PaperValidationResult,
    ParallelPaperValidationReport,
    ValidationStatus,
    ValidatorVerdict,
)
from research_core.strategy_evolution.pipeline_integration import pipeline_reference

logger = logging.getLogger(__name__)

PIPELINE_ROLE = "PIPELINE_STEP_VALIDATOR"

REGISTRY_PATH = Path("tae_candidate_strategy_registry.json")
PORTFOLIO_PATH = Path("portfolio.csv")
PROMOTION_MIN_TRADES = 20


class ParallelPaperValidator:
    def __init__(
        self,
        registry_path: Path | str = REGISTRY_PATH,
        portfolio_csv: Path | str = PORTFOLIO_PATH,
    ) -> None:
        self._registry_path = Path(registry_path)
        self._portfolio_csv = Path(portfolio_csv)

    def validate(self) -> ParallelPaperValidationReport:
        registry_payload = self._load_registry()
        registry_report = CandidateStrategyRegistry(
            portfolio_csv=self._portfolio_csv,
        ).build()

        baseline_id = registry_payload.get("baseline_candidate_id") or "LIVE_BASELINE"
        baseline = self._find_candidate(registry_report.candidates, baseline_id)
        if baseline is None:
            raise ValueError(f"Baseline candidate {baseline_id!r} not found in registry build")

        validations: list[PaperValidationResult] = []
        for candidate in registry_report.candidates:
            is_baseline = candidate.candidate_id == baseline_id
            validations.append(
                self._validate_candidate(
                    candidate=candidate,
                    baseline_metrics=baseline.metrics,
                    is_baseline=is_baseline,
                )
            )

        return ParallelPaperValidationReport(
            verdict=ValidatorVerdict.PARALLEL_PAPER_VALIDATOR_READY,
            validations=validations,
            baseline_candidate_id=baseline_id,
            registry_verdict=str(registry_payload.get("verdict"))
            if registry_payload
            else None,
            sources_loaded={
                self._registry_path.name: registry_payload is not None,
                self._portfolio_csv.name: self._portfolio_csv.is_file(),
            },
            pipeline_reference={
                **pipeline_reference(),
                "pipeline_role": PIPELINE_ROLE,
                "pipeline_step": 2,
            },
        )

    def _load_registry(self) -> dict | None:
        if not self._registry_path.is_file():
            logger.warning("Registry not found: %s", self._registry_path)
            return None
        try:
            payload = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read registry %s: %s", self._registry_path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _find_candidate(
        candidates: list[StrategyCandidate],
        candidate_id: str,
    ) -> StrategyCandidate | None:
        for candidate in candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        return None

    def _validate_candidate(
        self,
        candidate: StrategyCandidate,
        baseline_metrics: CandidateMetrics,
        is_baseline: bool,
    ) -> PaperValidationResult:
        metrics = candidate.metrics
        if is_baseline:
            beats_pnl = False
            beats_pf = False
            beats_exp = False
        else:
            beats_pnl = metrics.total_pnl > baseline_metrics.total_pnl
            beats_pf = metrics.profit_factor > baseline_metrics.profit_factor
            beats_exp = metrics.expectancy > baseline_metrics.expectancy

        return PaperValidationResult(
            candidate_id=candidate.candidate_id,
            status=candidate.status,
            promotion_readiness=self._promotion_readiness(metrics, baseline_metrics),
            trades=metrics.trades,
            closed_trades=metrics.closed_trades,
            open_trades=metrics.open_trades,
            total_pnl=metrics.total_pnl,
            avg_pnl=metrics.avg_pnl,
            median_pnl=metrics.median_pnl,
            win_rate=metrics.win_rate,
            gross_profit=metrics.gross_profit,
            gross_loss=metrics.gross_loss,
            profit_factor=metrics.profit_factor,
            expectancy=metrics.expectancy,
            delta_vs_baseline_total_pnl=metrics.delta_vs_baseline_total_pnl,
            delta_vs_baseline_expectancy=metrics.delta_vs_baseline_expectancy,
            beats_baseline_total_pnl=beats_pnl,
            beats_baseline_profit_factor=beats_pf,
            beats_baseline_expectancy=beats_exp,
            validation_status=self._validation_status(
                metrics=metrics,
                beats_pnl=beats_pnl,
                beats_pf=beats_pf,
                beats_exp=beats_exp,
                is_baseline=is_baseline,
            ),
        )

    @staticmethod
    def _promotion_readiness(
        metrics: CandidateMetrics,
        baseline: CandidateMetrics,
    ) -> PromotionReadiness:
        if metrics.trades >= PROMOTION_MIN_TRADES:
            if (
                metrics.profit_factor > baseline.profit_factor
                and metrics.expectancy > baseline.expectancy
                and metrics.total_pnl > baseline.total_pnl
            ):
                return PromotionReadiness.PROMOTION_REVIEW_ELIGIBLE
            return PromotionReadiness.NOT_READY
        if metrics.trades >= 1:
            return PromotionReadiness.PAPER_TRACKING
        return PromotionReadiness.NOT_READY

    @staticmethod
    def _validation_status(
        metrics: CandidateMetrics,
        beats_pnl: bool,
        beats_pf: bool,
        beats_exp: bool,
        is_baseline: bool,
    ) -> ValidationStatus:
        if is_baseline:
            return ValidationStatus.BASELINE_REFERENCE

        beats_all = beats_pnl and beats_pf and beats_exp

        if metrics.trades >= PROMOTION_MIN_TRADES and beats_all:
            return ValidationStatus.PROMOTION_REVIEW_ELIGIBLE
        if beats_all and metrics.trades < PROMOTION_MIN_TRADES:
            return ValidationStatus.PAPER_TRACKING
        if metrics.trades < PROMOTION_MIN_TRADES:
            return ValidationStatus.INSUFFICIENT_SAMPLE
        if beats_pnl:
            return ValidationStatus.OUTPERFORMS_BASELINE
        return ValidationStatus.UNDERPERFORMS_BASELINE
