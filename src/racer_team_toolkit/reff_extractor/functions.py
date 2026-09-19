"""Reusable REFF and screen-video extraction functions."""

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import PurePosixPath

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TransferSpeedColumn,
)

from racer_team_toolkit.adb import (
    get_adb_executable,
    get_connected_android_devices,
    run_adb_command,
)
from racer_team_toolkit.adb.device_detection import DeviceType
from racer_team_toolkit.config import (
    LOCAL_DUMP_DIR,
    MAX_FLIGHT_TIME_DIFF,
    PROJECT_STATUS,
    SUPPORTED_DEVICE_TYPES,
    VIDEO_FILE_PREFIX,
    VIDEO_REMOTE_PATH,
    AndroidDevice,
)
from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
    FlightFile,
    FlightFileType,
)
from racer_team_toolkit.reff_extractor.time_adjustment_functions import (
    get_remote_files_from_today,
    validate_device_times_before_extraction,
)
from racer_team_toolkit.ui.functions import (
    console,
    print_extraction_summary,
    print_flight_table,
)

MIN_REFF_FILE_SIZE_BYTES = 500_000
MIN_VIDEO_FILE_SIZE_BYTES = 5_000_000

MAX_VIDEO_AFTER_REFF_SECONDS = 60
MAX_REFF_AFTER_VIDEO_SECONDS = 8 * 60


def extract_reff() -> None:
    """Extract REFF files from connected devices without screen videos."""

    run_extraction(include_videos=False)


def extract_reff_and_videos() -> None:
    """Extract REFF files and screen videos from connected devices."""

    run_extraction(include_videos=True)


def run_extraction(*, include_videos: bool) -> None:
    """Run the shared extraction workflow for one menu option."""

    create_output_directory()

    next_flight_number = get_next_flight_number()

    connected_devices = get_connected_android_devices()

    if not connected_devices:
        print("[-] No Supported Devices Are Connected. Please connect a device and try again.")
        return

    devices_to_process = validate_device_times_before_extraction(connected_devices)

    if not devices_to_process:
        console.print(
            "\n[yellow]No devices with valid file timestamps remain. Extraction cancelled.[/yellow]"
        )
        return

    print_connected_devices(devices_to_process)

    connected_device_types: tuple[str, ...] = tuple(
        device.file_prefix for device in devices_to_process
    )

    processed_any = False
    copied_reff_files = 0
    copied_videos = 0
    flights: list[Flight] = []

    for device in devices_to_process:
        result = process_device(
            device,
            include_videos=include_videos,
        )

        copied_reff_files += result["reff_files"]
        copied_videos += result["videos"]
        processed_any = True

    if processed_any:
        flights = group_files_into_flights(
            starting_flight_number=next_flight_number,
        )

    print_extraction_result(
        processed_any,
        flights,
        copied_reff_files,
        copied_videos,
        include_videos,
        connected_device_types,
    )


def print_connected_devices(devices: list[AndroidDevice]) -> None:
    """Print the connected-device count and identity details."""

    print(f"[+] Connected devices: {len(devices)}")
    for device in devices:
        print(f"    {device.name} (Serial: {device.serial})")


def print_extraction_result(
    processed_any: bool,
    flights: list[Flight],
    copied_reff_files: int,
    copied_videos: int,
    include_videos: bool,
    device_types: tuple[str, ...],
) -> None:
    """Print the extraction completion message."""

    print("\n==================================================")

    if processed_any:
        console.print("[bold green]✓ Extraction completed successfully[/bold green]")

        if flights:
            print_flight_table(
                flights,
                device_types,
                include_videos=include_videos,
            )

        summary: dict[str, int] = {
            "Flight folders created": len(flights),
            f"REFF files {get_transfer_verb().lower()}": copied_reff_files,
        }

        if include_videos:
            summary[f"Screen videos {get_transfer_verb().lower()}"] = copied_videos

        print_extraction_summary(summary)

        print(f"\n[V] All files are located at:\n    {os.path.abspath(LOCAL_DUMP_DIR)}")

    else:
        print("[!] No matched devices were processed.")

    print("=============================================================")


