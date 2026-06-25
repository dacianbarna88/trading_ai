"""Research framework contracts."""

from research_core.contracts.components import (
    FeatureRegistryProtocol,
    ReporterProtocol,
    RuleEvaluatorProtocol,
    RuleGeneratorProtocol,
    SignalCollectorProtocol,
    WalkForwardValidatorProtocol,
)
from research_core.contracts.stages import PipelineStageProtocol

__all__ = [
    "FeatureRegistryProtocol",
    "PipelineStageProtocol",
    "ReporterProtocol",
    "RuleEvaluatorProtocol",
    "RuleGeneratorProtocol",
    "SignalCollectorProtocol",
    "WalkForwardValidatorProtocol",
]
