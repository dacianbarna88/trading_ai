"""Shared types for the research core framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Rule:
    """A candidate edge defined as conjunction of bin column flags."""

    rule_id: str
    description: str
    bin_columns: tuple[str, ...]
    complexity: int
    feature_groups: frozenset[str]

    def apply(self, df: pd.DataFrame) -> pd.Series:
        mask = pd.Series(True, index=df.index)
        for col in self.bin_columns:
            mask &= df[col].astype(bool)
        return mask


@dataclass
class SignalDataset:
    """Container for binned signal-level research data."""

    signals: pd.DataFrame
    baseline_metrics: dict[str, Any]
    universe_size: int
    tickers_loaded: int

    @property
    def min_date(self) -> pd.Timestamp:
        return self.signals["Signal_Date"].min()

    @property
    def max_date(self) -> pd.Timestamp:
        return self.signals["Signal_Date"].max()


@dataclass
class EvaluationResult:
    """Full evaluation output for one candidate rule."""

    rule: Rule
    metrics: dict[str, Any]
    robustness_score: float
    walk_forward_score: float
    walk_forward_passes: int
    walk_forward_valid_splits: int
    edge_confidence_score: float
    robustness_issues: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    explanation: str = ""

    def to_row(self) -> dict[str, Any]:
        row = dict(self.metrics)
        row.update(
            {
                "Rule_ID": self.rule.rule_id,
                "Rule_Description": self.rule.description,
                "Complexity": self.rule.complexity,
                "Robustness_Score": self.robustness_score,
                "Walk_Forward_Score": self.walk_forward_score,
                "Walk_Forward_Passes": self.walk_forward_passes,
                "Walk_Forward_Valid_Splits": self.walk_forward_valid_splits,
                "Edge_Confidence_Score": self.edge_confidence_score,
                "Explanation": self.explanation,
                "Recommendation": self.metrics.get(
                    "Recommendation", "DISCOVERY_ONLY"
                ),
            }
        )
        return row
