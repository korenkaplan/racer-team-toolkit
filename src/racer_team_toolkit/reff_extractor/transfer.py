import os
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from queue import Queue
from typing import Any, Callable

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
    MIN_REFF_FILE_SIZE_BYTES,
    MIN_VIDEO_FILE_SIZE_BYTES,
    PROJECT_STATUS,
    REFF_REMOTE_PATHS,
    VIDEO_REMOTE_PATHS,
    AndroidDevice,
)
from racer_team_toolkit.reff_extractor.custom_naming import (
    flag_custom_recording_filename,
)
from racer_team_toolkit.reff_extractor.extraction_dataclasses import (
    DeviceExtractionResult,
)
from racer_team_toolkit.reff_extractor.time_adjustment_functions import (
    get_remote_files_from_today,
)
from racer_team_toolkit.ui.functions import console

TransferStatusCallback = Callable[[str], None] | None


@dataclass(frozen=True)
class TransferEvent:
    """Progress update or message sent from a device worker."""

    device_name: str
    task_id: TaskID | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    message: str | None = None


class QueuedTransferProgress:
    """Forward worker progress updates without touching the terminal."""

    def __init__(
        self,
        events: Queue[TransferEvent],
        device_name: str,
    ) -> None:
        self.events = events
        self.device_name = device_name

        # Support existing progress.console.print(...) calls.
        self.console = self

    def update(self, task_id: TaskID, **changes: Any) -> None:
        self.events.put(
            TransferEvent(
                device_name=self.device_name,
                task_id=task_id,
                changes=changes,
            )
        )

    def print(self, message: str) -> None:
        self.events.put(
            TransferEvent(
                device_name=self.device_name,
                message=message,
            )
        )


def get_remote_files_from_today_from_paths(
    device: AndroidDevice,
    remote_paths: tuple[str, ...],
) -> list[str]:
    """Return today's files from every configured remote source path."""

    files: list[str] = []

    for remote_path in remote_paths:
        files.extend(
            get_remote_files_from_today(
                device,
                remote_path,
            )
        )

    return list(dict.fromkeys(files))


def _emit_status(
    callback: TransferStatusCallback,
    message: str,
) -> None:
    """Emit routine status for callback consumers outside queued CLI progress."""

    if callback is None:
        return

    # Queued CLI progress already displays file-transfer status in its rows.
    if isinstance(
        getattr(callback, "__self__", None),
        QueuedTransferProgress,
    ):
        return

    callback(message)


def report_transfer_message(
    message: str,
    *,
    status_callback: TransferStatusCallback = None,
    style: str | None = None,
) -> None:
    """Send worker messages through callback or print during sequential use."""

    if status_callback is not None:
        status_callback(message)
    else:
        console.print(message, style=style, markup=False)


