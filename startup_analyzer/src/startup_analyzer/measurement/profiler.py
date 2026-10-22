"""Bottleneck analysis and profiling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import Application, ProcessMetrics
    from startup_analyzer.platform.base import PlatformBackend


@dataclass
class Bottleneck:
    """Identified bottleneck during startup."""

    category: str  # io, cpu, network, library, lock, other
    description: str
    severity: float  # 0-1, higher = more severe
    evidence: dict
    suggestion: str


class StartupProfiler:
    """Analyzes startup behavior to identify bottlenecks."""

    def __init__(self, backend: PlatformBackend):
        self.backend = backend

    def analyze(
        self,
        app: Application,
        metrics: list[ProcessMetrics],
        timeline: dict,
    ) -> list[Bottleneck]:
        """Analyze metrics and timeline to identify bottlenecks."""
        bottlenecks = []

        # Analyze CPU patterns
        bottlenecks.extend(self._analyze_cpu(metrics))

        # Analyze memory patterns
        bottlenecks.extend(self._analyze_memory(metrics))

        # Analyze I/O patterns
        bottlenecks.extend(self._analyze_io(metrics))

        # Analyze timeline
        bottlenecks.extend(self._analyze_timeline(timeline))

        # Platform-specific analysis
        bottlenecks.extend(self._analyze_platform_specific(app, metrics))

        # Sort by severity
        bottlenecks.sort(key=lambda b: b.severity, reverse=True)

        return bottlenecks

    def _analyze_cpu(self, metrics: list[ProcessMetrics]) -> list[Bottleneck]:
        """Analyze CPU usage patterns."""
        bottlenecks = []

        if not metrics:
            return bottlenecks

        cpu_values = [m.cpu_percent for m in metrics]
        avg_cpu = sum(cpu_values) / len(cpu_values)
        peak_cpu = max(cpu_values)

        # High sustained CPU
        if avg_cpu > 50:
            bottlenecks.append(
                Bottleneck(
                    category="cpu",
                    description=f"High sustained CPU usage (avg: {avg_cpu:.1f}%, peak: {peak_cpu:.1f}%)",
                    severity=min(avg_cpu / 100, 1.0),
                    evidence={"avg_cpu": avg_cpu, "peak_cpu": peak_cpu},
                    suggestion="Consider profiling with perf/instruments to identify hot functions. "
                    "Check for busy loops, excessive computation, or synchronous initialization.",
                )
            )

        # CPU spikes
        spikes = sum(1 for c in cpu_values if c > 80)
        if spikes > len(cpu_values) * 0.1:
            bottlenecks.append(
                Bottleneck(
                    category="cpu",
                    description=f"Frequent CPU spikes ({spikes}/{len(cpu_values)} samples > 80%)",
                    severity=0.6,
                    evidence={"spike_count": spikes, "total_samples": len(cpu_values)},
                    suggestion="Look for periodic heavy operations. Consider lazy initialization or background threads.",
                )
            )

        return bottlenecks

    def _analyze_memory(self, metrics: list[ProcessMetrics]) -> list[Bottleneck]:
        """Analyze memory usage patterns."""
        bottlenecks = []

        if not metrics:
            return bottlenecks

        mem_values = [m.memory_rss for m in metrics]
        if len(mem_values) < 2:
            return bottlenecks

        peak_mem = max(mem_values)
        start_mem = mem_values[0]
        growth = peak_mem - start_mem
        growth_rate = growth / len(metrics) if len(metrics) > 0 else 0

        # Excessive memory growth
        if growth > 100 * 1024 * 1024:  # 100MB growth
            bottlenecks.append(
                Bottleneck(
                    category="memory",
                    description=f"High memory growth during startup: {growth / (1024*1024):.1f} MB",
                    severity=min(growth / (500 * 1024 * 1024), 1.0),
                    evidence={"growth_mb": growth / (1024 * 1024), "peak_mb": peak_mem / (1024 * 1024)},
                    suggestion="Check for memory leaks, excessive caching, or loading unnecessary data. "
                    "Consider lazy loading of resources.",
                )
            )

        # Memory allocation rate
        if growth_rate > 10 * 1024 * 1024:  # 10MB per sample
            bottlenecks.append(
                Bottleneck(
                    category="memory",
                    description=f"Rapid memory allocation rate: {growth_rate / (1024*1024):.1f} MB/sample",
                    severity=0.5,
                    evidence={"growth_rate_mb_per_sample": growth_rate / (1024 * 1024)},
                    suggestion="High allocation rate can trigger GC pauses. Consider object pooling or reducing allocations.",
                )
            )

        return bottlenecks

    def _analyze_io(self, metrics: list[ProcessMetrics]) -> list[Bottleneck]:
        """Analyze I/O patterns."""
        bottlenecks = []

        if not metrics:
            return bottlenecks

        read_values = [m.read_bytes for m in metrics]
        write_values = [m.write_bytes for m in metrics]

        total_read = max(read_values) - min(read_values) if read_values else 0
        total_write = max(write_values) - min(write_values) if write_values else 0

        # High I/O volume
        if total_read > 50 * 1024 * 1024:  # 50MB read
            bottlenecks.append(
                Bottleneck(
                    category="io",
                    description=f"High disk read during startup: {total_read / (1024*1024):.1f} MB",
                    severity=min(total_read / (200 * 1024 * 1024), 1.0),
                    evidence={"read_mb": total_read / (1024 * 1024)},
                    suggestion="Consider preloading/caching files, using memory-mapped files, or deferring non-critical reads.",
                )
            )

        if total_write > 10 * 1024 * 1024:  # 10MB write
            bottlenecks.append(
                Bottleneck(
                    category="io",
                    description=f"High disk write during startup: {total_write / (1024*1024):.1f} MB",
                    severity=min(total_write / (50 * 1024 * 1024), 1.0),
                    evidence={"write_mb": total_write / (1024 * 1024)},
                    suggestion="Writes during startup can be slow. Defer logging, cache writes, or use async I/O.",
                )
            )

        return bottlenecks

    def _analyze_timeline(self, timeline: dict) -> list[Bottleneck]:
        """Analyze startup timeline for delays."""
        bottlenecks = []

        time_to_window = timeline.get("time_to_window")
        time_to_idle = timeline.get("time_to_idle")
        time_to_first_cpu = timeline.get("time_to_first_cpu")

        if time_to_window and time_to_window > 10:
            bottlenecks.append(
                Bottleneck(
                    category="timeline",
                    description=f"Slow time to window: {time_to_window:.2f}s",
                    severity=min(time_to_window / 30, 1.0),
                    evidence={"time_to_window": time_to_window},
                    suggestion="Main window creation is delayed. Check for synchronous operations in UI initialization. "
                    "Consider showing splash screen or loading indicator earlier.",
                )
            )

        if time_to_idle and time_to_idle > 20:
            bottlenecks.append(
                Bottleneck(
                    category="timeline",
                    description=f"Long time to idle: {time_to_idle:.2f}s",
                    severity=min(time_to_idle / 60, 1.0),
                    evidence={"time_to_idle": time_to_idle},
                    suggestion="Application takes long to settle. Background tasks may be blocking. "
                    "Move non-critical work to background threads.",
                )
            )

        if time_to_first_cpu and time_to_first_cpu > 2:
            bottlenecks.append(
                Bottleneck(
                    category="timeline",
                    description=f"Slow process initialization: {time_to_first_cpu:.2f}s before first CPU activity",
                    severity=min(time_to_first_cpu / 10, 1.0),
                    evidence={"time_to_first_cpu": time_to_first_cpu},
                    suggestion="Process startup overhead is high. Check for heavy dynamic linking, "
                    "large binary size, or slow loader.",
                )
            )

        return bottlenecks

    def _analyze_platform_specific(
        self,
        app: Application,
        metrics: list[ProcessMetrics],
    ) -> list[Bottleneck]:
        """Platform-specific bottleneck analysis."""
        bottlenecks = []

        platform = self.backend.platform

        if platform.value == "macos":
            bottlenecks.extend(self._analyze_macos(app, metrics))
        elif platform.value == "linux":
            bottlenecks.extend(self._analyze_linux(app, metrics))
        elif platform.value == "windows":
            bottlenecks.extend(self._analyze_windows(app, metrics))

        return bottlenecks

    def _analyze_macos(self, app: Application, metrics: list[ProcessMetrics]) -> list[Bottleneck]:
        """macOS-specific analysis."""
        bottlenecks = []

        # Check for dyld loading time (would need dtrace/instruments for details)
        if app.app_type.value == "native":
            bottlenecks.append(
                Bottleneck(
                    category="library",
                    description="Consider checking dyld shared cache and library loading times with instruments",
                    severity=0.3,
                    evidence={},
                    suggestion="Run: instruments -t \"Time Profiler\" <app>. Use dyld stats for library loading analysis.",
                )
            )

        return bottlenecks

    def _analyze_linux(self, app: Application, metrics: list[ProcessMetrics]) -> list[Bottleneck]:
        """Linux-specific analysis."""
        bottlenecks = []

        # Check for preload/prelink opportunities
        if app.app_type.value == "native":
            bottlenecks.append(
                Bottleneck(
                    category="library",
                    description="Consider using preload or systemd-analyze for library loading optimization",
                    severity=0.3,
                    evidence={},
                    suggestion="Run: systemd-analyze blame. Consider installing preload daemon for adaptive prefetching.",
                )
            )

        return bottlenecks

    def _analyze_windows(self, app: Application, metrics: list[ProcessMetrics]) -> list[Bottleneck]:
        """Windows-specific analysis."""
        bottlenecks = []

        bottlenecks.append(
            Bottleneck(
                category="system",
                description="Consider Windows Prefetcher and SuperFetch for startup optimization",
                severity=0.3,
                evidence={},
                suggestion="Run: winsat formal. Check prefetcher layout in C:\\Windows\\Prefetch. "
                "Use WPR (Windows Performance Recorder) for detailed analysis.",
            )
        )

        return bottlenecks


def run_external_profiler(app: Application, backend, output_dir: Path) -> dict:
    """Run platform-specific external profilers for deeper analysis."""
    results = {}
    platform = backend.platform

    if platform.value == "macos":
        # Could use instruments, dtrace, sample
        pass
    elif platform.value == "linux":
        # Could use perf, strace, valgrind
        pass
    elif platform.value == "windows":
        # Could use WPR, xperf, ETW
        pass

    return results