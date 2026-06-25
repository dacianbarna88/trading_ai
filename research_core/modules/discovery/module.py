"""Edge discovery research module — first implementation of ResearchModule."""

from __future__ import annotations

from research_core.config.discovery import DiscoveryConfig
from research_core.framework.module import ResearchModule
from research_core.framework.pipeline import ResearchPipeline
from research_core.framework.registry import ModuleRegistry
from research_core.modules.discovery.stages import (
    EvaluateCandidatesStage,
    GenerateRulesStage,
    InitProgressStage,
    LoadDatasetStage,
    WriteReportsStage,
)


class DiscoveryResearchModule(ResearchModule):
    """Automated edge discovery — V3.0 implementation."""

    def __init__(self, config: DiscoveryConfig | None = None) -> None:
        super().__init__(config or DiscoveryConfig.v30_default())

    @property
    def module_id(self) -> str:
        return self.config.module_id

    @property
    def module_version(self) -> str:
        return self.config.version

    def banner_title(self) -> str:
        return f"EDGE DISCOVERY ENGINE V{self.module_version}"

    def build_pipeline(self) -> ResearchPipeline:
        return ResearchPipeline(
            [
                InitProgressStage(),
                LoadDatasetStage(),
                GenerateRulesStage(),
                EvaluateCandidatesStage(),
                WriteReportsStage(),
            ]
        )


def register_discovery_module() -> None:
    ModuleRegistry.register(
        "edge_discovery",
        lambda: DiscoveryResearchModule(DiscoveryConfig.v30_default()),
    )

register_discovery_module()
