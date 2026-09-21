import os
import shutil
import subprocess
import time
from collections.abc import Callable
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
    run_adb_command,
)
from racer_team_toolkit.config import (
    LOCAL_DUMP_DIR,
    PROJECT_STATUS,
    VIDEO_REMOTE_PATH,
    AndroidDevice,
)
from racer_team_toolkit.reff_extractor.extraction_dataclasses import (
    DeviceExtractionResult,
)
from racer_team_toolkit.reff_extractor.time_adjustment_functions import (
    get_remote_files_from_today,
)
from racer_team_toolkit.ui.functions import console

MIN_REFF_FILE_SIZE_BYTES = 500_000
MIN_VIDEO_FILE_SIZE_BYTES = 5_000_000

TransferStatusCallback = Callable[[str], None] | None


def _emit_status(
    callback: TransferStatusCallback,
    message: str,
) -> None:
    """Emit a transfer status message when a callback is provided."""

    if callback is not None:
        callback(message)


def pull_reff_files(
    device: AndroidDevice,
    progress: Progress,
    task_id: TaskID,
    *,
    status_callback: TransferStatusCallback = None,
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
        status_callback=status_callback,
    )

    reff_files = list(reff_file_sizes)

    total_reff_files = len(reff_files)
    total_reff_bytes = sum(reff_file_sizes.values())

    if not reff_files:
        progress.console.print("[dim]  REFF: No files found[/dim]")
        _emit_status(status_callback, "REFF: No files found")
        return 0

    progress.update(
        task_id,
        total=total_reff_bytes,
        completed=0,
        description=(f"REFF: {get_transfer_verb()} 0 of {total_reff_files} files"),
        visible=True,
    )

    records_dir = os.path.join(
        LOCAL_DUMP_DIR,
        "Records",
    )

    os.makedirs(
        records_dir,
        exist_ok=True,
    )

    try:
        for file_number, remote_file in enumerate(
            reff_files,
            start=1,
        ):
            description = (
                f"REFF: {get_transfer_verb()} "
                f"{file_number} of {total_reff_files} files"
            )
            _emit_status(
                status_callback,
                f"{description}: {PurePosixPath(remote_file).name}",
            )

            pull_remote_file(
                device,
                remote_file,
                records_dir,
                progress,
                task_id,
                description,
                status_callback=status_callback,
            )

        return move_record_files(
            records_dir,
            device,
        )

    finally:
        remove_temporary_directory(
            records_dir,
        )


def pull_videos(
    device: AndroidDevice,
    progress: Progress,
    task_id: TaskID,
    *,
    status_callback: TransferStatusCallback = None,
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
        status_callback=status_callback,
    )

    video_files = list(video_file_sizes)

    total_video_files = len(video_files)
    total_video_bytes = sum(video_file_sizes.values())

    if not video_files:
        progress.console.print("[dim]  Videos: No files found[/dim]")
        _emit_status(status_callback, "Videos: No files found")
        return 0

    progress.update(
        task_id,
        total=total_video_bytes,
        completed=0,
        description=(f"Videos: {get_transfer_verb()} 0 of {total_video_files} files"),
        visible=True,
    )

    videos_dir = os.path.join(
        LOCAL_DUMP_DIR,
        "Screen-Videos",
    )

    os.makedirs(
        videos_dir,
        exist_ok=True,
    )

    try:
        for file_number, remote_file in enumerate(
            video_files,
            start=1,
        ):
            description = (
                f"Videos: {get_transfer_verb()} "
                f"{file_number} of {total_video_files} files"
            )
            _emit_status(
                status_callback,
                f"{description}: {PurePosixPath(remote_file).name}",
            )

            pull_remote_file(
                device,
                remote_file,
                videos_dir,
                progress,
                task_id,
                description,
                status_callback=status_callback,
            )

        return move_video_files(
            videos_dir,
            device,
        )

    finally:
        remove_temporary_directory(
            videos_dir,
        )


