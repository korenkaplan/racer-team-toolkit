"""Tests for repeated extraction grouping and flight numbering."""

import os
from pathlib import Path

from racer_team_toolkit.reff_extractor import grouping


def write_file(
    path: Path,
    *,
    mtime: float,
    size: int = 1024,
) -> None:
    """Create a small local fixture with a controlled modification time."""

    path.write_bytes(b"x" * size)
    os.utime(
        path,
        (
            mtime,
            mtime,
        ),
    )


def test_existing_flight_is_checked_before_standalone_grouping(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Matching existing Flight folders must win over new standalone grouping."""

    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(tmp_path),
    )

    flight_dir = tmp_path / "Flight_05_28-09-2026_12-30-00"
    flight_dir.mkdir()

    base_time = 1_800_000_000.0

    write_file(
        flight_dir / "RACER_existing.reff",
        mtime=base_time,
    )
    write_file(
        tmp_path / "ISR_new.reff",
        mtime=base_time + 20,
    )
    write_file(
        tmp_path / "TABLET_new.reff",
        mtime=base_time + 30,
    )

    result = grouping.group_files_into_flights()

    assert (flight_dir / "ISR_new.reff").is_file()
    assert (flight_dir / "TABLET_new.reff").is_file()
    assert not (tmp_path / "ISR_new.reff").exists()
    assert not (tmp_path / "TABLET_new.reff").exists()
    assert len(result.flights) == 1
    assert result.flights[0].number == 5
    assert result.next_flight_number == 6


def test_previous_standalone_reff_is_reconsidered_on_later_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A REFF left standalone by an earlier run participates in later grouping."""

    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(tmp_path),
    )

    base_time = 1_800_000_000.0

    write_file(
        tmp_path / "RACER_previous.reff",
        mtime=base_time,
    )

    first_result = grouping.group_files_into_flights()

    assert len(first_result.standalone_reffs) == 1
    assert (tmp_path / "RACER_previous.reff").is_file()

    write_file(
        tmp_path / "ISR_current.reff",
        mtime=base_time + 30,
    )

    second_result = grouping.group_files_into_flights()

    flight_dirs = [
        path
        for path in tmp_path.iterdir()
        if path.is_dir() and path.name.startswith("Flight_")
    ]

    assert len(flight_dirs) == 1
    assert flight_dirs[0].name.startswith("Flight_01_")
    assert (flight_dirs[0] / "RACER_previous.reff").is_file()
    assert (flight_dirs[0] / "ISR_current.reff").is_file()
    assert second_result.standalone_reffs == []


def test_numbering_starts_after_highest_folder_and_counts_standalone_reffs_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Deleted folder numbers stay unused and standalone videos do not count."""

    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(tmp_path),
    )

    (tmp_path / "Flight_01_old").mkdir()
    (tmp_path / "Flight_05_old").mkdir()

    write_file(
        tmp_path / "RACER_standalone.reff",
        mtime=1_800_001_000.0,
    )
    write_file(
        tmp_path / "VIDEO_ISR_standalone.mp4",
        mtime=1_800_001_100.0,
    )

    assert grouping.get_next_flight_number() == 7


def test_existing_flight_name_is_not_changed_when_reff_joins(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Adding a matching REFF must preserve the existing folder name."""

    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(tmp_path),
    )

    flight_name = "Flight_09_original-name"
    flight_dir = tmp_path / flight_name
    flight_dir.mkdir()

    base_time = 1_800_000_000.0

    write_file(
        flight_dir / "RACER_existing.reff",
        mtime=base_time,
    )
    write_file(
        tmp_path / "ISR_new.reff",
        mtime=base_time + 10,
    )

    grouping.group_files_into_flights()

    assert flight_dir.is_dir()
    assert (flight_dir / "ISR_new.reff").is_file()
    assert not any(
        path.is_dir()
        and path.name.startswith("Flight_")
        and path.name != flight_name
        for path in tmp_path.iterdir()
    )
