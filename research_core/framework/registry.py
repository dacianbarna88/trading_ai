"""Registry for research modules and pluggable components."""

from __future__ import annotations

from typing import Callable, TypeVar

from research_core.framework.module import ResearchModule

T = TypeVar("T")


class ModuleRegistry:
    """Register future research modules by id for CLI / orchestration."""

    _modules: dict[str, Callable[[], ResearchModule]] = {}

    @classmethod
    def register(
        cls,
        module_id: str,
        factory: Callable[[], ResearchModule],
    ) -> None:
        cls._modules[module_id] = factory

    @classmethod
    def get(cls, module_id: str) -> ResearchModule | None:
        factory = cls._modules.get(module_id)
        return factory() if factory else None

    @classmethod
    def list_modules(cls) -> list[str]:
        return sorted(cls._modules.keys())


class ComponentRegistry:
    """Generic registry for validators, scorers, feature packs, etc."""

    _components: dict[str, dict[str, object]] = {}

    @classmethod
    def register(cls, category: str, name: str, component: object) -> None:
        cls._components.setdefault(category, {})[name] = component

    @classmethod
    def get(cls, category: str, name: str) -> object | None:
        return cls._components.get(category, {}).get(name)

    @classmethod
    def list_category(cls, category: str) -> list[str]:
        return sorted(cls._components.get(category, {}).keys())
