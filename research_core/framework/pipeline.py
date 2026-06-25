"""Sequential pipeline runner with audit logging."""

from __future__ import annotations

from typing import Any

from research_core.contracts.stages import PipelineStageProtocol
from research_core.framework.context import ResearchContext, ResearchStageError


class ResearchPipeline:
    """Runs ordered stages; each stage reads/writes context.artifacts."""

    def __init__(self, stages: list[PipelineStageProtocol]) -> None:
        self._stages = stages

    @property
    def stage_names(self) -> list[str]:
        return [s.name for s in self._stages]

    def run(self, context: ResearchContext) -> dict[str, Any]:
        stage_metrics: dict[str, Any] = {}
        for stage in self._stages:
            context.log(stage.name, "start")
            try:
                metrics = stage.run(context)
                stage_metrics[stage.name] = metrics
                context.log(stage.name, "complete", metrics=metrics)
            except ResearchStageError as exc:
                context.log(stage.name, "failed", detail=exc.message)
                raise
            except Exception as exc:
                context.log(stage.name, "error", detail=str(exc))
                raise ResearchStageError(stage.name, str(exc)) from exc
        return stage_metrics
