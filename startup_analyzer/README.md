# Startup Analyzer

Cross-platform application startup time analyzer and optimizer. Measure, analyze, and optimize application startup performance on macOS, Linux, and Windows.

## Features

- 🔍 **Discover Applications** - Automatically find installed applications
- ⏱️ **Measure Startup Time** - Precise timing with multiple measurement modes (cold/warm/hot)
- 📊 **Resource Monitoring** - Track CPU, memory, I/O, and thread usage during startup
- 🔬 **Bottleneck Analysis** - Identify performance bottlenecks automatically
- ⚡ **Safe Optimizations** - Apply user-level optimizations (prefetch, env vars, launch args)
- 📈 **Before/After Comparison** - Statistical comparison with confidence intervals
- 📋 **Rich Reports** - Terminal, JSON, HTML, and Markdown output formats

## Installation

```bash
# From source
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Start

```bash
# List discovered applications
startup-analyzer list

# Find a specific application
startup-analyzer find "Visual Studio Code"

# Measure startup performance
startup-analyzer measure "Firefox" --iterations 5

# Analyze bottlenecks
startup-analyzer analyze "Chrome"

# List available optimizations for an app
startup-analyzer optimize "VS Code" --list

# Run full optimization analysis
startup-analyzer optimize "MyApp" --apply --output report.html
```

## Commands

| Command | Description |
|---------|-------------|
| `list` | List all discovered applications |
| `find` | Find an application by name or path |
| `measure` | Measure startup performance |
| `analyze` | Analyze startup bottlenecks |
| `optimize` | Apply optimizations and compare before/after |
| `optimizations` | List available optimizations |
| `compare` | Compare two measurement files |

## Supported Platforms

- ✅ macOS (10.15+)
- ✅ Linux (Ubuntu 20.04+, Fedora 35+, Arch, etc.)
- ✅ Windows (10/11)

## Supported Application Types

- Native executables
- Electron apps (VS Code, Discord, Slack, etc.)
- Java applications
- Python scripts
- .NET applications
- Go binaries
- Rust binaries

## Optimizations

### Prefetch & Cache Warming
- Pre-load libraries into filesystem cache
- Warm application data/cache directories

### Environment Variables
- Disable telemetry/analytics (DO_NOT_TRACK, DISABLE_TELEMETRY, etc.)
- Runtime-specific optimizations (PYTHONOPTIMIZE, NODE_OPTIONS, DOTNET_ReadyToRun, etc.)
- Electron-specific flags (disable GPU, sandbox, etc.)

### Launch Arguments
- Add fast-start flags (--disable-gpu, --no-sandbox, etc.)
- Remove slow flags (--enable-logging, debug flags, etc.)
- Disable auto-update checks

## Example Output

### Terminal Report
```
📊 Startup Analyzer Report
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Application: VS Code (code)                         ┃
┃ Platform: macos | Type: electron                    ┃
┃ Generated: 2024-01-15 14:30:22                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

🔧 Optimizations Applied
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Optimization                ┃ Status      ┃ Message                              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ DisableTelemetry            │ ✅ Success  │ Applied 12 telemetry-disabling vars │
│ RuntimeOptimizationFlags    │ ✅ Success  │ Applied 3 runtime optimization flags │
│ LaunchArgumentOptimization  │ ✅ Success  │ Added 8 flags, removed 2 flags      │
└─────────────────────────────┴─────────────┴──────────────────────────────────────┘

⚡ Performance Comparison
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Metric                      ┃ Baseline    ┃ Optimized   ┃ Change      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Time to Window (s)          │ 3.45        │ 2.12        │ 🟢 -38.5%   │
│ Time to Idle (s)            │ 5.21        │ 3.87        │ 🟢 -25.7%   │
│ Peak Memory (MB)            │ 412.3       │ 398.1       │ 🟢 -3.4%    │
│ Peak CPU (%)                │ 89.2        │ 76.5        │ 🟢 -14.2%   │
└─────────────────────────────┴─────────────┴─────────────┴─────────────┘

📈 Summary
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Overall improvement: 20.5%                            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Configuration

Create a config file at `~/.config/startup-analyzer/config.toml`:

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

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/startup_analyzer

# Linting
ruff check src/startup_analyzer
ruff format src/startup_analyzer
```

## Architecture

```
src/startup_analyzer/
├── cli.py                 # CLI entry point
├── core/
│   ├── analyzer.py        # Main orchestration
│   ├── metrics.py         # Data models
│   └── report.py          # Report generation
├── platform/
│   ├── base.py            # Abstract platform interface
│   ├── macos.py           # macOS implementation
│   ├── linux.py           # Linux implementation
│   └── windows.py         # Windows implementation
├── measurement/
│   ├── timer.py           # Startup timing
│   ├── resources.py       # Resource monitoring
│   └── profiler.py        # Bottleneck analysis
├── optimization/
│   ├── registry.py        # Optimization registry
│   ├── prefetch.py        # Prefetch/cache warming
│   ├── env_vars.py        # Environment variable tweaks
│   └── launch_args.py     # Launch argument optimization
└── utils/
    ├── process.py         # Process utilities
    └── formatting.py      # Output formatting
```

## License

MIT License - see LICENSE file for details.