def create_output_directory() -> None:
    """Create the local extraction directory if it does not exist."""

    os.makedirs(LOCAL_DUMP_DIR, exist_ok=True)


def get_device_type_from_filename(filename: str) -> DeviceType | None:
    """Return the registered device type encoded in a filename."""

    normalized_filename = filename.upper().replace(" ", "_")

    for device_type in SUPPORTED_DEVICE_TYPES:
        if normalized_filename.startswith(f"{device_type}_"):
            return DeviceType(device_type)

    return None


def get_video_device_type(
    filename: str,
) -> DeviceType | None:
    """Return the registered device type encoded in a video filename."""

    normalized_filename = filename.upper().replace(" ", "_")

    for device_type in SUPPORTED_DEVICE_TYPES:
        if normalized_filename.startswith(f"{VIDEO_FILE_PREFIX}_{device_type}"):
            return DeviceType(device_type)

    return None


def get_video_files() -> list[FlightFile]:
    """Return standalone downloaded videos from the dump directory."""

    videos: list[FlightFile] = []

    for filename in os.listdir(LOCAL_DUMP_DIR):
        if not filename.upper().startswith(f"{VIDEO_FILE_PREFIX}_"):
            continue

        file_path = os.path.join(
            LOCAL_DUMP_DIR,
            filename,
        )

        if not os.path.isfile(file_path):
            continue

        device_type = get_video_device_type(filename)

        if device_type is None:
            continue

        try:
            videos.append(
                FlightFile(
                    filename=filename,
                    path=file_path,
                    device_type=device_type,
                    file_type=FlightFileType.VIDEO,
                    mtime=os.path.getmtime(file_path),
                    size=os.path.getsize(file_path),
                )
            )

        except OSError:
            continue

    return videos


def attach_videos_to_flight(
    flight_dir: str,
    videos: list[FlightFile],
) -> int:
    """Move matched videos into a flight directory."""

    moved_count = 0

    for video in videos:
        destination = os.path.join(
            flight_dir,
            video.filename,
        )

        try:
            shutil.move(
                video.path,
                destination,
            )

            moved_count += 1

        except OSError as error:
            print(f"[!] Failed to move screen video {video.filename}: {error}")

    return moved_count


def group_files_into_flights(
    starting_flight_number: int,
) -> list[Flight]:
    """Group compatible REFF files into flight folders."""

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return []

    files = collect_reff_files()

    if not files:
        return []

    files.sort(key=lambda file_info: file_info.mtime)

    used_indexes: set[int] = set()
    flights: list[Flight] = []

    flight_number = starting_flight_number

    for index in range(len(files)):
        if index in used_indexes:
            continue

        selected_files, selected_indexes = select_flight_files(
            files,
            index,
            used_indexes,
        )

        # Phase 1 creates a folder only when two or more
        # REFF files are matched.
        if len(selected_files) < 2:
            continue

        flight_name, flight_dir = create_flight_directory(
            flight_number,
            selected_files[0].mtime,
        )

        move_flight_files(
            flight_dir,
            selected_files,
        )

        used_indexes.update(selected_indexes)

        flights.append(
            Flight(
                number=flight_number,
                name=flight_name,
                path=flight_dir,
                reff_files=selected_files,
            )
        )

        flight_number += 1

    return flights


def collect_reff_files() -> list[FlightFile]:
    """Collect standalone REFF files from the dump directory."""

    files: list[FlightFile] = []

    for filename in os.listdir(LOCAL_DUMP_DIR):
        file_path = os.path.join(
            LOCAL_DUMP_DIR,
            filename,
        )

        if not os.path.isfile(file_path):
            continue

        device_type = get_device_type_from_filename(filename)

        if device_type is None:
            continue

        try:
            files.append(
                FlightFile(
                    filename=filename,
                    path=file_path,
                    device_type=device_type,
                    file_type=FlightFileType.REFF,
                    mtime=os.path.getmtime(file_path),
                    size=os.path.getsize(file_path),
                )
            )

        except OSError:
            continue

    return files


