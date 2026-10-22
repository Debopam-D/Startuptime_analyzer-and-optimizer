"""Resource monitoring during startup."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import ProcessMetrics
    from startup_analyzer.platform.base import PlatformBackend


@dataclass
class MonitoringConfig:
    """Configuration for resource monitoring."""

    interval: float = 0.1  # Sampling interval in seconds
    track_io: bool = True
    track_threads: bool = True
    track_fds: bool = True


class ResourceMonitor:
    """Monitors CPU, memory, I/O, and other resources during startup."""

    def __init__(self, backend: PlatformBackend, config: MonitoringConfig | None = None):
        self.backend = backend
        self.config = config or MonitoringConfig()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._metrics: list[ProcessMetrics] = []
        self._callbacks: list[Callable[[ProcessMetrics], None]] = []
        self._pid: int | None = None

    def start(self, pid: int) -> None:
        """Start monitoring a process."""
        self._pid = pid
        self._stop_event.clear()
        self._metrics.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> list[ProcessMetrics]:
        """Stop monitoring and return collected metrics."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        return self._metrics.copy()

    def add_callback(self, callback: Callable[[ProcessMetrics], None]) -> None:
        """Add a callback for real-time metric updates."""
        self._callbacks.append(callback)

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        if self._pid is None:
            return

        while not self._stop_event.is_set():
            metrics = self.backend.get_process_metrics(self._pid)
            if metrics is None:
                # Process ended
                break

            from startup_analyzer.core.metrics import ProcessMetrics

            pm = ProcessMetrics(
                timestamp=time.perf_counter(),
                cpu_percent=metrics["cpu_percent"],
                memory_rss=metrics["memory_rss"],
                memory_vms=metrics["memory_vms"],
                num_threads=metrics["num_threads"],
                num_fds=metrics.get("num_fds"),
                read_bytes=metrics.get("read_bytes", 0),
                write_bytes=metrics.get("write_bytes", 0),
            )

            self._metrics.append(pm)

            for callback in self._callbacks:
                try:
                    callback(pm)
                except Exception:
                    pass

            time.sleep(self.config.interval)

    def get_summary(self) -> dict:
        """Get summary statistics from collected metrics."""
        if not self._metrics:
            return {}

        cpu_values = [m.cpu_percent for m in self._metrics]
        mem_values = [m.memory_rss for m in self._metrics]
        thread_values = [m.num_threads for m in self._metrics]

        return {
            "cpu": {
                "peak": max(cpu_values),
                "avg": sum(cpu_values) / len(cpu_values),
                "samples": len(cpu_values),
            },
            "memory_rss": {
                "peak": max(mem_values),
                "avg": sum(mem_values) / len(mem_values),
            },
            "threads": {
                "peak": max(thread_values),
                "avg": sum(thread_values) / len(thread_values),
            },
            "duration": self._metrics[-1].timestamp - self._metrics[0].timestamp if len(self._metrics) > 1 else 0,
        }