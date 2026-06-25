"""TAE Discovery — rule discovery facade + Phase IV research opportunity engine."""

from research_core.discovery.discovery_engine import ResearchDiscoveryEngine
from research_core.discovery.discovery_to_hypothesis import (
    DiscoveryToHypothesisBridge,
    BridgeResult,
)
from research_core.discovery.discovery_model import (
    Discovery,
    DiscoveryCategory,
    DiscoveryStatus,
)
from research_core.discovery.discovery_registry import (
    DEFAULT_REGISTRY_PATH,
    DiscoveryRegistry,
)
from research_core.discovery.engine import DiscoveryEngine

__all__ = [
    "BridgeResult",
    "DEFAULT_REGISTRY_PATH",
    "Discovery",
    "DiscoveryCategory",
    "DiscoveryEngine",
    "DiscoveryRegistry",
    "DiscoveryStatus",
    "DiscoveryToHypothesisBridge",
    "ResearchDiscoveryEngine",
]
