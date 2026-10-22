"""Tests for the startup analyzer."""

import pytest
from pathlib import Path


def test_metrics_import():
    """Test that core metrics can be imported."""
    from startup_analyzer.core.metrics import (
        Application,
        Measurement,
        MeasurementSet,
        MeasurementMode,
        Platform,
        AppType,
        Optimization,
        OptimizationRisk,
    )

    # Test enums
    assert Platform.MACOS.value == "macos"
    assert AppType.ELECTRON.value == "electron"
    assert MeasurementMode.COLD.value == "cold"
    assert OptimizationRisk.LOW.value == "low"


def test_application_creation():
    """Test Application model creation."""
    from startup_analyzer.core.metrics import Application, Platform, AppType

    app = Application(
        name="TestApp",
        executable=Path("/usr/bin/test"),
        platform=Platform.LINUX,
        app_type=AppType.NATIVE,
    )

    assert app.name == "TestApp"
    assert app.platform == Platform.LINUX
    assert app.app_type == AppType.NATIVE


def test_startup_timeline():
    """Test StartupTimeline calculations."""
    from startup_analyzer.core.metrics import StartupTimeline

    timeline = StartupTimeline(
        process_start=1000.0,
        first_cpu_activity=1000.5,
        main_window_visible=1002.0,
        process_idle=1005.0,
    )

    assert timeline.time_to_first_cpu == 0.5
    assert timeline.time_to_window == 2.0
    assert timeline.time_to_idle == 5.0


def test_resource_summary():
    """Test ResourceSummary."""
    from startup_analyzer.core.metrics import ResourceSummary

    summary = ResourceSummary(
        peak_cpu_percent=80.0,
        avg_cpu_percent=45.0,
        peak_memory_rss=100_000_000,
        avg_memory_rss=80_000_000,
        peak_threads=20,
        total_read_bytes=10_000_000,
        total_write_bytes=5_000_000,
        sample_count=100,
    )

    assert summary.peak_cpu_percent == 80.0
    assert summary.sample_count == 100


def test_measurement_statistics():
    """Test MeasurementSet statistics."""
    from startup_analyzer.core.metrics import (
        Application,
        Measurement,
        MeasurementSet,
        MeasurementMode,
        Platform,
        AppType,
        StartupTimeline,
        ResourceSummary,
    )

    app = Application(
        name="TestApp",
        executable=Path("/usr/bin/test"),
        platform=Platform.LINUX,
    )

    measurements = []
    for i in range(3):
        timeline = StartupTimeline(
            process_start=1000.0 + i,
            first_cpu_activity=1000.5 + i,
            main_window_visible=1002.0 + i,
            process_idle=1005.0 + i,
        )
        resources = ResourceSummary(
            peak_cpu_percent=80.0,
            avg_cpu_percent=45.0,
            peak_memory_rss=100_000_000,
            avg_memory_rss=80_000_000,
            peak_threads=20,
            total_read_bytes=10_000_000,
            total_write_bytes=5_000_000,
            sample_count=100,
        )
        m = Measurement(
            app=app,
            mode=MeasurementMode.WARM,
            timeline=timeline,
            resources=resources,
            iteration=i + 1,
        )
        measurements.append(m)

    measurement_set = MeasurementSet(
        app=app,
        mode=MeasurementMode.WARM,
        measurements=measurements,
    )

    stats = measurement_set.get_statistics("time_to_window")
    assert stats["count"] == 3
    assert stats["mean"] == 2.0
    assert stats["median"] == 2.0


def test_comparison_report():
    """Test ComparisonReport improvements."""
    from startup_analyzer.core.metrics import (
        Application,
        Measurement,
        MeasurementSet,
        ComparisonReport,
        MeasurementMode,
        Platform,
        AppType,
        StartupTimeline,
        ResourceSummary,
        OptimizationResult,
        Optimization,
        OptimizationRisk,
    )

    app = Application(
        name="TestApp",
        executable=Path("/usr/bin/test"),
        platform=Platform.LINUX,
    )

    # Baseline measurements (slower)
    baseline_measurements = []
    for i in range(3):
        timeline = StartupTimeline(
            process_start=1000.0,
            main_window_visible=1004.0,  # 4s to window
        )
        resources = ResourceSummary(
            peak_cpu_percent=80.0,
            avg_cpu_percent=50.0,
            peak_memory_rss=200_000_000,
            avg_memory_rss=150_000_000,
            peak_threads=20,
            total_read_bytes=50_000_000,
            total_write_bytes=10_000_000,
            sample_count=100,
        )
        m = Measurement(
            app=app,
            mode=MeasurementMode.WARM,
            timeline=timeline,
            resources=resources,
            iteration=i + 1,
        )
        baseline_measurements.append(m)

    # Optimized measurements (faster)
    optimized_measurements = []
    for i in range(3):
        timeline = StartupTimeline(
            process_start=1000.0,
            main_window_visible=1002.5,  # 2.5s to window
        )
        resources = ResourceSummary(
            peak_cpu_percent=70.0,
            avg_cpu_percent=40.0,
            peak_memory_rss=180_000_000,
            avg_memory_rss=130_000_000,
            peak_threads=18,
            total_read_bytes=40_000_000,
            total_write_bytes=8_000_000,
            sample_count=100,
        )
        m = Measurement(
            app=app,
            mode=MeasurementMode.WARM,
            timeline=timeline,
            resources=resources,
            iteration=i + 1,
        )
        optimized_measurements.append(m)

    baseline = MeasurementSet(
        app=app,
        mode=MeasurementMode.WARM,
        measurements=baseline_measurements,
    )
    optimized = MeasurementSet(
        app=app,
        mode=MeasurementMode.WARM,
        measurements=optimized_measurements,
    )

    report = ComparisonReport(
        app=app,
        baseline=baseline,
        optimized=optimized,
        optimizations_applied=[],
    )

    # Test improvement calculation
    imp = report.get_improvement("time_to_window")
    assert imp["improvement_pct"] > 0  # Should be positive (faster)
    assert abs(imp["improvement_pct"] - 37.5) < 0.1  # (4-2.5)/4 * 100 = 37.5%

    imp_mem = report.get_improvement("peak_memory_rss")
    assert imp_mem["improvement_pct"] > 0  # Should be positive (less memory)


def test_optimization_registry():
    """Test optimization registry."""
    from startup_analyzer.optimization.registry import registry

    # Should have registered optimizations
    all_opts = registry.get_all()
    assert len(all_opts) > 0

    # Check some known optimizations
    assert "disable-telemetry" in all_opts
    assert "prefetch-libraries" in all_opts
    assert "launch-args" in all_opts


def test_platform_detection():
    """Test platform backend detection."""
    import sys
    from startup_analyzer.platform.base import get_current_platform, get_platform_backend
    from startup_analyzer.core.metrics import Platform

    platform = get_current_platform()
    assert platform in (Platform.MACOS, Platform.LINUX, Platform.WINDOWS)

    backend = get_platform_backend()
    assert backend.platform == platform


if __name__ == "__main__":
    pytest.main([__file__, "-v"])