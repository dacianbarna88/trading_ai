"""Shared research CSV loading for TAE organisms."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_V18_FEATURES = Path("context_v18_signal_features.csv")
DEFAULT_ENSEMBLE_SCORES = Path("edge_ensemble_signal_scores.csv")
DEFAULT_V18_PATTERNS = Path("context_v18_pattern_rankings.csv")


def load_research_csv(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    if not path.exists():
        return None, f"Missing file: {path}"
    try:
        df = pd.read_csv(path)
        if df.empty:
            return None, f"Empty file: {path}"
        if "Signal_Date" in df.columns:
            df["Signal_Date"] = pd.to_datetime(df["Signal_Date"])
        return df, None
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return None, f"Failed to read {path}: {exc}"


def pick_signal_row(
    df: pd.DataFrame,
    cycle: int,
    sort_column: str,
    ascending: bool = False,
) -> pd.Series:
    if sort_column not in df.columns:
        ranked = df
    else:
        ranked = df.sort_values(sort_column, ascending=ascending, na_position="last")
    pick_index = min(max(cycle - 1, 0), len(ranked) - 1)
    return ranked.iloc[pick_index]


def safe_float(value: object, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def format_signal_date(value: object) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)
