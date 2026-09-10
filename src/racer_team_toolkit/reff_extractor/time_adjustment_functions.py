from datetime import datetime
from pathlib import PurePosixPath

import questionary
from rich.table import Table
from racer_team_toolkit.adb import run_adb_command
from racer_team_toolkit.config import MAX_DEVICE_TIME_DIFF_SECONDS, VIDEO_REMOTE_PATH, AndroidDevice
from racer_team_toolkit.reff_extractor.time_adjustment_dataclasses import (
    DeviceTimeInfo,
    FileTimeCorrection,
)
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
    devices: list[AndroidDevice],
    pc_datetime: datetime,
) -> list[DeviceTimeInfo]:
    """Return clock information for the supplied connected devices."""

    time_info = []

    for device in devices:
        device_info = get_device_time_info(
            device,
            pc_datetime,
        )

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


def set_remote_file_timestamp(
    device: AndroidDevice,
    file_path: str,
    timestamp: int,
) -> bool:
    """Set a remote Android file modification time using Unix seconds."""

    result = run_adb_command(
        [
            "adb",
            "-s",
            device.serial,
            "shell",
            "touch",
            "-m",
            "-d",
            f"@{timestamp}",
            file_path,
        ]
    )

    return result.returncode == 0


def apply_file_time_corrections(
    device: AndroidDevice,
    corrections: list[FileTimeCorrection],
) -> int:
    """Apply approved timestamp corrections and return success count."""

    corrected_count = 0

    for correction in corrections:
        success = set_remote_file_timestamp(
            device,
            correction.file_path,
            correction.corrected_timestamp,
        )

        if success:
            corrected_count += 1

    return corrected_count


def adjust_remote_file_timestamp(
    device_info: DeviceTimeInfo,
    file_path: str,
) -> bool:
    """Correct one remote file timestamp using the device clock difference."""

    original_timestamp = get_remote_file_timestamp(
        device_info.device,
        file_path,
    )

    if original_timestamp is None:
        return False

    corrected_timestamp = calculate_corrected_timestamp(
        original_timestamp,
        device_info.difference_seconds,
    )

    return set_remote_file_timestamp(
        device_info.device,
        file_path,
        corrected_timestamp,
    )


def adjust_remote_files(
    device_info: DeviceTimeInfo,
    file_paths: list[str],
) -> int:
    """Correct timestamps for a collection of remote files."""

    adjusted_count = 0

    for file_path in file_paths:
        if adjust_remote_file_timestamp(device_info, file_path):
            adjusted_count += 1

    return adjusted_count


def build_file_time_corrections(
    device_info: DeviceTimeInfo,
    file_paths: list[str],
) -> list[FileTimeCorrection]:
    """Build timestamp corrections without modifying any files."""

    corrections = []

    for file_path in file_paths:
        current_timestamp = get_remote_file_timestamp(
            device_info.device,
            file_path,
        )

        if current_timestamp is None:
            continue

        corrected_timestamp = calculate_corrected_timestamp(
            current_timestamp,
            device_info.difference_seconds,
        )

        corrections.append(
            FileTimeCorrection(
                file_path=file_path,
                current_timestamp=current_timestamp,
                corrected_timestamp=corrected_timestamp,
            )
        )

    return corrections


def print_file_time_correction_table(
    device_info: DeviceTimeInfo,
    corrections: list[FileTimeCorrection],
) -> None:
    """Display the planned file timestamp corrections."""

    table = Table(
        title=f"{device_info.device.name} - Files Time Correction",
        show_lines=True,
    )

    table.add_column("Name")
    table.add_column("Current Date")
    table.add_column("After Correction")

    for correction in corrections:
        table.add_row(
            PurePosixPath(correction.file_path).name,
            datetime.fromtimestamp(correction.current_timestamp).strftime("%d-%m-%Y %H:%M:%S"),
            datetime.fromtimestamp(correction.corrected_timestamp).strftime("%d-%m-%Y %H:%M:%S"),
        )

    console.print()
    console.print(table)


