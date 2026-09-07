from datetime import datetime

from rich.table import Table

from racer_team_toolkit.adb import get_connected_serials, run_adb_command
from racer_team_toolkit.config import MAX_DEVICE_TIME_DIFF_SECONDS, VIDEO_REMOTE_PATH, AndroidDevice
from racer_team_toolkit.reff_extractor.functions import get_connected_devices
from racer_team_toolkit.reff_extractor.time_adjustment_dataclasses import DeviceTimeInfo
from racer_team_toolkit.ui.functions import console


def get_pc_datetime() -> datetime:
    """Return the current date and time of the computer."""

    return datetime.now()


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


def calculate_time_difference_seconds(
    pc_datetime: datetime,
    device_datetime: datetime,
) -> float:
    """Return the number of seconds needed to correct the device clock."""

    difference = pc_datetime - device_datetime

    return difference.total_seconds()


def device_time_needs_fix(difference_seconds: float) -> bool:
    """Return True when the device clock differs too much from the PC clock."""

    return abs(difference_seconds) > MAX_DEVICE_TIME_DIFF_SECONDS


def get_devices_needing_time_fix(
    time_info: list[DeviceTimeInfo],
) -> list[DeviceTimeInfo]:
    """Return only devices whose clocks need correction."""

    return [device_info for device_info in time_info if device_info.needs_fix]


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


def format_time_difference(difference_seconds: float) -> str:
    """Return a readable signed time difference."""

    sign = "+" if difference_seconds >= 0 else "-"
    total_seconds = abs(int(difference_seconds))

    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)

    if days:
        return f"{sign}{days}d {hours:02}:{minutes:02}:{seconds:02}"

    return f"{sign}{hours:02}:{minutes:02}:{seconds:02}"


def print_device_time_table(
    pc_datetime: datetime,
    time_info: list[DeviceTimeInfo],
) -> None:
    """Display the PC and Android device clock comparison."""

    table = Table(
        title="Device Time Status",
        show_lines=True,
    )

    table.add_column("Device")
    table.add_column("Device Time")
    table.add_column("Difference")
    table.add_column("Status")

    for device_info in time_info:
        status = "[red]Needs Fix[/red]" if device_info.needs_fix else "[green]✓ OK[/green]"

        table.add_row(
            device_info.device.name,
            device_info.device_datetime.strftime("%d-%m-%Y %H:%M:%S"),
            format_time_difference(device_info.difference_seconds),
            status,
        )

    console.print()
    console.print(table)
    console.print(f"\nPC Time: {pc_datetime.strftime('%d-%m-%Y %H:%M:%S')}")


def get_remote_files(device: AndroidDevice, remote_path: str) -> list[str]:
    """Return all files under a remote Android directory."""

    result = run_adb_command(
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "find",
            remote_path,
            "-type",
            "f",
        ]
    )

    if result.returncode != 0:
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_remote_file_timestamp(
    device: AndroidDevice,
    file_path: str,
) -> int | None:
    """Return a remote file modification timestamp as Unix seconds."""

    result = run_adb_command(
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "stat",
            "-c",
            "%Y",
            file_path,
        ]
    )

    if result.returncode != 0:
        return None

    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def remote_file_matches_wrong_date(
    file_timestamp: int,
    wrong_datetime: datetime,
) -> bool:
    """Return True when the remote file was modified on the device's wrong date."""

    file_datetime = datetime.fromtimestamp(file_timestamp)

    return file_datetime.date() == wrong_datetime.date()


def adjust_time_for_reff() -> None:
    """Check device clocks and dry-run file detection for incorrect devices."""

    pc_datetime = get_pc_datetime()
    time_info = get_connected_device_time_info(pc_datetime)

    if not time_info:
        console.print("[yellow]No connected supported devices found.[/yellow]")
        return

    print_device_time_table(pc_datetime, time_info)

    incorrect_devices = get_devices_needing_time_fix(time_info)

    if not incorrect_devices:
        console.print("\n[green]✓ All connected device clocks are correct.[/green]")
        return

    console.print(f"\n[yellow]{len(incorrect_devices)} device(s) need time adjustment.[/yellow]")

    # Dry-run test:
    # Find files whose modification date matches the device's incorrect date.
    for device_info in incorrect_devices:
        device = device_info.device
        wrong_date = device_info.device_datetime.date()

        console.rule(f"[bold]{device.name}[/bold]")

        console.print(f"Wrong device date: [yellow]{wrong_date.strftime('%d-%m-%Y')}[/yellow]")

        reff_files = get_remote_files_from_wrong_date(
            device_info,
            device.remote_log_path,
        )

        video_files = get_remote_files_from_wrong_date(
            device_info,
            VIDEO_REMOTE_PATH,
        )

        console.print(f"\n[bold]REFF files found: {len(reff_files)}[/bold]")

        for file_path in reff_files:
            console.print(f"  {file_path}")

        console.print(f"\n[bold]Screen videos found: {len(video_files)}[/bold]")

        for file_path in video_files:
            console.print(f"  {file_path}")

        console.print()


def get_remote_files_from_wrong_date(
    device_info: DeviceTimeInfo,
    remote_path: str,
) -> list[str]:
    """Return remote files created on the device's current incorrect date."""

    matching_files = []

    remote_files = get_remote_files(
        device_info.device,
        remote_path,
    )

    for file_path in remote_files:
        timestamp = get_remote_file_timestamp(
            device_info.device,
            file_path,
        )

        if timestamp is None:
            continue

        if remote_file_matches_wrong_date(
            timestamp,
            device_info.device_datetime,
        ):
            matching_files.append(file_path)

    return matching_files
