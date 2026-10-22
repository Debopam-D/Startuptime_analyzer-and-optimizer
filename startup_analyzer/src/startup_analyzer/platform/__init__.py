"""Platform package initialization."""

from startup_analyzer.core.metrics import Platform
from startup_analyzer.platform.base import (
    PlatformBackend,
    get_current_platform,
    get_platform_backend,
)

__all__ = ["PlatformBackend", "get_platform_backend", "get_current_platform", "Platform"]