"""Startup time measurement engine."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from startup_analyzer.core.metrics import MeasurementMode

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import (
        Application,
        Measurement,
        ProcessMetrics,
    )
    from startup_analyzer.platform.base import PlatformBackend


@dataclass
class TimerConfig:
    """Configuration for startup timing."""

    cpu_idle_threshold: float = 5.0  # CPU% below which process is considered idle
    cpu_idle_duration: float = 2.0  # Seconds of low CPU to consider idle
    window_timeout: float = 15.0  # Max time to wait for window
    idle_timeout: float = 20.0  # Max time to wait for idle
    sample_interval: float = 0.1  # Metrics sampling interval (seconds)
    max_iterations: int = 5  # Max measurement iterations


class StartupTimer:
    """Measures application startup time with detailed timeline."""

    def __init__(self, backend: PlatformBackend, config: TimerConfig | None = None):
        self.backend = backend
        self.config = config or TimerConfig()

    def measure(self, app: Application, mode: MeasurementMode = MeasurementMode.WARM) -> Measurement:
        """Perform a single startup measurement."""
        from startup_analyzer.core.metrics import (
            Measurement,
            ProcessMetrics,
            ResourceSummary,
            StartupTimeline,
        )

        timeline = StartupTimeline(process_start=0.0)
        raw_metrics: list[ProcessMetrics] = []

        # Prepare environment
        env = dict(app.env_vars)

        # Launch application
        t0 = time.perf_counter()
        timeline.process_start = t0

        proc = self.backend.launch_application(app)
        pid = proc.pid

        # Prime CPU measurement for the process
        try:
            import psutil
            psutil.Process(pid).cpu_percent(interval=0.1)
        except Exception:
            pass

        # Wait for first CPU activity
        first_cpu = None
        start_wait = time.perf_counter()
        while time.perf_counter() - start_wait < self.config.window_timeout:
            metrics = self.backend.get_process_metrics(pid)
            if metrics and metrics.get("cpu_percent", 0) > 0.1:
                first_cpu = time.perf_counter()
                timeline.first_cpu_activity = first_cpu
                break
            time.sleep(0.01)

        # Sample metrics during startup
        sample_start = time.perf_counter()
        cpu_samples = []
        mem_samples = []
        thread_samples = []
        read_bytes = 0
        write_bytes = 0

        # Wait for window
        window_visible = False
        window_start = time.perf_counter()
        while time.perf_counter() - window_start < self.config.window_timeout:
            metrics = self.backend.get_process_metrics(pid)
            if metrics:
                raw_metrics.append(
                    ProcessMetrics(
                        timestamp=time.perf_counter(),
                        cpu_percent=metrics["cpu_percent"],
                        memory_rss=metrics["memory_rss"],
                        memory_vms=metrics["memory_vms"],
                        num_threads=metrics["num_threads"],
                        num_fds=metrics.get("num_fds"),
                        read_bytes=metrics.get("read_bytes", 0),
                        write_bytes=metrics.get("write_bytes", 0),
                    )
                )
                cpu_samples.append(metrics["cpu_percent"])
                mem_samples.append(metrics["memory_rss"])
                thread_samples.append(metrics["num_threads"])
                read_bytes = max(read_bytes, metrics.get("read_bytes", 0))
                write_bytes = max(write_bytes, metrics.get("write_bytes", 0))

            if not window_visible and self.backend.wait_for_window(pid, 0.5):
                timeline.main_window_visible = time.perf_counter()
                window_visible = True

            # Check if process exited
            try:
                if proc.poll() is not None:
                    break
            except Exception:
                break

            time.sleep(self.config.sample_interval)

        # Wait for idle
        idle_start = time.perf_counter()
        self.backend.wait_for_idle(
            pid,
            self.config.cpu_idle_threshold,
            self.config.cpu_idle_duration,
            self.config.idle_timeout,
        )
        timeline.process_idle = time.perf_counter()

        # Ensure process is still running for final metrics
        final_metrics = self.backend.get_process_metrics(pid)

        # Calculate resource summary
        resources = ResourceSummary(
            peak_cpu_percent=max(cpu_samples) if cpu_samples else 0.0,
            avg_cpu_percent=sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0,
            peak_memory_rss=max(mem_samples) if mem_samples else 0,
            avg_memory_rss=int(sum(mem_samples) / len(mem_samples)) if mem_samples else 0,
            peak_threads=max(thread_samples) if thread_samples else 0,
            total_read_bytes=read_bytes,
            total_write_bytes=write_bytes,
            sample_count=len(raw_metrics),
        )

        return Measurement(
            app=app,
            mode=mode,
            timeline=timeline,
            resources=resources,
            raw_metrics=raw_metrics,
            success=timeline.main_window_visible is not None,
            error=None if timeline.main_window_visible else "Window did not appear",
        )

    def measure_multiple(
        self,
        app: Application,
        mode: MeasurementMode = MeasurementMode.WARM,
        iterations: int = 3,
        cooldown: float = 2.0,
    ) -> list[Measurement]:
        """Perform multiple measurements with cooldown between runs."""

        measurements = []
        for i in range(iterations):
            measurement = self.measure(app, mode)
            measurement.iteration = i + 1
            measurements.append(measurement)

            # Cooldown between runs
            if i < iterations - 1:
                time.sleep(cooldown)

        return measurements