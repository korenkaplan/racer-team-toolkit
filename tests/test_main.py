"""Tests for the application."""

from pathlib import Path

from racer_team_toolkit.reff_extractor.functions import (
    attach_videos_to_flight,
    find_target_reff_for_video,
)


def test_main_can_be_imported():
    """Test that main function can be imported from the main module."""

    from racer_team_toolkit.main import main as imported_main

    assert callable(imported_main)


def test_attach_videos_to_flight_moves_video(tmp_path: Path):
    """Matched videos are moved into the flight folder."""

    flight_dir = tmp_path / "Flight_01"
    flight_dir.mkdir()

    video_path = tmp_path / "VIDEO_TABLET_recording.mp4"
    video_path.write_bytes(b"video")

    videos = [
        {
            "filename": video_path.name,
            "path": str(video_path),
            "mtime": 1_060,
        }
    ]

    assert (
        attach_videos_to_flight(
            str(flight_dir),
            videos,
        )
        == 1
    )

    assert (flight_dir / video_path.name).exists()
    assert not video_path.exists()


def test_video_matches_previous_reff_within_30_seconds():
    """A video up to 30 seconds after a REFF belongs to that previous REFF."""

    video = {
        "filename": "VIDEO_TABLET_recording.mp4",
        "path": "video.mp4",
        "mtime": 1_030,
    }

    reff_files = [
        {
            "filename": "TABLET_first.reff",
            "path": "first.reff",
            "type": "TABLET",
            "mtime": 1_000,
        },
        {
            "filename": "TABLET_second.reff",
            "path": "second.reff",
            "type": "TABLET",
            "mtime": 1_200,
        },
    ]

    target = find_target_reff_for_video(
        video,
        reff_files,
    )

    assert target == reff_files[0]


def test_video_matches_next_reff_when_previous_is_more_than_30_seconds_away():
    """A video more than 30 seconds after a REFF belongs to the next REFF."""

    video = {
        "filename": "VIDEO_TABLET_recording.mp4",
        "path": "video.mp4",
        "mtime": 1_060,
    }

    reff_files = [
        {
            "filename": "TABLET_first.reff",
            "path": "first.reff",
            "type": "TABLET",
            "mtime": 1_000,
        },
        {
            "filename": "TABLET_second.reff",
            "path": "second.reff",
            "type": "TABLET",
            "mtime": 1_200,
        },
    ]

    target = find_target_reff_for_video(
        video,
        reff_files,
    )

    assert target == reff_files[1]


def test_video_only_matches_same_device_type():
    """A video only matches REFF files from the same device type."""

    video = {
        "filename": "VIDEO_TABLET_recording.mp4",
        "path": "video.mp4",
        "mtime": 1_010,
    }

    reff_files = [
        {
            "filename": "ISR_first.reff",
            "path": "isr.reff",
            "type": "ISR",
            "mtime": 1_000,
        },
        {
            "filename": "TABLET_first.reff",
            "path": "tablet.reff",
            "type": "TABLET",
            "mtime": 1_100,
        },
    ]

    target = find_target_reff_for_video(
        video,
        reff_files,
    )

    assert target == reff_files[1]


def test_video_matches_previous_reff_at_exact_30_second_boundary():
    """The 30-second boundary still belongs to the previous REFF."""

    video = {
        "filename": "VIDEO_TABLET_recording.mp4",
        "path": "video.mp4",
        "mtime": 1_030,
    }

    reff_files = [
        {
            "filename": "TABLET_first.reff",
            "path": "first.reff",
            "type": "TABLET",
            "mtime": 1_000,
        },
        {
            "filename": "TABLET_second.reff",
            "path": "second.reff",
            "type": "TABLET",
            "mtime": 1_100,
        },
    ]

    target = find_target_reff_for_video(
        video,
        reff_files,
    )

    assert target == reff_files[0]


def test_video_matches_next_reff_at_31_seconds():
    """A video 31 seconds after the previous REFF belongs to the next REFF."""

    video = {
        "filename": "VIDEO_TABLET_recording.mp4",
        "path": "video.mp4",
        "mtime": 1_031,
    }

    reff_files = [
        {
            "filename": "TABLET_first.reff",
            "path": "first.reff",
            "type": "TABLET",
            "mtime": 1_000,
        },
        {
            "filename": "TABLET_second.reff",
            "path": "second.reff",
            "type": "TABLET",
            "mtime": 1_100,
        },
    ]

    target = find_target_reff_for_video(
        video,
        reff_files,
    )

    assert target == reff_files[1]
