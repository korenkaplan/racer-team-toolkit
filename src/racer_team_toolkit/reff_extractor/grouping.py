import os
import re
import shutil
from datetime import datetime

from racer_team_toolkit.adb.device_detection import DeviceType
from racer_team_toolkit.config import (
    LOCAL_DUMP_DIR,
    MAX_FLIGHT_TIME_DIFF,
    MAX_VIDEO_TIME_DIFF,
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
    starting_flight_number: int | None = None,
) -> ReffGroupingResult:
    """Group REFF files, preferring existing flight folders first.

    Existing Flight_* folders are authoritative and are never renamed.
    Every top-level REFF is reconsidered on every run, including files left
    standalone by previous extractions.

    The starting_flight_number argument is kept for compatibility with older
    callers. Numbering is derived from the current dump-folder state.
    """

    del starting_flight_number

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return ReffGroupingResult(
            flights=[],
            standalone_reffs=[],
            next_flight_number=1,
        )

    existing_flights = load_existing_flights()
    standalone_files = collect_reff_files()
    standalone_files.sort(key=lambda file_info: file_info.mtime)

    unmatched_files: list[FlightFile] = []

    # Priority 1: existing Flight_* folders.
    for file_info in standalone_files:
        matched_flight = find_best_existing_flight_for_reff(
            file_info,
            existing_flights,
        )

        if matched_flight is None:
            unmatched_files.append(file_info)
            continue

        if not attach_reff_to_flight(
            matched_flight,
            file_info,
        ):
            unmatched_files.append(file_info)

    # Priority 2: remaining standalone REFF files.
    groups, remaining_standalone = plan_standalone_reff_groups(
        unmatched_files,
    )

    # New folders continue from the highest assigned Flight_* number.
    # Remaining standalone REFFs are counted when calculating the next number.
    highest_existing_number = get_highest_flight_folder_number()
    flight_number = highest_existing_number + 1

    created_flights: list[Flight] = []

    for selected_files in groups:
        flight_name, flight_dir = create_flight_directory(
            flight_number,
            selected_files[0].mtime,
        )

        move_flight_files(
            flight_dir,
            selected_files,
        )

        created_flights.append(
            Flight(
                number=flight_number,
                name=flight_name,
                path=flight_dir,
                reff_files=selected_files,
            )
        )

        flight_number += 1

    flights = [*existing_flights, *created_flights]

    return ReffGroupingResult(
        flights=flights,
        standalone_reffs=remaining_standalone,
        next_flight_number=get_next_flight_number(),
    )


def plan_standalone_reff_groups(
    files: list[FlightFile],
) -> tuple[list[list[FlightFile]], list[FlightFile]]:
    """Plan new flight groups from top-level REFF files without moving them."""

    files = sorted(
        files,
        key=lambda file_info: file_info.mtime,
    )

    used_indexes: set[int] = set()
    groups: list[list[FlightFile]] = []
    standalone_reffs: list[FlightFile] = []

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

        groups.append(selected_files)
        used_indexes.update(selected_indexes)

    return groups, standalone_reffs


def load_existing_flights() -> list[Flight]:
    """Reconstruct existing Flight_* folders from files already on disk."""

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return []

    flights: list[Flight] = []

    for name in os.listdir(LOCAL_DUMP_DIR):
        flight_number = get_flight_number_from_name(name)

        if flight_number is None:
            continue

        flight_path = os.path.join(
            LOCAL_DUMP_DIR,
            name,
        )

        if not os.path.isdir(flight_path):
            continue

        reff_files: list[FlightFile] = []
        videos: list[FlightFile] = []

        for filename in os.listdir(flight_path):
            file_path = os.path.join(
                flight_path,
                filename,
            )

            if not os.path.isfile(file_path):
                continue

            try:
                if filename.lower().endswith(".reff"):
                    device_type = get_device_type_from_filename(filename)

                    if device_type is not None:
                        reff_files.append(
                            FlightFile(
                                filename=filename,
                                path=file_path,
                                device_type=device_type,
                                file_type=FlightFileType.REFF,
                                mtime=os.path.getmtime(file_path),
                                size=os.path.getsize(file_path),
                            )
                        )

                elif filename.upper().startswith(f"{VIDEO_FILE_PREFIX}_"):
                    device_type = get_video_device_type(filename)

                    if device_type is not None:
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

        reff_files.sort(key=lambda file_info: file_info.mtime)
        videos.sort(key=lambda file_info: file_info.mtime)

        flights.append(
            Flight(
                number=flight_number,
                name=name,
                path=flight_path,
                reff_files=reff_files,
                videos=videos,
            )
        )

    flights.sort(key=lambda flight: flight.number)
    return flights


