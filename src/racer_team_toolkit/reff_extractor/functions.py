"""Reusable REFF and screen-video extraction functions."""

import os
import shutil
from datetime import datetime
from typing import Optional

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from racer_team_toolkit.adb import get_connected_serials, run_adb_command
from racer_team_toolkit.config import (
    DEVICES_REGISTRY,
    LOCAL_DUMP_DIR,
    MAX_FLIGHT_TIME_DIFF,
    MAX_VIDEO_TIME_DIFF,
    PROJECT_STATUS,
    SUPPORTED_DEVICE_TYPES,
    VIDEO_REMOTE_PATH,
    AndroidDevice,
)
from racer_team_toolkit.ui.functions import (
    console,
    print_extraction_summary,
    print_flight_table,
)


def extract_reff() -> None:
    """Extract REFF files from connected devices without screen videos."""

    run_extraction(include_videos=False)


def extract_reff_and_videos() -> None:
    """Extract REFF files and screen videos from connected devices."""

    run_extraction(include_videos=True)


def adjust_time_for_reff() -> None:
    """Report that REFF timestamp adjustment is not implemented yet."""

    print("[i] REFF timestamp adjustment is not implemented yet.")


def run_extraction(*, include_videos: bool) -> None:
    """Run the shared extraction workflow for one menu option."""

    create_output_directory()
    connected_serials = get_connected_serials()

    if not connected_serials:
        print("[-] No Devices Are Connected. Please connect a device and try again.")
        return

    connected_devices = get_connected_devices(connected_serials)
    print_connected_devices(connected_devices)
    # Limit report columns to devices that participated in this extraction.
    connected_device_types = tuple(device.file_prefix for device in connected_devices)
    processed_any = False
    copied_reff_files = 0
    copied_videos = 0
    flights = []

    for device in connected_devices:
        result = process_device(device, include_videos=include_videos)
        copied_reff_files += result["reff_files"]
        copied_videos += result["videos"]
        processed_any = True

    if processed_any:
        flights = group_files_into_flights()

    print_extraction_result(
        processed_any,
        flights,
        copied_reff_files,
        copied_videos,
        include_videos,
        connected_device_types,
    )


def get_connected_devices(connected_serials: set[str]) -> list[AndroidDevice]:
    """Return registered devices that are currently connected."""

    return [device for device in DEVICES_REGISTRY if device.serial in connected_serials]


def print_connected_devices(devices: list[AndroidDevice]) -> None:
    """Print the connected-device count and identity details."""

    print(f"[+] Connected devices: {len(devices)}")
    for device in devices:
        print(f"    {device.name} (Serial: {device.serial})")


