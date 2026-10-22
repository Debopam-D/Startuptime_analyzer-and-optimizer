"""Optimization registry and base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import (
        Application,
        Optimization,
        OptimizationResult,
        Platform,
    )


@dataclass
class OptimizationContext:
    """Context passed to optimizations during apply/revert."""

    app: Application
    platform: Platform
    dry_run: bool = False
    user_config: dict[str, Any] = field(default_factory=dict)


class BaseOptimization(ABC):
    """Base class for all optimizations."""

    def __init__(self, definition: Optimization):
        self.definition = definition

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def risk(self) -> str:
        return self.definition.risk.value

    @property
    def applies_to(self) -> list[str]:
        return [a.value for a in self.definition.applies_to]

    @property
    def platforms(self) -> list[str]:
        return [p.value for p in self.definition.platforms]

    @property
    def reversible(self) -> bool:
        return self.definition.reversible

    @property
    def requires_sudo(self) -> bool:
        return self.definition.requires_sudo

    @abstractmethod
    def can_apply(self, ctx: OptimizationContext) -> bool:
        """Check if this optimization can be applied to the given app."""

    @abstractmethod
    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        """Apply the optimization."""

    @abstractmethod
    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        """Revert the optimization."""


class OptimizationRegistry:
    """Registry of available optimizations."""

    def __init__(self):
        self._optimizations: dict[str, type[BaseOptimization]] = {}
        self._definitions: dict[str, Optimization] = {}

    def register(self, optimization_class: type[BaseOptimization], definition: Optimization | None = None) -> None:
        """Register an optimization class with its definition."""
        if definition is None:
            from startup_analyzer.core.metrics import (
                AppType,
                Optimization,
                OptimizationRisk,
                Platform,
            )

            definition = Optimization(
                name=optimization_class.__name__,
                description="",
                risk=OptimizationRisk.LOW,
                applies_to=[AppType.UNKNOWN],
                platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
            )
        self._optimizations[definition.name] = optimization_class
        self._definitions[definition.name] = definition

    def get(self, name: str) -> type[BaseOptimization] | None:
        """Get an optimization class by name."""
        return self._optimizations.get(name)

    def get_definition(self, name: str) -> Optimization | None:
        """Get an optimization definition by name."""
        return self._definitions.get(name)

    def get_all(self) -> dict[str, type[BaseOptimization]]:
        """Get all registered optimizations."""
        return self._optimizations.copy()

    def get_applicable(self, ctx: OptimizationContext) -> list[type[BaseOptimization]]:
        """Get all optimizations applicable to the given context."""
        applicable = []
        for name, opt_class in self._optimizations.items():
            definition = self._definitions.get(name)
            if definition is None:
                continue
            instance = opt_class(definition)
            if instance.can_apply(ctx):
                applicable.append(opt_class)
        return applicable

    def create_instance(self, name: str, definition: Optimization | None = None) -> BaseOptimization | None:
        """Create an instance of an optimization with its definition."""
        opt_class = self.get(name)
        if opt_class is None:
            return None
        if definition is None:
            definition = self._definitions.get(name)
        if definition is None:
            return None
        return opt_class(definition)


# Global registry instance
registry = OptimizationRegistry()