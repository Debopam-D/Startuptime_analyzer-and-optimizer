# Quick Start: Startup Analyzer

Welcome to Startup Analyzer! This guide will help you get up and running with the application startup time analyzer and optimizer.

## Installation

### Option 1: Using pip (Recommended)

```bash
# Install the package
pip install startup-analyzer

# Or install in development mode for hacking
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

### Option 2: From source

```bash
# Clone the repository
# (If using git)

# Install dependencies
pip install -r requirements.txt

# Or install from pyproject.toml
pip install -e .
```

## Basic Usage

### 1. List Discovered Applications

```bash
# List all applications found on your system
startup-analyzer list

# Filter by application type (e.g., electron, python, native)
startup-analyzer list --type electron

# Output as JSON for scripting
startup-analyzer list --json
```

### 2. Find a Specific Application

```bash
# Find application by name (case-insensitive)
startup-analyzer find "Visual Studio Code"

# Find application by path (supports .app bundles on macOS)
startup-analyzer find "/Applications/Chrome.app"
```

### 3. Measure Startup Performance

```bash
# Measure startup with default settings (warm start)
startup-analyzer measure "Firefox" --iterations 5

# Different measurement modes:
# Cold start (first launch after reboot)
startup-analyzer measure "Eclipse" --mode cold

# Hot start (very recent launch)
startup-analyzer measure "PyCharm" --mode hot

# Custom iterations and output
startup-analyzer measure "Code" --iterations 3 --output codemeasurement.json
```

### 4. Analyze Bottlenecks

```bash
# Analyze startup bottlenecks for an application
startup-analyzer analyze "MyApp"

# Combine measurement and analysis in one step
startup-analyzer analyze "Chrome" --mode warm
```

### 5. Apply Optimizations

```bash
# List available optimizations for an app
startup-analyzer optimize "VS Code" --list

# Apply optimizations (dry-run first)
startup-analyzer optimize "VS Code" --dry-run

# Actually apply optimizations and compare before/after
startup-analyzer optimize "Firefox" --apply --output firefox_report.html

# Apply specific optimizations
startup-analyzer optimize "MyApp" --optimization disable-telemetry --optimization launch-args

# Interactive optimization selection
startup-analyzer optimize "Chrome" --interactive
```

### 6. Compare Measurements

```bash
# Compare baseline and optimized measurements
startup-analyzer compare baseline.json optimized.json --output comparison.html

# Generate markdown comparison
startup-analyzer compare old.json new.json --output markdown_report.md
```

## Configuration

Create a configuration file at `~/.config/startup-analyzer/config.toml`:

```toml
[measurement]
iterations = 5
cooldown = 3.0
cpu_idle_threshold = 3.0
cpu_idle_duration = 3.0
window_timeout = 60.0
idle_timeout = 120.0
sample_interval = 0.05

[output]
format = "html"
include_charts = true
```

You can override config file settings with command line options:

```bash
# Command line overrides config
startup-analyzer measure "App" --iterations 10 --cooldown 5.0
```

## Programmatic Usage

If you want to integrate the analyzer into your own Python scripts:

```python
from startup_analyzer.core import create_analyzer, AnalyzerConfig
from startup_analyzer.core.metrics import MeasurementMode

# Create analyzer with custom configuration
config = AnalyzerConfig(
    iterations=5,
    cooldown=2.0,
    dry_run=False,
)

analyzer = create_analyzer(config)

# Find and measure an application
app = analyzer.find_application("MyApp")
if app:
    measurement_set = analyzer.measure_startup(app, MeasurementMode.WARM)

    # Analyze bottlenecks
    measurement = measurement_set.successful_measurements[0]
    bottlenecks = analyzer.analyze_bottlenecks(app, measurement)

    # Apply optimizations
    applicable = analyzer.get_applicable_optimizations(app)
    applied = analyzer.apply_optimizations(app, ["disable-telemetry", "launch-args"])

    # Run full analysis
    report = analyzer.run_full_analysis(app, ["disable-telemetry"])
```

## Supported Platforms

- **macOS**: Native .app bundles, Electron apps, Java, Python
- **Linux**: Desktop .desktop files, native executables
- **Windows**: Registry-based discovery, Start Menu shortcuts, Store apps

## Supported Application Types

- **Native**: Standard executables
- **Electron**: VS Code, Discord, Slack, etc.
- **Java**: Eclipse, IntelliJ, etc.
- **Python**: PyCharm, VS Code, etc.
- **.NET**: Visual Studio, etc.
- **Go**: Go applications
- **Rust**: Rust applications

## Common Optimizations

### Environment Variables
- `disable-telemetry`: Disable telemetry/analytics
- `runtime-flags`: Set runtime-specific optimizations (PYTHONOPTIMIZE, NODE_OPTIONS, etc.)
- `electron-flags`: Electron-specific startup flags

### Launch Arguments
- `--disable-gpu`, `--no-sandbox`: Faster UI rendering
- `-Xverify:none`: Skip Java verification
- `-O`: Python optimize flag

### Prefetch and Cache Warming
- `prefetch-libraries`: Pre-load libraries into filesystem cache
- `warm-cache`: Warm application cache directories

## Troubleshooting

### Application not found
- Try with exact executable path
- Check if the application is installed on your system
- Verify permissions

### Measurement fails
- Ensure you have permission to launch the application
- Check system resources
- Try with `--dry-run` to see what would be done

### Command not found
```bash
# Install the package
pip install startup-analyzer

# Verify installation
which startup-analyzer
```

### Advanced Usage

```bash
# Run with verbose output
startup-analyzer measure "App" -v

# Use custom measurement mode
startup-analyzer measure "App" --mode cold

# Export results to different formats
startup-analyzer measure "App" --output report.json
startup-analyzer optimize "App" --output report.html
```

## Getting Help

- `startup-analyzer --help`: Display general help
- `startup-analyzer <command> --help`: Display help for a specific command
- Check the `README.md` file for detailed documentation
- Visit the project repository for additional resources

## Contributing

If you find this project useful or want to contribute:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

The Startup Analyzer is designed to be extensible, so feel free to add new optimizations or platform backends!

## License

MIT License - See `LICENSE` file for details.