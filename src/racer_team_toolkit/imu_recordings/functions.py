"""Reusable IMU recordings extraction operations."""

from datetime import datetime
from pathlib import Path

import paramiko
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TransferSpeedColumn,
)

from racer_team_toolkit.imu_recordings.config import (
    IMU_FILE_PREFIX,
    IMU_FILE_SUFFIX,
    IMU_REMOTE_DIRECTORY,
)
from racer_team_toolkit.imu_recordings.dataclasses import (
    ImuRecording,
)
from racer_team_toolkit.ui.functions import (
    console,
    select_multiple_menu,
)


def get_imu_recordings(
    ssh: paramiko.SSHClient,
) -> list[ImuRecording]:
    """Return IMU recordings sorted newest first."""

    recordings: list[ImuRecording] = []

    with ssh.open_sftp() as sftp:
        for entry in sftp.listdir_attr(IMU_REMOTE_DIRECTORY):
            if not (
                entry.filename.startswith(IMU_FILE_PREFIX)
                and entry.filename.endswith(IMU_FILE_SUFFIX)
            ):
                continue

            recordings.append(
                ImuRecording(
                    filename=entry.filename,
                    modified_at=datetime.fromtimestamp(entry.st_mtime),
                    size=entry.st_size,
                )
            )

    recordings.sort(
        key=lambda recording: recording.modified_at,
        reverse=True,
    )

    return recordings


def copy_imu_recordings(
    ssh,
    recordings: list[ImuRecording],
    destination: Path,
) -> list[Path]:
    """Copy selected IMU recordings from the server to a local folder."""

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    copied_files: list[Path] = []

    with ssh.open_sftp() as sftp:
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
        ) as progress:
            for recording in recordings:
                remote_path = f"{IMU_REMOTE_DIRECTORY}/{recording.filename}"

                local_path = destination / recording.filename

                task_id = progress.add_task(
                    recording.filename,
                    total=recording.size,
                )

                try:
                    sftp.get(
                        remote_path,
                        str(local_path),
                        callback=lambda transferred, total: progress.update(
                            task_id,
                            completed=transferred,
                            total=total,
                        ),
                    )

                    copied_files.append(local_path)

                except OSError as error:
                    console.print(f"[red]Failed to copy {recording.filename}: {error}[/red]")

    return copied_files


def clear_imu_csv_files(
    ssh: paramiko.SSHClient,
) -> tuple[int, list[str]]:
    """Delete all CSV files directly inside the remote IMU recordings directory."""

    deleted_count = 0
    failures: list[str] = []

    with ssh.open_sftp() as sftp:
        for entry in sftp.listdir_attr(IMU_REMOTE_DIRECTORY):
            if not entry.filename.lower().endswith(IMU_FILE_SUFFIX):
                continue

            remote_path = f"{IMU_REMOTE_DIRECTORY}/{entry.filename}"

            try:
                sftp.remove(remote_path)
                deleted_count += 1

            except OSError as error:
                failures.append(f"{entry.filename}: {error}")

    return deleted_count, failures


def get_local_imu_directory() -> Path:
    """Return the local folder used for IMU recordings."""

    return Path.home() / "Downloads" / "IMU Recordings"


def choose_imu_recordings(
    recordings: list[ImuRecording],
) -> list[ImuRecording]:
    """Let the user select one or more IMU recordings."""

    if not recordings:
        return []

    choices = [
        (f"{recording.filename}    {recording.modified_at:%d/%m/%Y %H:%M:%S}")
        for recording in recordings
    ]

    selected_choices = select_multiple_menu(
        "Select IMU recordings:",
        choices,
    )

    if not selected_choices:
        return []

    selected_recordings: list[ImuRecording] = []

    for recording, choice in zip(
        recordings,
        choices,
        strict=True,
    ):
        if choice in selected_choices:
            selected_recordings.append(recording)

    return selected_recordings
