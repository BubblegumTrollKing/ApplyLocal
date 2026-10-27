"""Installed-browser selection and opt-in discovery of an existing local session."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from .domain import AssistanceRequired
from .local_ai import loopback_url


BROWSERS = {
    "Google Chrome": ("Google/Chrome/Application/chrome.exe", "Google/Chrome/User Data", "google-chrome", "google-chrome"),
    "Microsoft Edge": ("Microsoft/Edge/Application/msedge.exe", "Microsoft/Edge/User Data", "microsoft-edge", "microsoft-edge"),
    "Brave": ("BraveSoftware/Brave-Browser/Application/brave.exe", "BraveSoftware/Brave-Browser/User Data", "brave-browser", "BraveSoftware/Brave-Browser"),
    "Chromium": ("Chromium/Application/chrome.exe", "Chromium/User Data", "chromium", "chromium"),
}


def installed_browsers() -> dict[str, str]:
    found = {}
    for name, (relative, _, command, _) in BROWSERS.items():
        if sys.platform == "win32":
            candidates = [Path(os.environ[key]) / relative
                          for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if os.environ.get(key)]
            executable = next((str(p) for p in candidates if p.is_file()), "")
        else:
            executable = shutil.which(command) or (shutil.which("chromium-browser") if name == "Chromium" else "")
        if executable:
            found[name] = executable
    return found


def browser_executable(name: str = "Automatic", custom: str = "") -> str:
    if custom:
        if Path(custom).is_file():
            return str(Path(custom).resolve())
        raise AssistanceRequired("The selected browser executable was not found.")
    available = installed_browsers()
    if name == "Automatic" and available:
        return next(iter(available.values()))
    if name in available:
        return available[name]
    raise AssistanceRequired("Choose an installed Chromium browser in Browser settings.")


def profile_directories(name: str = "Automatic") -> list[Path]:
    result = []
    for browser, (_, windows_profile, _, linux_profile) in BROWSERS.items():
        if name not in {"Automatic", browser}:
            continue
        if sys.platform == "win32":
            if os.environ.get("LOCALAPPDATA"):
                result.append(Path(os.environ["LOCALAPPDATA"]) / windows_profile)
        elif sys.platform == "darwin":
            mac = {"Google Chrome": "Google/Chrome", "Microsoft Edge": "Microsoft Edge",
                   "Brave": "BraveSoftware/Brave-Browser", "Chromium": "Chromium"}[browser]
            result.append(Path.home() / "Library/Application Support" / mac)
        else:
            result.append(Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / linux_profile)
    return result


def local_browser_endpoint(value: str) -> str:
    if not value.startswith("ws:"):
        return loopback_url(value)
    p = urlsplit(value)
    if (p.scheme != "ws" or p.hostname not in {"127.0.0.1", "localhost", "::1"}
            or p.username or p.password or p.fragment or not p.port
            or not re.fullmatch(r"/devtools/browser/[A-Za-z0-9_-]+", p.path)):
        raise ValueError("Use a local browser debugging address.")
    host = "[::1]" if p.hostname == "::1" else "127.0.0.1"
    return f"ws://{host}:{p.port}{p.path}" + ("?" + p.query if p.query else "")


def discover_existing(name: str = "Automatic", profile: str = "") -> str | None:
    folders = [Path(profile)] if profile else profile_directories(name)
    for folder in folders:
        try:
            # Only this endpoint descriptor is read. No cookies or login data.
            lines = (folder / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()
            port = int(lines[0])
            if not 1 <= port <= 65535 or len(lines) < 2:
                continue
            endpoint = local_browser_endpoint(f"ws://127.0.0.1:{port}{lines[1].strip()}")
            return endpoint
        except (OSError, ValueError, IndexError):
            continue
    return None


def connection_endpoint(settings) -> str:
    if settings.connection_mode == "existing":
        discovered = discover_existing(settings.browser_name, settings.browser_profile)
        if discovered:
            return discovered
    return local_browser_endpoint(settings.endpoint)


def open_debug_settings(name: str, custom: str = ""):
    if name == "Automatic" and not custom:
        name = next(iter(installed_browsers()), "Google Chrome")
    scheme = "edge" if name == "Microsoft Edge" else "brave" if name == "Brave" else "chrome"
    return subprocess.Popen([browser_executable(name, custom), f"{scheme}://inspect/#remote-debugging"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
