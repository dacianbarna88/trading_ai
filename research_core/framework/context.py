"""Run context, audit trail, and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.config.base import BaseResearchConfig


@dataclass
class AuditEntry:
    """One auditable pipeline event."""

    stage: str
    event: str
    detail: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metrics: dict[str, Any] = field(default_factory=dict)


class ResearchStageError(Exception):
    """Raised when a pipeline stage cannot continue."""

    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        self.message = message
        super().__init__(f"[{stage}] {message}")


@dataclass
class ResearchContext:
    """
    Mutable run context passed through every pipeline stage.
    Future modules store intermediate artifacts here instead of ad-hoc globals.
    """

    config: BaseResearchConfig
    output_dir: Path
    module_id: str
    module_version: str
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    artifacts: dict[str, Any] = field(default_factory=dict)
    audit_log: list[AuditEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def log(
        self,
        stage: str,
        event: str,
        detail: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> None:
        self.audit_log.append(
            AuditEntry(
                stage=stage,
                event=event,
                detail=detail,
                metrics=metrics or {},
            )
        )

    def artifact(self, key: str, default: Any = None) -> Any:
        return self.artifacts.get(key, default)


@dataclass
class RunResult:
    """Standard return type for every research module run."""

    module_id: str
    module_version: str
    status: str
    output_dir: Path
    started_at: datetime
    finished_at: datetime
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    audit_log: list[AuditEntry] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_version": self.module_version,
            "status": self.status,
            "output_dir": str(self.output_dir),
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "summary": self.summary.split("\n")[0] if self.summary else "",
        }
