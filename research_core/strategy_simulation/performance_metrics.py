"""
Performance metrics schema — Phase X Sprint X.3B

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Canonical performance metric fields. All values PENDING until historical execution.
"""

from __future__ import annotations

from typing import Any

PENDING_VALUE = "PENDING"

METRIC_FIELDS: tuple[str, ...] = (
    "profit_pct",
    "max_drawdown",
    "sharpe",
    "sortino",
    "profit_factor",
    "win_rate",
    "expectancy",
    "trade_count",
    "average_hold_days",
    "recovery_factor",
    "kelly_fraction",
)


def pending_performance_metrics() -> dict[str, str]:
    return {field: PENDING_VALUE for field in METRIC_FIELDS}


def validate_performance_metrics_schema(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    for field in METRIC_FIELDS:
        if field not in metrics:
            warnings.append(f"Missing performance metric field: {field}")
        elif metrics[field] != PENDING_VALUE:
            warnings.append(f"Metric {field} expected PENDING in foundation sprint")

    extra = set(metrics.keys()) - set(METRIC_FIELDS)
    if extra:
        warnings.append(f"Unexpected performance metric fields: {sorted(extra)}")

    return len(warnings) == 0, warnings