def get_flight_number_from_name(name: str) -> int | None:
    """Return the numeric Flight_XX prefix from a flight-folder name."""

    match = re.match(
        r"^Flight_(\d+)(?:_|$)",
        name,
    )

    if match is None:
        return None

    return int(match.group(1))


def get_highest_flight_folder_number() -> int:
    """Return the highest number already assigned to a Flight_* folder."""

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return 0

    numbers: list[int] = []

    for name in os.listdir(LOCAL_DUMP_DIR):
        path = os.path.join(
            LOCAL_DUMP_DIR,
            name,
        )

        if not os.path.isdir(path):
            continue

        number = get_flight_number_from_name(name)

        if number is not None:
            numbers.append(number)

    return max(numbers, default=0)


def find_best_existing_flight_for_reff(
    reff: FlightFile,
    flights: list[Flight],
) -> Flight | None:
    """Return the best existing flight allowed by the REFF grouping rules."""

    matches: list[tuple[int, float, Flight]] = []

    for flight in flights:
        if not flight.reff_files:
            continue

        # Only one REFF from each device type may belong to one flight.
        if any(
            existing.device_type == reff.device_type
            for existing in flight.reff_files
        ):
            continue

        proposed_files = [*flight.reff_files, reff]

        if not flight_is_within_time_limit(proposed_files):
            continue

        base_file = min(
            flight.reff_files,
            key=lambda file_info: file_info.mtime,
        )

        matches.append(
            (
                0
                if same_clock_minute(
                    reff.mtime,
                    base_file.mtime,
                )
                else 1,
                abs(reff.mtime - base_file.mtime),
                flight,
            )
        )

    if not matches:
        return None

    return min(
        matches,
        key=lambda match: (
            match[0],
            match[1],
        ),
    )[2]


def attach_reff_to_flight(
    flight: Flight,
    reff: FlightFile,
) -> bool:
    """Move one top-level REFF into an existing flight folder."""

    destination = os.path.join(
        flight.path,
        reff.filename,
    )

    if os.path.exists(destination):
        return False

    try:
        shutil.move(
            reff.path,
            destination,
        )

        reff.path = destination
        flight.reff_files.append(reff)
        flight.reff_files.sort(key=lambda file_info: file_info.mtime)
        return True

    except OSError as error:
        print(f"[!] Failed to move REFF file {reff.filename}: {error}")
        return False

def group_videos_into_flights(
    flights: list[Flight],
    standalone_reffs: list[FlightFile],
    starting_flight_number: int,
) -> VideoGroupingResult:
    """Group videos into existing or newly created flights."""

    videos = get_video_files()
    videos.sort(key=lambda file_info: file_info.mtime)

    warnings: list[GroupingWarning] = []
    standalone_videos: list[FlightFile] = []

    flight_number = starting_flight_number

    for video in videos:
        # Priority 1: existing flight folders.
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

        # Priority 2: standalone REFF files.
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

            standalone_reffs.remove(
                matched_reff,
            )

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

        # Priority 3: standalone video files.
        matched_video = find_best_standalone_video_for_video(
            video,
            standalone_videos,
        )

        if matched_video is not None:
            new_flight = create_flight_from_standalone_videos(
                matched_video,
                video,
                flight_number,
            )

            if new_flight is None:
                continue

            flights.append(
                new_flight,
            )

            standalone_videos.remove(
                matched_video,
            )

            warnings.append(
                create_missing_reff_warning(
                    matched_video,
                    new_flight,
                )
            )

            warnings.append(
                create_missing_reff_warning(
                    video,
                    new_flight,
                )
            )

            flight_number += 1

            continue

        # Keep unmatched videos available because a later video may match them.
        standalone_videos.append(
            video,
        )

    for video in standalone_videos:
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
    """Return the next flight number without filling deleted folder gaps.

    Existing Flight_* folders keep their assigned numbers. Every top-level
    standalone REFF also counts as a flight. Standalone videos do not count.
    """

    if not os.path.isdir(LOCAL_DUMP_DIR):
        return 1

    highest_flight_number = get_highest_flight_folder_number()
    standalone_reff_count = len(collect_reff_files())

    return highest_flight_number + standalone_reff_count + 1

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


