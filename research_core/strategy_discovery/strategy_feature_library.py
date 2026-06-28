"""
Strategy Feature Library — Phase X Sprint X.3A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Canonical feature definitions for deterministic strategy discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FeatureCategory(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    FILTER = "FILTER"


@dataclass(frozen=True)
class FeatureDefinition:
    feature_id: str
    category: FeatureCategory
    label: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "feature_id": self.feature_id,
            "category": self.category.value,
            "label": self.label,
            "description": self.description,
        }


ENTRY_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("RSI", FeatureCategory.ENTRY, "RSI", "Relative Strength Index oversold/overbought entry"),
    FeatureDefinition("MACD", FeatureCategory.ENTRY, "MACD", "MACD signal-line crossover entry"),
    FeatureDefinition("EMA_CROSS", FeatureCategory.ENTRY, "EMA Cross", "Fast/slow EMA crossover entry"),
    FeatureDefinition("SMA_BREAKOUT", FeatureCategory.ENTRY, "SMA Breakout", "Price breakout above SMA entry"),
    FeatureDefinition("MOMENTUM", FeatureCategory.ENTRY, "Momentum", "Price momentum threshold entry"),
    FeatureDefinition("VOLUME_SPIKE", FeatureCategory.ENTRY, "Volume Spike", "Abnormal volume spike entry"),
    FeatureDefinition("ATR_BREAKOUT", FeatureCategory.ENTRY, "ATR Breakout", "ATR expansion breakout entry"),
    FeatureDefinition("GAP_UP", FeatureCategory.ENTRY, "Gap Up", "Gap-up continuation entry"),
    FeatureDefinition("GAP_DOWN", FeatureCategory.ENTRY, "Gap Down", "Gap-down reversal entry"),
    FeatureDefinition("RELATIVE_STRENGTH", FeatureCategory.ENTRY, "Relative Strength", "Sector-relative strength entry"),
)

EXIT_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("ATR_STOP", FeatureCategory.EXIT, "ATR Stop", "ATR-based stop-loss exit"),
    FeatureDefinition("TRAILING_STOP", FeatureCategory.EXIT, "Trailing Stop", "Trailing percentage stop exit"),
    FeatureDefinition("FIXED_STOP", FeatureCategory.EXIT, "Fixed Stop", "Fixed percentage stop exit"),
    FeatureDefinition("TIME_EXIT", FeatureCategory.EXIT, "Time Exit", "Maximum holding period exit"),
    FeatureDefinition("PROFIT_TARGET", FeatureCategory.EXIT, "Profit Target", "Fixed profit target exit"),
    FeatureDefinition("RSI_EXIT", FeatureCategory.EXIT, "RSI Exit", "RSI overbought/oversold exit"),
    FeatureDefinition("EMA_EXIT", FeatureCategory.EXIT, "EMA Exit", "EMA crossover reversal exit"),
    FeatureDefinition("SMA_EXIT", FeatureCategory.EXIT, "SMA Exit", "SMA breakdown exit"),
)

FILTER_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("US_ONLY", FeatureCategory.FILTER, "US Only", "United States equities filter"),
    FeatureDefinition("EU_ONLY", FeatureCategory.FILTER, "EU Only", "European equities filter"),
    FeatureDefinition("UK_ONLY", FeatureCategory.FILTER, "UK Only", "United Kingdom equities filter"),
    FeatureDefinition("BULL_ONLY", FeatureCategory.FILTER, "Bull Only", "Bull market regime filter"),
    FeatureDefinition("BEAR_ONLY", FeatureCategory.FILTER, "Bear Only", "Bear market regime filter"),
    FeatureDefinition("ABOVE_SMA200", FeatureCategory.FILTER, "Above SMA200", "Price above 200-day SMA filter"),
    FeatureDefinition("ABOVE_SMA50", FeatureCategory.FILTER, "Above SMA50", "Price above 50-day SMA filter"),
    FeatureDefinition("HIGH_VOLUME", FeatureCategory.FILTER, "High Volume", "Above-average volume filter"),
    FeatureDefinition("LOW_VOLATILITY", FeatureCategory.FILTER, "Low Volatility", "Low volatility regime filter"),
    FeatureDefinition("HIGH_VOLATILITY", FeatureCategory.FILTER, "High Volatility", "High volatility regime filter"),
)

HOLDING_PERIODS: tuple[int, ...] = (3, 5, 8, 10, 14, 21, 30)

EXPECTED_ENTRY_COUNT = 10
EXPECTED_EXIT_COUNT = 8
EXPECTED_FILTER_COUNT = 10
EXPECTED_HOLDING_COUNT = 7


def get_feature_library() -> dict[str, Any]:
    return {
        "entry_features": [feature.to_dict() for feature in ENTRY_FEATURES],
        "exit_features": [feature.to_dict() for feature in EXIT_FEATURES],
        "filter_features": [feature.to_dict() for feature in FILTER_FEATURES],
        "holding_periods": list(HOLDING_PERIODS),
        "counts": {
            "entry": len(ENTRY_FEATURES),
            "exit": len(EXIT_FEATURES),
            "filter": len(FILTER_FEATURES),
            "holding": len(HOLDING_PERIODS),
        },
    }


def validate_feature_library() -> tuple[bool, list[str]]:
    warnings: list[str] = []
    checks = [
        (len(ENTRY_FEATURES), EXPECTED_ENTRY_COUNT, "entry"),
        (len(EXIT_FEATURES), EXPECTED_EXIT_COUNT, "exit"),
        (len(FILTER_FEATURES), EXPECTED_FILTER_COUNT, "filter"),
        (len(HOLDING_PERIODS), EXPECTED_HOLDING_COUNT, "holding"),
    ]
    for actual, expected, label in checks:
        if actual != expected:
            warnings.append(f"Feature library {label} count {actual} != expected {expected}")

    for group in (ENTRY_FEATURES, EXIT_FEATURES, FILTER_FEATURES):
        ids = [feature.feature_id for feature in group]
        if len(ids) != len(set(ids)):
            warnings.append("Duplicate feature IDs detected in feature library")

    return len(warnings) == 0, warnings
