"""Tests for IMU recordings extraction."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from racer_team_toolkit.imu_recordings.dataclasses import ImuRecording
from racer_team_toolkit.imu_recordings.functions import (
    choose_imu_recordings,
    clear_imu_csv_files,
    copy_imu_recordings,
    get_imu_recordings,
    get_local_imu_directory,
)


def make_sftp_context(sftp: MagicMock) -> MagicMock:
    """Return a context manager that yields the supplied SFTP mock."""

    context = MagicMock()
    context.__enter__.return_value = sftp
    context.__exit__.return_value = False
    return context


def test_get_imu_recordings_filters_and_sorts_newest_first() -> None:
    """Only IMU CSV files are returned, with the newest first."""

    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        SimpleNamespace(
            filename="imu_20260920_090000.csv",
            st_mtime=100,
            st_size=1000,
        ),
        SimpleNamespace(
            filename="notes.txt",
            st_mtime=300,
            st_size=2000,
        ),
        SimpleNamespace(
            filename="imu_20260921_100000.csv",
            st_mtime=200,
            st_size=3000,
        ),
        SimpleNamespace(
            filename="other_20260921.csv",
            st_mtime=400,
            st_size=4000,
        ),
    ]

    ssh = MagicMock()
    ssh.open_sftp.return_value = make_sftp_context(sftp)

    recordings = get_imu_recordings(ssh)

    assert [recording.filename for recording in recordings] == [
        "imu_20260921_100000.csv",
        "imu_20260920_090000.csv",
    ]
    assert [recording.size for recording in recordings] == [
        3000,
        1000,
    ]
    assert recordings[0].modified_at == datetime.fromtimestamp(200)
    assert recordings[1].modified_at == datetime.fromtimestamp(100)


def test_choose_imu_recordings_returns_selected_items() -> None:
    """The checkbox selections are mapped back to their recordings."""

    recordings = [
        ImuRecording(
            filename="imu_new.csv",
            modified_at=datetime(2026, 9, 21, 10, 0, 0),
            size=200,
        ),
        ImuRecording(
            filename="imu_old.csv",
            modified_at=datetime(2026, 9, 20, 9, 0, 0),
            size=100,
        ),
    ]

    selected_label = "imu_old.csv    20/09/2026 09:00:00"

    with patch(
        "racer_team_toolkit.imu_recordings.functions.select_multiple_menu",
        return_value=[selected_label],
    ):
        selected = choose_imu_recordings(recordings)

    assert selected == [recordings[1]]


def test_choose_imu_recordings_returns_empty_when_nothing_selected() -> None:
    """Cancelling or selecting nothing returns an empty list."""

    recording = ImuRecording(
        filename="imu_test.csv",
        modified_at=datetime(2026, 9, 21, 10, 0, 0),
        size=100,
    )

    with patch(
        "racer_team_toolkit.imu_recordings.functions.select_multiple_menu",
        return_value=[],
    ):
        selected = choose_imu_recordings([recording])

    assert selected == []


def test_get_local_imu_directory_uses_downloads(tmp_path: Path) -> None:
    """The local destination is the IMU Recordings folder under Downloads."""

    with patch(
        "racer_team_toolkit.imu_recordings.functions.Path.home",
        return_value=tmp_path,
    ):
        destination = get_local_imu_directory()

    assert destination == tmp_path / "Downloads" / "IMU Recordings"


def test_copy_imu_recordings_downloads_selected_files(tmp_path: Path) -> None:
    """Selected recordings are copied from the expected remote paths."""

    recordings = [
        ImuRecording(
            filename="imu_one.csv",
            modified_at=datetime(2026, 9, 21, 10, 0, 0),
            size=100,
        ),
        ImuRecording(
            filename="imu_two.csv",
            modified_at=datetime(2026, 9, 21, 11, 0, 0),
            size=200,
        ),
    ]

    sftp = MagicMock()
    ssh = MagicMock()
    ssh.open_sftp.return_value = make_sftp_context(sftp)

    copied = copy_imu_recordings(
        ssh,
        recordings,
        tmp_path,
    )

    assert copied == [
        tmp_path / "imu_one.csv",
        tmp_path / "imu_two.csv",
    ]
    assert sftp.get.call_count == 2

    first_remote, first_local = sftp.get.call_args_list[0].args[:2]
    second_remote, second_local = sftp.get.call_args_list[1].args[:2]

    assert first_remote == "/home/pod/imuRecord/imu_one.csv"
    assert first_local == str(tmp_path / "imu_one.csv")
    assert second_remote == "/home/pod/imuRecord/imu_two.csv"
    assert second_local == str(tmp_path / "imu_two.csv")


def test_copy_imu_recordings_keeps_successful_files_when_one_fails(
    tmp_path: Path,
) -> None:
    """A failed transfer does not discard successfully copied recordings."""

    recordings = [
        ImuRecording(
            filename="imu_ok.csv",
            modified_at=datetime(2026, 9, 21, 10, 0, 0),
            size=100,
        ),
        ImuRecording(
            filename="imu_fail.csv",
            modified_at=datetime(2026, 9, 21, 11, 0, 0),
            size=200,
        ),
    ]

    sftp = MagicMock()
    sftp.get.side_effect = [
        None,
        OSError("transfer failed"),
    ]

    ssh = MagicMock()
    ssh.open_sftp.return_value = make_sftp_context(sftp)

    copied = copy_imu_recordings(
        ssh,
        recordings,
        tmp_path,
    )

    assert copied == [
        tmp_path / "imu_ok.csv",
    ]


def test_clear_imu_csv_files_deletes_only_csv_files() -> None:
    """Cleanup removes CSV files and leaves non-CSV files untouched."""

    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        SimpleNamespace(filename="imu_one.csv"),
        SimpleNamespace(filename="imu_two.CSV"),
        SimpleNamespace(filename="notes.txt"),
    ]

    ssh = MagicMock()
    ssh.open_sftp.return_value = make_sftp_context(sftp)

    deleted_count, failures = clear_imu_csv_files(ssh)

    assert deleted_count == 2
    assert failures == []
    assert [call.args[0] for call in sftp.remove.call_args_list] == [
        "/home/pod/imuRecord/imu_one.csv",
        "/home/pod/imuRecord/imu_two.CSV",
    ]


def test_clear_imu_csv_files_keeps_going_when_one_delete_fails() -> None:
    """Cleanup reports a failed delete while continuing with the other CSV files."""

    sftp = MagicMock()
    sftp.listdir_attr.return_value = [
        SimpleNamespace(filename="imu_ok.csv"),
        SimpleNamespace(filename="imu_fail.csv"),
    ]
    sftp.remove.side_effect = [
        None,
        OSError("delete failed"),
    ]

    ssh = MagicMock()
    ssh.open_sftp.return_value = make_sftp_context(sftp)

    deleted_count, failures = clear_imu_csv_files(ssh)

    assert deleted_count == 1
    assert len(failures) == 1
    assert failures[0].startswith("imu_fail.csv:")
