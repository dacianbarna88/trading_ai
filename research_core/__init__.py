"""
Trading AI Research Core — reusable scientific research framework.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Every future research module should extend ResearchModule and register
with ModuleRegistry. Shared data, metrics, and validation live here.
"""

from research_core.config import (
    BaseResearchConfig,
    DiscoveryConfig,
    ResearchConfig,
    SECTOR_GROUPS,
)
from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.engine import DiscoveryEngine
from research_core.framework import (
    ComponentRegistry,
    ModuleRegistry,
    ResearchContext,
    ResearchModule,
    ResearchPipeline,
    RunResult,
)
from research_core.modules.discovery.module import DiscoveryResearchModule
from research_core.types import EvaluationResult, Rule, SignalDataset

# Register built-in modules on import.
import research_core.modules.discovery.module  # noqa: F401

__all__ = [
    "BaseResearchConfig",
    "ComponentRegistry",
    "DiscoveryConfig",
    "DiscoveryEngine",
    "DiscoveryResearchModule",
    "EvaluationResult",
    "ModuleRegistry",
    "RESEARCH_SAFETY_BANNER",
    "ResearchConfig",
    "ResearchContext",
    "ResearchModule",
    "ResearchPipeline",
    "Rule",
    "RunResult",
    "SECTOR_GROUPS",
    "SignalDataset",
]
