"""Research framework — base for all future modules."""

from research_core.framework.context import (
    AuditEntry,
    ResearchContext,
    ResearchStageError,
    RunResult,
)
from research_core.framework.module import ResearchModule
from research_core.framework.pipeline import ResearchPipeline
from research_core.framework.registry import ComponentRegistry, ModuleRegistry

__all__ = [
    "AuditEntry",
    "ComponentRegistry",
    "ModuleRegistry",
    "ResearchContext",
    "ResearchModule",
    "ResearchPipeline",
    "ResearchStageError",
    "RunResult",
]
