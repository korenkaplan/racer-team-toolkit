"""Tests for the application."""

import os
from pathlib import Path
from unittest.mock import patch

from racer_team_toolkit.reff_extractor.functions import attach_videos_to_flight


def test_main_can_be_imported():
    """Test that main function can be imported from the main module."""
    from racer_team_toolkit.main import main as imported_main

    assert callable(imported_main)


def test_attach_videos_to_flight_moves_videos_within_time_limit(tmp_path: Path):
    """Videos close to a flight log are moved into that flight folder."""
    flight_dir = tmp_path / "Flight_01"
    flight_dir.mkdir()
    video_path = tmp_path / "VIDEO_TABLET_recording.mp4"
    video_path.write_bytes(b"video")
    os.utime(video_path, (1_060, 1_060))

    flight_files = [{"mtime": 1_000}]
    videos = [{"filename": video_path.name, "path": str(video_path), "mtime": 1_060}]

    with patch("racer_team_toolkit.reff_extractor.functions.PROJECT_STATUS", "production"):
        assert attach_videos_to_flight(str(flight_dir), flight_files, videos) == 1

    assert (flight_dir / video_path.name).exists()
    assert not video_path.exists()


def test_attach_videos_to_flight_moves_files_into_flight_folder(tmp_path: Path):
    """Videos close to a flight log are not duplicated in the dump root."""
    flight_dir = tmp_path / "Flight_01"
    flight_dir.mkdir()
    video_path = tmp_path / "VIDEO_TABLET_recording.mp4"
    video_path.write_bytes(b"video")
    os.utime(video_path, (1_060, 1_060))

    flight_files = [{"mtime": 1_000}]
    videos = [{"filename": video_path.name, "path": str(video_path), "mtime": 1_060}]

    assert attach_videos_to_flight(str(flight_dir), flight_files, videos) == 1

    assert (flight_dir / video_path.name).exists()
    assert not video_path.exists()
