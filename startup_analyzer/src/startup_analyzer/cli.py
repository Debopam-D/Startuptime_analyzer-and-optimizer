"""Command-line interface for startup analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from startup_analyzer.core import (
    AnalyzerConfig,
    MeasurementMode,
    ReportGenerator,
    create_analyzer,
)
from startup_analyzer.optimization.registry import registry

app = typer.Typer(
    name="startup-analyzer",
    help="Cross-platform application startup time analyzer and optimizer",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


def get_analyzer(ctx: typer.Context) -> StartupAnalyzer:
    """Get or create analyzer instance."""
    if not hasattr(ctx, "_analyzer"):
        config = AnalyzerConfig(
            iterations=ctx.obj.get("iterations", 3),
            cooldown=ctx.obj.get("cooldown", 2.0),
            cpu_idle_threshold=ctx.obj.get("cpu_threshold", 5.0),
            cpu_idle_duration=ctx.obj.get("idle_duration", 2.0),
            window_timeout=ctx.obj.get("window_timeout", 30.0),
            idle_timeout=ctx.obj.get("idle_timeout", 60.0),
            sample_interval=ctx.obj.get("sample_interval", 0.1),
            dry_run=ctx.obj.get("dry_run", False),
        )
        ctx._analyzer = create_analyzer(config)
    return ctx._analyzer


@app.callback()
def main(
    ctx: typer.Context,
    iterations: int = typer.Option(3, "--iterations", "-n", help="Number of measurement iterations"),
    cooldown: float = typer.Option(2.0, "--cooldown", "-c", help="Cooldown between runs (seconds)"),
    cpu_threshold: float = typer.Option(5.0, "--cpu-threshold", help="CPU % threshold for idle detection"),
    idle_duration: float = typer.Option(2.0, "--idle-duration", help="Duration of low CPU for idle (seconds)"),
    window_timeout: float = typer.Option(15.0, "--window-timeout", help="Max time to wait for window (seconds)"),
    idle_timeout: float = typer.Option(20.0, "--idle-timeout", help="Max time to wait for idle (seconds)"),
    sample_interval: float = typer.Option(0.1, "--sample-interval", help="Metrics sampling interval (seconds)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without applying"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Startup Analyzer - Measure, analyze, and optimize application startup time."""
    ctx.ensure_object(dict)
    ctx.obj.update({
        "iterations": iterations,
        "cooldown": cooldown,
        "cpu_threshold": cpu_threshold,
        "idle_duration": idle_duration,
        "window_timeout": window_timeout,
        "idle_timeout": idle_timeout,
        "sample_interval": sample_interval,
        "dry_run": dry_run,
        "verbose": verbose,
    })


@app.command("list")
def list_apps(
    ctx: typer.Context,
    filter_type: str | None = typer.Option(None, "--type", "-t", help="Filter by app type"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List discovered applications."""
    analyzer = get_analyzer(ctx)
    apps = analyzer.list_applications()

    if filter_type:
        apps = [a for a in apps if a.app_type.value == filter_type.lower()]

    if json_output:
        data = [
            {
                "name": a.name,
                "executable": str(a.executable),
                "type": a.app_type.value,
                "platform": a.platform.value,
                "version": a.version,
                "bundle_id": a.bundle_id,
            }
            for a in apps
        ]
        console.print_json(json.dumps(data))
        return

    table = Table(title="Discovered Applications", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Executable", style="dim")
    table.add_column("Version", style="yellow")

    for app_info in apps:
        table.add_row(
            app_info.name,
            app_info.app_type.value,
            str(app_info.executable),
            app_info.version or "Unknown",
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(apps)} applications[/dim]")


@app.command("find")
def find_app(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Application name or path"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Find an application by name or path."""
    analyzer = get_analyzer(ctx)
    app = analyzer.find_application(name)

    if not app:
        console.print(f"[red]Application not found: {name}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print_json(json.dumps({
            "name": app.name,
            "executable": str(app.executable),
            "type": app.app_type.value,
            "platform": app.platform.value,
            "version": app.version,
            "bundle_id": app.bundle_id,
            "arguments": app.arguments,
        }))
        return

    console.print(Panel.fit(
        f"[bold cyan]{app.name}[/bold cyan]\n"
        f"Type: [green]{app.app_type.value}[/green]\n"
        f"Platform: [green]{app.platform.value}[/green]\n"
        f"Executable: [yellow]{app.executable}[/yellow]\n"
        f"Version: [yellow]{app.version or 'Unknown'}[/yellow]\n"
        f"Bundle ID: [yellow]{app.bundle_id or 'N/A'}[/yellow]",
        title="🔍 Application Found",
        border_style="cyan",
    ))


