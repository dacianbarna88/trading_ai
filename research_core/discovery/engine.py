"""Discovery engine — delegates to DiscoveryResearchModule."""

from __future__ import annotations

from pathlib import Path

from research_core.config import DiscoveryConfig
from research_core.modules.discovery.module import DiscoveryResearchModule


class DiscoveryEngine(DiscoveryResearchModule):
    """
    Backward-compatible facade for V3.0 entry point.
    New code should use DiscoveryResearchModule or ModuleRegistry.
    """

    def run(self, output_dir: str | None = None) -> dict:
        result = super().run(output_dir)
        return {
            "status": result.status,
            "signals": result.metrics.get("signals", result.metrics.get("load_dataset.signals", 0)),
            "candidates": result.metrics.get(
                "candidates", result.metrics.get("evaluate_candidates.candidates", 0)
            ),
            "survivors": result.metrics.get(
                "survivors", result.metrics.get("evaluate_candidates.survivors", 0)
            ),
            "rejected": result.metrics.get(
                "rejected", result.metrics.get("evaluate_candidates.rejected", 0)
            ),
        }
