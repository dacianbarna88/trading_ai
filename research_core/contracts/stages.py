"""Pipeline stage contracts."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from research_core.framework.context import ResearchContext


@runtime_checkable
class PipelineStageProtocol(Protocol):
    """One auditable step in a research module pipeline."""

    name: str

    def run(self, context: ResearchContext) -> dict[str, Any]:
        """
        Execute the stage, mutate context.artifacts as needed, return stage metrics.
        Raise ResearchStageError to abort the run with an auditable message.
        """
        ...
