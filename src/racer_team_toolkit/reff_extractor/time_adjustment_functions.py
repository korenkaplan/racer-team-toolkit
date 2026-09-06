from datetime import datetime

from rich.progress import console

from racer_team_toolkit.adb import get_connected_serials, run_adb_command
from racer_team_toolkit.config import MAX_DEVICE_TIME_DIFF_SECONDS, AndroidDevice
from racer_team_toolkit.reff_extractor.functions import get_connected_devices
from racer_team_toolkit.reff_extractor.time_adjustment_dataclasses import DeviceTimeInfo


def device_time_needs_fix(difference_seconds: float) -> bool:
    """Return True when the device clock differs too much from the PC clock."""

    return abs(difference_seconds) > MAX_DEVICE_TIME_DIFF_SECONDS


def calculate_time_difference_seconds(
    pc_datetime: datetime,
    device_datetime: datetime,
) -> float:
    """Return the number of seconds needed to correct the device clock."""

    difference = pc_datetime - device_datetime

    return difference.total_seconds()


def get_device_datetime(device: AndroidDevice) -> datetime | None:
    """Read the current date and time from an Android device."""

    result = run_adb_command(["adb", "-s", device.serial, "shell", "date", "+%s"])

    if result.returncode != 0:
        return None

    try:
        timestamp = int(result.stdout.strip())
    except ValueError:
        return None

    return datetime.fromtimestamp(timestamp)


def get_pc_datetime() -> datetime:
    """Return the current date and time of the computer."""

    return datetime.now()


def get_connected_device_time_info(
    pc_datetime: datetime,
) -> list[DeviceTimeInfo]:
    """Return clock information for all connected registered devices."""

    connected_serials = get_connected_serials()
    connected_devices = get_connected_devices(connected_serials)

    time_info = []

    for device in connected_devices:
        device_info = get_device_time_info(device, pc_datetime)

        if device_info is not None:
            time_info.append(device_info)

    return time_info


def get_devices_needing_time_fix(
    time_info: list[DeviceTimeInfo],
) -> list[DeviceTimeInfo]:
    """Return only devices whose clocks need correction."""

    return [device_info for device_info in time_info if device_info.needs_fix]


def get_device_time_info(
    device: AndroidDevice,
    pc_datetime: datetime,
) -> DeviceTimeInfo | None:
    """Compare one Android device clock with the computer clock."""

    device_datetime = get_device_datetime(device)

    if device_datetime is None:
        return None

    difference_seconds = calculate_time_difference_seconds(
        pc_datetime,
        device_datetime,
    )

    return DeviceTimeInfo(
        device=device,
        device_datetime=device_datetime,
        difference_seconds=difference_seconds,
        needs_fix=device_time_needs_fix(difference_seconds),
    )


def adjust_time_for_reff() -> None:
    """Check connected Android device clocks against the computer clock."""

    pc_datetime = get_pc_datetime()

    time_info = get_connected_device_time_info(pc_datetime)

    if not time_info:
        console.print("[yellow]No connected supported devices found.[/yellow]")
        return

    incorrect_devices = get_devices_needing_time_fix(time_info)

    print(f"PC time: {pc_datetime}")

    for device_info in time_info:
        print(
            device_info.device.name,
            device_info.device_datetime,
            device_info.difference_seconds,
            device_info.needs_fix,
        )

    print(f"Devices needing fix: {len(incorrect_devices)}")