@app.command("measure")
def measure(
    ctx: typer.Context,
    app_name: str = typer.Argument(..., help="Application name or path"),
    mode: MeasurementMode = typer.Option(MeasurementMode.WARM, "--mode", "-m", help="Measurement mode"),
    iterations: int | None = typer.Option(None, "--iterations", "-n", help="Override iterations"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """Measure application startup performance."""
    analyzer = get_analyzer(ctx)
    app = analyzer.find_application(app_name)

    if not app:
        console.print(f"[red]Application not found: {app_name}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Measuring {app.name} ({mode.value} start)...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running measurements...", total=None)
        measurement_set = analyzer.measure_startup(app, mode, iterations)
        progress.update(task, completed=True)

    # Print results
    _print_measurement_results(measurement_set)

    if output:
        _save_measurement_json(measurement_set, output)
        console.print(f"\n[green]Results saved to {output}[/green]")


@app.command("analyze")
def analyze(
    ctx: typer.Context,
    app_name: str = typer.Argument(..., help="Application name or path"),
    mode: MeasurementMode = typer.Option(MeasurementMode.WARM, "--mode", "-m", help="Measurement mode"),
):
    """Analyze startup bottlenecks for an application."""
    analyzer = get_analyzer(ctx)
    app = analyzer.find_application(app_name)

    if not app:
        console.print(f"[red]Application not found: {app_name}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Analyzing {app.name}...[/bold]\n")

    measurement_set = analyzer.measure_startup(app, mode)

    # Analyze bottlenecks from first successful measurement
    successful = measurement_set.successful_measurements
    if not successful:
        console.print("[red]No successful measurements[/red]")
        raise typer.Exit(1)

    measurement = successful[0]
    bottlenecks = analyzer.analyze_bottlenecks(app, measurement)

    if not bottlenecks:
        console.print("[green]No significant bottlenecks detected[/green]")
        return

    console.print(Panel(
        f"Found [bold]{len(bottlenecks)}[/bold] potential bottlenecks",
        title="🔍 Bottleneck Analysis",
        border_style="yellow",
    ))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Severity", style="bold")
    table.add_column("Description")
    table.add_column("Suggestion")

    for b in bottlenecks:
        severity_color = "red" if b.severity > 0.7 else "yellow" if b.severity > 0.4 else "green"
        table.add_row(
            b.category,
            f"[{severity_color}]{b.severity:.0%}[/{severity_color}]",
            b.description,
            b.suggestion,
        )

    console.print(table)


@app.command("optimize")
def optimize(
    ctx: typer.Context,
    app_name: str = typer.Argument(..., help="Application name or path"),
    optimizations: list[str] | None = typer.Option(None, "--optimization", "-O", help="Optimizations to apply"),
    list_only: bool = typer.Option(False, "--list", "-l", help="List available optimizations"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive selection"),
    apply: bool = typer.Option(False, "--apply", "-a", help="Apply optimizations (not just dry-run)"),
    mode: MeasurementMode = typer.Option(MeasurementMode.WARM, "--mode", "-m", help="Measurement mode"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output report file"),
    format: str = typer.Option("terminal", "--format", "-f", help="Report format: terminal, json, html, markdown"),
):
    """Optimize application startup."""
    analyzer = get_analyzer(ctx)
    app = analyzer.find_application(app_name)

    if not app:
        console.print(f"[red]Application not found: {app_name}[/red]")
        raise typer.Exit(1)

    # Get applicable optimizations
    from startup_analyzer.optimization.registry import OptimizationContext

    applicable = []
    for name in registry.get_all():
        instance = registry.create_instance(name)
        if instance is None:
            continue
        ctx_obj = OptimizationContext(app=app, platform=analyzer.backend.platform, dry_run=True)
        if instance.can_apply(ctx_obj):
            applicable.append(instance)

    if list_only:
        _print_optimizations_table(applicable)
        return

    if not optimizations and not interactive:
        console.print("[yellow]No optimizations specified. Use --list to see available options.[/yellow]")
        _print_optimizations_table(applicable)
        return

    # Interactive selection
    if interactive:
        optimizations = _interactive_select(applicable)

    if not optimizations:
        console.print("[red]No optimizations selected[/red]")
        raise typer.Exit(1)

    # Run full analysis with optimizations
    console.print(f"\n[bold]Running full analysis on {app.name}...[/bold]\n")

    # Update analyzer config for dry_run
    analyzer.config.dry_run = not apply

    report = analyzer.run_full_analysis(app, optimizations, mode)

    # Generate report
    generator = ReportGenerator()

    if format == "json" or (output and output.suffix == ".json"):
        output_path = output or Path(f"{app.name}_report.json")
        generator.generate_json(report, output_path)
        console.print(f"[green]JSON report saved to {output_path}[/green]")
    elif format == "html" or (output and output.suffix == ".html"):
        output_path = output or Path(f"{app.name}_report.html")
        generator.generate_html(report, output_path)
        console.print(f"[green]HTML report saved to {output_path}[/green]")
    elif format == "markdown" or (output and output.suffix in [".md", ".markdown"]):
        output_path = output or Path(f"{app.name}_report.md")
        generator.generate_markdown(report, output_path)
        console.print(f"[green]Markdown report saved to {output_path}[/green]")
    else:
        generator.print_terminal_report(report)


@app.command("compare")
def compare(
    ctx: typer.Context,
    baseline_file: Path = typer.Argument(..., help="Baseline measurement JSON file"),
    optimized_file: Path = typer.Argument(..., help="Optimized measurement JSON file"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output report file"),
    format: str = typer.Option("terminal", "--format", "-f", help="Report format"),
):
    """Compare two measurement files (JSON files saved with `measure --output`)."""
    import statistics

    def load_set(path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except Exception as e:
            console.print(f"[red]Failed to read {path}: {e}[/red]")
            raise typer.Exit(1)

    def series(measurements: list[dict], section: str, attr: str) -> list[float]:
        vals = []
        for m in measurements:
            v = (m.get(section) or {}).get(attr)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return vals

    base = load_set(baseline_file)
    opt = load_set(optimized_file)
    base_ms = base.get("measurements", [])
    opt_ms = opt.get("measurements", [])

    rows = [
        ("timeline", "time_to_window", "Time to Window (s)", False),
        ("timeline", "time_to_idle", "Time to Idle (s)", False),
        ("timeline", "time_to_first_cpu", "Time to First CPU (s)", False),
        ("resources", "peak_cpu_percent", "Peak CPU (%)", False),
        ("resources", "avg_cpu_percent", "Avg CPU (%)", False),
        ("resources", "peak_memory_rss", "Peak Memory (MB)", True),
        ("resources", "avg_memory_rss", "Avg Memory (MB)", True),
        ("resources", "total_read_bytes", "Disk Read (MB)", True),
        ("resources", "total_write_bytes", "Disk Write (MB)", True),
    ]

    table = Table(title="Measurement Comparison", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", style="yellow")
    table.add_column("Optimized", style="green")
    table.add_column("Change", style="bold")

    for section, attr, label, is_bytes in rows:
        b = series(base_ms, section, attr)
        o = series(opt_ms, section, attr)
        if not b or not o:
            continue
        b_mean = statistics.mean(b)
        o_mean = statistics.mean(o)
        if is_bytes:
            b_str = f"{b_mean / (1024*1024):.1f} MB"
            o_str = f"{o_mean / (1024*1024):.1f} MB"
        else:
            b_str = f"{b_mean:.2f}"
            o_str = f"{o_mean:.2f}"
        pct = ((b_mean - o_mean) / b_mean * 100) if b_mean else 0.0
        change = f"[green]↓ {pct:.1f}%[/green]" if pct > 0 else (f"[red]↑ {abs(pct):.1f}%[/red]" if pct < 0 else "[dim]—[/dim]")
        table.add_row(label, b_str, o_str, change)

    if output is None and format == "terminal":
        console.print(table)
        return

    # Save comparison as JSON or Markdown
    output_path = output or Path("comparison.json")
    if format == "markdown" or output_path.suffix in (".md", ".markdown"):
        lines = ["# Measurement Comparison", "", f"- Baseline: `{baseline_file}`", f"- Optimized: `{optimized_file}`", ""]
        # Re-render plain text rows for markdown
        lines.append("| Metric | Baseline | Optimized |")
        lines.append("|---|---|---|")
        console.print(table)
        output_path.write_text("\n".join(lines))
        console.print(f"[green]Comparison saved to {output_path}[/green]")
    else:
        output_path.write_text(json.dumps({"baseline_file": str(baseline_file), "optimized_file": str(optimized_file)}, indent=2))
        console.print(table)
        console.print(f"[green]Comparison saved to {output_path}[/green]")


@app.command("optimizations")
def list_optimizations(
    ctx: typer.Context,
    app_name: str | None = typer.Option(None, "--app", "-a", help="Filter by application"),
):
    """List all available optimizations."""
    analyzer = get_analyzer(ctx)

    if app_name:
        app = analyzer.find_application(app_name)
        if not app:
            console.print(f"[red]Application not found: {app_name}[/red]")
            raise typer.Exit(1)

        from startup_analyzer.optimization.registry import OptimizationContext

        applicable = []
        for name in registry.get_all():
            instance = registry.create_instance(name)
            if instance is None:
                continue
            ctx_obj = OptimizationContext(app=app, platform=analyzer.backend.platform, dry_run=True)
            if instance.can_apply(ctx_obj):
                applicable.append(instance)

        _print_optimizations_table(applicable)
    else:
        # Show all registered optimizations
        table = Table(title="All Registered Optimizations", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan")
        table.add_column("Module", style="green")

        for name, opt_class in registry.get_all().items():
            table.add_row(name, opt_class.__module__)

        console.print(table)


def _print_measurement_results(measurement_set) -> None:
    """Print measurement results in a nice table."""
    successful = measurement_set.successful_measurements
    if not successful:
        console.print("[red]No successful measurements[/red]")
        return

    # Summary statistics
    stats = {}
    for attr in ["time_to_first_cpu", "time_to_window", "time_to_idle", "peak_cpu_percent", "avg_cpu_percent", "peak_memory_rss", "avg_memory_rss"]:
        stats[attr] = measurement_set.get_statistics(attr)

    table = Table(title=f"Measurement Results ({len(successful)} runs)", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Mean", style="yellow")
    table.add_column("Median", style="green")
    table.add_column("Min", style="blue")
    table.add_column("Max", style="red")
    table.add_column("StdDev", style="magenta")

    for attr, label in [
        ("time_to_first_cpu", "Time to First CPU (s)"),
        ("time_to_window", "Time to Window (s)"),
        ("time_to_idle", "Time to Idle (s)"),
        ("peak_cpu_percent", "Peak CPU (%)"),
        ("avg_cpu_percent", "Avg CPU (%)"),
        ("peak_memory_rss", "Peak Memory (MB)"),
        ("avg_memory_rss", "Avg Memory (MB)"),
    ]:
        s = stats.get(attr, {})
        if s:
            if "memory" in attr:
                table.add_row(
                    label,
                    f"{s['mean']/(1024*1024):.1f}",
                    f"{s['median']/(1024*1024):.1f}",
                    f"{s['min']/(1024*1024):.1f}",
                    f"{s['max']/(1024*1024):.1f}",
                    f"{s['stdev']/(1024*1024):.1f}",
                )
            else:
                table.add_row(
                    label,
                    f"{s['mean']:.2f}",
                    f"{s['median']:.2f}",
                    f"{s['min']:.2f}",
                    f"{s['max']:.2f}",
                    f"{s['stdev']:.2f}",
                )

    console.print(table)


def _save_measurement_json(measurement_set, output: Path) -> None:
    """Save measurement set to JSON."""
    from startup_analyzer.core.report import ReportGenerator
    generator = ReportGenerator()
    data = generator._measurement_set_to_dict(measurement_set)
    output.write_text(json.dumps(data, indent=2, default=str))


def _print_optimizations_table(optimizations: list) -> None:
    """Print available optimizations in a table."""
    table = Table(title="Available Optimizations", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Risk", style="bold")
    table.add_column("Applies To", style="green")
    table.add_column("Reversible", style="yellow")

    for opt in optimizations:
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(opt.risk.lower(), "white")
        table.add_row(
            opt.name,
            opt.description[:80] + "..." if len(opt.description) > 80 else opt.description,
            f"[{risk_color}]{opt.risk.upper()}[/{risk_color}]",
            ", ".join(opt.applies_to) if opt.applies_to else "All",
            "✅" if opt.reversible else "❌",
        )

    console.print(table)


def _interactive_select(optimizations: list) -> list[str]:
    """Interactive optimization selection."""
    console.print("\n[bold]Select optimizations to apply (space to select, enter to confirm):[/bold]\n")

    selected = []
    for i, opt in enumerate(optimizations, 1):
        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(opt.risk.lower(), "white")
        console.print(f"  [{i}] {opt.name} - [{risk_color}]{opt.risk}[/{risk_color}] - {opt.description}")

    console.print()
    choices = typer.prompt("Enter numbers (comma-separated) or 'all'").strip()

    if choices.lower() == "all":
        return [opt.name for opt in optimizations]

    try:
        indices = [int(c.strip()) - 1 for c in choices.split(",")]
        for idx in indices:
            if 0 <= idx < len(optimizations):
                selected.append(optimizations[idx].name)
    except ValueError:
        console.print("[red]Invalid input[/red]")

    return selected


if __name__ == "__main__":
    app()