from datetime import datetime
from pathlib import Path

import pytest

from racer_team_toolkit.adb.device_detection import DeviceType
from racer_team_toolkit.reff_extractor import grouping
from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
    FlightFile,
    FlightFileType,
)

from tests.integration.reff_extractor.config import (
    SOURCE_REFF_1,
    SOURCE_REFF_2,
    SOURCE_VIDEO,
)
from tests.integration.reff_extractor.helpers import create_local_test_file

pytestmark = pytest.mark.reff_integration


def ts(hour: int, minute: int, second: int = 0) -> float:
    return datetime(
        2026,
        9,
        19,
        hour,
        minute,
        second,
    ).timestamp()


def patch_dump(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> None:
    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(root),
    )


def create_reff(
    root: Path,
    device_type: DeviceType,
    timestamp: float,
    *,
    source: Path = SOURCE_REFF_1,
    suffix: str = "",
) -> Path:
    dt = datetime.fromtimestamp(timestamp)
    filename = (
        f"{device_type.value}_"
        f"{dt.strftime('%d_%m_%Y_%H_%M_%S')}"
        f"{suffix}.reff"
    )

    return create_local_test_file(
        root,
        source,
        filename,
        timestamp,
    )


def create_video(
    root: Path,
    device_type: DeviceType,
    timestamp: float,
    *,
    suffix: str = "",
) -> Path:
    dt = datetime.fromtimestamp(timestamp)
    filename = (
        f"VIDEO_{device_type.value}_ScreenRec_"
        f"{dt.strftime('%Y-%m-%d_%H-%M-%S')}"
        f"{suffix}.mp4"
    )

    return create_local_test_file(
        root,
        SOURCE_VIDEO,
        filename,
        timestamp,
    )


def run_grouping() -> tuple[
    list[Flight],
    list,
    list[FlightFile],
]:
    reff_result = grouping.group_files_into_flights(
        starting_flight_number=1,
    )

    video_result = grouping.group_videos_into_flights(
        flights=reff_result.flights,
        standalone_reffs=reff_result.standalone_reffs,
        starting_flight_number=reff_result.next_flight_number,
    )

    return (
        video_result.flights,
        video_result.warnings,
        reff_result.standalone_reffs,
    )


def make_flight_file(
    device_type: DeviceType,
    file_type: FlightFileType,
    timestamp: float,
    name: str,
) -> FlightFile:
    return FlightFile(
        filename=name,
        path=f"/tmp/{name}",
        device_type=device_type,
        file_type=file_type,
        mtime=timestamp,
        size=1_000_000,
    )


def make_flight(
    number: int,
    *reffs: FlightFile,
) -> Flight:
    return Flight(
        number=number,
        name=f"Flight_{number:02d}",
        path=f"/tmp/Flight_{number:02d}",
        reff_files=list(reffs),
    )


def test_case_01_normal_multi_device_flight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ISR + RACER REFF with a RACER video creates one clean flight."""

    patch_dump(monkeypatch, tmp_path)

    create_reff(tmp_path, DeviceType.ISR, ts(8, 0, 0))
    create_reff(
        tmp_path,
        DeviceType.RACER,
        ts(8, 0, 10),
        source=SOURCE_REFF_2,
    )
    create_video(tmp_path, DeviceType.RACER, ts(8, 0, 40))

    flights, warnings, _ = run_grouping()

    assert len(flights) == 1
    assert warnings == []
    assert {reff.device_type for reff in flights[0].reff_files} == {
        DeviceType.ISR,
        DeviceType.RACER,
    }
    assert [video.device_type for video in flights[0].videos] == [
        DeviceType.RACER,
    ]


def test_case_02_missing_device_reff_video_joins_existing_flight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RACER video can join ISR + TABLET flight and emits one warning."""

    patch_dump(monkeypatch, tmp_path)

    create_reff(tmp_path, DeviceType.ISR, ts(8, 10, 0))
    create_reff(
        tmp_path,
        DeviceType.TABLET,
        ts(8, 10, 10),
        source=SOURCE_REFF_2,
    )
    create_video(tmp_path, DeviceType.RACER, ts(8, 10, 30))

    flights, warnings, _ = run_grouping()

    assert len(flights) == 1
    assert len(flights[0].videos) == 1
    assert flights[0].videos[0].device_type == DeviceType.RACER
    assert len(warnings) == 1
    assert warnings[0].device_type == DeviceType.RACER
    assert warnings[0].flight_name == flights[0].name