def pull_remote_file(
    device: AndroidDevice,
    remote_file: str,
    local_directory: str,
    progress: Progress,
    task_id: TaskID,
    description: str,
    *,
    status_callback: TransferStatusCallback = None,
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
        _emit_status(
            status_callback,
            f"✗ Failed to transfer {local_filename}",
        )

        if error.strip():
            console.print(f"[red]{error.strip()}[/red]")
            _emit_status(
                status_callback,
                error.strip(),
            )

        return False

    _emit_status(
        status_callback,
        f"✓ Transferred {local_filename}",
    )
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


def filter_remote_files_by_size(
    device: AndroidDevice,
    remote_files: list[str],
    minimum_size_bytes: int,
    *,
    status_callback: TransferStatusCallback = None,
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
            message = (
                f"Skipping {PurePosixPath(remote_file).name}: "
                f"{file_size / 1_000_000:.1f} MB "
                f"(minimum {minimum_size_bytes / 1_000_000:.1f} MB)"
            )
            console.print(f"[yellow]{message}[/yellow]")
            _emit_status(
                status_callback,
                f"⚠ {message}",
            )
            continue

        valid_files[remote_file] = file_size

    return valid_files


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


def transfer_file(source_path: str, destination_path: str) -> None:
    """Copy files in development and move them in production."""

    if PROJECT_STATUS == "development":
        shutil.copy2(source_path, destination_path)
    elif PROJECT_STATUS == "production":
        shutil.move(source_path, destination_path)
    else:
        raise ValueError(f"Unsupported project status: {PROJECT_STATUS}")


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


def add_device_prefix(filename: str, file_prefix: str) -> str:
    """Return a filename with a device prefix unless it already has one."""

    if filename.startswith(f"{file_prefix}_"):
        return filename

    return f"{file_prefix}_{filename}"


def remove_temporary_directory(
    directory: str,
) -> None:
    """Remove staging directory if it contains no real files."""

    if not os.path.isdir(directory):
        return

    real_files: list[str] = []

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.startswith("."):
                continue

            real_files.append(
                os.path.join(
                    root,
                    filename,
                )
            )

    if real_files:
        console.print(
            "[yellow]Temporary folder was not removed because real files still remain:[/yellow]"
        )

        for file_path in real_files:
            console.print(f"[yellow]  {file_path}[/yellow]")

        return

    try:
        shutil.rmtree(directory)

    except OSError as error:
        console.print(f"[yellow]Could not remove temporary folder {directory}: {error}[/yellow]")


def get_transfer_verb() -> str:
    """Return the output verb matching the configured transfer mode."""

    return "Moved" if PROJECT_STATUS == "production" else "Copied"


def process_device(
    device: AndroidDevice,
    *,
    include_videos: bool = True,
    status_callback: TransferStatusCallback = None,
) -> DeviceExtractionResult:
    """Pull REFF files from one device and optionally pull its videos."""

    print(f"\n[--->] Starting {get_transfer_verb().lower()} from: {device.name}")
    _emit_status(
        status_callback,
        f"▶ Starting {get_transfer_verb().lower()} from {device.name}",
    )

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
            visible=False,
        )

        reff_files = pull_reff_files(
            device,
            progress,
            reff_task_id,
            status_callback=status_callback,
        )

        videos = 0

        if include_videos:
            video_task_id = progress.add_task(
                f"Videos: {get_transfer_verb()} 0 of 0 files",
                total=0,
                visible=False,
            )

            videos = pull_videos(
                device,
                progress,
                video_task_id,
                status_callback=status_callback,
            )

    print(f"[<---] Finished {get_transfer_verb().lower()} from: {device.name}")
    _emit_status(
        status_callback,
        f"✓ Finished {get_transfer_verb().lower()} from {device.name}",
    )

    return DeviceExtractionResult(
        reff_files=reff_files,
        videos=videos,
    )
