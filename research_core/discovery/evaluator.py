"""Candidate rule evaluation orchestration."""

from __future__ import annotations

import pandas as pd

from research_core.config.discovery import DiscoveryConfig
from research_core.explanation.narrator import EdgeNarrator
from research_core.metrics.performance import compute_metrics
from research_core.scoring.confidence import EdgeConfidenceScorer
from research_core.types import EvaluationResult, Rule, SignalDataset
from research_core.validation.rejection import RejectionPipeline
from research_core.validation.robustness import RobustnessValidator
from research_core.validation.walk_forward import WalkForwardValidator


class RuleEvaluator:
    """Evaluates one candidate rule against baseline and validation modules."""

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config
        self._robustness = RobustnessValidator(config)
        self._walk_forward = WalkForwardValidator(config)
        self._rejection = RejectionPipeline(config)
        self._scorer = EdgeConfidenceScorer(config)
        self._narrator = EdgeNarrator()

    def evaluate(
        self,
        dataset: SignalDataset,
        rule: Rule,
        test_windows: list[dict],
    ) -> EvaluationResult:
        df = dataset.signals
        baseline = dataset.baseline_metrics
        return_col = self._config.return_column

        mask = rule.apply(df)
        sub = df[mask]
        rets = sub[return_col].astype(float).values
        metrics = compute_metrics(rets, baseline)
        metrics["MAE_Median"] = round(float(sub["MAE"].median()), 4) if len(sub) else None
        metrics["MFE_Median"] = round(float(sub["MFE"].median()), 4) if len(sub) else None
        metrics["Ticker_Diversity"] = int(sub["Ticker"].nunique()) if len(sub) else 0
        metrics["Sector_Diversity"] = int(sub["Sector"].nunique()) if len(sub) else 0

        robustness, issues = self._robustness.evaluate(df, mask, baseline, return_col)
        wf_score, wf_pass, wf_valid = self._walk_forward.score(
            df, mask, test_windows, return_col
        )
        metrics["Robustness_Score"] = robustness
        metrics["Walk_Forward_Score"] = wf_score
        metrics["Walk_Forward_Passes"] = wf_pass
        metrics["Walk_Forward_Valid_Splits"] = wf_valid

        confidence = self._scorer.score(
            robustness,
            wf_score,
            metrics["Trades"],
            metrics["Sector_Diversity"],
            metrics.get("Lift_vs_Baseline_Avg") or 0,
            metrics.get("Profit_Factor") or 0,
            baseline["Profit_Factor"],
        )
        metrics["Edge_Confidence_Score"] = confidence

        rejection = self._rejection.reason(metrics, baseline, issues)
        explanation = self._narrator.explain(rule, metrics, baseline, issues)

        if confidence >= self._config.production_review_confidence and rejection is None:
            metrics["Recommendation"] = "PRODUCTION_CANDIDATE_FOR_HUMAN_REVIEW"
        else:
            metrics["Recommendation"] = "DISCOVERY_ONLY"

        return EvaluationResult(
            rule=rule,
            metrics=metrics,
            robustness_score=robustness,
            walk_forward_score=wf_score,
            walk_forward_passes=wf_pass,
            walk_forward_valid_splits=wf_valid,
            edge_confidence_score=confidence,
            robustness_issues=issues,
            rejection_reason=rejection,
            explanation=explanation,
        )
