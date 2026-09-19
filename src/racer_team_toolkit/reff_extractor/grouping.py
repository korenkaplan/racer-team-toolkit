import os
import shutil
from datetime import datetime

from racer_team_toolkit.adb.device_detection import DeviceType
from racer_team_toolkit.config import (
    LOCAL_DUMP_DIR,
    MAX_FLIGHT_TIME_DIFF,
    VIDEO_FILE_PREFIX,
)
from racer_team_toolkit.reff_extractor.file_detection import (
    get_device_type_from_filename,
    get_video_device_type,
)
from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
    FlightFile,
    FlightFileType,
)

MAX_VIDEO_AFTER_REFF_SECONDS = 60
MAX_REFF_AFTER_VIDEO_SECONDS = 8 * 60


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
