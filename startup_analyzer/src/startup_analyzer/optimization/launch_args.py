"""Launch argument optimizations."""

from __future__ import annotations

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
    pass


class LaunchArgumentOptimization(BaseOptimization):
    """Add/remove launch arguments for faster startup."""

    # Known fast-start flags per app type
    FAST_START_FLAGS = {
        AppType.ELECTRON: [
            "--disable-gpu",
            "--disable-gpu-compositing",
            "--disable-software-rasterizer",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-default-apps",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-component-update",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-ipc-flooding-protection",
        ],
        AppType.CHROMIUM: [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-extensions",
            "--no-first-run",
            "--disable-default-apps",
        ],
        AppType.JAVA: [
            "-Xverify:none",
            "-XX:+TieredCompilation",
            "-XX:TieredStopAtLevel=1",
            "-XX:+UseSerialGC",
            "-Xms64m",
            "-Xmx512m",
        ],
        AppType.DOTNET: [
            "--roll-forward",
            "LatestMajor",
        ],
        AppType.PYTHON: [
            "-O",  # Optimize
            "-B",  # Don't write bytecode
            "-S",  # Don't import site
        ],
    }

    # Flags to remove (known to slow startup)
    SLOW_FLAGS = {
        AppType.ELECTRON: [
            "--enable-logging",
            "--enable-gpu-benchmarking",
            "--enable-features",
            "--force-fieldtrials",
        ],
        AppType.JAVA: [
            "-Xdebug",
            "-Xrunjdwp",
            "-agentlib:jdwp",
        ],
    }

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return ctx.app.app_type in self.FAST_START_FLAGS

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            add_flags = self.FAST_START_FLAGS.get(ctx.app.app_type, [])
            remove_flags = self.SLOW_FLAGS.get(ctx.app.app_type, [])
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"[DRY RUN] Would add {len(add_flags)} flags, remove {len(remove_flags)} flags",
                revert_info={
                    "action": "launch_args",
                    "add_flags": add_flags,
                    "remove_flags": remove_flags,
                    "original_args": list(ctx.app.arguments),
                    "dry_run": True,
                },
            )

        original_args = list(ctx.app.arguments)
        add_flags = self.FAST_START_FLAGS.get(ctx.app.app_type, [])
        remove_flags = self.SLOW_FLAGS.get(ctx.app.app_type, [])

        # Remove slow flags
        new_args = [arg for arg in ctx.app.arguments if arg not in remove_flags]

        # Add fast flags (avoid duplicates)
        for flag in add_flags:
            if flag not in new_args:
                new_args.append(flag)

        ctx.app.arguments = new_args

        return OptimizationResult(
            optimization=self.definition,
            success=True,
            message=f"Modified launch arguments: added {len(add_flags)}, removed {len(remove_flags)}",
            revert_info={
                "action": "launch_args",
                "original_args": original_args,
                "added_flags": add_flags,
                "removed_flags": remove_flags,
            },
        )

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        original_args = revert_info.get("original_args", [])
        ctx.app.arguments = original_args
        return True


class DisableAutoUpdateOptimization(BaseOptimization):
    """Disable auto-update checks during startup."""

    # Known auto-update flags to disable
    UPDATE_DISABLE_FLAGS = {
        AppType.ELECTRON: ["--disable-component-update", "--disable-background-networking"],
        AppType.CHROMIUM: ["--disable-component-update", "--disable-background-networking"],
        AppType.NATIVE: [],  # App-specific
    }

    # Environment variables that disable updates
    UPDATE_DISABLE_ENVS = {
        "AUTO_UPDATE": "0",
        "DISABLE_AUTO_UPDATE": "1",
        "NO_AUTO_UPDATE": "1",
        "UPDATE_DISABLED": "1",
        # App-specific
        "ELECTRON_AUTO_UPDATE": "0",
        "NWJS_AUTO_UPDATE": "0",
    }

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return True

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            flags = self.UPDATE_DISABLE_FLAGS.get(ctx.app.app_type, [])
            envs = self.UPDATE_DISABLE_ENVS
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"[DRY RUN] Would add {len(flags)} flags and {len(envs)} env vars to disable auto-updates",
                revert_info={"action": "disable_autoupdate", "flags": flags, "envs": list(envs.keys()), "dry_run": True},
            )

        applied_flags = []
        applied_envs = {}

        # Add flags
        flags = self.UPDATE_DISABLE_FLAGS.get(ctx.app.app_type, [])
        for flag in flags:
            if flag not in ctx.app.arguments:
                ctx.app.arguments.append(flag)
                applied_flags.append(flag)

        # Add env vars
        for var, value in self.UPDATE_DISABLE_ENVS.items():
            if var not in ctx.app.env_vars:
                ctx.app.env_vars[var] = value
                applied_envs[var] = value

        return OptimizationResult(
            optimization=self.definition,
            success=True,
            message=f"Disabled auto-update: {len(applied_flags)} flags, {len(applied_envs)} env vars",
            revert_info={
                "action": "disable_autoupdate",
                "applied_flags": applied_flags,
                "applied_envs": list(applied_envs.keys()),
            },
        )

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        for flag in revert_info.get("applied_flags", []):
            if flag in ctx.app.arguments:
                ctx.app.arguments.remove(flag)
        for var in revert_info.get("applied_envs", []):
            ctx.app.env_vars.pop(var, None)
        return True


class SplashScreenOptimization(BaseOptimization):
    """Enable/disable splash screen for faster perceived startup."""

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return ctx.app.app_type in (AppType.ELECTRON, AppType.JAVA, AppType.DOTNET, AppType.NATIVE)

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message="[DRY RUN] Would configure splash screen settings",
                revert_info={"action": "splash_screen", "dry_run": True},
            )

        # This is app-specific - just set common env vars
        applied = {}
        splash_vars = {
            "SHOW_SPLASH": "1",
            "SPLASH_SCREEN": "1",
            "JAVA_SPLASH": "1",
        }

        for var, value in splash_vars.items():
            if var not in ctx.app.env_vars:
                ctx.app.env_vars[var] = value
                applied[var] = value

        return OptimizationResult(
            optimization=self.definition,
            success=True,
            message=f"Configured splash screen: {len(applied)} env vars",
            revert_info={"action": "splash_screen", "applied_envs": list(applied.keys())},
        )

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        for var in revert_info.get("applied_envs", []):
            ctx.app.env_vars.pop(var, None)
        return True


# Register
from startup_analyzer.optimization.registry import registry

registry.register(
    LaunchArgumentOptimization,
    Optimization(
        name="launch-args",
        description="Add fast-start flags and remove known slow flags from launch arguments",
        risk=OptimizationRisk.MEDIUM,
        applies_to=[AppType.ELECTRON, AppType.CHROMIUM, AppType.JAVA, AppType.DOTNET, AppType.PYTHON],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)
registry.register(
    DisableAutoUpdateOptimization,
    Optimization(
        name="disable-autoupdate",
        description="Disable auto-update checks during startup via flags and env vars",
        risk=OptimizationRisk.LOW,
        applies_to=[AppType.UNKNOWN],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)
registry.register(
    SplashScreenOptimization,
    Optimization(
        name="splash-screen",
        description="Configure splash screen settings for faster perceived startup",
        risk=OptimizationRisk.LOW,
        applies_to=[AppType.ELECTRON, AppType.JAVA, AppType.DOTNET, AppType.NATIVE],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)