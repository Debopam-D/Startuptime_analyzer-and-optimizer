"""Platform abstraction layer for cross-platform operations."""

from __future__ import annotations

import abc
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import Application, Platform


class PlatformBackend(abc.ABC):
    """Abstract base class for platform-specific operations."""

    @property
    @abc.abstractmethod
    def platform(self) -> Platform:
        """Return the platform this backend supports."""

    @abc.abstractmethod
    def discover_applications(self) -> list[Application]:
        """Discover installed applications."""

    @abc.abstractmethod
    def find_application(self, name: str) -> Application | None:
        """Find an application by name or path."""

    @abc.abstractmethod
    def launch_application(self, app: Application) -> subprocess.Popen:
        """Launch an application and return the process handle."""

    @abc.abstractmethod
    def get_process_metrics(self, pid: int) -> dict | None:
        """Get current metrics for a process."""

    @abc.abstractmethod
    def wait_for_window(self, pid: int, timeout: float) -> bool:
        """Wait for the main window to become visible."""

    @abc.abstractmethod
    def wait_for_idle(self, pid: int, cpu_threshold: float, duration: float, timeout: float) -> bool:
        """Wait for process to become idle (low CPU for sustained period)."""

    @abc.abstractmethod
    def get_app_type(self, app: Application) -> str:
        """Detect the application type."""

    @abc.abstractmethod
    def get_app_version(self, app: Application) -> str | None:
        """Get application version."""

    @abc.abstractmethod
    def apply_optimization(self, optimization_name: str, app: Application) -> dict:
        """Apply a platform-specific optimization."""

    @abc.abstractmethod
    def revert_optimization(self, optimization_name: str, app: Application, revert_info: dict) -> bool:
        """Revert a platform-specific optimization."""

    @abc.abstractmethod
    def get_system_info(self) -> dict:
        """Get system information for reports."""


def get_platform_backend() -> PlatformBackend:
    """Get the platform backend for the current system."""
    platform = sys.platform

    if platform == "darwin":
        from startup_analyzer.platform.macos import MacOSBackend

        return MacOSBackend()
    if platform == "linux":
        from startup_analyzer.platform.linux import LinuxBackend

        return LinuxBackend()
    if platform == "win32":
        from startup_analyzer.platform.windows import WindowsBackend

        return WindowsBackend()
    raise RuntimeError(f"Unsupported platform: {platform}")


def get_current_platform() -> Platform:
    """Get the current platform enum."""
    platform = sys.platform
    if platform == "darwin":
        from startup_analyzer.core.metrics import Platform

        return Platform.MACOS
    if platform == "linux":
        from startup_analyzer.core.metrics import Platform

        return Platform.LINUX
    if platform == "win32":
        from startup_analyzer.core.metrics import Platform

        return Platform.WINDOWS
    raise RuntimeError(f"Unsupported platform: {platform}")