def select_flight_files(
    files: list[FlightFile],
    base_index: int,
    used_indexes: set[int],
) -> tuple[list[FlightFile], set[int]]:
    """Select the best compatible REFF from each device type."""

    base_file = files[base_index]

    selected_files: list[FlightFile] = [base_file]

    selected_indexes: set[int] = {base_index}

    candidates_by_type = collect_flight_candidates(
        files,
        base_index,
        used_indexes,
    )

    for candidates in candidates_by_type.values():
        candidates.sort(
            key=lambda candidate: (
                0
                if same_clock_minute(
                    candidate.mtime,
                    base_file.mtime,
                )
                else 1,
                -candidate.size,
                abs(candidate.mtime - base_file.mtime),
            )
        )

        selected_candidate = candidates[0]

        selected_index = files.index(selected_candidate)

        proposed_files = selected_files + [selected_candidate]

        if flight_is_within_time_limit(proposed_files):
            selected_files.append(selected_candidate)

            selected_indexes.add(selected_index)

    return (
        selected_files,
        selected_indexes,
    )


def collect_flight_candidates(
    files: list[FlightFile],
    base_index: int,
    used_indexes: set[int],
) -> dict[DeviceType, list[FlightFile]]:
    """Collect compatible REFF candidates by device type."""

    base_file = files[base_index]

    candidates_by_type: dict[
        DeviceType,
        list[FlightFile],
    ] = {}

    for index in range(
        base_index + 1,
        len(files),
    ):
        if index in used_indexes:
            continue

        candidate = files[index]

        # Files are already sorted by mtime.
        # Once we pass the maximum time difference,
        # later files cannot match this base REFF.
        if candidate.mtime - base_file.mtime > MAX_FLIGHT_TIME_DIFF:
            break

        # Only one REFF from each device type
        # may belong to the same flight.
        if candidate.device_type == base_file.device_type:
            continue

        candidates_by_type.setdefault(
            candidate.device_type,
            [],
        ).append(candidate)

    return candidates_by_type


def same_clock_minute(first_timestamp: float, second_timestamp: float) -> bool:
    """Return whether two timestamps occur in the same local clock minute."""

    first_minute = datetime.fromtimestamp(first_timestamp).replace(second=0, microsecond=0)
    second_minute = datetime.fromtimestamp(second_timestamp).replace(second=0, microsecond=0)
    return first_minute == second_minute


def flight_is_within_time_limit(
    flight_files: list[FlightFile],
) -> bool:
    """Return whether all REFF end times fit within the flight time window."""

    if not flight_files:
        return False

    timestamps: list[float] = [file_info.mtime for file_info in flight_files]

    return max(timestamps) - min(timestamps) <= MAX_FLIGHT_TIME_DIFF


def get_next_flight_number() -> int:
    """Return the next number based on existing top-level flight items."""

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return 1

    flight_count = 0

    for name in os.listdir(LOCAL_DUMP_DIR):
        path = os.path.join(
            LOCAL_DUMP_DIR,
            name,
        )

        if os.path.isdir(path) and name.startswith("Flight_"):
            flight_count += 1
            continue

        if not os.path.isfile(path):
            continue

        if name.upper().startswith(f"{VIDEO_FILE_PREFIX}_"):
            flight_count += 1
            continue

        if name.lower().endswith(".reff") and get_device_type_from_filename(name) is not None:
            flight_count += 1

    return flight_count + 1


