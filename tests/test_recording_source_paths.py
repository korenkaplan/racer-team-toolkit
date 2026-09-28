"""Tests for multiple REFF and video source paths."""

from subprocess import CompletedProcess
from unittest.mock import patch

from racer_team_toolkit.config import (
    REFF_REMOTE_PATHS,
    VIDEO_REMOTE_PATHS,
    AndroidDevice,
)
from racer_team_toolkit.quick_reset.functions import build_reset_plan_counts
from racer_team_toolkit.reff_extractor.transfer import (
    get_remote_files_from_today_from_paths,
)


def make_device() -> AndroidDevice:
    return AndroidDevice(
        name="Tablet",
        serial="TEST123",
        remote_log_path=REFF_REMOTE_PATHS[0],
        file_prefix="TABLET",
        apk_name_pattern="*.apk",
        package_name="com.example.test",
    )


def test_default_source_lists_cover_both_android_layouts() -> None:
    assert REFF_REMOTE_PATHS == (
        "/sdcard/Eyesatop-Records/Manual-Records",
        "/sdcard/Records",
    )
    assert VIDEO_REMOTE_PATHS == (
        "/sdcard/Eyesatop-Records/Videos/Full-Screen",
        "/sdcard/Eyesatop-Records/Videos/Camera-Only",
        "/sdcard/Eyesatop-Records/Screen-Videos",
    )


def test_extraction_collects_files_from_every_source() -> None:
    device = make_device()

    with patch(
        "racer_team_toolkit.reff_extractor.transfer.get_remote_files_from_today",
        side_effect=[
            ["/new/a.reff"],
            ["/old/b.reff"],
        ],
    ):
        files = get_remote_files_from_today_from_paths(
            device,
            ("/new", "/old"),
        )

    assert files == [
        "/new/a.reff",
        "/old/b.reff",
    ]


def test_reset_counts_every_reff_and_video_source() -> None:
    device = make_device()

    file_counts = {
        REFF_REMOTE_PATHS[0]: 2,
        REFF_REMOTE_PATHS[1]: 3,
        VIDEO_REMOTE_PATHS[0]: 4,
        VIDEO_REMOTE_PATHS[1]: 5,
    }

    def fake_run_adb(arguments, **_kwargs):
        remote_path = arguments[-3]
        count = file_counts[remote_path]
        stdout = "\n".join(f"/file/{index}" for index in range(count))
        return CompletedProcess(arguments, 0, stdout, "")

    with patch(
        "racer_team_toolkit.quick_reset.functions.run_adb_command",
        side_effect=fake_run_adb,
    ):
        counts = build_reset_plan_counts(
            [device],
            {device.serial: {"reff", "videos"}},
        )

    assert counts[device.serial] == {
        "reff": 5,
        "videos": 9,
    }
