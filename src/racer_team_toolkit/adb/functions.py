"""Shared ADB command helpers."""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from racer_team_toolkit.adb.device_detection import (
    DeviceType,
    classify_device,
)
from racer_team_toolkit.config import (
    DEVICE_TYPE_CONFIGS,
    AndroidDevice,
)


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
    """Detect, classify, and configure connected Android devices."""

    connected_devices = []

    for serial in get_connected_serials():
        model = get_device_model(serial)
        device_type = classify_device(model)

        if device_type == DeviceType.UNKNOWN:
            print(f"[!] Unsupported Android device: {model or 'Unknown model'} (Serial: {serial})")
            continue

        config = DEVICE_TYPE_CONFIGS[device_type.value]

        connected_devices.append(
            AndroidDevice(
                name=config.name,
                serial=serial,
                remote_log_path=config.remote_log_path,
                file_prefix=config.file_prefix,
                apk_name_pattern=config.apk_name_pattern,
                package_name=config.package_name,
                permissions=config.permissions,
            )
        )

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


def get_device_model(serial: str) -> str:
    """Return the Android model of a connected device."""

    result = run_adb_command(
        [
            "-s",
            serial,
            "shell",
            "getprop",
            "ro.product.model",
        ]
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


__all__ = [
    "AndroidDevice",
    "get_connected_serials",
    "run_adb_command",
    "get_adb_executable",
    "get_device_model",
]