def create_flight_directory(flight_number: int, first_file_mtime: float) -> tuple[str, str]:
    """Create a flight directory named with its number and first-file timestamp."""

    while True:
        timestamp = datetime.fromtimestamp(first_file_mtime).strftime("%d-%m-%Y_%H-%M-%S")
        flight_name = f"Flight_{flight_number:02d}_{timestamp}"
        flight_dir = os.path.join(LOCAL_DUMP_DIR, flight_name)

        if not os.path.exists(flight_dir):
            os.makedirs(flight_dir)
            return flight_name, flight_dir

        flight_number += 1


def move_flight_files(
    flight_dir: str,
    flight_files: list[FlightFile],
) -> None:
    """Move selected REFF files into a flight directory."""

    for file_info in flight_files:
        destination = os.path.join(
            flight_dir,
            file_info.filename,
        )

        try:
            shutil.move(
                file_info.path,
                destination,
            )

        except OSError as error:
            print(f"[!] Failed to move REFF file {file_info.filename}: {error}")


def process_device(
    device: AndroidDevice,
    *,
    include_videos: bool = True,
) -> dict[str, int]:
    """Pull REFF files from one device and optionally pull its videos."""

    print(f"\n[--->] Starting {get_transfer_verb().lower()} from: {device.name}")

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        transient=False,
    ) as progress:
        reff_task_id = progress.add_task(
            f"REFF: {get_transfer_verb()} 0 of 0 files",
            total=0,
        )

        create_output_directory()

        reff_files = pull_reff_files(
            device,
            progress,
            reff_task_id,
        )

        videos = 0

        if include_videos:
            video_task_id = progress.add_task(
                f"Videos: {get_transfer_verb()} 0 of 0 files",
                total=0,
            )

            videos = pull_videos(
                device,
                progress,
                video_task_id,
            )

    print(f"[<---] Finished {get_transfer_verb().lower()} from: {device.name}")

    return {
        "reff_files": reff_files,
        "videos": videos,
    }


def build_pull_command(
    serial: str,
    remote_file: str,
    local_directory: str,
) -> list[str]:
    """Build an ADB command for pulling one remote file."""

    return [
        "-s",
        serial,
        "pull",
        "-a",
        remote_file,
        local_directory,
    ]


def move_record_files(
    records_dir: str,
    device: AndroidDevice,
) -> int:
    """Move record files into the dump directory with device prefixes."""

    copied_count = 0

    for root, _, filenames in os.walk(records_dir):
        for filename in filenames:
            source_path = os.path.join(
                root,
                filename,
            )

            prefixed_filename = add_device_prefix(
                filename,
                device.file_prefix,
            )

            destination_path = os.path.join(
                LOCAL_DUMP_DIR,
                prefixed_filename,
            )

            try:
                original_mtime = os.path.getmtime(source_path)

                transfer_file(
                    source_path,
                    destination_path,
                )

                if PROJECT_STATUS == "production":
                    os.utime(
                        destination_path,
                        (
                            original_mtime,
                            original_mtime,
                        ),
                    )

                else:
                    os.remove(source_path)

                copied_count += 1

            except OSError as error:
                print(f"[!] Failed to move a REFF file: {error}")

    return copied_count


def add_device_prefix(filename: str, file_prefix: str) -> str:
    """Return a filename with a device prefix unless it already has one."""

    if filename.startswith(f"{file_prefix}_"):
        return filename

    return f"{file_prefix}_{filename}"


def remove_empty_directories(directory: str) -> None:
    """Remove empty directories below a directory, deepest first."""

    for root, _, _ in os.walk(directory, topdown=False):
        try:
            os.rmdir(root)
        except OSError:
            pass


