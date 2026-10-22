"""Optimization package initialization."""

# Import all optimizations to register them
from startup_analyzer.optimization import env_vars, launch_args, prefetch  # noqa: F401
from startup_analyzer.optimization.registry import (
    BaseOptimization,
    OptimizationContext,
    OptimizationRegistry,
    registry,
)

__all__ = [
    "OptimizationRegistry",
    "BaseOptimization",
    "OptimizationContext",
    "registry",
]