"""Environment variable optimizations."""

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


class DisableTelemetryOptimization(BaseOptimization):
    """Disable common telemetry/analytics environment variables."""

    # Known telemetry environment variables
    TELEMETRY_VARS = {
        # General
        "DO_NOT_TRACK": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_METRICS": "1",
        "NO_TELEMETRY": "1",
        "OPT_OUT": "1",
        # Node.js / Electron
        "NEXT_TELEMETRY_DISABLED": "1",
        "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false",
        "ELECTRON_DISABLE_TELEMETRY": "1",
        # Python
        "PYTHON_NO_TELEMETRY": "1",
        "PYTHON_INSPECT": "0",
        # .NET
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_TELEMETRY_OPTOUT": "1",
        # Java
        "JAVA_TOOL_OPTIONS": "-Ddisable.telemetry=true",
        # Go
        "GO_TELEMETRY": "off",
        # Rust
        "RUSTUP_TELEMETRY": "0",
        # Various CLIs
        "GATSBY_TELEMETRY_DISABLED": "1",
        "HINT_TELEMETRY": "0",
        "STRIPE_CLI_TELEMETRY": "0",
        "VERCEL_TELEMETRY_DISABLED": "1",
        "NETLIFY_TELEMETRY_DISABLED": "1",
    }

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return True

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"[DRY RUN] Would set {len(self.TELEMETRY_VARS)} telemetry env vars",
                revert_info={"action": "disable_telemetry", "vars": list(self.TELEMETRY_VARS.keys()), "dry_run": True},
            )

        # Apply to app's env_vars
        applied = {}
        for var, value in self.TELEMETRY_VARS.items():
            if var not in ctx.app.env_vars:  # Don't override user-set values
                ctx.app.env_vars[var] = value
                applied[var] = value

        return OptimizationResult(
            optimization=self.definition,
            success=True,
            message=f"Applied {len(applied)} telemetry-disabling environment variables",
            revert_info={"action": "disable_telemetry", "vars_applied": list(applied.keys())},
        )

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        vars_applied = revert_info.get("vars_applied", [])
        for var in vars_applied:
            ctx.app.env_vars.pop(var, None)
        return True


class RuntimeOptimizationFlags(BaseOptimization):
    """Set runtime-specific optimization flags."""

    # Per-runtime optimization flags
    RUNTIME_FLAGS = {
        AppType.PYTHON: {
            "PYTHONOPTIMIZE": "2",  # Enable optimizations, remove asserts/docstrings
            "PYTHONDONTWRITEBYTECODE": "1",  # Don't write .pyc files
            "PYTHONUNBUFFERED": "1",  # Unbuffered I/O
        },
        AppType.NODE: {
            "NODE_OPTIONS": "--optimize-for-size --no-warnings",
            "UV_THREADPOOL_SIZE": "4",
        },
        AppType.JAVA: {
            "JAVA_TOOL_OPTIONS": "-XX:+TieredCompilation -XX:TieredStopAtLevel=1 -Xverify:none",
            "_JAVA_OPTIONS": "-XX:+UseSerialGC -Xms64m -Xmx512m",
        },
        AppType.DOTNET: {
            "DOTNET_ReadyToRun": "1",
            "DOTNET_TieredCompilation": "1",
            "DOTNET_TieredPGO": "1",
            "COMPlus_TieredCompilation": "1",
        },
        AppType.GO: {
            "GOMEMLIMIT": "512MiB",
            "GOGC": "100",
        },
        AppType.RUST: {
            "RUST_BACKTRACE": "0",
        },
    }

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return ctx.app.app_type in self.RUNTIME_FLAGS

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            flags = self.RUNTIME_FLAGS.get(ctx.app.app_type, {})
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"[DRY RUN] Would set {len(flags)} runtime optimization flags",
                revert_info={"action": "runtime_flags", "flags": list(flags.keys()), "dry_run": True},
            )

        flags = self.RUNTIME_FLAGS.get(ctx.app.app_type, {})
        applied = {}

        for var, value in flags.items():
            if var not in ctx.app.env_vars:
                ctx.app.env_vars[var] = value
                applied[var] = value

        return OptimizationResult(
            optimization=self.definition,
            success=True,
            message=f"Applied {len(applied)} runtime optimization flags for {ctx.app.app_type.value}",
            revert_info={"action": "runtime_flags", "flags_applied": list(applied.keys())},
        )

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        flags_applied = revert_info.get("flags_applied", [])
        for var in flags_applied:
            ctx.app.env_vars.pop(var, None)
        return True


class ElectronOptimizationFlags(BaseOptimization):
    """Electron-specific optimization flags."""

    ELECTRON_FLAGS = {
        "ELECTRON_DISABLE_GPU": "1",
        "ELECTRON_DISABLE_SANDBOX": "1",
        "ELECTRON_NO_ASAR": "1",
        "ELECTRON_RUN_AS_NODE": "0",
    }

    def __init__(self, definition: Optimization):
        super().__init__(definition)

    def can_apply(self, ctx: OptimizationContext) -> bool:
        return ctx.app.app_type == AppType.ELECTRON

    def apply(self, ctx: OptimizationContext) -> OptimizationResult:
        if ctx.dry_run:
            return OptimizationResult(
                optimization=self.definition,
                success=True,
                message=f"[DRY RUN] Would set {len(self.ELECTRON_FLAGS)} Electron optimization flags",
                revert_info={"action": "electron_flags", "flags": list(self.ELECTRON_FLAGS.keys()), "dry_run": True},
            )

        applied = {}
        for var, value in self.ELECTRON_FLAGS.items():
            if var not in ctx.app.env_vars:
                ctx.app.env_vars[var] = value
                applied[var] = value

        return OptimizationResult(
            optimization=self.definition,
            success=True,
            message=f"Applied {len(applied)} Electron optimization flags",
            revert_info={"action": "electron_flags", "flags_applied": list(applied.keys())},
        )

    def revert(self, ctx: OptimizationContext, revert_info: dict) -> bool:
        flags_applied = revert_info.get("flags_applied", [])
        for var in flags_applied:
            ctx.app.env_vars.pop(var, None)
        return True


# Register
from startup_analyzer.optimization.registry import registry

registry.register(
    DisableTelemetryOptimization,
    Optimization(
        name="disable-telemetry",
        description="Set environment variables to disable common telemetry/analytics that can block startup",
        risk=OptimizationRisk.LOW,
        applies_to=[AppType.UNKNOWN],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)
registry.register(
    RuntimeOptimizationFlags,
    Optimization(
        name="runtime-flags",
        description="Set runtime-specific optimization flags (PYTHONOPTIMIZE, NODE_OPTIONS, DOTNET_ReadyToRun, ...)",
        risk=OptimizationRisk.LOW,
        applies_to=[AppType.PYTHON, AppType.NODE, AppType.JAVA, AppType.DOTNET, AppType.GO, AppType.RUST],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)
registry.register(
    ElectronOptimizationFlags,
    Optimization(
        name="electron-flags",
        description="Set Electron-specific environment flags for faster startup",
        risk=OptimizationRisk.MEDIUM,
        applies_to=[AppType.ELECTRON],
        platforms=[Platform.MACOS, Platform.LINUX, Platform.WINDOWS],
        reversible=True,
        requires_sudo=False,
    ),
)