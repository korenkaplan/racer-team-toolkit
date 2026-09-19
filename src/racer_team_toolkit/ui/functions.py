from collections.abc import Callable
from typing import TypeVar

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table

from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
    GroupingWarning,
)

console = Console()
T = TypeVar("T")


def run_with_spinner(
    message: str,
    function: Callable[..., T],
    *args,
    **kwargs,
) -> T:
    """Run a function while displaying a spinner."""

    with Status(
        message,
        console=console,
        spinner="dots",
    ):
        return function(*args, **kwargs)


def select_menu(message: str, choices: list[str]) -> str:
    """Display a menu of choices and return the selected option."""
    return questionary.select(message, choices=choices).ask()


def select_menu_tuple(message: str, choices: list[str]) -> tuple[int, str]:
    """Display a menu and return the index and selected option."""

    selected = questionary.select(message, choices=choices).ask()
    index = choices.index(selected)

    return index, selected


def print_header(title: str) -> None:
    """Print a formatted header using rich."""
    console.print(Panel.fit(title))


def print_success(message: str) -> None:
    """Print a success message in green."""
    console.print(f"[green][V][/green] {message}")


def print_info(message: str) -> None:
    """Print an informational message in cyan."""
    console.print(f"[cyan][i][/cyan] {message}")


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    console.print(f"[yellow][!][/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message in red."""
    console.print(f"[red][-][/red] {message}")


def pause(message: str = "Press Enter to return...") -> None:
    """Pause the program and wait for user input."""
    input(message)


def print_flight_table(
    flights: list[Flight],
    device_types: tuple[str, ...],
    *,
    include_videos: bool = True,
) -> None:
    """Render grouped REFF files and videos in a Rich table."""

    table = Table(
        title="Flights",
        show_lines=True,
    )

    table.add_column(
        "Flight",
        style="bold cyan",
    )

    for device_type in device_types:
        table.add_column(device_type)

    if include_videos:
        table.add_column("Screen Videos")

    for flight in flights:
        row: list[str] = [flight.name]

        for device_type in device_types:
            filenames = [
                reff.filename for reff in flight.reff_files if reff.device_type.value == device_type
            ]

            row.append("\n".join(filenames) if filenames else "-")

        if include_videos:
            video_names = [video.filename for video in flight.videos]

            row.append("\n".join(video_names) if video_names else "-")

        table.add_row(*row)

    console.print(table)


def print_extraction_summary(summary: dict[str, int]) -> None:
    """Render extraction totals in a Rich summary table."""

    table = Table(title="Extraction Summary", show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right", style="cyan")

    for label, value in summary.items():
        table.add_row(label, str(value))

    console.print(table)


def print_grouping_warnings(
    warnings: list[GroupingWarning],
) -> None:
    """Render recording warnings in a Rich table."""

    table = Table(
        title="Recording Warnings",
        show_lines=True,
    )

    table.add_column(
        "Device",
        style="yellow",
    )
    table.add_column("Video")
    table.add_column("Flight")
    table.add_column("Warning")

    for warning in warnings:
        table.add_row(
            warning.device_type.value,
            warning.filename,
            warning.flight_name or "Standalone",
            warning.message,
        )

    console.print()
    console.print(table)
