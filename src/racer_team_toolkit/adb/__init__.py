"""Shared ADB command helpers."""

import re
import subprocess
from typing import Sequence

from racer_team_toolkit.config import DEVICES_REGISTRY, AndroidDevice


def run_adb_command(
    command: Sequence[str], *, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run an ADB command and return its completed process result."""

    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=check,
    )


def get_connected_serials() -> set[str]:
    """Return the serial numbers of all connected Android devices."""

    try:
        result = run_adb_command(["adb", "devices"], check=True)
        connected_serials = set()

        for line in result.stdout.splitlines():
            match = re.match(r"^\s*(\S+)\s+device\s*$", line)

            if match:
                connected_serials.add(match.group(1))

        return connected_serials

    except Exception as error:
        print(f"[!] Failed to detect connected devices: {error}")
        return set()


def get_conneccted_android_devices() -> list[AndroidDevice]:
    """Return a list of connected AndroidDevice instances based on the registry."""

    connected_serials = get_connected_serials()
    connected_devices = [
        device for device in DEVICES_REGISTRY if device.serial in connected_serials
    ]

    return connected_devices


__all__ = [
    "AndroidDevice",
    "DEVICES_REGISTRY",
    "get_connected_serials",
    "run_adb_command",
]
