"""
Strategy Hypothesis Generator — Phase X Sprint X.3A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Deterministic generation of research strategy hypotheses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_core.strategy_discovery.strategy_feature_library import (
    ENTRY_FEATURES,
    EXIT_FEATURES,
    FILTER_FEATURES,
    HOLDING_PERIODS,
)

TARGET_HYPOTHESIS_COUNT = 100

RISK_PROFILES: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH")


@dataclass
class StrategyHypothesis:
    discovery_id: str
    entry_rule: str
    exit_rule: str
    market_filter: str
    holding_period: int
    risk_profile: str
    confidence_seed: float
    feature_vector: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_id": self.discovery_id,
            "entry_rule": self.entry_rule,
            "exit_rule": self.exit_rule,
            "market_filter": self.market_filter,
            "holding_period": self.holding_period,
            "risk_profile": self.risk_profile,
            "confidence_seed": self.confidence_seed,
            "feature_vector": list(self.feature_vector),
        }


def _discovery_id(index: int) -> str:
    return f"DISCOVERY_{index + 1:04d}"


def _entry_rule(index: int) -> str:
    primary = ENTRY_FEATURES[index % len(ENTRY_FEATURES)].feature_id
    secondary = ENTRY_FEATURES[(index // len(ENTRY_FEATURES)) % len(ENTRY_FEATURES)].feature_id
    if primary == secondary:
        return primary
    return f"{primary}+{secondary}"


def _confidence_seed(index: int) -> float:
    raw = 0.42 + ((index * 17 + 13) % 55) * 0.01
    return round(min(raw, 0.96), 4)


def _feature_vector(entry_rule: str, exit_rule: str, market_filter: str) -> list[str]:
    entries = entry_rule.split("+")
    return entries + [exit_rule, market_filter]


def generate_hypotheses(count: int = TARGET_HYPOTHESIS_COUNT) -> list[StrategyHypothesis]:
    if count <= 0:
        return []

    hypotheses: list[StrategyHypothesis] = []
    for index in range(count):
        entry_rule = _entry_rule(index)
        exit_rule = EXIT_FEATURES[(index // len(ENTRY_FEATURES)) % len(EXIT_FEATURES)].feature_id
        market_filter = FILTER_FEATURES[
            (index // (len(ENTRY_FEATURES) * len(EXIT_FEATURES))) % len(FILTER_FEATURES)
        ].feature_id
        holding_period = HOLDING_PERIODS[
            (index // (len(ENTRY_FEATURES) * len(EXIT_FEATURES) * len(FILTER_FEATURES)))
            % len(HOLDING_PERIODS)
        ]
        risk_profile = RISK_PROFILES[index % len(RISK_PROFILES)]

        hypotheses.append(
            StrategyHypothesis(
                discovery_id=_discovery_id(index),
                entry_rule=entry_rule,
                exit_rule=exit_rule,
                market_filter=market_filter,
                holding_period=holding_period,
                risk_profile=risk_profile,
                confidence_seed=_confidence_seed(index),
                feature_vector=_feature_vector(entry_rule, exit_rule, market_filter),
            )
        )

    return hypotheses
