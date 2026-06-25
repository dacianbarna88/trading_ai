"""Component contracts — implement these in new validators, scorers, collectors."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd

from research_core.types import EvaluationResult, Rule, SignalDataset


@runtime_checkable
class SignalCollectorProtocol(Protocol):
    """Collect trade-level signals from enriched OHLCV."""

    def collect(
        self,
        ticker: str,
        df: pd.DataFrame,
        spy_ctx: pd.DataFrame,
        sector: str,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class FeatureRegistryProtocol(Protocol):
    """Apply feature bins to a signal dataframe."""

    def register_defaults(self) -> None: ...
    def apply(self, df: pd.DataFrame) -> pd.DataFrame: ...
    def bin_column_groups(self, df: pd.DataFrame) -> dict[str, str]: ...


@runtime_checkable
class RuleGeneratorProtocol(Protocol):
    """Generate candidate rules from binned signals."""

    def generate(self, df: pd.DataFrame) -> list[Rule]: ...


@runtime_checkable
class RuleEvaluatorProtocol(Protocol):
    """Evaluate one candidate rule against baseline and validation stack."""

    def evaluate(
        self,
        dataset: SignalDataset,
        rule: Rule,
        test_windows: list[dict[str, Any]],
    ) -> EvaluationResult: ...


@runtime_checkable
class WalkForwardValidatorProtocol(Protocol):
    def build_test_windows(
        self,
        min_date: pd.Timestamp,
        max_date: pd.Timestamp,
    ) -> list[dict[str, Any]]: ...

    def score(
        self,
        df: pd.DataFrame,
        mask: pd.Series,
        windows: list[dict[str, Any]],
        return_col: str,
    ) -> tuple[float, int, int]: ...


@runtime_checkable
class ReporterProtocol(Protocol):
    """Write module outputs to disk."""

    def write_failure(self, base_dir: Any, message: str) -> None: ...
