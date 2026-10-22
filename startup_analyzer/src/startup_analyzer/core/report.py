"""Report generation for startup analysis."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from startup_analyzer.core.metrics import (
        ComparisonReport,
        MeasurementSet,
        OptimizationResult,
    )


class ReportGenerator:
    """Generates various report formats."""

    def __init__(self):
        self.console = Console()

    def print_terminal_report(self, report: ComparisonReport) -> None:
        """Print a rich terminal report."""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold cyan]Startup Analysis Report[/bold cyan]\n"
            f"Application: [yellow]{report.app.name}[/yellow] ({report.app.executable.name})\n"
            f"Platform: [green]{report.app.platform.value}[/green] | Type: [green]{report.app.app_type.value}[/green]\n"
            f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            title="📊 Startup Analyzer",
            border_style="cyan",
        ))

        # Optimizations applied
        if report.optimizations_applied:
            self._print_optimizations(report.optimizations_applied)

        # Before/After comparison
        self._print_comparison(report.baseline, report.optimized)

        # Bottlenecks
        self._print_bottlenecks(report)

        # Summary
        self._print_summary(report)

    def _print_optimizations(self, optimizations: list[OptimizationResult]) -> None:
        """Print applied optimizations table."""
        table = Table(title="🔧 Optimizations Applied", show_header=True, header_style="bold magenta")
        table.add_column("Optimization", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Message")

        for opt in optimizations:
            status = "✅ Success" if opt.success else "❌ Failed"
            table.add_row(opt.optimization.name, status, opt.message)

        self.console.print(table)
        self.console.print()

    def _print_comparison(self, baseline: MeasurementSet, optimized: MeasurementSet) -> None:
        """Print before/after comparison table."""
        table = Table(title="⚡ Performance Comparison", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Baseline", style="yellow")
        table.add_column("Optimized", style="green")
        table.add_column("Change", style="bold")

        # Time metrics
        metrics_to_compare = [
            ("time_to_first_cpu", "Time to First CPU (s)"),
            ("time_to_window", "Time to Window (s)"),
            ("time_to_idle", "Time to Idle (s)"),
            ("peak_cpu_percent", "Peak CPU (%)"),
            ("avg_cpu_percent", "Avg CPU (%)"),
            ("peak_memory_rss", "Peak Memory (MB)"),
            ("avg_memory_rss", "Avg Memory (MB)"),
            ("total_read_bytes", "Disk Read (MB)"),
            ("total_write_bytes", "Disk Write (MB)"),
        ]

        for attr, label in metrics_to_compare:
            base_stats = baseline.get_statistics(attr)
            opt_stats = optimized.get_statistics(attr)

            if not base_stats or not opt_stats:
                continue

            base_val = base_stats["mean"]
            opt_val = opt_stats["mean"]

            # Format values
            if "bytes" in attr or "memory" in attr.lower():
                base_str = f"{base_val / (1024*1024):.1f} MB"
                opt_str = f"{opt_val / (1024*1024):.1f} MB"
            else:
                base_str = f"{base_val:.2f}"
                opt_str = f"{opt_val:.2f}"

            # Calculate change
            if base_val != 0:
                pct = ((base_val - opt_val) / base_val) * 100
                if pct > 0:
                    change_str = f"[green]↓ {pct:.1f}%[/green]"
                elif pct < 0:
                    change_str = f"[red]↑ {abs(pct):.1f}%[/red]"
                else:
                    change_str = "[dim]—[/dim]"
            else:
                change_str = "[dim]N/A[/dim]"

            table.add_row(label, base_str, opt_str, change_str)

        self.console.print(table)
        self.console.print()

    def _print_bottlenecks(self, report: ComparisonReport) -> None:
        """Print identified bottlenecks."""
        # This would need bottleneck data in the report
        # For now, skip if not available
        pass

    def _print_summary(self, report: ComparisonReport) -> None:
        """Print summary panel."""
        improvements = []
        for attr in ["time_to_window", "time_to_idle", "peak_memory_rss", "peak_cpu_percent"]:
            imp = report.get_improvement(attr)
            if imp and "improvement_pct" in imp:
                improvements.append((attr, imp["improvement_pct"]))

        if improvements:
            avg_improvement = sum(i[1] for i in improvements) / len(improvements)
            if avg_improvement > 0:
                summary_text = f"[green]Overall improvement: {avg_improvement:.1f}%[/green]"
            else:
                summary_text = f"[red]Overall regression: {abs(avg_improvement):.1f}%[/red]"
        else:
            summary_text = "[yellow]No measurable improvement[/yellow]"

        self.console.print(Panel(
            summary_text,
            title="📈 Summary",
            border_style="green" if "improvement" in summary_text else "red",
        ))

    def generate_json(self, report: ComparisonReport, output_path: Path) -> None:
        """Generate JSON report."""
        data = self._report_to_dict(report)
        output_path.write_text(json.dumps(data, indent=2, default=str))

    def generate_html(self, report: ComparisonReport, output_path: Path) -> None:
        """Generate HTML report with charts."""
        from jinja2 import Environment, FileSystemLoader

        template_dir = Path(__file__).parent.parent / "templates"
        if not template_dir.exists():
            template_dir = Path.cwd() / "templates"

        env = Environment(loader=FileSystemLoader(template_dir) if template_dir.exists() else None)

        # Use inline template if no template dir
        template_str = self._get_html_template()
        template = env.from_string(template_str)

        html = template.render(
            report=self._report_to_dict(report),
            generated_at=datetime.now().isoformat(),
        )
        output_path.write_text(html)

    def generate_markdown(self, report: ComparisonReport, output_path: Path) -> None:
        """Generate Markdown report."""
        lines = [
            f"# Startup Analysis Report: {report.app.name}",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Platform:** {report.app.platform.value}",
            f"**App Type:** {report.app.app_type.value}",
            f"**Executable:** `{report.app.executable}`",
            "",
            "## Optimizations Applied",
            "",
        ]

        for opt in report.optimizations_applied:
            status = "✅" if opt.success else "❌"
            lines.append(f"- {status} **{opt.optimization.name}**: {opt.message}")

        lines.extend(["", "## Performance Comparison", ""])
        lines.append("| Metric | Baseline | Optimized | Change |")
        lines.append("|--------|----------|-----------|--------|")

        metrics_to_compare = [
            ("time_to_first_cpu", "Time to First CPU (s)"),
            ("time_to_window", "Time to Window (s)"),
            ("time_to_idle", "Time to Idle (s)"),
            ("peak_cpu_percent", "Peak CPU (%)"),
            ("avg_cpu_percent", "Avg CPU (%)"),
            ("peak_memory_rss", "Peak Memory (MB)"),
            ("avg_memory_rss", "Avg Memory (MB)"),
        ]

        for attr, label in metrics_to_compare:
            imp = report.get_improvement(attr)
            if not imp:
                continue

            base = imp["baseline_mean"]
            opt = imp["optimized_mean"]
            pct = imp["improvement_pct"]

            if "memory" in attr:
                base_str = f"{base / (1024*1024):.1f} MB"
                opt_str = f"{opt / (1024*1024):.1f} MB"
            else:
                base_str = f"{base:.2f}"
                opt_str = f"{opt:.2f}"

            change_str = f"{'+' if pct < 0 else ''}{pct:.1f}%"
            lines.append(f"| {label} | {base_str} | {opt_str} | {change_str} |")

        output_path.write_text("\n".join(lines))

    def _report_to_dict(self, report: ComparisonReport) -> dict:
        """Convert report to dictionary for serialization."""
        metrics_to_compare = [
            ("time_to_first_cpu", "Time to First CPU (s)"),
            ("time_to_window", "Time to Window (s)"),
            ("time_to_idle", "Time to Idle (s)"),
            ("peak_cpu_percent", "Peak CPU (%)"),
            ("avg_cpu_percent", "Avg CPU (%)"),
            ("peak_memory_rss", "Peak Memory (MB)"),
            ("avg_memory_rss", "Avg Memory (MB)"),
            ("total_read_bytes", "Disk Read (MB)"),
            ("total_write_bytes", "Disk Write (MB)"),
        ]
        comparison = []
        for attr, label in metrics_to_compare:
            imp = report.get_improvement(attr)
            if not imp:
                continue
            base = imp["baseline_mean"]
            opt = imp["optimized_mean"]
            if "memory" in attr or "bytes" in attr:
                base_str = f"{base / (1024*1024):.1f} MB"
                opt_str = f"{opt / (1024*1024):.1f} MB"
            else:
                base_str = f"{base:.2f}"
                opt_str = f"{opt:.2f}"
            comparison.append(
                {
                    "attr": attr,
                    "label": label,
                    "baseline": base_str,
                    "optimized": opt_str,
                    "baseline_value": base,
                    "optimized_value": opt,
                    "improvement": imp["improvement_pct"],
                }
            )
        return {
            "app": {
                "name": report.app.name,
                "executable": str(report.app.executable),
                "platform": report.app.platform.value,
                "app_type": report.app.app_type.value,
                "version": report.app.version,
            },
            "baseline": self._measurement_set_to_dict(report.baseline),
            "optimized": self._measurement_set_to_dict(report.optimized),
            "optimizations_applied": [
                {
                    "name": o.optimization.name,
                    "success": o.success,
                    "message": o.message,
                    "revert_info": o.revert_info,
                }
                for o in report.optimizations_applied
            ],
            "metrics_comparison": comparison,
            "generated_at": report.generated_at.isoformat(),
        }

    def _measurement_set_to_dict(self, ms) -> dict:
        return {
            "app": ms.app.name,
            "mode": ms.mode.value,
            "measurements": [
                {
                    "iteration": m.iteration,
                    "success": m.success,
                    "timeline": {
                        "process_start": m.timeline.process_start,
                        "first_cpu_activity": m.timeline.first_cpu_activity,
                        "main_window_visible": m.timeline.main_window_visible,
                        "process_idle": m.timeline.process_idle,
                        "time_to_first_cpu": m.timeline.time_to_first_cpu,
                        "time_to_window": m.timeline.time_to_window,
                        "time_to_idle": m.timeline.time_to_idle,
                    },
                    "resources": {
                        "peak_cpu_percent": m.resources.peak_cpu_percent,
                        "avg_cpu_percent": m.resources.avg_cpu_percent,
                        "peak_memory_rss": m.resources.peak_memory_rss,
                        "avg_memory_rss": m.resources.avg_memory_rss,
                        "peak_threads": m.resources.peak_threads,
                        "total_read_bytes": m.resources.total_read_bytes,
                        "total_write_bytes": m.resources.total_write_bytes,
                    },
                }
                for m in ms.measurements
            ],
        }

    def _get_html_template(self) -> str:
        """Get inline HTML template with Chart.js."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Startup Analysis Report - {{ report.app.name }}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #4a90d9; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 0; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .improved { color: #28a745; font-weight: bold; }
        .regressed { color: #dc3545; font-weight: bold; }
        .neutral { color: #6c757d; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        .chart-container { position: relative; height: 300px; margin: 20px 0; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric-card { background: #f8f9fa; padding: 15px; border-radius: 6px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #333; }
        .metric-label { font-size: 14px; color: #666; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>🚀 Startup Analysis Report: {{ report.app.name }}</h1>
    
    <div class="card">
        <h2>Application Info</h2>
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{{ report.app.name }}</div>
                <div class="metric-label">Application</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ report.app.platform.value }}</div>
                <div class="metric-label">Platform</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ report.app.app_type.value }}</div>
                <div class="metric-label">Type</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ report.generated_at[:19].replace('T', ' ') }}</div>
                <div class="metric-label">Generated</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2>Optimizations Applied</h2>
        <table>
            <thead>
                <tr><th>Optimization</th><th>Status</th><th>Details</th></tr>
            </thead>
            <tbody>
                {% for opt in report.optimizations_applied %}
                <tr>
                    <td>{{ opt.name }}</td>
                    <td><span class="badge {% if opt.success %}badge-success{% else %}badge-danger{% endif %}">{{ 'Success' if opt.success else 'Failed' }}</span></td>
                    <td>{{ opt.message }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>Performance Comparison</h2>
        <div class="chart-container">
            <canvas id="comparisonChart"></canvas>
        </div>
        <table>
            <thead>
                <tr><th>Metric</th><th>Baseline</th><th>Optimized</th><th>Change</th></tr>
            </thead>
            <tbody>
                {% for metric in report.metrics_comparison %}
                <tr>
                    <td>{{ metric.label }}</td>
                    <td>{{ metric.baseline }}</td>
                    <td>{{ metric.optimized }}</td>
                    <td class="{% if metric.improvement > 0 %}improved{% elif metric.improvement < 0 %}regressed{% else %}neutral{% endif %}">
                        {{ '%+.1f'|format(metric.improvement) }}%
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <script>
        // Chart.js comparison chart
        const ctx = document.getElementById('comparisonChart').getContext('2d');
        const data = {
            labels: [{% for m in report.metrics_comparison %}'{{ m.label }}',{% endfor %}],
            datasets: [
                {
                    label: 'Baseline',
                    data: [{% for m in report.metrics_comparison %}{{ m.baseline_value }},{% endfor %}],
                    backgroundColor: 'rgba(255, 193, 7, 0.7)',
                    borderColor: '#ffc107',
                    borderWidth: 1
                },
                {
                    label: 'Optimized',
                    data: [{% for m in report.metrics_comparison %}{{ m.optimized_value }},{% endfor %}],
                    backgroundColor: 'rgba(40, 167, 69, 0.7)',
                    borderColor: '#28a745',
                    borderWidth: 1
                }
            ]
        };
        new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: { y: { beginAtZero: true } }
            }
        });
    </script>
</body>
</html>"""