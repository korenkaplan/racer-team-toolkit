import re
from datetime import date, datetime
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
    """Compare absolute time and local wall-clock time with the computer."""

    device_epoch = get_device_epoch_seconds(device)
    device_datetime = get_device_local_datetime(device)

    if device_epoch is None or device_datetime is None:
        return None

    absolute_difference_seconds = pc_datetime.timestamp() - device_epoch
    local_difference_seconds = calculate_time_difference_seconds(
        pc_datetime.replace(microsecond=0),
        device_datetime,
    )

    absolute_time_needs_fix = device_time_needs_fix(
        absolute_difference_seconds,
    )
    local_time_needs_fix = device_time_needs_fix(
        local_difference_seconds,
    )

    return DeviceTimeInfo(
        device=device,
        device_datetime=device_datetime,
        difference_seconds=absolute_difference_seconds,
        needs_fix=(absolute_time_needs_fix or local_time_needs_fix),
        absolute_difference_seconds=absolute_difference_seconds,
        local_difference_seconds=local_difference_seconds,
        absolute_time_needs_fix=absolute_time_needs_fix,
        local_time_needs_fix=local_time_needs_fix,
    )


def get_device_epoch_seconds(device: AndroidDevice) -> int | None:
    """Read the Android device's absolute Unix time."""

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "date",
            "+%s",
        ]
    )

    if result.returncode != 0:
        return None

    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def get_device_local_datetime(device: AndroidDevice) -> datetime | None:
    """Read the Android device's displayed local wall-clock time."""

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "date",
            "+%Y-%m-%d_%H:%M:%S",
        ]
    )

    if result.returncode != 0:
        return None

    try:
        return datetime.strptime(
            result.stdout.strip(),
            "%Y-%m-%d_%H:%M:%S",
        )
    except ValueError:
        return None


def get_device_datetime(device: AndroidDevice) -> datetime | None:
    """Return the Android device's displayed local wall-clock time."""

    return get_device_local_datetime(device)


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
    table.add_column("Device Local Time")
    table.add_column("Absolute Diff")
    table.add_column("Local Diff")
    table.add_column("Status")

    for device_info in time_info:
        if device_info.absolute_time_needs_fix:
            status = "[red]Clock Needs Fix[/red]"
        elif device_info.local_time_needs_fix:
            status = "[yellow]Timezone / Local Time Needs Fix[/yellow]"
        else:
            status = "[green]✓ OK[/green]"

        table.add_row(
            device_info.device.name,
            device_info.device_datetime.strftime("%d-%m-%Y %H:%M:%S"),
            format_time_difference(device_info.absolute_difference_seconds),
            format_time_difference(device_info.local_difference_seconds),
            status,
        )

    console.print()
    console.print(table)
    console.print(f"\nPC Time: {pc_datetime.strftime('%d-%m-%Y %H:%M:%S')}")