def calculate_corrected_timestamp(
    file_timestamp: int,
    difference_seconds: float,
) -> int:
    """Return the corrected Unix timestamp for a file."""

    return int(file_timestamp + difference_seconds)


def ask_apply_time_corrections() -> bool:
    """Ask the user whether to apply the displayed timestamp corrections."""

    choice = questionary.select(
        "Apply these timestamp corrections?",
        choices=[
            "Yes",
            "Cancel",
        ],
    ).ask()

    return choice == "Yes"


def adjust_time_for_reff() -> None:
    """Correct file timestamps created while Android clocks were incorrect."""

    pc_datetime = get_pc_datetime()
    time_info = get_connected_device_time_info(pc_datetime)

    if not time_info:
        console.print("[yellow]No connected supported devices found.[/yellow]")
        return

    print_device_time_table(
        pc_datetime,
        time_info,
    )

    incorrect_devices = get_devices_needing_time_fix(time_info)

    if not incorrect_devices:
        console.print("\n[green]✓ All connected device clocks are correct.[/green]")
        return

    console.print(f"\n[yellow]{len(incorrect_devices)} device(s) need time adjustment.[/yellow]")

    correction_plans = []

    for device_info in incorrect_devices:
        device = device_info.device

        reff_files = get_remote_files_from_wrong_date(
            device_info,
            device.remote_log_path,
        )

        video_files = get_remote_files_from_wrong_date(
            device_info,
            VIDEO_REMOTE_PATH,
        )

        files_to_adjust = reff_files + video_files

        console.rule(f"[bold]{device.name}[/bold]")

        console.print(
            "Wrong device date: "
            f"[yellow]"
            f"{device_info.device_datetime.strftime('%d-%m-%Y')}"
            f"[/yellow]"
        )

        console.print(
            "Time correction: "
            f"[yellow]"
            f"{format_time_difference(device_info.difference_seconds)}"
            f"[/yellow]"
        )

        console.print(f"REFF files found: [cyan]{len(reff_files)}[/cyan]")

        console.print(f"Screen videos found: [cyan]{len(video_files)}[/cyan]")

        if not files_to_adjust:
            console.print("\n[yellow]No files found on the incorrect device date.[/yellow]")
            continue

        corrections = build_file_time_corrections(
            device_info,
            files_to_adjust,
        )

        if not corrections:
            console.print("\n[yellow]Could not build any file corrections.[/yellow]")
            continue

        print_file_time_correction_table(
            device_info,
            corrections,
        )

        correction_plans.append(
            (
                device_info,
                corrections,
                len(reff_files),
                len(video_files),
            )
        )

    if not correction_plans:
        return

    if not ask_apply_time_corrections():
        console.print("\n[yellow]No files were changed.[/yellow]")
        return

    for device_info, corrections, reff_count, video_count in correction_plans:
        corrected_count = apply_file_time_corrections(
            device_info.device,
            corrections,
        )

        console.print()
        console.print(
            f"[green]✓ {device_info.device.name}: {corrected_count} file(s) corrected.[/green]"
        )

        console.print(f"  REFF files: {reff_count}")
        console.print(f"  Screen videos: {video_count}")

    console.print()
    console.print("[bold yellow]⚠ The Android device clock is still incorrect.[/bold yellow]")

    console.print("Please manually correct the date and time on the affected device(s).")

def build_device_file_corrections(
    device_info: DeviceTimeInfo,
) -> tuple[list[FileTimeCorrection], int, int]:
    """Build REFF and video corrections for one incorrect device."""

    device = device_info.device

    reff_files = get_remote_files_from_wrong_date(
        device_info,
        device.remote_log_path,
    )

    video_files = get_remote_files_from_wrong_date(
        device_info,
        VIDEO_REMOTE_PATH,
    )

    files_to_adjust = reff_files + video_files

    corrections = build_file_time_corrections(
        device_info,
        files_to_adjust,
    )

    return corrections, len(reff_files), len(video_files)


