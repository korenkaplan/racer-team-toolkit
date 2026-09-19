import os

from racer_team_toolkit.adb import get_connected_android_devices
from racer_team_toolkit.config import (
    LOCAL_DUMP_DIR,
    AndroidDevice,
)
from racer_team_toolkit.reff_extractor.grouping import (
    get_next_flight_number,
    group_files_into_flights,
    group_videos_into_flights,
)
from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
    GroupingWarning,
)
from racer_team_toolkit.reff_extractor.time_adjustment_functions import (
    validate_device_times_before_extraction,
)
from racer_team_toolkit.reff_extractor.transfer import get_transfer_verb, process_device
from racer_team_toolkit.ui.functions import (
    console,
    print_extraction_summary,
    print_flight_table,
    print_grouping_warnings,
)


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
    warnings: list[GroupingWarning] = []

    for device in devices_to_process:
        result = process_device(
            device,
            include_videos=include_videos,
        )

        copied_reff_files += result.reff_files
        copied_videos += result.videos

        processed_any = True

    if processed_any:
        reff_grouping_result = group_files_into_flights(
            starting_flight_number=next_flight_number,
        )

        flights = reff_grouping_result.flights

        if include_videos:
            video_grouping_result = group_videos_into_flights(
                flights=reff_grouping_result.flights,
                standalone_reffs=reff_grouping_result.standalone_reffs,
                starting_flight_number=reff_grouping_result.next_flight_number,
            )

            flights = video_grouping_result.flights
            warnings = video_grouping_result.warnings

    print_extraction_result(
        processed_any,
        flights,
        warnings,
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
    warnings: list[GroupingWarning],
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

        if warnings:
            summary["Recording warnings"] = len(warnings)

        print_extraction_summary(summary)

        if warnings:
            print_grouping_warnings(warnings)

        print(f"\n[V] All files are located at:\n    {os.path.abspath(LOCAL_DUMP_DIR)}")

    else:
        print("[!] No matched devices were processed.")

    print("=============================================================")


def create_output_directory() -> None:
    """Create the local extraction directory if it does not exist."""

    os.makedirs(LOCAL_DUMP_DIR, exist_ok=True)