def get_remote_files(device: AndroidDevice, remote_path: str) -> list[str]:
    """Return all files under a remote Android directory."""

    result = run_adb_command(
        [
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
    """Return files affected by the device's absolute or local-clock problem."""

    matching_files = []

    remote_files = get_remote_files(
        device_info.device,
        remote_path,
    )

    target_date = (
        device_info.device_datetime.date()
        if device_info.absolute_time_needs_fix
        else datetime.now().date()
    )

    for file_path in remote_files:
        timestamp = get_remote_file_timestamp(
            device_info.device,
            file_path,
        )

        if timestamp is None:
            continue

        file_datetime = datetime.fromtimestamp(timestamp)

        if file_datetime.date() == target_date:
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
    """Correct file timestamps and timestamp-based filenames."""

    corrected_count = 0

    for correction in corrections:
        timestamp_updated = True

        if correction.corrected_timestamp != correction.current_timestamp:
            timestamp_updated = set_remote_file_timestamp(
                device,
                correction.file_path,
                correction.corrected_timestamp,
            )

        if not timestamp_updated:
            console.print(
                "[red]✗ Failed to correct timestamp: "
                f"{PurePosixPath(correction.file_path).name}"
                "[/red]"
            )
            continue

        rename_succeeded = rename_corrected_remote_file(
            device,
            correction.file_path,
            correction.corrected_timestamp,
        )

        if not rename_succeeded:
            console.print(
                "[red]✗ Timestamp corrected but filename rename failed: "
                f"{PurePosixPath(correction.file_path).name}"
                "[/red]"
            )
            continue

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

        corrected_timestamp = (
            calculate_corrected_timestamp(
                current_timestamp,
                device_info.absolute_difference_seconds,
            )
            if device_info.absolute_time_needs_fix
            else current_timestamp
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
        "Device local time: "
        f"[yellow]{device_info.device_datetime.strftime('%d-%m-%Y %H:%M:%S')}[/yellow]"
    )

    console.print(
        "Absolute time difference: "
        f"[yellow]{format_time_difference(device_info.absolute_difference_seconds)}[/yellow]"
    )

    console.print(
        "Local clock difference: "
        f"[yellow]{format_time_difference(device_info.local_difference_seconds)}[/yellow]"
    )

    if device_info.absolute_time_needs_fix:
        console.print("[yellow]Action: correct file mtime and timestamp-based filenames.[/yellow]")
    elif device_info.local_time_needs_fix:
        console.print(
            "[yellow]Action: keep absolute mtime unchanged and correct timestamp-based filenames.[/yellow]"
        )

    console.print(f"REFF files found: [cyan]{reff_count}[/cyan]")

    console.print(f"Screen videos found: [cyan]{video_count}[/cyan]")

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

    console.print(f"\n[yellow]{len(incorrect_devices)} device(s) have an incorrect clock.[/yellow]")

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
    console.print("[bold yellow]⚠ The Android clocks are still incorrect.[/bold yellow]")
    console.print("Please manually correct the date and time on the affected device(s).")

    return correct_devices + corrected_devices


def get_devices_with_correct_time(
    devices: list[AndroidDevice],
    incorrect_devices: list[DeviceTimeInfo],
) -> list[AndroidDevice]:
    """Return connected devices whose clocks were already correct."""

    incorrect_serials = {device_info.device.serial for device_info in incorrect_devices}

    return [device for device in devices if device.serial not in incorrect_serials]


def correct_files_for_incorrect_devices(
    incorrect_devices: list[DeviceTimeInfo],
) -> list[AndroidDevice]:
    """Correct files and return devices whose corrections fully succeeded."""

    corrected_devices = []

    for device_info in incorrect_devices:
        corrections, reff_count, video_count = build_device_file_corrections(device_info)

        print_device_correction_plan(
            device_info,
            corrections,
            reff_count,
            video_count,
        )

        if not corrections:
            console.print("[yellow]No affected files found for this device.[/yellow]")
            corrected_devices.append(device_info.device)
            continue

        corrected_count = apply_file_time_corrections(
            device_info.device,
            corrections,
        )

        if corrected_count == len(corrections):
            console.print(
                f"[green]✓ {device_info.device.name}: {corrected_count} file(s) corrected.[/green]"
            )

            corrected_devices.append(device_info.device)
        else:
            console.print(
                f"[red]✗ {device_info.device.name}: "
                f"{corrected_count} of {len(corrections)} "
                "file(s) corrected.[/red]"
            )

            console.print("[yellow]Device will be skipped during extraction.[/yellow]")

    return corrected_devices


def timestamp_is_today(
    timestamp: int,
    today: date,
) -> bool:
    """Return whether a Unix timestamp belongs to today's local date."""

    return datetime.fromtimestamp(timestamp).date() == today


def get_remote_files_from_today(
    device: AndroidDevice,
    remote_path: str,
) -> list[str]:
    """Return remote files whose modification date is today."""

    today = datetime.now().date()
    matching_files = []

    for file_path in get_remote_files(device, remote_path):
        timestamp = get_remote_file_timestamp(
            device,
            file_path,
        )

        if timestamp is None:
            continue

        if timestamp_is_today(timestamp, today):
            matching_files.append(file_path)

    return matching_files


def build_corrected_reff_filename(
    corrected_timestamp: int,
    filename: str | None = None,
) -> str | None:
    """Build a corrected REFF name while preserving known suffixes."""

    corrected_datetime = datetime.fromtimestamp(corrected_timestamp)

    if filename is None:
        return corrected_datetime.strftime("%d_%m_%Y_%H_%M_%S") + ".reff"

    match = re.fullmatch(
        (
            r"^(?P<prefix>.*?)"
            r"\d{2}_\d{2}_\d{4}_\d{2}_\d{2}"
            r"(?P<seconds>_\d{2})?"
            r"(?P<number>_Number_\d+)?"
            r"\.reff$"
        ),
        filename,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    timestamp_format = (
        "%d_%m_%Y_%H_%M_%S"
        if match.group("seconds")
        else "%d_%m_%Y_%H_%M"
    )

    return (
        f"{match.group('prefix')}"
        f"{corrected_datetime.strftime(timestamp_format)}"
        f"{match.group('number') or ''}"
        ".reff"
    )


def build_corrected_video_filename(
    filename: str,
    corrected_timestamp: int,
) -> str | None:
    """Return a corrected name for a known timestamp-based video format."""

    corrected_datetime = datetime.fromtimestamp(corrected_timestamp)

    screen_rec_match = re.fullmatch(
        (
            r"^(?P<prefix>ScreenRec_)"
            r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}"
            r"(?P<seconds>-\d{2})?"
            r"(?P<number>_Number_\d+)?"
            r"\.mp4$"
        ),
        filename,
        flags=re.IGNORECASE,
    )

    if screen_rec_match is not None:
        timestamp_format = (
            "%Y-%m-%d_%H-%M-%S"
            if screen_rec_match.group("seconds")
            else "%Y-%m-%d_%H-%M"
        )

        return (
            f"{screen_rec_match.group('prefix')}"
            f"{corrected_datetime.strftime(timestamp_format)}"
            f"{screen_rec_match.group('number') or ''}"
            ".mp4"
        )

    full_screen_match = re.fullmatch(
        (
            r"^(?P<prefix>full_screen_)"
            r"\d{2}_\d{2}_\d{4}_\d{2}_\d{2}"
            r"(?P<seconds>_\d{2})?"
            r"(?P<number>_Number_\d+)?"
            r"\.mp4$"
        ),
        filename,
        flags=re.IGNORECASE,
    )

    if full_screen_match is None:
        return None

    timestamp_format = (
        "%d_%m_%Y_%H_%M_%S"
        if full_screen_match.group("seconds")
        else "%d_%m_%Y_%H_%M"
    )

    return (
        f"{full_screen_match.group('prefix')}"
        f"{corrected_datetime.strftime(timestamp_format)}"
        f"{full_screen_match.group('number') or ''}"
        ".mp4"
    )


def build_corrected_filename(
    file_path: str,
    corrected_timestamp: int,
) -> str | None:
    """Return a corrected filename when the file naming format contains a timestamp."""

    remote_path = PurePosixPath(file_path)

    suffix = remote_path.suffix.lower()

    if suffix == ".reff":
        return build_corrected_reff_filename(
            corrected_timestamp,
            remote_path.name,
        )

    if suffix == ".mp4":
        return build_corrected_video_filename(
            remote_path.name,
            corrected_timestamp,
        )

    return None


def remote_file_exists(
    device: AndroidDevice,
    file_path: str,
) -> bool:
    """Return whether a remote Android file exists."""

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "test",
            "-e",
            file_path,
        ]
    )

    return result.returncode == 0


def rename_corrected_remote_file(
    device: AndroidDevice,
    file_path: str,
    corrected_timestamp: int,
) -> bool:
    """Rename a remote file when its filename contains timestamp information."""

    remote_path = PurePosixPath(file_path)

    corrected_filename = build_corrected_filename(
        file_path,
        corrected_timestamp,
    )

    if corrected_filename is None:
        return True

    destination_path = build_unique_remote_path(
        device,
        remote_path.parent,
        corrected_filename,
        file_path,
    )

    if destination_path == file_path:
        return True

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "mv",
            file_path,
            destination_path,
        ]
    )

    return result.returncode == 0


def build_unique_remote_path(
    device: AndroidDevice,
    directory: PurePosixPath,
    filename: str,
    original_path: str,
) -> str:
    """Return an available remote path without overwriting another file."""

    candidate = str(directory / filename)

    if candidate == original_path or not remote_file_exists(
        device,
        candidate,
    ):
        return candidate

    filename_path = PurePosixPath(filename)

    counter = 1

    while True:
        candidate = str(
            directory / (f"{filename_path.stem}_Number_{counter}{filename_path.suffix}")
        )

        if not remote_file_exists(
            device,
            candidate,
        ):
            return candidate

        counter += 1
