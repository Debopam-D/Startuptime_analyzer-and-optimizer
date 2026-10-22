"""
Example usage script for Startup Analyzer.

This script demonstrates how to use the Startup Analyzer library
programmatically to measure, analyze, and optimize application startup performance.
"""

import asyncio
from pathlib import Path

from startup_analyzer.core import create_analyzer, AnalyzerConfig
from startup_analyzer.core.metrics import MeasurementMode
from startup_analyzer.optimization.registry import registry
from startup_analyzer.platform.base import get_platform_backend
async def example_usage():
    """Example usage of the Startup Analyzer."""
    print("🚀 Startup Analyzer Example Usage")
    print("=" * 50)

    # Create analyzer with custom configuration
    config = AnalyzerConfig(
        iterations=3,
        cooldown=2.0,
        dry_run=False,  # Set to True for dry-run testing
    )
    analyzer = create_analyzer(config)

    print(f"📊 Platform: {analyzer.backend.platform.value}")
    print(f"⚙️ Config: {config.iterations} iterations, {config.cooldown}s cooldown")
    print()

    # Example 1: List discovered applications
    print("📋 Example 1: Listing Discovered Applications")
    print("-" * 50)
    apps = analyzer.list_applications()
    print(f"Found {len(apps)} applications:")
    for app in apps[:5]:  # Show first 5
        print(f"  - {app.name} ({app.app_type.value}) on {app.platform.value}")
    print()

    # Example 2: Measure startup performance
    if apps:
        target_app = apps[0]  # Use first discovered app
        print(f"📈 Example 2: Measuring {target_app.name} Startup Performance")
        print("-" * 50)

        measurement_set = analyzer.measure_startup(target_app, mode=MeasurementMode.WARM)
        print(f"Completed {len(measurement_set.measurements)} measurements")
        print(f"Successful measurements: {len(measurement_set.successful_measurements)}")

        # Print summary statistics
        stats = measurement_set.get_statistics("time_to_window")
        if stats:
            print(f"Average time to window: {stats['mean']:.2f}s")
            print(f"Median time to window: {stats['median']:.2f}s")
        print()

        # Example 3: Analyze bottlenecks
        if measurement_set.successful_measurements:
            measurement = measurement_set.successful_measurements[0]
            bottlenecks = analyzer.analyze_bottlenecks(target_app, measurement)
            print(f"🔍 Example 3: Bottleneck Analysis for {target_app.name}")
            print("-" * 50)
            print(f"Found {len(bottlenecks)} potential bottlenecks:")
            for i, bottleneck in enumerate(bottlenecks[:3]):  # Show first 3
                print(f"  {i + 1}. [{bottleneck.category.upper()}] {bottleneck.severity:.0%} - {bottleneck.description}")
                print(f"     Suggestion: {bottleneck.suggestion}")
            print()

        # Example 4: Apply optimizations
        print("⚡ Example 4: Applying Optimizations")
        print("-" * 50)
        applicable_opts = analyzer.get_applicable_optimizations(target_app)
        print(f"Available optimizations: {len(applicable_opts)}")

        # Try applying a few common optimizations
        test_optimizations = ["disable-telemetry", "launch-args", "prefetch-libraries"]
        applied_results = []

        for opt_name in test_optimizations:
            if opt_name in registry.get_all():
                # For demonstration, we'll just show what would be applied
                print(f"  Would apply '{opt_name}' optimization...")
                # In a real scenario: result = analyzer.apply_optimizations(target_app, [opt_name])
        print()

        # Example 5: Run full analysis with optimizations
        print("📊 Example 5: Full Analysis with Optimizations")
        print("-" * 50)
        print("This would run:")
        print("  1. Baseline measurement")
        print("  2. Apply selected optimizations")
        print("  3. Measure optimized performance")
        print("  4. Generate comparison report")
        print()

    # Example 6: Work with optimization registry
    print("🎯 Example 6: Exploring Available Optimizations")
    print("-" * 50)
    all_optimizations = registry.get_all()
    print(f"Total registered optimizations: {len(all_optimizations)}")
    print("Sample optimizations:")
    for i, (name, opt_class) in enumerate(list(all_optimizations.items())[:5]):
        print(f"  {i + 1}. {name} - {opt_class.__doc__ or 'No description'}")
    print()

    # Example 7: Compare measurements
    if apps and len(apps) > 1:
        print("🔄 Example 7: Comparing Two Applications")
        print("-" * 50)
        app1, app2 = apps[0], apps[1]
        print(f"Comparing startup performance of:")
        print(f"  - {app1.name} vs {app2.name}")
        # In a real scenario, you'd measure both and generate a comparison report

    print("✅ Example usage complete!")
    print()
    print("For more examples, see:")
    print("  - README.md in the project root")
    print("  - The CLI documentation: startup-analyzer --help")
if __name__ == "__main__":
    asyncio.run(example_usage())