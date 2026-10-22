"""Linux platform backend implementation."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

from startup_analyzer.core.metrics import (
    Application,
    AppType,
    Platform,
)
from startup_analyzer.platform.base import PlatformBackend

if TYPE_CHECKING:
    pass


class LinuxBackend(PlatformBackend):
    """Linux-specific implementation."""

    @property
    def platform(self) -> Platform:
        return Platform.LINUX

    def discover_applications(self) -> list[Application]:
        """Discover applications from .desktop files."""
        apps = []
        desktop_dirs = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications",
        ]

        for desktop_dir in desktop_dirs:
            if not desktop_dir.exists():
                continue

            for desktop_file in desktop_dir.glob("*.desktop"):
                try:
                    app = self._parse_desktop_file(desktop_file)
                    if app:
                        apps.append(app)
                except Exception:
                    continue

        return apps

    def _parse_desktop_file(self, desktop_file: Path) -> Application | None:
        """Parse a .desktop file and extract application metadata."""
        try:
            with desktop_file.open() as f:
                content = f.read()

            # Simple parsing of .desktop file
            exec_line = None
            name = None
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("Exec="):
                    exec_line = line[5:].strip()
                elif line.startswith("Name=") and not name:
                    name = line[5:].strip()

            if not exec_line or not name:
                return None

            # Extract executable from Exec line (remove field codes like %f, %u)
            exec_parts = exec_line.split()
            executable_path = exec_parts[0]
            arguments = exec_parts[1:] if len(exec_parts) > 1 else []

            # Resolve executable path
            if not Path(executable_path).is_absolute():
                # Search in PATH
                for path_dir in os.environ.get("PATH", "").split(":"):
                    full_path = Path(path_dir) / executable_path
                    if full_path.exists() and os.access(full_path, os.X_OK):
                        executable_path = str(full_path)
                        break

            executable = Path(executable_path)
            if not executable.exists():
                return None

            app_type = self._detect_app_type(executable, content)

            return Application(
                name=name,
                executable=executable,
                arguments=arguments,
                platform=Platform.LINUX,
                app_type=app_type,
                desktop_file=desktop_file,
            )
        except Exception:
            return None

    def _detect_app_type(self, executable: Path, desktop_content: str) -> AppType:
        """Detect application type."""
        exec_str = str(executable).lower()
        content_lower = desktop_content.lower()

        if "electron" in content_lower or "electron" in exec_str:
            return AppType.ELECTRON
        if executable.name == "java" or "java" in content_lower:
            return AppType.JAVA
        if executable.name.startswith("python") or ".py" in exec_str:
            return AppType.PYTHON
        if "dotnet" in exec_str or "mono" in exec_str:
            return AppType.DOTNET
        if executable.name == "go" or exec_str.endswith("/go"):
            return AppType.GO

        return AppType.NATIVE

    def find_application(self, name: str) -> Application | None:
        """Find an application by name, command, or path."""
        # Try as path first
        path = Path(name).expanduser()
        if path.exists():
            if path.is_file() and os.access(path, os.X_OK):
                return Application(
                    name=path.stem,
                    executable=path,
                    platform=Platform.LINUX,
                )

        # Search by name in desktop files
        apps = self.discover_applications()
        name_lower = name.lower()

        for app in apps:
            if (
                name_lower in app.name.lower()
                or name_lower in app.executable.name.lower()
                or (app.desktop_file and name_lower in app.desktop_file.stem.lower())
            ):
                return app

        # Try which/whereis
        try:
            result = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                exe_path = Path(result.stdout.strip())
                return Application(
                    name=name,
                    executable=exe_path,
                    platform=Platform.LINUX,
                )
        except Exception:
            pass

        return None

    def launch_application(self, app: Application) -> subprocess.Popen:
        """Launch a Linux application."""
        env = os.environ.copy()
        env.update(app.env_vars)

        cmd = [str(app.executable)] + app.arguments

        # Handle special cases
        if app.app_type == AppType.ELECTRON:
            # Add common Electron flags for faster startup
            pass

        return subprocess.Popen(
            cmd,
            cwd=app.working_dir,
            env=env,
            start_new_session=True,
        )

    def get_process_metrics(self, pid: int) -> dict | None:
        """Get process metrics using psutil."""
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                mem = proc.memory_info()
                io = proc.io_counters() if hasattr(proc, "io_counters") else None

                return {
                    "cpu_percent": proc.cpu_percent(interval=0),
                    "memory_rss": mem.rss,
                    "memory_vms": mem.vms,
                    "num_threads": proc.num_threads(),
                    "num_fds": proc.num_fds() if hasattr(proc, "num_fds") else None,
                    "read_bytes": io.read_bytes if io else 0,
                    "write_bytes": io.write_bytes if io else 0,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def wait_for_window(self, pid: int, timeout: float) -> bool:
        """Wait for main window using X11/Wayland."""
        try:
            # Try using xdotool or wmctrl for X11
            start = time.time()
            while time.time() - start < timeout:
                try:
                    # Use wmctrl to list windows for this PID
                    result = subprocess.run(
                        ["wmctrl", "-lp"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    for line in result.stdout.split("\n"):
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                win_pid = int(parts[2])
                                if win_pid == pid:
                                    return True
                            except ValueError:
                                continue
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                time.sleep(0.2)
        except Exception:
            pass

        # Fallback: just wait a bit
        time.sleep(1.0)
        return True

    def wait_for_idle(self, pid: int, cpu_threshold: float, duration: float, timeout: float) -> bool:
        """Wait for process to become idle."""
        try:
            proc = psutil.Process(pid)
            idle_start = None
            start = time.time()

            while time.time() - start < timeout:
                cpu = proc.cpu_percent(interval=0.1)
                if cpu < cpu_threshold:
                    if idle_start is None:
                        idle_start = time.time()
                    elif time.time() - idle_start >= duration:
                        return True
                else:
                    idle_start = None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True

        return False

    def get_app_type(self, app: Application) -> str:
        return app.app_type.value

    def get_app_version(self, app: Application) -> str | None:
        try:
            # Try common version flags
            for flag in ["--version", "-v", "-V", "version"]:
                try:
                    result = subprocess.run(
                        [str(app.executable), flag],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip().split("\n")[0]
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def apply_optimization(self, optimization_name: str, app: Application) -> dict:
        """Apply Linux-specific optimizations."""
        revert_info = {"optimization": optimization_name}

        if optimization_name == "preload_libraries":
            # Use preload or vmtouch to warm cache
            revert_info["action"] = "preload"
            return revert_info

        if optimization_name == "disable_telemetry":
            telemetry_vars = {
                "DO_NOT_TRACK": "1",
                "DISABLE_TELEMETRY": "1",
                "NEXT_TELEMETRY_DISABLED": "1",
            }
            revert_info["env_vars"] = telemetry_vars
            return revert_info

        if optimization_name == "transparent_hugepages":
            # Check THP status
            try:
                with open("/sys/kernel/mm/transparent_hugepage/enabled") as f:
                    revert_info["thp_status"] = f.read().strip()
            except Exception:
                pass
            return revert_info

        return revert_info

    def revert_optimization(self, optimization_name: str, app: Application, revert_info: dict) -> bool:
        return True

    def get_system_info(self) -> dict:
        """Get Linux system information."""
        info = {"os": "Linux"}
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        info[k.lower()] = v.strip('"')
        except Exception:
            pass

        try:
            info["kernel"] = subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip()
            info["cpu"] = subprocess.run(["lscpu"], capture_output=True, text=True).stdout.strip()
        except Exception:
            pass

        return info


def create_backend() -> PlatformBackend:
    return LinuxBackend()