def print_extraction_result(
    processed_any: bool,
    flights: list[dict],
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
            print_flight_table(flights, device_types, include_videos=include_videos)
        summary = {
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


def get_connected_devices_and_print_info() -> list[AndroidDevice]:
    """Return registered connected devices and print their status."""

    connected_serials = get_connected_serials()
    connected_devices = get_connected_devices(connected_serials)
    print_connected_devices(connected_devices)
    return connected_devices


def get_file_type(filename: str) -> Optional[str]:
    """Return the registered device type encoded in a filename."""

    normalized_filename = filename.upper().replace(" ", "_")

    for device_type in SUPPORTED_DEVICE_TYPES:
        if normalized_filename.startswith(f"{device_type}_"):
            return device_type

    return None


def get_video_files() -> list[dict]:
    """Return downloaded videos from the local dump directory."""

    videos = []

    for filename in os.listdir(LOCAL_DUMP_DIR):
        if not filename.upper().startswith("VIDEO_"):
            continue

        file_path = os.path.join(LOCAL_DUMP_DIR, filename)

        if not os.path.isfile(file_path):
            continue

        try:
            videos.append(
                {
                    "filename": filename,
                    "path": file_path,
                    "mtime": os.path.getmtime(file_path),
                    "size": os.path.getsize(file_path),
                }
            )
        except OSError:
            continue

    return videos


def attach_videos_to_flight(flight_dir: str, flight_files: list[dict], videos: list[dict]) -> int:
    """Move videos within the configured time limit into a flight directory."""

    flight_times = [file_info["mtime"] for file_info in flight_files]
    matching_videos = [
        video
        for video in videos
        if min(abs(video["mtime"] - flight_time) for flight_time in flight_times)
        <= MAX_VIDEO_TIME_DIFF
    ]

    for video in matching_videos:
        try:
            shutil.move(video["path"], os.path.join(flight_dir, video["filename"]))
        except OSError as error:
            print(f"[!] Failed to move a screen video: {error}")

    return len(matching_videos)


def group_files_into_flights() -> list[dict]:
    """Group compatible REFF files and videos into flight directories."""

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return []

    files = collect_reff_files()

    if not files:
        return []

    files.sort(key=lambda file_info: file_info["mtime"])
    used_indexes = set()
    used_video_paths = set()
    flights = []
    flight_number = 1

    for index, base_file in enumerate(files):
        if index in used_indexes:
            continue

        # Start with the earliest unused file and select compatible files by type.
        selected_files, selected_indexes = select_flight_files(files, index, used_indexes)
        matching_videos = find_matching_videos(
            selected_files,
            get_video_files(),
            used_video_paths,
        )

        # A flight needs either multiple device types or a matching video.
        if len(selected_files) < 2 and not matching_videos:
            continue

        flight_name, flight_dir = create_flight_directory(flight_number, selected_files[0]["mtime"])
        move_flight_files(flight_dir, selected_files)
        attach_videos_to_flight(flight_dir, selected_files, matching_videos)

        # Retain the moved filenames for the final Rich table.
        used_indexes.update(selected_indexes)
        used_video_paths.update(video["path"] for video in matching_videos)
        flights.append(
            {
                "name": flight_name,
                "files_by_type": group_files_by_type(selected_files),
                "videos": [video["filename"] for video in matching_videos],
            }
        )
        flight_number += 1

    return flights


def find_matching_videos(
    flight_files: list[dict],
    videos: list[dict],
    used_video_paths: Optional[set[str]] = None,
) -> list[dict]:
    """Return videos within the configured time limit of a flight."""

    used_video_paths = used_video_paths or set()
    flight_times = [file_info["mtime"] for file_info in flight_files]
    return [
        video
        for video in videos
        if video["path"] not in used_video_paths
        if min(abs(video["mtime"] - flight_time) for flight_time in flight_times)
        <= MAX_VIDEO_TIME_DIFF
    ]


def group_files_by_type(files: list[dict]) -> dict[str, list[str]]:
    """Group filenames by their registered device type."""

    grouped_files: dict[str, list[str]] = {}

    for file_info in files:
        grouped_files.setdefault(file_info["type"], []).append(file_info["filename"])

    return grouped_files


def collect_reff_files() -> list[dict]:
    """Collect REFF files and metadata from the dump directory."""

    files = []

    for filename in os.listdir(LOCAL_DUMP_DIR):
        file_path = os.path.join(LOCAL_DUMP_DIR, filename)

        if not os.path.isfile(file_path):
            continue

        file_type = get_file_type(filename)

        if file_type is None:
            continue

        try:
            files.append(
                {
                    "filename": filename,
                    "path": file_path,
                    "type": file_type,
                    "mtime": os.path.getmtime(file_path),
                    "size": os.path.getsize(file_path),
                }
            )
        except OSError:
            continue

    return files


def select_flight_files(
    files: list[dict], base_index: int, used_indexes: set[int]
) -> tuple[list[dict], set[int]]:
    """Select the best compatible file from each device type."""

    base_file = files[base_index]
    selected_files = [base_file]
    selected_indexes = {base_index}
    candidates_by_type = collect_flight_candidates(files, base_index, used_indexes)

    for device_type, candidates in candidates_by_type.items():
        # Prefer the same minute, then the largest file, then the closest time.
        candidates.sort(
            key=lambda candidate: (
                0 if candidate["same_minute"] else 1,
                -candidate["size"],
                candidate["time_diff"],
            )
        )
        selected_candidate = candidates[0]
        selected_index = files.index(selected_candidate)
        proposed_files = selected_files + [selected_candidate]

        if flight_is_within_time_limit(proposed_files):
            selected_files.append(selected_candidate)
            selected_indexes.add(selected_index)

    return selected_files, selected_indexes


def collect_flight_candidates(
    files: list[dict], base_index: int, used_indexes: set[int], s
) -> dict[str, list[dict]]:
    """Collect unused files close enough to the base file for a flight."""

    base_file = files[base_index]
    candidates_by_type: dict[str, list[dict]] = {}

    for index in range(base_index + 1, len(files)):
        if index in used_indexes:
            continue

        candidate = files[index]

        # Files are sorted by time, so once we're outside the allowed
        # flight window there is no reason to continue checking.
        if candidate["mtime"] - base_file["mtime"] > MAX_FLIGHT_TIME_DIFF:
            break

        # A flight can contain only one REFF file from each device type.
        # The device type is reliable here because our extraction code
        # adds the configured device prefix before flight grouping.
        if candidate["type"] == base_file["type"]:
            continue

        candidate["time_diff"] = abs(candidate["mtime"] - base_file["mtime"])

        candidate["same_minute"] = same_clock_minute(
            candidate["mtime"],
            base_file["mtime"],
        )

        candidates_by_type.setdefault(
            candidate["type"],
            [],
        ).append(candidate)

    return candidates_by_type


def same_clock_minute(first_timestamp: float, second_timestamp: float) -> bool:
    """Return whether two timestamps occur in the same local clock minute."""

    first_minute = datetime.fromtimestamp(first_timestamp).replace(second=0, microsecond=0)
    second_minute = datetime.fromtimestamp(second_timestamp).replace(second=0, microsecond=0)
    return first_minute == second_minute


def flight_is_within_time_limit(flight_files: list[dict]) -> bool:
    """Return whether a flight's first and last files are close enough."""

    timestamps = [file_info["mtime"] for file_info in flight_files]
    return max(timestamps) - min(timestamps) <= MAX_FLIGHT_TIME_DIFF


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


def move_flight_files(flight_dir: str, flight_files: list[dict]) -> None:
    """Move selected REFF files into a flight directory."""

    for file_info in flight_files:
        destination = os.path.join(flight_dir, file_info["filename"])

        try:
            shutil.move(file_info["path"], destination)
        except OSError as error:
            print(f"[!] Failed to move a REFF file: {error}")


def process_device(device: AndroidDevice, *, include_videos: bool = True) -> dict[str, int]:
    """Pull REFF files from one device and optionally pull its videos."""

    print(f"\n[--->] Starting {get_transfer_verb().lower()} from: {device.name}")

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=False,
    ) as progress:
        # REFF and video tasks have separate totals and counters.
        reff_task_id = progress.add_task(f"REFF: {get_transfer_verb()} 0 of 0 files", total=0)
        create_output_directory()
        reff_files = pull_reff_files(device, progress, reff_task_id)
        videos = 0

        if include_videos:
            video_task_id = progress.add_task(
                f"Videos: {get_transfer_verb()} 0 of 0 files", total=0
            )
            videos = pull_videos(device, progress, video_task_id)

    print(f"[<---] Finished {get_transfer_verb().lower()} from: {device.name}")

    return {"reff_files": reff_files, "videos": videos}


def pull_reff_files(device: AndroidDevice, progress: Progress, task_id: int) -> int:
    """Pull and flatten the Records directory from one device."""

    pull_command = build_pull_command(device.serial, device.remote_log_path)
    result = run_adb_command(pull_command)

    if result.returncode != 0:
        return 0

    records_dir = os.path.join(LOCAL_DUMP_DIR, "Records")

    if not os.path.isdir(records_dir):
        return 0

    total_files = count_files(records_dir)
    # ADB creates Records only after the pull, so calculate its total here.
    progress.update(
        task_id,
        total=total_files,
        description=f"REFF: {get_transfer_verb()} 0 of {total_files} files",
    )
    copied_count = move_record_files(records_dir, device, progress, task_id)
    remove_empty_directories(records_dir)

    if PROJECT_STATUS == "production" and copied_count == total_files:
        clear_remote_directory(device.serial, device.remote_log_path)

    return copied_count


def build_pull_command(serial: str, remote_path: str) -> list[str]:
    """Build an ADB pull command for a device path."""

    return ["adb", "-s", serial, "pull", "-a", remote_path, LOCAL_DUMP_DIR]


def move_record_files(
    records_dir: str, device: AndroidDevice, progress: Progress, task_id: int
) -> int:
    """Move record files into the dump directory with device prefixes."""

    copied_count = 0

    for root, _, filenames in os.walk(records_dir):
        for filename in filenames:
            source_path = os.path.join(root, filename)
            prefixed_filename = add_device_prefix(filename, device.file_prefix)
            destination_path = os.path.join(LOCAL_DUMP_DIR, prefixed_filename)

            try:
                # Flight matching depends on the original device timestamp.
                original_mtime = os.path.getmtime(source_path)
                transfer_file(source_path, destination_path)
                if PROJECT_STATUS == "production":
                    os.utime(destination_path, (original_mtime, original_mtime))
                else:
                    os.remove(source_path)
                copied_count += 1
            except OSError as error:
                print(f"[!] Failed to move a REFF file: {error}")
            finally:
                update_file_progress(progress, task_id, "REFF")

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


def pull_videos(device: AndroidDevice, progress: Progress, task_id: int) -> int:
    """Pull screen recordings and flatten them into the dump directory."""

    pull_command = build_pull_command(device.serial, VIDEO_REMOTE_PATH)
    result = run_adb_command(pull_command)

    if result.returncode != 0:
        return 0

    videos_dir = os.path.join(LOCAL_DUMP_DIR, "Screen-Videos")

    if not os.path.isdir(videos_dir):
        return 0

    total_video_files = count_files(videos_dir)
    progress.update(
        task_id,
        total=total_video_files,
        description=f"Videos: {get_transfer_verb()} 0 of {total_video_files} files",
    )
    video_count = move_video_files(videos_dir, device, progress, task_id)
    remove_empty_directories(videos_dir)

    if PROJECT_STATUS == "production" and video_count == total_video_files:
        clear_remote_directory(device.serial, VIDEO_REMOTE_PATH)

    return video_count


def move_video_files(
    videos_dir: str, device: AndroidDevice, progress: Progress, task_id: int
) -> int:
    """Move downloaded videos into the dump directory with device prefixes."""

    copied_count = 0

    for root, _, filenames in os.walk(videos_dir):
        for filename in filenames:
            source_path = os.path.join(root, filename)
            destination_name = f"VIDEO_{device.file_prefix}_{filename}"
            destination_path = os.path.join(LOCAL_DUMP_DIR, destination_name)

            try:
                original_mtime = os.path.getmtime(source_path)
                transfer_file(source_path, destination_path)
                if PROJECT_STATUS == "production":
                    os.utime(destination_path, (original_mtime, original_mtime))
                else:
                    os.remove(source_path)
                copied_count += 1
            except OSError as error:
                print(f"[!] Failed to move a screen video: {error}")
            finally:
                update_file_progress(progress, task_id, "Videos")

    return copied_count


def update_file_progress(progress: Progress, task_id: int, label: str) -> None:
    """Advance the device progress bar for each processed file."""

    task = progress.tasks[task_id]
    completed = task.completed + 1
    progress.update(
        task_id,
        advance=1,
        description=f"{label}: {get_transfer_verb()} {completed} of {task.total} files",
    )


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
            "adb",
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
