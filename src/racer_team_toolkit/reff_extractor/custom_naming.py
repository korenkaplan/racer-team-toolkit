import re
from pathlib import Path, PurePosixPath

from rich.table import Table

from racer_team_toolkit.reff_extractor.grouping_dataclasses import Flight
from racer_team_toolkit.ui.functions import console, select_menu

CUSTOM_NAME_PREFIX = "Custom_"

NORMAL_REFF_PATTERN = re.compile(
    r"\d{2}_\d{2}_\d{4}_\d{2}_\d{2}"
    r"(?:_\d{2})?"
    r"(?:_Number_\d+)?"
    r"\.reff",
    re.IGNORECASE,
)

NORMAL_VIDEO_PATTERNS = (
    re.compile(
        r"ScreenRec_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}"
        r"(?:-\d{2})?"
        r"(?:_Number_\d+)?"
        r"\.mp4",
        re.IGNORECASE,
    ),
    re.compile(
        r"full_screen_\d{2}_\d{2}_\d{4}_\d{2}_\d{2}"
        r"(?:_\d{2})?"
        r"(?:_Number_\d+)?"
        r"\.mp4",
        re.IGNORECASE,
    ),
)


def is_normal_recording_filename(filename: str) -> bool:
    """Recognize standard recording names before device prefixes are added."""

    if NORMAL_REFF_PATTERN.fullmatch(filename):
        return True

    return any(pattern.fullmatch(filename) for pattern in NORMAL_VIDEO_PATTERNS)


def flag_custom_recording_filename(filename: str) -> str:
    """Flag custom REFF/video names without changing normal recording names."""

    extension = PurePosixPath(filename).suffix.lower()

    if extension not in {".reff", ".mp4"}:
        return filename

    if filename.lower().startswith(CUSTOM_NAME_PREFIX.lower()):
        return filename

    if is_normal_recording_filename(filename):
        return filename

    return f"{CUSTOM_NAME_PREFIX}{filename}"


def get_custom_name(filename: str) -> str | None:
    """Read a custom name after extraction adds device and video prefixes."""

    match = re.fullmatch(
        r"(?:VIDEO_)?[^_]+_Custom_(.+)\.(?:reff|mp4)",
        filename,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    return match.group(1)


def choose_custom_flight_name(flight: Flight) -> str | None:
    """Choose one distinct custom name from files belonging to a flight."""

    files_by_name: dict[str, list[str]] = {}

    for file_info in [*flight.reff_files, *flight.videos]:
        custom_name = get_custom_name(file_info.filename)

        if custom_name is None:
            continue

        files_by_name.setdefault(custom_name, []).append(file_info.filename)

    if not files_by_name:
        return None

    if len(files_by_name) == 1:
        return next(iter(files_by_name))

    console.print(
        f"Custom naming conflict in {flight.name}",
        style="yellow",
        markup=False,
    )

    table = Table(title="Choose flight folder name")
    table.add_column("Custom name")
    table.add_column("Files")

    for custom_name, filenames in files_by_name.items():
        table.add_row(custom_name, "\n".join(filenames))

    console.print(table)

    return select_menu(
        "Select custom flight name:",
        choices=list(files_by_name),
    )


def apply_custom_flight_names(flights: list[Flight]) -> None:
    """Rename flight folders while preserving flight numbers and file paths."""

    for flight in flights:
        custom_name = choose_custom_flight_name(flight)

        if custom_name is None:
            continue

        invalid_name = (
            not custom_name.strip()
            or custom_name.endswith((" ", "."))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', custom_name) is not None
        )

        if invalid_name:
            console.print(
                f"Invalid folder name: {custom_name!r}. Keeping {flight.name}.",
                style="yellow",
                markup=False,
            )
            continue

        source = Path(flight.path)
        folder_name = f"Flight_{flight.number:02d}_{custom_name}"
        destination = source.parent / folder_name

        if source == destination:
            continue

        if destination.exists() or destination.is_symlink():
            console.print(
                f"Folder already exists: {folder_name}. Keeping {flight.name}.",
                style="yellow",
                markup=False,
            )
            continue

        try:
            source.rename(destination)
        except OSError as error:
            console.print(
                f"Failed to rename {flight.name}: {error}",
                style="red",
                markup=False,
            )
            continue

        previous_name = flight.name
        flight.name = folder_name
        flight.path = str(destination)

        for file_info in [*flight.reff_files, *flight.videos]:
            file_info.path = str(destination / file_info.filename)

        console.print(
            f"Renamed {previous_name} → {folder_name}",
            style="green",
            markup=False,
        )