def pull_videos(
    device: AndroidDevice,
    progress: Progress,
    task_id: TaskID,
) -> int:
    """Pull today's valid screen recordings from one Android device."""

    video_files = get_remote_files_from_today(
        device,
        VIDEO_REMOTE_PATH,
    )

    video_file_sizes = filter_remote_files_by_size(
        device,
        video_files,
        MIN_VIDEO_FILE_SIZE_BYTES,
    )

    video_files = list(video_file_sizes)

    total_video_files = len(video_files)

    total_video_bytes = sum(video_file_sizes.values())

    progress.update(
        task_id,
        total=total_video_bytes,
        completed=0,
        description=(f"Videos: {get_transfer_verb()} 0 of {total_video_files} files"),
    )

    if not video_files:
        return 0

    videos_dir = os.path.join(
        LOCAL_DUMP_DIR,
        "Screen-Videos",
    )

    os.makedirs(
        videos_dir,
        exist_ok=True,
    )

    for file_number, remote_file in enumerate(
        video_files,
        start=1,
    ):
        pull_remote_file(
            device,
            remote_file,
            videos_dir,
            progress,
            task_id,
            (f"Videos: {get_transfer_verb()} {file_number} of {total_video_files} files"),
        )

    video_count = move_video_files(
        videos_dir,
        device,
    )

    remove_empty_directories(videos_dir)

    return video_count


def move_video_files(
    videos_dir: str,
    device: AndroidDevice,
) -> int:
    """Move downloaded videos into the dump directory with device prefixes."""

    copied_count = 0

    for root, _, filenames in os.walk(videos_dir):
        for filename in filenames:
            source_path = os.path.join(
                root,
                filename,
            )

            destination_name = f"VIDEO_{device.file_prefix}_{filename}"

            destination_path = os.path.join(
                LOCAL_DUMP_DIR,
                destination_name,
            )

            try:
                original_mtime = os.path.getmtime(source_path)

                transfer_file(
                    source_path,
                    destination_path,
                )

                if PROJECT_STATUS == "production":
                    os.utime(
                        destination_path,
                        (
                            original_mtime,
                            original_mtime,
                        ),
                    )

                else:
                    os.remove(source_path)

                copied_count += 1

            except OSError as error:
                print(f"[!] Failed to move a screen video: {error}")

    return copied_count


def count_files(directory: str) -> int:
    """Count files recursively in a directory."""

    return sum(len(filenames) for _, _, filenames in os.walk(directory))


def transfer_file(source_path: str, destination_path: str) -> None:
    """Copy files in development and move them in production."""

    if PROJECT_STATUS == "development":
        shutil.copy2(source_path, destination_path)
    elif PROJECT_STATUS == "production":
        shutil.move(source_path, destination_path)
    else:
        raise ValueError(f"Unsupported project status: {PROJECT_STATUS}")


def get_transfer_verb() -> str:
    """Return the output verb matching the configured transfer mode."""

    return "Moved" if PROJECT_STATUS == "production" else "Copied"


def clear_remote_directory(serial: str, remote_path: str) -> bool:
    """Delete a remote directory's contents while preserving the directory."""

    result = run_adb_command(
        [
            "-s",
            serial,
            "shell",
            "find",
            remote_path,
            "-mindepth",
            "1",
            "-delete",
        ]
    )

    if result.returncode != 0:
        print("[!] Failed to clear transferred files from the Android device.")
        return False

    return True


def pull_remote_file(
    device: AndroidDevice,
    remote_file: str,
    local_directory: str,
    progress: Progress,
    task_id: TaskID,
    description: str,
) -> bool:
    """Pull one remote file while displaying live transfer progress."""

    local_filename = PurePosixPath(remote_file).name

    local_file = os.path.join(
        local_directory,
        local_filename,
    )

    if os.path.exists(local_file):
        os.remove(local_file)

    command = build_pull_command(
        device.serial,
        remote_file,
        local_directory,
    )

    process = subprocess.Popen(
        [
            get_adb_executable(),
            *command,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    previous_size = 0

    while process.poll() is None:
        if os.path.exists(local_file):
            current_size = os.path.getsize(local_file)

            if current_size > previous_size:
                progress.update(
                    task_id,
                    advance=(current_size - previous_size),
                    description=description,
                )

                previous_size = current_size

        time.sleep(0.1)

    _, error = process.communicate()

    if os.path.exists(local_file):
        final_size = os.path.getsize(local_file)

        if final_size > previous_size:
            progress.update(
                task_id,
                advance=(final_size - previous_size),
                description=description,
            )

    if process.returncode != 0:
        if os.path.exists(local_file):
            os.remove(local_file)

        console.print(f"[red]✗ Failed to transfer {local_filename}[/red]")

        if error.strip():
            console.print(f"[red]{error.strip()}[/red]")

        return False

    return True


def get_remote_file_size(
    device: AndroidDevice,
    remote_file: str,
) -> int | None:
    """Return the size of a remote Android file in bytes."""

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "stat",
            "-c",
            "%s",
            remote_file,
        ]
    )

    if result.returncode != 0:
        return None

    try:
        return int(result.stdout.strip())

    except ValueError:
        return None


