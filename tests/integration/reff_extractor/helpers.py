import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from racer_team_toolkit.config import AndroidDevice

from tests.integration.reff_extractor.config import (
    TEST_REMOTE_REFF_PATH,
    TEST_REMOTE_ROOT,
    TEST_REMOTE_VIDEO_PATH,
)


def run_adb(
    serial: str,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ADB against one fixed integration-test device."""

    return subprocess.run(
        [
            "adb",
            "-s",
            serial,
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
    )


def connected_serials() -> set[str]:
    """Return serials currently reported by adb devices."""

    result = subprocess.run(
        ["adb", "devices"],
        capture_output=True,
        text=True,
        check=True,
    )

    serials: set[str] = set()

    for line in result.stdout.splitlines()[1:]:
        parts = line.split()

        if len(parts) >= 2 and parts[1] == "device":
            serials.add(parts[0])

    return serials


def clear_remote_test_area(serial: str) -> None:
    """Delete only the isolated integration-test directory."""

    run_adb(
        serial,
        "shell",
        "rm",
        "-rf",
        TEST_REMOTE_ROOT,
    )


def prepare_remote_test_area(serial: str) -> None:
    """Create isolated REFF/video directories for integration tests."""

    run_adb(
        serial,
        "shell",
        "mkdir",
        "-p",
        TEST_REMOTE_REFF_PATH,
        TEST_REMOTE_VIDEO_PATH,
    )


def copy_with_timestamp(
    source: Path,
    destination: Path,
    timestamp: float,
) -> Path:
    """Copy a test asset and assign an exact modification time."""

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        destination,
    )

    os.utime(
        destination,
        (
            timestamp,
            timestamp,
        ),
    )

    return destination


def create_local_test_file(
    root: Path,
    source: Path,
    filename: str,
    timestamp: float,
) -> Path:
    """Create one local grouping fixture from a master source file."""

    return copy_with_timestamp(
        source,
        root / filename,
        timestamp,
    )


def push_named_file(
    serial: str,
    source: Path,
    remote_directory: str,
    remote_filename: str,
    timestamp: float,
    staging_directory: Path,
) -> str:
    """Push one master test file under a controlled name and timestamp."""

    local_file = copy_with_timestamp(
        source,
        staging_directory / serial / remote_filename,
        timestamp,
    )

    prepare_remote_test_area(serial)

    remote_path = f"{remote_directory}/{remote_filename}"

    run_adb(
        serial,
        "push",
        "-a",
        str(local_file),
        remote_path,
    )

    return remote_path


def build_test_device(
    serial: str,
    device_type: str,
) -> AndroidDevice:
    """Build an AndroidDevice that reads only from isolated test paths."""

    return AndroidDevice(
        name=f"{device_type} Test Device",
        serial=serial,
        remote_log_path=TEST_REMOTE_REFF_PATH,
        file_prefix=device_type,
        apk_name_pattern="",
        package_name="",
    )


def timestamp_today(
    hour: int,
    minute: int,
    second: int,
) -> float:
    """Return today's local timestamp at the supplied clock time."""

    now = datetime.now()

    return now.replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=0,
    ).timestamp()