def print_device_correction_plan(
    device_info: DeviceTimeInfo,
    corrections: list[FileTimeCorrection],
    reff_count: int,
    video_count: int,
) -> None:
    """Display files that will be corrected for one device."""

    console.rule(f"[bold]{device_info.device.name}[/bold]")

    console.print(
        "Wrong device date: "
        f"[yellow]{device_info.device_datetime.strftime('%d-%m-%Y')}[/yellow]"
    )

    console.print(
        "Time correction: "
        f"[yellow]{format_time_difference(device_info.difference_seconds)}[/yellow]"
    )

    console.print(
        f"REFF files found: [cyan]{reff_count}[/cyan]"
    )

    console.print(
        f"Screen videos found: [cyan]{video_count}[/cyan]"
    )

    if corrections:
        print_file_time_correction_table(
            device_info,
            corrections,
        )

def validate_device_times_before_extraction(
    devices: list[AndroidDevice],
) -> list[AndroidDevice]:
    """Return devices that may continue to extraction.

    Incorrect devices are corrected when approved by the user.
    If correction is declined or fails, only those devices are skipped.
    """

    pc_datetime = get_pc_datetime()

    time_info = get_connected_device_time_info(
        devices,
        pc_datetime,
    )

    incorrect_devices = get_devices_needing_time_fix(
        time_info,
    )

    if not incorrect_devices:
        return devices

    print_device_time_table(
        pc_datetime,
        time_info,
    )

    console.print(
        f"\n[yellow]{len(incorrect_devices)} "
        "device(s) have an incorrect clock.[/yellow]"
    )

    if not ask_apply_time_corrections():
        return get_devices_with_correct_time(
            devices,
            incorrect_devices,
        )

    corrected_devices = correct_files_for_incorrect_devices(
        incorrect_devices,
    )

    correct_devices = get_devices_with_correct_time(
        devices,
        incorrect_devices,
    )

    console.print()
    console.print(
        "[bold yellow]"
        "⚠ The Android clocks are still incorrect."
        "[/bold yellow]"
    )
    console.print(
        "Please manually correct the date and time "
        "on the affected device(s)."
    )

    return correct_devices + corrected_devices

def get_devices_with_correct_time(
    devices: list[AndroidDevice],
    incorrect_devices: list[DeviceTimeInfo],
) -> list[AndroidDevice]:
    """Return connected devices whose clocks were already correct."""

    incorrect_serials = {
        device_info.device.serial
        for device_info in incorrect_devices
    }

    return [
        device
        for device in devices
        if device.serial not in incorrect_serials
    ]

def correct_files_for_incorrect_devices(
    incorrect_devices: list[DeviceTimeInfo],
) -> list[AndroidDevice]:
    """Correct files and return devices whose corrections fully succeeded."""

    corrected_devices = []

    for device_info in incorrect_devices:
        corrections, reff_count, video_count = build_device_file_corrections(
            device_info
        )

        print_device_correction_plan(
            device_info,
            corrections,
            reff_count,
            video_count,
        )

        if not corrections:
            console.print(
                "[yellow]No affected files found for this device.[/yellow]"
            )
            corrected_devices.append(device_info.device)
            continue

        corrected_count = apply_file_time_corrections(
            device_info.device,
            corrections,
        )

        if corrected_count == len(corrections):
            console.print(
                f"[green]✓ {device_info.device.name}: "
                f"{corrected_count} file(s) corrected.[/green]"
            )

            corrected_devices.append(
                device_info.device
            )
        else:
            console.print(
                f"[red]✗ {device_info.device.name}: "
                f"{corrected_count} of {len(corrections)} "
                "file(s) corrected.[/red]"
            )

            console.print(
                "[yellow]Device will be skipped during extraction.[/yellow]"
            )

    return corrected_devices