def pull_reff_files(
    device: AndroidDevice,
    progress: Progress | QueuedTransferProgress,
    task_id: TaskID,
    *,
    status_callback: TransferStatusCallback = None,
) -> int:
    """Pull today's valid REFF files from one Android device."""

    reff_files = get_remote_files_from_today_from_paths(
        device,
        REFF_REMOTE_PATHS,
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
        report_transfer_message(
            "REFF: No files found",
            status_callback=status_callback,
            style="dim",
        )
        return 0

    progress.update(
        task_id,
        total=total_reff_bytes,
        completed=0,
        description=(f"REFF: {get_transfer_verb()} 0 of {total_reff_files} files"),
        visible=True,
    )

    records_dir = tempfile.mkdtemp(
        prefix=f"Records_{device.file_prefix}_",
        dir=LOCAL_DUMP_DIR,
    )

    successfully_pulled_files: list[str] = []

    try:
        for file_number, remote_file in enumerate(
            reff_files,
            start=1,
        ):
            description = f"REFF: {get_transfer_verb()} {file_number} of {total_reff_files} files"
            _emit_status(
                status_callback,
                f"{description}: {PurePosixPath(remote_file).name}",
            )

            pulled = pull_remote_file(
                device,
                remote_file,
                records_dir,
                progress,
                task_id,
                description,
                status_callback=status_callback,
            )

            if pulled:
                successfully_pulled_files.append(remote_file)

        return move_record_files(
            records_dir,
            device,
            successfully_pulled_files,
            status_callback=status_callback,
        )

    finally:
        remove_temporary_directory(
            records_dir,
            status_callback=status_callback,
        )


def pull_videos(
    device: AndroidDevice,
    progress: Progress | QueuedTransferProgress,
    task_id: TaskID,
    *,
    status_callback: TransferStatusCallback = None,
) -> int:
    """Pull today's valid screen recordings from one Android device."""

    video_files = get_remote_files_from_today_from_paths(
        device,
        VIDEO_REMOTE_PATHS,
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
        report_transfer_message(
            "Videos: No files found",
            status_callback=status_callback,
            style="dim",
        )
        return 0
    progress.update(
        task_id,
        total=total_video_bytes,
        completed=0,
        description=(f"Videos: {get_transfer_verb()} 0 of {total_video_files} files"),
        visible=True,
    )

    videos_dir = tempfile.mkdtemp(
        prefix=f"Screen-Videos_{device.file_prefix}_",
        dir=LOCAL_DUMP_DIR,
    )

    successfully_pulled_files: list[str] = []

    try:
        for file_number, remote_file in enumerate(
            video_files,
            start=1,
        ):
            description = (
                f"Videos: {get_transfer_verb()} {file_number} of {total_video_files} files"
            )
            _emit_status(
                status_callback,
                f"{description}: {PurePosixPath(remote_file).name}",
            )

            pulled = pull_remote_file(
                device,
                remote_file,
                videos_dir,
                progress,
                task_id,
                description,
                status_callback=status_callback,
            )

            if pulled:
                successfully_pulled_files.append(remote_file)

        return move_video_files(
            videos_dir,
            device,
            successfully_pulled_files,
            status_callback=status_callback,
        )

    finally:
        remove_temporary_directory(
            videos_dir,
            status_callback=status_callback,
        )


def pull_remote_file(
    device: AndroidDevice,
    remote_file: str,
    local_directory: str,
    progress: Progress | QueuedTransferProgress,
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

        report_transfer_message(
            f"✗ Failed to transfer {local_filename}",
            status_callback=status_callback,
            style="red",
        )

        if error.strip():
            report_transfer_message(
                error.strip(),
                status_callback=status_callback,
                style="red",
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
    """Return remote size, preserving spaces and special characters."""

    command = shlex.join(["stat", "-c", "%s", remote_file])

    result = run_adb_command(["-s", device.serial, "shell", command])

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
            report_transfer_message(
                f"⚠ {message}",
                status_callback=status_callback,
                style="yellow",
            )
            continue

        valid_files[remote_file] = file_size

    return valid_files


def move_video_files(
    videos_dir: str,
    device: AndroidDevice,
    remote_files: list[str],
    *,
    status_callback: TransferStatusCallback = None,
) -> int:
    """Finalize downloaded videos and delete remote sources in production."""

    copied_count = 0
    remote_by_filename = {
        PurePosixPath(remote_file).name: remote_file for remote_file in remote_files
    }

    for root, _, filenames in os.walk(videos_dir):
        for filename in filenames:
            remote_file = remote_by_filename.get(filename)

            if remote_file is None:
                continue

            source_path = os.path.join(
                root,
                filename,
            )

            flagged_filename = flag_custom_recording_filename(filename)

            destination_name = f"VIDEO_{device.file_prefix}_{flagged_filename}"

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

                    if not delete_remote_file(
                        device,
                        remote_file,
                        status_callback=status_callback,
                    ):
                        report_transfer_message(
                            f"⚠ Video copied locally but remote delete failed: {filename}",
                            status_callback=status_callback,
                            style="yellow",
                        )
                        continue

                else:
                    os.remove(source_path)

                copied_count += 1

            except OSError as error:
                report_transfer_message(
                    f"✗ Failed to move a screen video: {error}",
                    status_callback=status_callback,
                    style="red",
                )
    return copied_count


def move_record_files(
    records_dir: str,
    device: AndroidDevice,
    remote_files: list[str],
    *,
    status_callback: TransferStatusCallback = None,
) -> int:
    """Finalize downloaded REFF files and delete remote sources in production."""

    copied_count = 0
    remote_by_filename = {
        PurePosixPath(remote_file).name: remote_file for remote_file in remote_files
    }

    for root, _, filenames in os.walk(records_dir):
        for filename in filenames:
            remote_file = remote_by_filename.get(filename)

            if remote_file is None:
                continue

            source_path = os.path.join(
                root,
                filename,
            )

            flagged_filename = flag_custom_recording_filename(filename)

            prefixed_filename = add_device_prefix(
                flagged_filename,
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

                    if not delete_remote_file(
                        device,
                        remote_file,
                        status_callback=status_callback,
                    ):
                        report_transfer_message(
                            f"⚠ REFF copied locally but remote delete failed: {filename}",
                            status_callback=status_callback,
                            style="yellow",
                        )
                        continue

                else:
                    os.remove(source_path)

                copied_count += 1
            except OSError as error:
                report_transfer_message(
                    f"✗ Failed to move a REFF file: {error}",
                    status_callback=status_callback,
                    style="red",
                )
    return copied_count


def delete_remote_file(
    device: AndroidDevice,
    remote_file: str,
    *,
    status_callback: TransferStatusCallback = None,
) -> bool:
    """Delete one remote file after a successful production transfer."""

    result = run_adb_command(
        [
            "-s",
            device.serial,
            "shell",
            "rm",
            "-f",
            remote_file,
        ]
    )

    if result.returncode != 0:
        return False

    _emit_status(
        status_callback,
        f"✓ Removed remote source: {PurePosixPath(remote_file).name}",
    )

    return True


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
    *,
    status_callback: TransferStatusCallback = None,
) -> None:
    """Remove staging directory only when no real files remain."""

    if not os.path.isdir(directory):
        return

    real_files: list[str] = []

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.startswith("."):
                continue

            real_files.append(os.path.join(root, filename))

    if real_files:
        report_transfer_message(
            "Temporary folder was not removed because real files still remain:",
            status_callback=status_callback,
            style="yellow",
        )

        for file_path in real_files:
            report_transfer_message(
                f"  {file_path}",
                status_callback=status_callback,
                style="yellow",
            )

        return

    try:
        shutil.rmtree(directory)
    except OSError as error:
        report_transfer_message(
            f"Could not remove temporary folder {directory}: {error}",
            status_callback=status_callback,
            style="yellow",
        )


def get_transfer_verb() -> str:
    """Return the output verb matching the configured transfer mode."""

    return "Moved" if PROJECT_STATUS == "production" else "Copied"


def process_device(
    device: AndroidDevice,
    *,
    include_videos: bool = True,
    status_callback: TransferStatusCallback = None,
    progress: Progress | QueuedTransferProgress | None = None,
    reff_task_id: TaskID | None = None,
    video_task_id: TaskID | None = None,
) -> DeviceExtractionResult:
    """Pull one device's files using local or externally managed progress."""

    if progress is not None:
        if reff_task_id is None:
            raise ValueError("REFF progress task is required")

        if include_videos and video_task_id is None:
            raise ValueError("Video progress task is required")

        return pull_device_files(
            device,
            progress,
            reff_task_id,
            video_task_id,
            include_videos=include_videos,
            status_callback=status_callback,
        )

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
    ) as local_progress:
        local_reff_task = local_progress.add_task(
            f"REFF: {get_transfer_verb()} 0 of 0 files",
            total=0,
            visible=False,
        )

        local_video_task = None

        if include_videos:
            local_video_task = local_progress.add_task(
                f"Videos: {get_transfer_verb()} 0 of 0 files",
                total=0,
                visible=False,
            )

        result = pull_device_files(
            device,
            local_progress,
            local_reff_task,
            local_video_task,
            include_videos=include_videos,
            status_callback=status_callback,
        )

    print(f"[<---] Finished {get_transfer_verb().lower()} from: {device.name}")
    _emit_status(
        status_callback,
        f"✓ Finished {get_transfer_verb().lower()} from {device.name}",
    )

    return result


def pull_device_files(
    device: AndroidDevice,
    progress: Progress | QueuedTransferProgress,
    reff_task_id: TaskID,
    video_task_id: TaskID | None,
    *,
    include_videos: bool,
    status_callback: TransferStatusCallback = None,
) -> DeviceExtractionResult:
    """Pull REFFs, then videos, sequentially for one device."""

    reff_files = pull_reff_files(
        device,
        progress,
        reff_task_id,
        status_callback=status_callback,
    )

    videos = 0

    if include_videos:
        if video_task_id is None:
            raise ValueError("Video progress task is required")

        videos = pull_videos(
            device,
            progress,
            video_task_id,
            status_callback=status_callback,
        )

    return DeviceExtractionResult(
        reff_files=reff_files,
        videos=videos,
    )
