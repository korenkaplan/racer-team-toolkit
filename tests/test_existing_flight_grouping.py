"""Tests for repeated extraction grouping and flight numbering."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from racer_team_toolkit.reff_extractor import extraction, grouping


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
        path for path in tmp_path.iterdir() if path.is_dir() and path.name.startswith("Flight_")
    ]

    assert len(flight_dirs) == 1
    assert flight_dirs[0].name.startswith("Flight_01_")
    assert (flight_dirs[0] / "RACER_previous.reff").is_file()
    assert (flight_dirs[0] / "ISR_current.reff").is_file()
    assert second_result.standalone_reffs == []


def test_numbering_counts_existing_standalone_reffs_and_preserves_gaps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Existing standalone REFFs count; deleted folder numbers stay unused."""

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
        path.is_dir() and path.name.startswith("Flight_") and path.name != flight_name
        for path in tmp_path.iterdir()
    )


@pytest.mark.parametrize(
    ("existing_names", "existing_reffs", "incoming_standalone", "expected_number"),
    [
        ((), 0, 0, 1),
        ((), 0, 3, 1),
        (("flight_01", "Flight_2"), 2, 0, 5),
        (("Flight_01", "Flight_02"), 2, 3, 5),
        (("Flight_01", "Flight_05"), 1, 0, 7),
    ],
)
@pytest.mark.parametrize("include_videos", [False, True])
def test_extraction_captures_number_before_pulling_new_recordings(
    tmp_path: Path,
    monkeypatch,
    existing_names: tuple[str, ...],
    existing_reffs: int,
    incoming_standalone: int,
    expected_number: int,
    include_videos: bool,
) -> None:
    """Existing REFFs reserve numbers; incoming grouped REFFs never count twice."""

    monkeypatch.setattr(grouping, "LOCAL_DUMP_DIR", str(tmp_path))
    monkeypatch.setattr(extraction, "LOCAL_DUMP_DIR", str(tmp_path))
    for name in existing_names:
        (tmp_path / name).mkdir()
    base_time = 1_800_000_000.0
    for index in range(existing_reffs):
        write_file(
            tmp_path / f"ISR_existing_{index}.reff",
            mtime=base_time - (index + 1) * 3600,
        )
    write_file(tmp_path / "VIDEO_TABLET_existing.mp4", mtime=base_time - 86400)

    device = SimpleNamespace(name="Racer", serial="TEST", file_prefix="RACER")
    monkeypatch.setattr(extraction, "get_connected_android_devices", lambda: [device])
    monkeypatch.setattr(
        extraction, "validate_device_times_before_extraction", lambda devices: devices
    )
    monkeypatch.setattr(extraction, "print_connected_devices", lambda devices: None)
    captured = {}
    monkeypatch.setattr(
        extraction, "print_extraction_result", lambda *args: captured.update(args=args)
    )

    def fake_process_device(
        device,
        *,
        include_videos,
        status_callback=None,
        progress=None,
        reff_task_id=None,
        video_task_id=None,
    ):
        write_file(tmp_path / "RACER_current.reff", mtime=base_time)
        partner = "VIDEO_RACER_current.mp4" if include_videos else "ISR_current.reff"
        write_file(tmp_path / partner, mtime=base_time + 20)
        for index in range(incoming_standalone):
            write_file(
                tmp_path / f"RACER_incoming_{index}.reff",
                mtime=base_time + (index + 1) * 3600,
            )
        return SimpleNamespace(reff_files=1, videos=int(include_videos))

    monkeypatch.setattr(extraction, "process_device", fake_process_device)
    extraction.run_extraction(include_videos=include_videos)

    flights = captured["args"][1]
    new_flights = [flight for flight in flights if flight.name not in existing_names]
    assert len(new_flights) == 1
    flight = new_flights[0]
    assert flight.number == expected_number
    assert flight.name.startswith(f"Flight_{expected_number:02d}_")
    assert (Path(flight.path) / "RACER_current.reff").is_file()
    partner = "VIDEO_RACER_current.mp4" if include_videos else "ISR_current.reff"
    assert (Path(flight.path) / partner).is_file()
    assert all((tmp_path / name).is_dir() for name in existing_names)
    assert len(grouping.collect_reff_files()) == existing_reffs + incoming_standalone


def test_reff_and_video_groups_share_one_pre_extraction_counter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Video-created folders continue after REFF groups without recounting files."""

    monkeypatch.setattr(grouping, "LOCAL_DUMP_DIR", str(tmp_path))
    base_time = 1_800_000_000.0
    (tmp_path / "Flight_02_old").mkdir()
    write_file(tmp_path / "ISR_existing.reff", mtime=base_time - 7200)
    starting_number = grouping.get_next_flight_number()
    assert starting_number == 4

    write_file(tmp_path / "RACER_pair.reff", mtime=base_time)
    write_file(tmp_path / "ISR_pair.reff", mtime=base_time + 20)
    write_file(tmp_path / "RACER_video_pair.reff", mtime=base_time + 3600)
    write_file(tmp_path / "VIDEO_RACER_pair.mp4", mtime=base_time + 3620)
    reff_result = grouping.group_files_into_flights(starting_flight_number=starting_number)
    assert reff_result.next_flight_number == 5
    result = grouping.group_videos_into_flights(
        reff_result.flights, reff_result.standalone_reffs, reff_result.next_flight_number
    )
    assert [flight.number for flight in result.flights] == [2, 4, 5]
    assert all(
        Path(file.path).is_file()
        for flight in result.flights
        for file in [*flight.reff_files, *flight.videos]
    )
