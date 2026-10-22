"""Main analyzer orchestration logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from startup_analyzer.core.metrics import MeasurementMode

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import (
        Application,
        ComparisonReport,
        Measurement,
        MeasurementSet,
        Optimization,
        OptimizationResult,
    )
    from startup_analyzer.measurement.profiler import Bottleneck, StartupProfiler
    from startup_analyzer.measurement.timer import StartupTimer
    from startup_analyzer.optimization.registry import OptimizationRegistry
    from startup_analyzer.platform.base import PlatformBackend


@dataclass
class AnalyzerConfig:
    """Configuration for the analyzer."""

    iterations: int = 3
    cooldown: float = 2.0
    cpu_idle_threshold: float = 5.0
    cpu_idle_duration: float = 2.0
    window_timeout: float = 30.0
    idle_timeout: float = 60.0
    sample_interval: float = 0.1
    dry_run: bool = False


class StartupAnalyzer:
    """Main orchestrator for startup analysis and optimization."""

    def __init__(
        self,
        backend: PlatformBackend,
        timer: StartupTimer,
        profiler: StartupProfiler,
        registry: OptimizationRegistry,
        config: AnalyzerConfig | None = None,
    ):
        self.backend = backend
        self.timer = timer
        self.profiler = profiler
        self.registry = registry
        self.config = config or AnalyzerConfig()

    def find_application(self, name: str) -> Application | None:
        """Find an application by name or path."""
        return self.backend.find_application(name)

    def list_applications(self) -> list[Application]:
        """List all discovered applications."""
        return self.backend.discover_applications()

    def measure_startup(
        self,
        app: Application,
        mode: MeasurementMode = MeasurementMode.WARM,
        iterations: int | None = None,
    ) -> MeasurementSet:
        """Measure application startup performance."""
        from startup_analyzer.core.metrics import MeasurementSet

        iters = iterations or self.config.iterations
        measurements = self.timer.measure_multiple(
            app,
            mode,
            iterations=iters,
            cooldown=self.config.cooldown,
        )

        return MeasurementSet(
            app=app,
            mode=mode,
            measurements=measurements,
        )

    def analyze_bottlenecks(
        self,
        app: Application,
        measurement: Measurement,
    ) -> list[Bottleneck]:
        """Analyze bottlenecks from a measurement."""
        timeline = {
            "time_to_first_cpu": measurement.timeline.time_to_first_cpu,
            "time_to_window": measurement.timeline.time_to_window,
            "time_to_idle": measurement.timeline.time_to_idle,
        }
        return self.profiler.analyze(app, measurement.raw_metrics, timeline)

    def get_applicable_optimizations(self, app: Application) -> list[Optimization]:
        """Get all optimizations applicable to an application."""
        from startup_analyzer.optimization.registry import OptimizationContext

        ctx = OptimizationContext(
            app=app,
            platform=self.backend.platform,
            dry_run=True,
        )

        applicable = []
        for name in self.registry.get_all():
            definition = self.registry.get_definition(name)
            instance = self.registry.create_instance(name)
            if definition is not None and instance is not None and instance.can_apply(ctx):
                applicable.append(definition)
        return applicable

    def apply_optimizations(
        self,
        app: Application,
        optimization_names: list[str],
        dry_run: bool = False,
    ) -> list[OptimizationResult]:
        """Apply selected optimizations to an application."""
        from startup_analyzer.optimization.registry import OptimizationContext

        ctx = OptimizationContext(
            app=app,
            platform=self.backend.platform,
            dry_run=dry_run or self.config.dry_run,
        )

        results = []
        for name in optimization_names:
            opt_instance = self.registry.create_instance(name, self._get_definition(name))
            if opt_instance:
                if opt_instance.can_apply(ctx):
                    result = opt_instance.apply(ctx)
                    results.append(result)
                else:
                    from startup_analyzer.core.metrics import Optimization, OptimizationResult

                    # Create a dummy definition for the error result
                    dummy_def = Optimization(
                        name=name,
                        description="Not applicable",
                        risk="low",
                    )
                    results.append(OptimizationResult(
                        optimization=dummy_def,
                        success=False,
                        message="Optimization not applicable to this application",
                    ))
            else:
                from startup_analyzer.core.metrics import Optimization, OptimizationResult

                dummy_def = Optimization(
                    name=name,
                    description="Unknown optimization",
                    risk="low",
                )
                results.append(OptimizationResult(
                    optimization=dummy_def,
                    success=False,
                    message=f"Unknown optimization: {name}",
                ))

        return results

    def _get_definition(self, name: str) -> Optimization | None:
        """Get optimization definition by name."""
        return self.registry.get_definition(name)

    def run_full_analysis(
        self,
        app: Application,
        optimization_names: list[str] | None = None,
        mode: MeasurementMode = MeasurementMode.WARM,
    ) -> ComparisonReport:
        """Run complete analysis: baseline -> optimize -> compare."""
        from startup_analyzer.core.metrics import ComparisonReport

        self._print_step("Measuring baseline performance...")
        baseline = self.measure_startup(app, mode)

        # Apply optimizations
        if optimization_names:
            self._print_step(f"Applying {len(optimization_names)} optimizations...")
            opt_results = self.apply_optimizations(app, optimization_names)
        else:
            opt_results = []

        self._print_step("Measuring optimized performance...")
        optimized = self.measure_startup(app, mode)

        # Generate comparison report
        report = ComparisonReport(
            app=app,
            baseline=baseline,
            optimized=optimized,
            optimizations_applied=opt_results,
        )

        return report

    def _print_step(self, message: str) -> None:
        """Print a step message."""
        print(f"\n{'='*60}")
        print(f"  {message}")
        print(f"{'='*60}\n")


def create_analyzer(config: AnalyzerConfig | None = None) -> StartupAnalyzer:
    """Factory function to create a fully configured analyzer."""
    from startup_analyzer.measurement.profiler import StartupProfiler
    from startup_analyzer.measurement.timer import StartupTimer, TimerConfig
    from startup_analyzer.optimization.registry import registry
    from startup_analyzer.platform.base import get_platform_backend

    backend = get_platform_backend()

    timer_config = TimerConfig(
        cpu_idle_threshold=config.cpu_idle_threshold if config else 5.0,
        cpu_idle_duration=config.cpu_idle_duration if config else 2.0,
        window_timeout=config.window_timeout if config else 30.0,
        idle_timeout=config.idle_timeout if config else 60.0,
        sample_interval=config.sample_interval if config else 0.1,
    )

    timer = StartupTimer(backend, timer_config)
    profiler = StartupProfiler(backend)

    analyzer_config = config or AnalyzerConfig()
    analyzer = StartupAnalyzer(backend, timer, profiler, registry, analyzer_config)

    return analyzer