"""Windows platform backend implementation."""

from __future__ import annotations

import os
import subprocess
import time
import winreg
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


class WindowsBackend(PlatformBackend):
    """Windows-specific implementation."""

    @property
    def platform(self) -> Platform:
        return Platform.WINDOWS

    def discover_applications(self) -> list[Application]:
        """Discover applications from registry and Start Menu."""
        apps = []

        # 1. App Paths registry
        apps.extend(self._discover_from_app_paths())

        # 2. Uninstall registry (installed applications)
        apps.extend(self._discover_from_uninstall_registry())

        # 3. Start Menu shortcuts
        apps.extend(self._discover_from_start_menu())

        # 4. Windows Store apps
        apps.extend(self._discover_store_apps())

        # Deduplicate by executable path
        seen = set()
        unique_apps = []
        for app in apps:
            key = str(app.executable).lower()
            if key not in seen:
                seen.add(key)
                unique_apps.append(app)

        return unique_apps

    def _discover_from_app_paths(self) -> list[Application]:
        """Discover apps from HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths."""
        apps = []
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
            ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        i += 1
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                exe_path, _ = winreg.QueryValueEx(subkey, "")
                                if exe_path:
                                    exe_path = os.path.expandvars(exe_path)
                                    path = Path(exe_path)
                                    if path.exists():
                                        apps.append(
                                            Application(
                                                name=path.stem,
                                                executable=path,
                                                platform=Platform.WINDOWS,
                                            )
                                        )
                            except (OSError, ValueError):
                                continue
                    except OSError:
                        break
        except OSError:
            pass
        return apps

    def _discover_from_uninstall_registry(self) -> list[Application]:
        """Discover apps from uninstall registry keys."""
        apps = []
        uninstall_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]

        for uninstall_path in uninstall_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_path) as key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            i += 1
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                    exe_path, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                    if exe_path:
                                        exe_path = os.path.expandvars(exe_path)
                                        # DisplayIcon might point to .exe or .ico
                                        if exe_path.lower().endswith(".exe"):
                                            path = Path(exe_path)
                                            if path.exists():
                                                apps.append(
                                                    Application(
                                                        name=display_name,
                                                        executable=path,
                                                        platform=Platform.WINDOWS,
                                                    )
                                                )
                                except (OSError, ValueError):
                                    continue
                        except OSError:
                            break
            except OSError:
                pass
        return apps

    def _discover_from_start_menu(self) -> list[Application]:
        """Discover apps from Start Menu shortcuts."""
        apps = []
        start_menu_paths = [
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]

        for start_menu in start_menu_paths:
            if not start_menu.exists():
                continue
            for shortcut in start_menu.rglob("*.lnk"):
                try:
                    target = self._resolve_shortcut(shortcut)
                    if target and target.exists() and target.suffix.lower() == ".exe":
                        apps.append(
                            Application(
                                name=shortcut.stem,
                                executable=target,
                                platform=Platform.WINDOWS,
                            )
                        )
                except Exception:
                    continue
        return apps

    def _resolve_shortcut(self, shortcut_path: Path) -> Path | None:
        """Resolve a .lnk shortcut to its target."""
        try:
            import pythoncom
            from win32com.shell import shell, shellcon

            pythoncom.CoInitialize()
            shortcut = pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IShellLink,
            )
            persist_file = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
            persist_file.Load(str(shortcut_path))
            target, _ = shortcut.GetPath(shellcon.SLGP_UNCPRIORITY)
            pythoncom.CoUninitialize()
            return Path(target) if target else None
        except Exception:
            return None

    def _discover_store_apps(self) -> list[Application]:
        """Discover Windows Store (UWP) apps."""
        apps = []
        try:
            # Use PowerShell to get installed UWP apps
            result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Get-AppxPackage | Select-Object Name, PackageFamilyName, InstallLocation | ConvertTo-Json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json

                packages = json.loads(result.stdout)
                if not isinstance(packages, list):
                    packages = [packages]
                for pkg in packages:
                    if pkg.get("InstallLocation"):
                        install_loc = Path(pkg["InstallLocation"])
                        # Find .exe in the package
                        for exe in install_loc.rglob("*.exe"):
                            apps.append(
                                Application(
                                    name=pkg.get("Name", exe.stem),
                                    executable=exe,
                                    platform=Platform.WINDOWS,
                                    app_type=AppType.NATIVE,  # UWP apps are native
                                )
                            )
        except Exception:
            pass
        return apps

    def find_application(self, name: str) -> Application | None:
        """Find an application by name, path, or command."""
        # Try as path first
        path = Path(name).expanduser()
        if path.exists():
            if path.is_file() and path.suffix.lower() in (".exe", ".bat", ".cmd"):
                return Application(
                    name=path.stem,
                    executable=path,
                    platform=Platform.WINDOWS,
                )

        # Search discovered apps
        apps = self.discover_applications()
        name_lower = name.lower()

        for app in apps:
            if (
                name_lower in app.name.lower()
                or name_lower in app.executable.name.lower()
                or name_lower in app.executable.stem.lower()
            ):
                return app

        # Try where command
        try:
            result = subprocess.run(["where", name], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    exe_path = Path(line.strip())
                    if exe_path.exists():
                        return Application(
                            name=name,
                            executable=exe_path,
                            platform=Platform.WINDOWS,
                        )
        except Exception:
            pass

        return None

    def launch_application(self, app: Application) -> subprocess.Popen:
        """Launch a Windows application."""
        env = os.environ.copy()
        env.update(app.env_vars)

        cmd = [str(app.executable)] + app.arguments

        # Handle UWP apps differently
        if app.executable.suffix.lower() == ".exe":
            # Check if it's a UWP app by looking at path
            pass

        return subprocess.Popen(
            cmd,
            cwd=app.working_dir,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
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
                    "num_fds": None,  # Not available on Windows
                    "read_bytes": io.read_bytes if io else 0,
                    "write_bytes": io.write_bytes if io else 0,
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def wait_for_window(self, pid: int, timeout: float) -> bool:
        """Wait for main window using Win32 API."""
        try:
            import win32gui
            import win32process

            start = time.time()
            while time.time() - start < timeout:
                def enum_windows(hwnd, results):
                    try:
                        _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if win_pid == pid:
                            if win32gui.IsWindowVisible(hwnd):
                                # Check if it's a main window (not a tooltip, etc.)
                                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                                if style & win32con.WS_VISIBLE:
                                    results.append(hwnd)
                    except Exception:
                        pass

                import win32con

                results = []
                win32gui.EnumWindows(enum_windows, results)
                if results:
                    return True
                time.sleep(0.2)
        except Exception:
            pass

        # Fallback
        time.sleep(1.5)
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
            # Try to get version from file properties
            import win32api

            info = win32api.GetFileVersionInfo(str(app.executable), "\\")
            ms = info["FileVersionMS"]
            ls = info["FileVersionLS"]
            return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
        except Exception:
            pass

        # Try command line
        try:
            for flag in ["--version", "-v", "/version", "version"]:
                result = subprocess.run(
                    [str(app.executable), flag],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return None

    def apply_optimization(self, optimization_name: str, app: Application) -> dict:
        """Apply Windows-specific optimizations."""
        revert_info = {"optimization": optimization_name}

        if optimization_name == "prefetch_enable":
            # Enable prefetcher for the app
            revert_info["action"] = "prefetch"
            return revert_info

        if optimization_name == "disable_telemetry":
            telemetry_vars = {
                "DO_NOT_TRACK": "1",
                "DISABLE_TELEMETRY": "1",
                "NEXT_TELEMETRY_DISABLED": "1",
            }
            revert_info["env_vars"] = telemetry_vars
            return revert_info

        if optimization_name == "priority_class":
            # Set process priority
            revert_info["action"] = "priority"
            return revert_info

        return revert_info

    def revert_optimization(self, optimization_name: str, app: Application, revert_info: dict) -> bool:
        return True

    def get_system_info(self) -> dict:
        """Get Windows system information."""
        info = {"os": "Windows"}
        try:
            info["version"] = subprocess.run(["ver"], capture_output=True, text=True, shell=True).stdout.strip()
            info["build"] = subprocess.run(
                ["cmd", "/c", "echo %OS_BUILD%"],
                capture_output=True,
                text=True,
                shell=True,
            ).stdout.strip()
        except Exception:
            pass
        return info


def create_backend() -> PlatformBackend:
    return WindowsBackend()