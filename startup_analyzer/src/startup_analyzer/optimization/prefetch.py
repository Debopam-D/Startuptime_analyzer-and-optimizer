"""Prefetch and cache warming optimizations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from startup_analyzer.core.metrics import (
    AppType,
    Optimization,
    OptimizationResult,
    OptimizationRisk,
    Platform,
)
from startup_analyzer.optimization.registry import BaseOptimization, OptimizationContext

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import Application


class PrefetchLibrariesOptimization(BaseOptimization):
    """Pre-load commonly used libraries into filesystem cache."""

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return ctx.app.app_type in (AppType.NATIVE, AppType.ELECTRON, AppType.JAVA, AppType.DOTNET)

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message="[DRY RUN] Would preload libraries into cache",
                revert_info={"action": "prefetch", "dry_run": True},
            )

        revert_info = {"action": "prefetch", "files_warmed": []}

        try:
            # Platform-specific prefetch
            if ctx.platform == Platform.MACOS:
                self._prefetch_macos(ctx.app, revert_info)
            elif ctx.platform == Platform.LINUX:
                self._prefetch_linux(ctx.app, revert_info)
            elif ctx.platform == Platform.WINDOWS:
                self._prefetch_windows(ctx.app, revert_info)

            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"Warmed cache for {len(revert_info['files_warmed'])} files",
                revert_info=revert_info,
            )
        except Exception as e:
            return OptimizationResult(
                optimization=self.definition,
                success=False,
                message=f"Prefetch failed: {e}",
                revert_info=revert_info,
            )

    def _prefetch_macos(self, app: Application, revert_info: dict) -> None:
        """Use vmtouch or manual read to warm cache on macOS."""
        # Find library directories
        lib_dirs = []
        if app.executable.suffix == ".app" or app.executable.parent.name == "MacOS":
            # .app bundle
            lib_dirs.append(app.executable.parent.parent / "Frameworks")
            lib_dirs.append(app.executable.parent.parent / "Resources")
        else:
            # Regular executable - check for libs nearby
            lib_dirs.append(app.executable.parent / "lib")
            lib_dirs.append(app.executable.parent / "libs")

        # Also check system library paths
        lib_dirs.extend([
            Path("/usr/local/lib"),
            Path("/opt/homebrew/lib"),
        ])

        for lib_dir in lib_dirs:
            if lib_dir.exists():
                for lib_file in lib_dir.rglob("*.dylib"):
                    try:
                        # Read file into cache
                        with open(lib_file, "rb") as f:
                            f.read(1024 * 1024)  # Read first 1MB
                        revert_info["files_warmed"].append(str(lib_file))
                    except Exception:
                        continue

        # Use vmtouch if available
        try:
            subprocess.run(["vmtouch", "-t", str(app.executable)], capture_output=True, timeout=30)
        except Exception:
            pass

    def _prefetch_linux(self, app: Application, revert_info: dict) -> None:
        """Use vmtouch, preload, or readahead on Linux."""
        lib_dirs = [
            Path("/usr/lib"),
            Path("/usr/local/lib"),
            Path("/lib"),
            Path("/lib64"),
        ]

        # App-specific libs
        if app.executable.parent.name == "lib":
            lib_dirs.append(app.executable.parent)

        for lib_dir in lib_dirs:
            if lib_dir.exists():
                for lib_file in lib_dir.rglob("*.so*"):
                    try:
                        with open(lib_file, "rb") as f:
                            f.read(1024 * 1024)
                        revert_info["files_warmed"].append(str(lib_file))
                    except Exception:
                        continue

        # Use readahead if available
        try:
            subprocess.run(["readahead", "-p", str(app.executable)], capture_output=True, timeout=30)
        except Exception:
            pass

    def _prefetch_windows(self, app: Application, revert_info: dict) -> None:
        """Use Windows prefetcher or manual caching."""
        # Windows has built-in prefetcher, but we can trigger it
        try:
            # Touch the executable and its directory to encourage prefetching
            for root, dirs, files in os.walk(app.executable.parent):
                for f in files[:20]:  # Limit to avoid too many
                    if f.endswith((".dll", ".exe")):
                        filepath = Path(root) / f
                        try:
                            with open(filepath, "rb") as fp:
                                fp.read(64 * 1024)
                            revert_info["files_warmed"].append(str(filepath))
                        except Exception:
                            continue
        except Exception:
            pass

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        # Prefetch doesn't need explicit revert - cache will naturally evict
        return True


class WarmCacheOptimization(BaseOptimization):
    """Warm the application's data/cache directories."""

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return True  # Applicable to all apps

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message="[DRY RUN] Would warm application cache directories",
                revert_info={"action": "warm_cache", "dry_run": True},
            )

        revert_info = {"action": "warm_cache", "dirs_warmed": []}

        try:
            # Common cache directories per platform
            cache_dirs = self._get_cache_dirs(ctx.app, ctx.platform)

            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    self._warm_directory(cache_dir, revert_info)

            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"Warmed {len(revert_info['dirs_warmed'])} cache directories",
                revert_info=revert_info,
            )
        except Exception as e:
            return OptimizationResult(
                optimization=self.definition,
                success=False,
                message=f"Cache warming failed: {e}",
                revert_info=revert_info,
            )

    def _get_cache_dirs(self, app: Application, platform: Platform) -> list[Path]:
        """Get platform-specific cache directories for an app."""
        dirs = []

        if platform == Platform.MACOS:
            dirs.extend([
                Path.home() / "Library" / "Caches" / (app.bundle_id or app.name),
                Path.home() / "Library" / "Application Support" / (app.bundle_id or app.name),
            ])
        elif platform == Platform.LINUX:
            dirs.extend([
                Path.home() / ".cache" / app.name.lower(),
                Path.home() / ".config" / app.name.lower(),
                Path("/var/cache") / app.name.lower(),
            ])
        elif platform == Platform.WINDOWS:
            local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
            if local_app_data:
                dirs.append(local_app_data / app.name)
            app_data = Path(os.environ.get("APPDATA", ""))
            if app_data:
                dirs.append(app_data / app.name)

        return [d for d in dirs if d.exists()]

    def _warm_directory(self, dir_path: Path, revert_info: dict) -> None:
        """Read files in directory into cache."""
        try:
            for f in dir_path.rglob("*"):
                if f.is_file() and f.stat().st_size < 10 * 1024 * 1024:  # Skip large files
                    try:
                        with open(f, "rb") as fp:
                            fp.read(min(f.stat().st_size, 1024 * 1024))
                    except Exception:
                        continue
            revert_info["dirs_warmed"].append(str(dir_path))
        except Exception:
            pass

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        return True


# Register optimizations
from startup_analyzer.optimization.registry import registry

registry.register(
    PrefetchLibrariesOptimization,
    Optimization(
        name="prefetch-libraries",
        description="Pre-load commonly used libraries into the filesystem cache for faster startup",
        risk=OptimizationRisk.LOW,
        applies_to=[AppType.NATIVE, AppType.ELECTRON, AppType.JAVA, AppType.DOTNET, AppType.UNKNOWN],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)
registry.register(
    WarmCacheOptimization,
    Optimization(
        name="warm-cache",
        description="Warm the application's data/cache directories into the filesystem cache",
        risk=OptimizationRisk.LOW,
        applies_to=[AppType.UNKNOWN],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)