def get_video_time_match(
    video_time: float,
    reference_time: float,
) -> tuple[int, float] | None:
    """Return the time-match priority and difference for a video and REFF time."""

    video_after_reference = video_time - reference_time

    if 0 <= video_after_reference <= MAX_VIDEO_AFTER_REFF_SECONDS:
        return (
            1,
            video_after_reference,
        )

    reference_after_video = reference_time - video_time

    if 0 < reference_after_video <= MAX_REFF_AFTER_VIDEO_SECONDS:
        return (
            2,
            reference_after_video,
        )

    return None


def get_video_to_video_match(
    first_video_time: float,
    second_video_time: float,
) -> float | None:
    """Return the time difference when two videos are related."""

    time_diff = abs(first_video_time - second_video_time)

    if time_diff <= MAX_VIDEO_TIME_DIFF:
        return time_diff

    return None


def find_best_standalone_video_for_video(
    video: FlightFile,
    standalone_videos: list[FlightFile],
) -> FlightFile | None:
    """Return the closest related standalone video."""

    matches: list[tuple[float, FlightFile]] = []

    for candidate in standalone_videos:
        time_diff = get_video_to_video_match(
            video.mtime,
            candidate.mtime,
        )

        if time_diff is None:
            continue

        matches.append(
            (
                time_diff,
                candidate,
            )
        )

    if not matches:
        return None

    return min(
        matches,
        key=lambda match: match[0],
    )[1]


def find_best_existing_flight_for_video(
    video: FlightFile,
    flights: list[Flight],
) -> Flight | None:
    """Return the best existing flight for a video.

    Priority:
    1. Same-device REFF match.
    2. Cross-device REFF match.
    3. Video-to-video match.
    """

    same_device_matches: list[tuple[int, float, Flight]] = []
    fallback_matches: list[tuple[int, float, Flight]] = []
    video_matches: list[tuple[float, Flight]] = []

    for flight in flights:
        if flight.reff_files:
            same_device_reffs = [
                reff for reff in flight.reff_files if reff.device_type == video.device_type
            ]

            if same_device_reffs:
                same_device_end = max(reff.mtime for reff in same_device_reffs)

                same_device_match = get_video_time_match(
                    video.mtime,
                    same_device_end,
                )

                if same_device_match is not None:
                    priority, time_diff = same_device_match

                    same_device_matches.append(
                        (
                            priority,
                            time_diff,
                            flight,
                        )
                    )

            flight_end = get_latest_flight_end_time(
                flight,
            )

            fallback_match = get_video_time_match(
                video.mtime,
                flight_end,
            )

            if fallback_match is not None:
                priority, time_diff = fallback_match

                fallback_matches.append(
                    (
                        priority,
                        time_diff,
                        flight,
                    )
                )

        for existing_video in flight.videos:
            video_time_diff = get_video_to_video_match(
                video.mtime,
                existing_video.mtime,
            )

            if video_time_diff is None:
                continue

            video_matches.append(
                (
                    video_time_diff,
                    flight,
                )
            )

    if same_device_matches:
        return min(
            same_device_matches,
            key=lambda match: (
                match[0],
                match[1],
            ),
        )[2]

    if fallback_matches:
        return min(
            fallback_matches,
            key=lambda match: (
                match[0],
                match[1],
            ),
        )[2]

    if video_matches:
        return min(
            video_matches,
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
    """Return the best standalone REFF, preferring the video's device type."""

    same_device_matches: list[tuple[int, float, FlightFile]] = []
    fallback_matches: list[tuple[int, float, FlightFile]] = []

    for reff in standalone_reffs:
        time_match = get_video_time_match(
            video.mtime,
            reff.mtime,
        )

        if time_match is None:
            continue

        priority, time_diff = time_match
        match = (
            priority,
            time_diff,
            reff,
        )

        if reff.device_type == video.device_type:
            same_device_matches.append(match)
        else:
            fallback_matches.append(match)

    if same_device_matches:
        return min(
            same_device_matches,
            key=lambda match: (
                match[0],
                match[1],
            ),
        )[2]

    if fallback_matches:
        return min(
            fallback_matches,
            key=lambda match: (
                match[0],
                match[1],
            ),
        )[2]

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


def create_flight_from_standalone_videos(
    first_video: FlightFile,
    second_video: FlightFile,
    flight_number: int,
) -> Flight | None:
    """Create a flight from two related standalone videos."""

    first_file_mtime = min(
        first_video.mtime,
        second_video.mtime,
    )

    flight_name, flight_dir = create_flight_directory(
        flight_number,
        first_file_mtime,
    )

    flight = Flight(
        number=flight_number,
        name=flight_name,
        path=flight_dir,
    )

    if not attach_video_to_flight(
        flight,
        first_video,
    ):
        return None

    if not attach_video_to_flight(
        flight,
        second_video,
    ):
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
