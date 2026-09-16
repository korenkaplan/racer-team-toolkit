"""Shared ADB command helpers."""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from racer_team_toolkit.config import DEVICES_REGISTRY, AndroidDevice


def run_adb_command(
    arguments: Sequence[str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run an ADB command using the resolved ADB executable."""

    adb_executable = get_adb_executable()

    return subprocess.run(
        [adb_executable, *arguments],
        capture_output=True,
        text=True,
        check=check,
    )


def get_connected_serials() -> set[str]:
    """Return the serial numbers of all connected Android devices."""

    try:
        result = run_adb_command(["devices"], check=True)
        connected_serials = set()

        for line in result.stdout.splitlines():
            match = re.match(r"^\s*(\S+)\s+device\s*$", line)

            if match:
                connected_serials.add(match.group(1))

        return connected_serials

    except Exception as error:
        print(f"[!] Failed to detect connected devices: {error}")
        return set()


def get_connected_android_devices() -> list[AndroidDevice]:
    """Return a list of connected AndroidDevice instances based on the registry."""

    connected_serials = get_connected_serials()
    connected_devices = [
        device for device in DEVICES_REGISTRY if device.serial in connected_serials
    ]

    return connected_devices


def get_adb_executable() -> str:
    """Return the ADB executable path for development or packaged builds."""

    # PyInstaller one-file build.
    if getattr(sys, "frozen", False):
        bundle_directory = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        bundled_adb = bundle_directory / "adb.exe"

        if bundled_adb.exists():
            return str(bundled_adb)

    # Development environment.
    system_adb = shutil.which("adb")

    if system_adb:
        return system_adb

    raise FileNotFoundError(
        "ADB was not found. Install Android Platform Tools "
        "or use the packaged Racer Team Toolkit build."
    )


__all__ = [
    "AndroidDevice",
    "DEVICES_REGISTRY",
    "get_connected_serials",
    "run_adb_command",
    "get_adb_executable",
]
