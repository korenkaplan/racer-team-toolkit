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
    GroupingWarning,
    ReffGroupingResult,
    VideoGroupingResult,
)

MAX_VIDEO_AFTER_REFF_SECONDS = 60
MAX_REFF_AFTER_VIDEO_SECONDS = 8 * 60


def group_files_into_flights(
    starting_flight_number: int,
) -> ReffGroupingResult:
    """Group compatible REFF files and return grouped and standalone results."""

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return ReffGroupingResult(
            flights=[],
            standalone_reffs=[],
            next_flight_number=starting_flight_number,
        )

    files = collect_reff_files()

    if not files:
        return ReffGroupingResult(
            flights=[],
            standalone_reffs=[],
            next_flight_number=starting_flight_number,
        )

    files.sort(key=lambda file_info: file_info.mtime)

    used_indexes: set[int] = set()
    standalone_reffs: list[FlightFile] = []
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

        if len(selected_files) < 2:
            standalone_reffs.append(files[index])
            used_indexes.add(index)
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

    return ReffGroupingResult(
        flights=flights,
        standalone_reffs=standalone_reffs,
        next_flight_number=flight_number,
    )


def group_videos_into_flights(
    flights: list[Flight],
    standalone_reffs: list[FlightFile],
    starting_flight_number: int,
) -> VideoGroupingResult:
    """Group standalone videos into existing or newly created flights."""

    videos = get_video_files()

    warnings: list[GroupingWarning] = []

    flight_number = starting_flight_number

    for video in videos:
        matched_flight = find_best_existing_flight_for_video(
            video,
            flights,
        )

        if matched_flight is not None:
            attached = attach_video_to_flight(
                matched_flight,
                video,
            )

            if not attached:
                continue

            if not flight_has_same_device_reff(
                matched_flight,
                video,
            ):
                warnings.append(
                    create_missing_reff_warning(
                        video,
                        matched_flight,
                    )
                )

            continue

        matched_reff = find_best_standalone_reff_for_video(
            video,
            standalone_reffs,
        )

        if matched_reff is not None:
            new_flight = create_flight_from_standalone_reff_and_video(
                matched_reff,
                video,
                flight_number,
            )

            if new_flight is None:
                continue

            flights.append(new_flight)

            standalone_reffs.remove(matched_reff)

            if not flight_has_same_device_reff(
                new_flight,
                video,
            ):
                warnings.append(
                    create_missing_reff_warning(
                        video,
                        new_flight,
                    )
                )

            flight_number += 1

            continue

        warnings.append(
            create_missing_reff_warning(
                video,
                None,
            )
        )

    return VideoGroupingResult(
        flights=flights,
        warnings=warnings,
    )


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
    """Move REFF files into a flight directory and update their paths."""

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

            file_info.path = destination

        except OSError as error:
            print(f"[!] Failed to move REFF file {file_info.filename}: {error}")


def attach_video_to_flight(
    flight: Flight,
    video: FlightFile,
) -> bool:
    """Move one video into a flight and update the Flight object."""

    destination = os.path.join(
        flight.path,
        video.filename,
    )

    try:
        shutil.move(
            video.path,
            destination,
        )

        video.path = destination
        flight.videos.append(video)

        return True

    except OSError as error:
        print(f"[!] Failed to move screen video {video.filename}: {error}")

        return False


def get_latest_flight_end_time(
    flight: Flight,
) -> float:
    """Return the latest REFF end time for a flight."""

    if not flight.reff_files:
        raise ValueError(f"Flight {flight.name} has no REFF files.")

    return max(reff.mtime for reff in flight.reff_files)


def find_best_existing_flight_for_video(
    video: FlightFile,
    flights: list[Flight],
) -> Flight | None:
    """Return the best existing flight for a video based on end times."""

    priority_one_matches: list[tuple[float, Flight]] = []
    priority_two_matches: list[tuple[float, Flight]] = []

    for flight in flights:
        flight_end = get_latest_flight_end_time(flight)

        video_after_flight = video.mtime - flight_end

        if 0 <= video_after_flight <= MAX_VIDEO_AFTER_REFF_SECONDS:
            priority_one_matches.append(
                (
                    video_after_flight,
                    flight,
                )
            )
            continue

        flight_after_video = flight_end - video.mtime

        if 0 < flight_after_video <= MAX_REFF_AFTER_VIDEO_SECONDS:
            priority_two_matches.append(
                (
                    flight_after_video,
                    flight,
                )
            )

    if priority_one_matches:
        return min(
            priority_one_matches,
            key=lambda match: match[0],
        )[1]

    if priority_two_matches:
        return min(
            priority_two_matches,
            key=lambda match: match[0],
        )[1]

    return None


def flight_has_same_device_reff(
    flight: Flight,
    video: FlightFile,
) -> bool:
    """Return whether the flight has a REFF from the video's device type."""

    return any(reff.device_type == video.device_type for reff in flight.reff_files)


def find_best_standalone_reff_for_video(
    video: FlightFile,
    standalone_reffs: list[FlightFile],
) -> FlightFile | None:
    """Return the best standalone REFF for a video based on end times."""

    priority_one_matches: list[tuple[float, FlightFile]] = []
    priority_two_matches: list[tuple[float, FlightFile]] = []

    for reff in standalone_reffs:
        video_after_reff = video.mtime - reff.mtime

        if 0 <= video_after_reff <= MAX_VIDEO_AFTER_REFF_SECONDS:
            priority_one_matches.append(
                (
                    video_after_reff,
                    reff,
                )
            )
            continue

        reff_after_video = reff.mtime - video.mtime

        if 0 < reff_after_video <= MAX_REFF_AFTER_VIDEO_SECONDS:
            priority_two_matches.append(
                (
                    reff_after_video,
                    reff,
                )
            )

    if priority_one_matches:
        return min(
            priority_one_matches,
            key=lambda match: match[0],
        )[1]

    if priority_two_matches:
        return min(
            priority_two_matches,
            key=lambda match: match[0],
        )[1]

    return None


def create_flight_from_standalone_reff_and_video(
    reff: FlightFile,
    video: FlightFile,
    flight_number: int,
) -> Flight | None:
    """Create a new flight from a standalone REFF and matching video."""

    flight_name, flight_dir = create_flight_directory(
        flight_number,
        reff.mtime,
    )

    move_flight_files(
        flight_dir,
        [reff],
    )

    flight = Flight(
        number=flight_number,
        name=flight_name,
        path=flight_dir,
        reff_files=[reff],
    )

    video_attached = attach_video_to_flight(
        flight,
        video,
    )

    if not video_attached:
        return None

    return flight


def create_missing_reff_warning(
    video: FlightFile,
    flight: Flight | None,
) -> GroupingWarning:
    """Create a warning for a video without a REFF from the same device."""

    flight_name = flight.name if flight is not None else None

    if flight_name is not None:
        message = (
            f"Screen recording from {video.device_type.value} was grouped into "
            f"{flight_name}, but no matching REFF from the same device was found."
        )
    else:
        message = (
            f"Screen recording from {video.device_type.value} has no matching "
            "REFF and could not be grouped into a flight folder."
        )

    return GroupingWarning(
        device_type=video.device_type,
        filename=video.filename,
        flight_name=flight_name,
        message=message,
    )