def test_case_03_cross_device_video_creates_flight_from_standalone_reff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ISR standalone REFF + RACER video creates a flight with warning."""

    patch_dump(monkeypatch, tmp_path)

    create_reff(tmp_path, DeviceType.ISR, ts(8, 20, 0))
    create_video(tmp_path, DeviceType.RACER, ts(8, 20, 20))

    flights, warnings, standalone_reffs = run_grouping()

    assert len(flights) == 1
    assert standalone_reffs == []
    assert len(warnings) == 1
    assert warnings[0].device_type == DeviceType.RACER
    assert {reff.device_type for reff in flights[0].reff_files} == {
        DeviceType.ISR,
    }


def test_case_04_same_device_standalone_reff_and_video(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RACER standalone REFF + RACER video creates a flight without warning."""

    patch_dump(monkeypatch, tmp_path)

    create_reff(tmp_path, DeviceType.RACER, ts(8, 30, 0))
    create_video(tmp_path, DeviceType.RACER, ts(8, 30, 20))

    flights, warnings, standalone_reffs = run_grouping()

    assert len(flights) == 1
    assert standalone_reffs == []
    assert warnings == []
    assert flights[0].reff_files[0].device_type == DeviceType.RACER
    assert flights[0].videos[0].device_type == DeviceType.RACER


def test_case_05_same_device_priority_beats_cross_device_fallback() -> None:
    """Same-device Priority 2 beats a cross-device Priority 1 fallback."""

    video = make_flight_file(
        DeviceType.RACER,
        FlightFileType.VIDEO,
        ts(9, 0, 40),
        "VIDEO_RACER_test.mp4",
    )

    fallback_flight = make_flight(
        1,
        make_flight_file(
            DeviceType.ISR,
            FlightFileType.REFF,
            ts(9, 0, 0),
            "ISR_fallback.reff",
        ),
    )

    same_device_flight = make_flight(
        2,
        make_flight_file(
            DeviceType.RACER,
            FlightFileType.REFF,
            ts(9, 2, 40),
            "RACER_same_device.reff",
        ),
    )

    matched = grouping.find_best_existing_flight_for_video(
        video,
        [
            fallback_flight,
            same_device_flight,
        ],
    )

    assert matched is same_device_flight


def test_case_06_priority_one_beats_priority_two_within_same_device() -> None:
    """A valid video-after-REFF match beats a later REFF match."""

    video = make_flight_file(
        DeviceType.RACER,
        FlightFileType.VIDEO,
        ts(9, 10, 40),
        "VIDEO_RACER_test.mp4",
    )

    priority_one = make_flight(
        1,
        make_flight_file(
            DeviceType.RACER,
            FlightFileType.REFF,
            ts(9, 10, 0),
            "RACER_before.reff",
        ),
    )

    priority_two = make_flight(
        2,
        make_flight_file(
            DeviceType.RACER,
            FlightFileType.REFF,
            ts(9, 12, 40),
            "RACER_after.reff",
        ),
    )

    matched = grouping.find_best_existing_flight_for_video(
        video,
        [
            priority_one,
            priority_two,
        ],
    )

    assert matched is priority_one


def test_case_07_priority_two_used_when_no_priority_one() -> None:
    """A flight ending five minutes after the video is a valid Priority 2 match."""

    video = make_flight_file(
        DeviceType.RACER,
        FlightFileType.VIDEO,
        ts(9, 20, 0),
        "VIDEO_RACER_test.mp4",
    )

    later_flight = make_flight(
        1,
        make_flight_file(
            DeviceType.RACER,
            FlightFileType.REFF,
            ts(9, 25, 0),
            "RACER_later.reff",
        ),
    )

    matched = grouping.find_best_existing_flight_for_video(
        video,
        [later_flight],
    )

    assert matched is later_flight


