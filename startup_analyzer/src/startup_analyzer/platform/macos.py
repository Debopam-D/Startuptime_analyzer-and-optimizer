"""macOS platform backend implementation."""

from __future__ import annotations

import os
import plistlib
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


class MacOSBackend(PlatformBackend):
    """macOS-specific implementation."""

    def __init__(self):
        self._process_cache: dict[int, psutil.Process] = {}

    @property
    def platform(self) -> Platform:
        return Platform.MACOS

    def discover_applications(self) -> list[Application]:
        """Discover applications in standard macOS locations."""
        apps = []
        search_paths = [
            Path("/Applications"),
            Path("/System/Applications"),
            Path.home() / "Applications",
            Path("/Applications/Utilities"),
        ]

        for search_path in search_paths:
            if not search_path.exists():
                continue

            for item in search_path.iterdir():
                if item.suffix == ".app" and item.is_dir():
                    try:
                        app = self._parse_app_bundle(item)
                        if app:
                            apps.append(app)
                    except Exception:
                        continue

        return apps

    def _parse_app_bundle(self, bundle_path: Path) -> Application | None:
        """Parse an .app bundle and extract metadata."""
        info_plist = bundle_path / "Contents" / "Info.plist"
        if not info_plist.exists():
            return None

        try:
            with info_plist.open("rb") as f:
                plist = plistlib.load(f)

            executable_name = plist.get("CFBundleExecutable")
            if not executable_name:
                return None

            executable = bundle_path / "Contents" / "MacOS" / executable_name
            if not executable.exists():
                return None

            bundle_id = plist.get("CFBundleIdentifier")
            version = plist.get("CFBundleShortVersionString") or plist.get("CFBundleVersion")
            name = plist.get("CFBundleDisplayName") or plist.get("CFBundleName") or bundle_path.stem

            app_type = self._detect_app_type(bundle_path, plist)

            return Application(
                name=name,
                executable=executable,
                bundle_id=bundle_id,
                version=version,
                platform=Platform.MACOS,
                app_type=app_type,
            )
        except Exception:
            return None

    def _detect_app_type(self, bundle_path: Path, plist: dict) -> AppType:
        """Detect application type from bundle contents."""
        # Check for Electron
        resources = bundle_path / "Contents" / "Resources"
        if (resources / "app.asar").exists() or (resources / "app").exists():
            return AppType.ELECTRON

        # Check for Java
        if (bundle_path / "Contents" / "Java").exists():
            return AppType.JAVA

        # Check for Python
        if (bundle_path / "Contents" / "Resources" / "Python").exists():
            return AppType.PYTHON

        return AppType.NATIVE

    def find_application(self, name: str) -> Application | None:
        """Find an application by name, bundle ID, or path."""
        # Try as path first
        path = Path(name).expanduser()
        if path.exists():
            if path.suffix == ".app":
                return self._parse_app_bundle(path)
            if path.is_file() and os.access(path, os.X_OK):
                return Application(
                    name=path.stem,
                    executable=path,
                    platform=Platform.MACOS,
                )

        # Search by name
        apps = self.discover_applications()
        name_lower = name.lower()

        for app in apps:
            if (
                name_lower in app.name.lower()
                or (app.bundle_id and name_lower in app.bundle_id.lower())
                or name_lower in app.executable.name.lower()
            ):
                return app

        # Try mdfind for more comprehensive search
        try:
            result = subprocess.run(
                ["mdfind", f"kMDItemKind == Application && kMDItemDisplayName == '{name}'"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    app = self._parse_app_bundle(Path(line))
                    if app:
                        return app
        except Exception:
            pass

        return None

    def launch_application(self, app: Application) -> subprocess.Popen:
        """Launch a macOS application and return a handle that tracks the actual app process."""
        if app.executable.suffix == ".app" or app.executable.parent.name == "MacOS":
            # Launch .app bundle properly
            launcher = subprocess.Popen(["open", "-a", str(app.executable)], start_new_session=True)
            
            # Wait a bit for the app to start, then find the actual process
            time.sleep(0.5)
            
            # Find the actual application process by bundle ID or name
            actual_pid = self._find_app_process(app)
            if actual_pid:
                # Create a wrapper that mimics Popen but uses the actual PID
                class AppProcess:
                    def __init__(self, pid, launcher):
                        self.pid = pid
                        self._launcher = launcher
                        self._proc = psutil.Process(pid)
                    
                    def poll(self):
                        try:
                            return None if self._proc.is_running() else 0
                        except Exception:
                            return 0
                    
                    def wait(self, timeout=None):
                        try:
                            self._proc.wait(timeout=timeout)
                            return 0
                        except Exception:
                            return 0
                    
                    def terminate(self):
                        try:
                            self._proc.terminate()
                        except Exception:
                            pass
                        try:
                            self._launcher.terminate()
                        except Exception:
                            pass
                    
                    def kill(self):
                        try:
                            self._proc.kill()
                        except Exception:
                            pass
                        try:
                            self._launcher.kill()
                        except Exception:
                            pass
                
                return AppProcess(actual_pid, launcher)
            
            return launcher
        
        # Launch executable directly
        env = os.environ.copy()
        env.update(app.env_vars)
        return subprocess.Popen(
            [str(app.executable)] + app.arguments,
            cwd=app.working_dir,
            env=env,
            start_new_session=True,
        )
    
    def _find_app_process(self, app: Application) -> int | None:
        """Find the actual application process by bundle ID or executable name."""
        try:
            target_name = app.executable.name
            if target_name.endswith(".app"):
                target_name = target_name[:-4]
            elif app.executable.parent.name == "MacOS":
                target_name = app.executable.name
            
            # Also check bundle ID
            bundle_id = app.bundle_id
            
            for p in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    pinfo = p.info
                    if pinfo['name'] and (target_name.lower() in pinfo['name'].lower() or 
                                          (bundle_id and bundle_id.lower() in (pinfo.get('exe') or '').lower())):
                        return pinfo['pid']
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def get_process_metrics(self, pid: int) -> dict | None:
        """Get process metrics using psutil with cached process for accurate CPU."""
        try:
            # Get or create cached process
            if pid not in self._process_cache:
                self._process_cache[pid] = psutil.Process(pid)
                # Prime CPU measurement
                self._process_cache[pid].cpu_percent(interval=0.1)
            
            proc = self._process_cache[pid]
            with proc.oneshot():
                mem = proc.memory_info()
                io = proc.io_counters() if hasattr(proc, "io_counters") else None
                
                # Non-blocking CPU reading
                cpu = proc.cpu_percent(interval=None)

                return {
                    "cpu_percent": cpu,
                    "memory_rss": mem.rss,
                    "memory_vms": mem.vms,
                    "num_threads": proc.num_threads(),
                    "num_fds": proc.num_fds() if hasattr(proc, "num_fds") else None,
                    "read_bytes": io.read_bytes if io else 0,
                    "write_bytes": io.write_bytes if io else 0,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Clean up cache
            self._process_cache.pop(pid, None)
            return None

    def wait_for_window(self, pid: int, timeout: float) -> bool:
        """Wait for main window using Quartz accessibility API."""
        try:
            from Quartz import (
                CGWindowListCopyWindowInfo,
                kCGNullWindowID,
                kCGWindowListOptionOnScreenOnly,
            )

            start = time.time()
            while time.time() - start < timeout:
                try:
                    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
                    for w in windows:
                        if w.get("kCGWindowOwnerPID") == pid:
                            # Check if it's a main window (not a helper)
                            layer = w.get("kCGWindowLayer", 0)
                            if layer == 0:  # Normal window layer
                                return True
                except Exception:
                    pass
                time.sleep(0.1)
        except ImportError:
            # Fallback: just wait a bit
            time.sleep(1.0)
            return True

        return False

    def wait_for_idle(self, pid: int, cpu_threshold: float, duration: float, timeout: float) -> bool:
        """Wait for process to become idle."""
        try:
            # Use cached process if available
            if pid not in self._process_cache:
                self._process_cache[pid] = psutil.Process(pid)
                self._process_cache[pid].cpu_percent(interval=0.1)
            
            proc = self._process_cache[pid]
            
            idle_start = None
            start = time.time()

            while time.time() - start < timeout:
                cpu = proc.cpu_percent(interval=None)
                if cpu < cpu_threshold:
                    if idle_start is None:
                        idle_start = time.time()
                    elif time.time() - idle_start >= duration:
                        return True
                else:
                    idle_start = None
                time.sleep(0.1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True  # Process ended, consider it idle

        return False

    def get_app_type(self, app: Application) -> str:
        return app.app_type.value

    def get_app_version(self, app: Application) -> str | None:
        return app.version

    def apply_optimization(self, optimization_name: str, app: Application) -> dict:
        """Apply macOS-specific optimizations."""
        revert_info = {"optimization": optimization_name}

        if optimization_name == "clear_dyld_cache":
            # Clear user dyld cache (requires careful handling)
            revert_info["action"] = "dyld_cache"
            return revert_info

        if optimization_name == "disable_telemetry":
            # Set environment variables to disable common telemetry
            telemetry_vars = {
                "DO_NOT_TRACK": "1",
                "DISABLE_TELEMETRY": "1",
                "NEXT_TELEMETRY_DISABLED": "1",
                "HINT_TELEMETRY": "0",
            }
            revert_info["env_vars"] = telemetry_vars
            return revert_info

        if optimization_name == "prefetch_libraries":
            # Pre-load common libraries using dtruss or similar
            revert_info["action"] = "prefetch"
            return revert_info

        return revert_info

    def revert_optimization(self, optimization_name: str, app: Application, revert_info: dict) -> bool:
        """Revert macOS-specific optimizations."""
        # Most user-level optimizations don't need explicit revert
        return True

    def get_system_info(self) -> dict:
        """Get macOS system information."""
        try:
            sw_vers = subprocess.run(["sw_vers"], capture_output=True, text=True).stdout
            hw = subprocess.run(["sysctl", "-n", "hw.model", "hw.ncpu", "hw.memsize"], capture_output=True, text=True).stdout
            return {
                "os": "macOS",
                "details": sw_vers.strip(),
                "hardware": hw.strip(),
            }
        except Exception:
            return {"os": "macOS"}


# Register the backend
def create_backend() -> PlatformBackend:
    return MacOSBackend()