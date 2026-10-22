"""Core data models for the startup analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported platforms."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"


class AppType(str, Enum):
    """Types of applications."""

    NATIVE = "native"
    ELECTRON = "electron"
    CHROMIUM = "chromium"
    NODE = "node"
    JAVA = "java"
    PYTHON = "python"
    DOTNET = "dotnet"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class MeasurementMode(str, Enum):
    """Startup measurement modes."""

    COLD = "cold"  # First launch after reboot
    WARM = "warm"  # Subsequent launches
    HOT = "hot"    # Very recent launch (cached)


class OptimizationRisk(str, Enum):
    """Risk levels for optimizations."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ProcessMetrics:
    """Point-in-time process metrics."""

    timestamp: float
    cpu_percent: float
    memory_rss: int  # bytes
    memory_vms: int  # bytes
    num_threads: int
    num_fds: int | None = None  # Unix only
    read_bytes: int = 0
    write_bytes: int = 0


@dataclass
class StartupTimeline:
    """Timeline of startup events."""

    process_start: float
    first_cpu_activity: float | None = None
    main_window_visible: float | None = None
    process_idle: float | None = None
    custom_markers: dict[str, float] = field(default_factory=dict)

    @property
    def time_to_first_cpu(self) -> float | None:
        if self.first_cpu_activity:
            return self.first_cpu_activity - self.process_start
        return None

    @property
    def time_to_window(self) -> float | None:
        if self.main_window_visible:
            return self.main_window_visible - self.process_start
        return None

    @property
    def time_to_idle(self) -> float | None:
        if self.process_idle:
            return self.process_idle - self.process_start
        return None


@dataclass
class ResourceSummary:
    """Summary of resource usage during startup."""

    peak_cpu_percent: float
    avg_cpu_percent: float
    peak_memory_rss: int
    avg_memory_rss: int
    peak_threads: int
    total_read_bytes: int
    total_write_bytes: int
    sample_count: int


class Application(BaseModel):
    """Application metadata."""

    name: str
    executable: Path
    arguments: list[str] = Field(default_factory=list)
    working_dir: Path | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    platform: Platform
    app_type: AppType = AppType.UNKNOWN
    version: str | None = None
    bundle_id: str | None = None  # macOS
    desktop_file: Path | None = None  # Linux

    model_config = {"arbitrary_types_allowed": True}


class Measurement(BaseModel):
    """Single startup measurement."""

    app: Application
    mode: MeasurementMode
    timeline: StartupTimeline
    resources: ResourceSummary
    raw_metrics: list[ProcessMetrics] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    iteration: int = 1
    success: bool = True
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


class MeasurementSet(BaseModel):
    """Collection of measurements for statistical analysis."""

    app: Application
    mode: MeasurementMode
    measurements: list[Measurement]
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def successful_measurements(self) -> list[Measurement]:
        return [m for m in self.measurements if m.success]

    def get_statistics(self, attr: str) -> dict[str, float]:
        """Calculate statistics for a numeric attribute."""
        import statistics

        values = []
        for m in self.successful_measurements:
            val = getattr(m.timeline, attr, None)
            if val is not None:
                values.append(val)
            else:
                val = getattr(m.resources, attr, None)
                if val is not None:
                    values.append(val)

        if not values:
            return {}

        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }


class Optimization(BaseModel):
    """Optimization definition."""

    name: str
    description: str
    risk: OptimizationRisk = OptimizationRisk.LOW
    applies_to: list[AppType] = Field(default_factory=lambda: [AppType.UNKNOWN])
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.MACOS, Platform.LINUX, Platform.WINDOWS])
    reversible: bool = True
    requires_sudo: bool = False

    model_config = {"arbitrary_types_allowed": True}


class OptimizationResult(BaseModel):
    """Result of applying an optimization."""

    optimization: Optimization
    success: bool
    message: str
    applied_at: datetime = Field(default_factory=datetime.now)
    revert_info: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class ComparisonReport(BaseModel):
    """Before/after comparison report."""

    app: Application
    baseline: MeasurementSet
    optimized: MeasurementSet
    optimizations_applied: list[OptimizationResult]
    generated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"arbitrary_types_allowed": True}

    def get_improvement(self, attr: str) -> dict[str, float]:
        """Calculate improvement percentage for an attribute."""
        base_stats = self.baseline.get_statistics(attr)
        opt_stats = self.optimized.get_statistics(attr)

        if not base_stats or not opt_stats:
            return {}

        base_mean = base_stats["mean"]
        opt_mean = opt_stats["mean"]

        if base_mean == 0:
            return {}

        improvement_pct = ((base_mean - opt_mean) / base_mean) * 100

        return {
            "baseline_mean": base_mean,
            "optimized_mean": opt_mean,
            "improvement_pct": improvement_pct,
            "baseline_median": base_stats["median"],
            "optimized_median": opt_stats["median"],
        }