def test_case_08_outside_eight_minute_window_stays_standalone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Video ten minutes before the next flight stays standalone with warning."""

    patch_dump(monkeypatch, tmp_path)

    create_video(tmp_path, DeviceType.RACER, ts(9, 30, 0))
    create_reff(tmp_path, DeviceType.ISR, ts(9, 40, 0))
    create_reff(
        tmp_path,
        DeviceType.TABLET,
        ts(9, 40, 5),
        source=SOURCE_REFF_2,
    )

    flights, warnings, _ = run_grouping()

    assert len(flights) == 1
    assert flights[0].videos == []
    assert len(warnings) == 1
    assert warnings[0].flight_name is None

    standalone_videos = [
        path
        for path in tmp_path.iterdir()
        if path.is_file() and path.name.startswith("VIDEO_RACER_")
    ]

    assert len(standalone_videos) == 1


def test_case_09_repeated_extraction_numbering_continuity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two flight folders + standalone REFF + video makes the next number 5."""

    patch_dump(monkeypatch, tmp_path)

    (tmp_path / "Flight_01_19-09-2026_08-00-00").mkdir()
    (tmp_path / "Flight_02_19-09-2026_08-10-00").mkdir()

    create_reff(tmp_path, DeviceType.ISR, ts(10, 0, 0))
    create_video(tmp_path, DeviceType.TABLET, ts(10, 5, 0))

    assert grouping.get_next_flight_number() == 5


def test_case_10_closest_match_wins_within_same_priority() -> None:
    """When two same-device Priority 1 matches exist, closest time wins."""

    video = make_flight_file(
        DeviceType.RACER,
        FlightFileType.VIDEO,
        ts(10, 20, 0),
        "VIDEO_RACER_test.mp4",
    )

    farther = make_flight(
        1,
        make_flight_file(
            DeviceType.RACER,
            FlightFileType.REFF,
            ts(10, 19, 10),
            "RACER_farther.reff",
        ),
    )

    closer = make_flight(
        2,
        make_flight_file(
            DeviceType.RACER,
            FlightFileType.REFF,
            ts(10, 19, 40),
            "RACER_closer.reff",
        ),
    )

    matched = grouping.find_best_existing_flight_for_video(
        video,
        [
            farther,
            closer,
        ],
    )

    assert matched is closer


def test_case_11_paths_update_after_reff_and_video_move(
    tmp_path: Path,
) -> None:
    """FlightFile.path follows both REFF and video moves."""

    reff_path = create_reff(
        tmp_path,
        DeviceType.ISR,
        ts(10, 30, 0),
    )
    video_path = create_video(
        tmp_path,
        DeviceType.ISR,
        ts(10, 30, 20),
    )

    reff = FlightFile(
        filename=reff_path.name,
        path=str(reff_path),
        device_type=DeviceType.ISR,
        file_type=FlightFileType.REFF,
        mtime=ts(10, 30, 0),
        size=reff_path.stat().st_size,
    )

    video = FlightFile(
        filename=video_path.name,
        path=str(video_path),
        device_type=DeviceType.ISR,
        file_type=FlightFileType.VIDEO,
        mtime=ts(10, 30, 20),
        size=video_path.stat().st_size,
    )

    flight_dir = tmp_path / "Flight_01"
    flight_dir.mkdir()

    grouping.move_flight_files(
        str(flight_dir),
        [reff],
    )

    flight = Flight(
        number=1,
        name="Flight_01",
        path=str(flight_dir),
        reff_files=[reff],
    )

    assert grouping.attach_video_to_flight(
        flight,
        video,
    )

    assert Path(reff.path).parent == flight_dir
    assert Path(video.path).parent == flight_dir
    assert Path(reff.path).is_file()
    assert Path(video.path).is_file()
