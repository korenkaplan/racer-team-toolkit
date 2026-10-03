import os
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TransferSpeedColumn,
)
from rich.text import Text

from racer_team_toolkit.adb import get_connected_android_devices
from racer_team_toolkit.config import (
    LOCAL_DUMP_DIR,
    AndroidDevice,
)
from racer_team_toolkit.multithreading.functions import TaskResult, run_tasks
from racer_team_toolkit.reff_extractor.custom_naming import (
    apply_custom_flight_names,
)
from racer_team_toolkit.reff_extractor.extraction_dataclasses import (
    DeviceExtractionResult,
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
from racer_team_toolkit.reff_extractor.transfer import (
    QueuedTransferProgress,
    TransferEvent,
    get_transfer_verb,
    process_device,
)
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


def extract_devices_concurrently(
    devices: list[AndroidDevice],
    *,
    include_videos: bool,
) -> list[TaskResult[AndroidDevice, DeviceExtractionResult]]:
    """Extract per device while main thread renders shared progress."""

    if not devices:
        return []

    events: Queue[TransferEvent] = Queue()

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.fields[device]}"),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
        auto_refresh=False,
        transient=False,
    ) as progress:
        task_ids = {}

        for device in devices:
            reff_task = progress.add_task(
                "REFF: Waiting",
                device=Text(device.name),
                total=None,
                start=False,
            )

            video_task = None

            if include_videos:
                video_task = progress.add_task(
                    "Videos: Waiting",
                    device=Text(device.name),
                    total=None,
                    start=False,
                )

            task_ids[device.serial] = (reff_task, video_task)

        def worker(device: AndroidDevice) -> DeviceExtractionResult:
            queued_progress = QueuedTransferProgress(events, device.name)
            reff_task, video_task = task_ids[device.serial]

            queued_progress.update(
                reff_task,
                description="REFF: Scanning files",
            )

            try:
                result = process_device(
                    device,
                    include_videos=include_videos,
                    progress=queued_progress,
                    reff_task_id=reff_task,
                    video_task_id=video_task,
                    status_callback=queued_progress.print,
                )
            except Exception:
                for task_id in (reff_task, video_task):
                    if task_id is not None:
                        queued_progress.update(
                            task_id,
                            description="Extraction failed",
                            worker_finished=True,
                        )
                raise

            queued_progress.update(
                reff_task,
                description=f"REFF: Finished — {result.reff_files} files finalized",
                worker_finished=True,
            )

            if video_task is not None:
                queued_progress.update(
                    video_task,
                    description=f"Videos: Finished — {result.videos} files finalized",
                    worker_finished=True,
                )

            return result

        def apply_event(event: TransferEvent) -> None:
            if event.task_id is not None:
                changes = dict(event.changes)
                finished = changes.pop("worker_finished", False)

                if not finished:
                    progress.start_task(event.task_id)

                progress.update(event.task_id, **changes)

                if finished:
                    progress.stop_task(event.task_id)

            elif event.message is not None:
                progress.console.print(Text(f"{event.device_name}: {event.message}"))

        progress.refresh()

        with ThreadPoolExecutor(max_workers=1) as coordinator:
            future = coordinator.submit(
                run_tasks,
                devices,
                worker,
                max_workers=len(devices),
            )

            while True:
                try:
                    event = events.get(timeout=0.1)
                except Empty:
                    progress.refresh()

                    if future.done():
                        # Workers have stopped producing events.
                        # Drain any updates queued just before completion.
                        while True:
                            try:
                                event = events.get_nowait()
                            except Empty:
                                break

                            apply_event(event)

                        progress.refresh()
                        break

                    continue

                apply_event(event)

                while True:
                    try:
                        event = events.get_nowait()
                    except Empty:
                        break

                    apply_event(event)

                progress.refresh()

            return future.result()


def run_extraction(*, include_videos: bool) -> None:
    """Run the shared extraction workflow for one menu option."""

    create_output_directory()

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

    starting_flight_number = get_next_flight_number()

    task_results = extract_devices_concurrently(
        devices_to_process,
        include_videos=include_videos,
    )

    worker_failed = False

    for task_result in task_results:
        if task_result.error is not None:
            worker_failed = True
            console.print(
                Text(
                    f"✗ {task_result.item.name}: "
                    f"{type(task_result.error).__name__}: {task_result.error}",
                    style="red",
                )
            )
            continue

        result = task_result.value

        if result is None:
            worker_failed = True
            console.print(
                Text(
                    f"✗ {task_result.item.name}: Worker returned no result.",
                    style="red",
                )
            )
            continue

        copied_reff_files += result.reff_files
        copied_videos += result.videos
        processed_any = True

    if worker_failed:
        console.print(
            "[yellow]Extraction encountered a worker error. "
            "Downloaded files remain in the dump folder; "
            "grouping was not started.[/yellow]"
        )
        return
    if processed_any:
        reff_grouping_result = group_files_into_flights(
            starting_flight_number=starting_flight_number,
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

        apply_custom_flight_names(flights)

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
            "Flight folders in dump": len(flights),
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
