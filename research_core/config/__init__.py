"""Configuration presets for research modules."""

from research_core.config.base import BaseResearchConfig
from research_core.config.discovery import DEFAULT_ROLLING_CONFIGS, DiscoveryConfig
from research_core.config.sectors import SECTOR_GROUPS

# Backward-compatible alias used by V3.0 entry point and existing imports.
ResearchConfig = DiscoveryConfig

__all__ = [
    "BaseResearchConfig",
    "DEFAULT_ROLLING_CONFIGS",
    "DiscoveryConfig",
    "ResearchConfig",
    "SECTOR_GROUPS",
]