def pull_reff_files(
    device: AndroidDevice,
    progress: Progress,
    task_id: TaskID,
) -> int:
    """Pull today's valid REFF files from one Android device."""

    reff_files = get_remote_files_from_today(
        device,
        device.remote_log_path,
    )

    reff_file_sizes = filter_remote_files_by_size(
        device,
        reff_files,
        MIN_REFF_FILE_SIZE_BYTES,
    )

    reff_files = list(reff_file_sizes)

    total_reff_files = len(reff_files)

    total_reff_bytes = sum(reff_file_sizes.values())

    progress.update(
        task_id,
        total=total_reff_bytes,
        completed=0,
        description=(f"REFF: {get_transfer_verb()} 0 of {total_reff_files} files"),
    )

    if not reff_files:
        return 0

    records_dir = os.path.join(
        LOCAL_DUMP_DIR,
        "Records",
    )

    os.makedirs(
        records_dir,
        exist_ok=True,
    )

    for file_number, remote_file in enumerate(
        reff_files,
        start=1,
    ):
        pull_remote_file(
            device,
            remote_file,
            records_dir,
            progress,
            task_id,
            (f"REFF: {get_transfer_verb()} {file_number} of {total_reff_files} files"),
        )

    copied_count = move_record_files(
        records_dir,
        device,
    )

    remove_empty_directories(records_dir)

    return copied_count


def filter_remote_files_by_size(
    device: AndroidDevice,
    remote_files: list[str],
    minimum_size_bytes: int,
) -> dict[str, int]:
    """Return remote files that meet the minimum size requirement."""

    valid_files: dict[str, int] = {}

    for remote_file in remote_files:
        file_size = get_remote_file_size(
            device,
            remote_file,
        )

        if file_size is None:
            continue

        if file_size < minimum_size_bytes:
            console.print(
                f"[yellow]Skipping {PurePosixPath(remote_file).name}: "
                f"{file_size / 1_000_000:.1f} MB "
                f"(minimum {minimum_size_bytes / 1_000_000:.1f} MB)[/yellow]"
            )
            continue

        valid_files[remote_file] = file_size

    return valid_files


def find_target_reff_for_video(
    video: dict,
    reff_files: list[dict],
) -> dict | None:
    """Return the REFF file that a video should be associated with."""

    video_device_type = get_video_device_type(video["filename"])

    if video_device_type is None:
        return None

    same_device_reffs = [reff for reff in reff_files if reff["type"] == video_device_type]

    if not same_device_reffs:
        return None

    same_device_reffs.sort(key=lambda reff: reff["mtime"])

    video_time = video["mtime"]

    previous_reffs = [reff for reff in same_device_reffs if reff["mtime"] <= video_time]

    if previous_reffs:
        previous_reff = max(
            previous_reffs,
            key=lambda reff: reff["mtime"],
        )

        seconds_after_reff = video_time - previous_reff["mtime"]

        if 0 <= seconds_after_reff <= MAX_VIDEO_AFTER_REFF_SECONDS:
            return previous_reff

    following_reffs = [reff for reff in same_device_reffs if reff["mtime"] > video_time]

    if following_reffs:
        return min(
            following_reffs,
            key=lambda reff: reff["mtime"],
        )

    return None
