# Templates Directory

This directory contains HTML templates for report generation.

## Usage

The `ReportGenerator.generate_html()` method will look for templates in the following order:
1. `src/startup_analyzer/templates/` (inside the package)
2. Current working directory's `templates/` folder
3. Use inline template if no template directory exists

## Template Variables

The HTML template uses the following variables from the report:
- `report.app.name` - Application name
- `report.app.platform.value` - Platform (macos, linux, windows)
- `report.app.app_type.value` - Application type
- `report.generated_at` - Generation timestamp
- `report.optimizations_applied` - List of applied optimizations
- `report.metrics_comparison` - Performance comparison metrics

## Template Features

- Responsive design for mobile and desktop
- Chart.js integration for performance visualization
- Color-coded improvements/regressions
- Metric cards with statistical summaries
- Detailed tables for optimization results