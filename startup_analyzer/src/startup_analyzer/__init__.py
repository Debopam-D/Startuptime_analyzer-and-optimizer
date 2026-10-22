"""Startup Analyzer - Cross-platform application startup time analyzer and optimizer."""

from startup_analyzer.core import (
    AnalyzerConfig,
    Application,
    AppType,
    Bottleneck,
    ComparisonReport,
    Measurement,
    MeasurementMode,
    MeasurementSet,
    Optimization,
    OptimizationResult,
    OptimizationRisk,
    Platform,
    ProcessMetrics,
    ReportGenerator,
    ResourceSummary,
    StartupAnalyzer,
    StartupTimeline,
    create_analyzer,
)

__version__ = "0.1.0"
__author__ = "Debopam Das"
__license__ = "MIT"

__all__ = [
    "Application",
    "Measurement",
    "MeasurementSet",
    "MeasurementMode",
    "ComparisonReport",
    "Optimization",
    "OptimizationResult",
    "OptimizationRisk",
    "ProcessMetrics",
    "StartupTimeline",
    "ResourceSummary",
    "Platform",
    "AppType",
    "Bottleneck",
    "StartupAnalyzer",
    "AnalyzerConfig",
    "create_analyzer",
    "ReportGenerator",
]