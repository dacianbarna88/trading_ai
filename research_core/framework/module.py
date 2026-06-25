"""Base class for all research modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.config.base import BaseResearchConfig
from research_core.framework.context import ResearchContext, RunResult
from research_core.framework.pipeline import ResearchPipeline


class ResearchModule(ABC):
    """
    Foundation for every future research module (discovery, robustness, walk-forward, etc.).

    Subclasses implement:
      - module_id / module_version
      - build_pipeline()
      - optional banner_title()
    """

    @property
    @abstractmethod
    def module_id(self) -> str: ...

    @property
    @abstractmethod
    def module_version(self) -> str: ...

    @abstractmethod
    def build_pipeline(self) -> ResearchPipeline: ...

    def __init__(self, config: BaseResearchConfig) -> None:
        self.config = config

    def banner_title(self) -> str:
        return f"{self.module_id.upper()} V{self.module_version}"

    def run(self, output_dir: str | Path | None = None) -> RunResult:
        base = Path(output_dir or self.config.output_dir)
        base.mkdir(parents=True, exist_ok=True)

        context = ResearchContext(
            config=self.config,
            output_dir=base,
            module_id=self.module_id,
            module_version=self.module_version,
        )
        started = context.started_at

        self._print_banner()
        pipeline = self.build_pipeline()
        context.log("pipeline", "stages_registered", detail=", ".join(pipeline.stage_names))

        try:
            stage_metrics = pipeline.run(context)
            status = "ok"
        except Exception:
            status = "failed"
            stage_metrics = {}

        finished = datetime.now(timezone.utc)
        result = RunResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=status,
            output_dir=base,
            started_at=started,
            finished_at=finished,
            metrics=self._aggregate_metrics(stage_metrics, context),
            artifacts=self._artifact_paths(context),
            audit_log=list(context.audit_log),
            summary=str(context.artifact("summary", "")),
        )
        context.artifacts["run_result"] = result
        return result

    def _print_banner(self) -> None:
        print(f"===== {self.banner_title()} =====")
        print(RESEARCH_SAFETY_BANNER)
        print("Research Core framework — no automatic production promotion.")
        print()

    def _aggregate_metrics(
        self,
        stage_metrics: dict,
        context: ResearchContext,
    ) -> dict:
        metrics: dict = {}
        for stage_name, data in stage_metrics.items():
            if isinstance(data, dict):
                metrics.update({f"{stage_name}.{k}": v for k, v in data.items()})
        run_metrics = context.artifact("run_metrics")
        if isinstance(run_metrics, dict):
            metrics.update(run_metrics)
        return metrics

    def _artifact_paths(self, context: ResearchContext) -> dict[str, str]:
        paths = context.artifact("output_paths")
        if isinstance(paths, dict):
            return {k: str(v) for k, v in paths.items()}
        return {}
