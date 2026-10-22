"""Utility modules."""

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def find_executable(name: str) -> Path | None:
    """Find an executable in PATH."""
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        full_path = Path(path_dir) / name
        if full_path.exists() and os.access(full_path, os.X_OK):
            return full_path

    # Also check common locations
    common_paths = [
        Path("/usr/local/bin"),
        Path("/opt/homebrew/bin"),
        Path.home() / ".local" / "bin",
    ]
    for path_dir in common_paths:
        full_path = path_dir / name
        if full_path.exists() and os.access(full_path, os.X_OK):
            return full_path

    return None


def get_process_tree(pid: int) -> list[int]:
    """Get all descendant PIDs of a process."""
    try:
        import psutil

        proc = psutil.Process(pid)
        children = proc.children(recursive=True)
        return [proc.pid] + [c.pid for c in children]
    except Exception:
        return [pid]


def is_process_running(pid: int) -> bool:
    """Check if a process is still running."""
    try:
        import psutil

        return psutil.pid_exists(pid)
    except Exception:
        return False


def format_bytes(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 0.001:
        return f"{seconds*1_000_000:.0f} µs"
    if seconds < 1:
        return f"{seconds*1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    if seconds < 3600:
        return f"{seconds/60:.1f} m"
    return f"{seconds/3600:.1f} h"


def get_system_info() -> dict:
    """Get basic system information."""
    import platform

    info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    try:
        import psutil

        info["cpu_count"] = psutil.cpu_count()
        info["cpu_count_logical"] = psutil.cpu_count(logical=True)
        info["memory_total"] = psutil.virtual_memory().total
        info["disk_usage"] = psutil.disk_usage("/")._asdict()
    except Exception:
        pass

    return info


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path