from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

from racer_team_toolkit.adb.device_detection import DeviceType
from racer_team_toolkit.reff_extractor import grouping, transfer
from racer_team_toolkit.reff_extractor.grouping_dataclasses import (
    Flight,
)
from tests.integration.reff_extractor.config import (
    ISR_SERIAL,
    REAL_REMOTE_REFF_PATH,
    REAL_REMOTE_VIDEO_PATH,
    SOURCE_REFF_1,
    SOURCE_REFF_2,
    SOURCE_VIDEO,
    TABLET_SERIAL,
)
from tests.integration.reff_extractor.helpers import (
    build_test_device,
    ensure_real_remote_directories,
    push_file_direct,
    real_reff_path,
    real_video_path,
    recreate_case_directory,
    remove_remote_files,
    write_actual_tree,
    write_case_description,
    write_status,
    write_warnings,
)

pytestmark = [
    pytest.mark.reff_integration,
    pytest.mark.adb_integration,
]


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
    dump_dir: Path,
) -> None:
    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(dump_dir),
    )
    monkeypatch.setattr(
        transfer,
        "LOCAL_DUMP_DIR",
        str(dump_dir),
    )
    monkeypatch.setattr(
        transfer,
        "VIDEO_REMOTE_PATH",
        REAL_REMOTE_VIDEO_PATH,
    )


def process_role(
    monkeypatch: pytest.MonkeyPatch,
    *,
    serial: str,
    device_type: str,
    reff_files: list[str] | None = None,
    video_files: list[str] | None = None,
) -> None:
    """Run the real transfer code against exact files on the real Android path."""

    selected_reffs = list(reff_files or [])
    selected_videos = list(video_files or [])

    def selected_files(device, remote_path: str) -> list[str]:
        if remote_path == REAL_REMOTE_REFF_PATH:
            return selected_reffs

        if remote_path == REAL_REMOTE_VIDEO_PATH:
            return selected_videos

        return []

    monkeypatch.setattr(
        transfer,
        "get_remote_files_from_today",
        selected_files,
    )

    transfer.process_device(
        build_test_device(
            serial,
            device_type,
        ),
        include_videos=True,
    )


def run_grouping(
    *,
    starting_flight_number: int,
) -> tuple[list[Flight], list]:
    reff_result = grouping.group_files_into_flights(
        starting_flight_number=starting_flight_number,
    )

    video_result = grouping.group_videos_into_flights(
        flights=reff_result.flights,
        standalone_reffs=reff_result.standalone_reffs,
        starting_flight_number=reff_result.next_flight_number,
    )

    return video_result.flights, video_result.warnings


def push_reff(
    serial: str,
    filename: str,
    timestamp: float,
    *,
    source: Path = SOURCE_REFF_1,
) -> str:
    remote_path = real_reff_path(filename)

    return push_file_direct(
        serial,
        source,
        remote_path,
        timestamp,
    )


def push_video(
    serial: str,
    filename: str,
    timestamp: float,
) -> str:
    remote_path = real_video_path(filename)

    return push_file_direct(
        serial,
        SOURCE_VIDEO,
        remote_path,
        timestamp,
    )


@contextmanager
def visible_case(
    case_name: str,
    *,
    title: str,
    purpose: str,
    setup: str,
    expected: str,
):
    case_dir = recreate_case_directory(case_name)
    dump_dir = case_dir / "DUMP"
    dump_dir.mkdir()

    write_case_description(
        case_dir,
        title=title,
        purpose=purpose,
        setup=setup,
        expected=expected,
    )

    try:
        yield case_dir, dump_dir
    except Exception as error:
        write_actual_tree(
            case_dir,
            dump_dir,
        )
        write_status(
            case_dir,
            "FAIL",
            str(error),
        )
        raise
    else:
        write_actual_tree(
            case_dir,
            dump_dir,
        )
        write_status(
            case_dir,
            "PASS",
        )


def cleanup_remote(
    paths_by_serial: dict[str, list[str]],
) -> None:
    for serial, paths in paths_by_serial.items():
        remove_remote_files(
            serial,
            paths,
        )


def test_case_01_normal_multi_device_flight(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """ISR + logical RACER REFF/video creates one clean flight."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup: dict[str, list[str]] = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_01_Normal_Multi_Device",
        title="Normal multi-device flight",
        purpose=(
            "Verify a normal two-device flight. The ISR uses the physical ISR. "
            "The RACER logical stream uses the physical Tablet because no separate "
            "RACER serial is configured in this test environment."
        ),
        setup=("ISR REFF: 08:00:00\nRACER REFF: 08:00:10\nRACER video: 08:00:40"),
        expected=(
            "Exactly one Flight_01 folder.\n"
            "It contains ISR REFF + RACER REFF + RACER video.\n"
            "No warning."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(
            monkeypatch,
            dump_dir,
        )

        isr_reff = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C01_ISR.reff",
            ts(8, 0, 0),
        )
        racer_reff = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C01_RACER.reff",
            ts(8, 0, 10),
            source=SOURCE_REFF_2,
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C01_RACER.mp4",
            ts(8, 0, 40),
        )

        cleanup[ISR_SERIAL].append(isr_reff)
        cleanup[TABLET_SERIAL].extend(
            [
                racer_reff,
                racer_video,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_reff],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_reff],
                video_files=[racer_video],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1
            assert warnings == []
            assert len(flights[0].reff_files) == 2
            assert len(flights[0].videos) == 1
            assert {reff.device_type for reff in flights[0].reff_files} == {
                DeviceType.ISR,
                DeviceType.RACER,
            }
            assert flights[0].videos[0].device_type == DeviceType.RACER
        finally:
            cleanup_remote(cleanup)


def test_case_02_missing_device_reff_video_joins_existing_flight(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """RACER video joins ISR + TABLET flight and emits warning."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_02_Missing_Racer_REFF",
        title="Video from a device with a missing REFF",
        purpose=(
            "Verify cross-device fallback. ISR + TABLET REFFs create the flight, "
            "while a RACER video has no RACER REFF."
        ),
        setup=(
            "ISR REFF: 08:10:00\n"
            "TABLET REFF: 08:10:10\n"
            "RACER video: 08:10:30\n"
            "RACER REFF: intentionally missing"
        ),
        expected=(
            "Exactly one Flight_01 folder.\n"
            "It contains ISR REFF + TABLET REFF + RACER video.\n"
            "Exactly one warning: RACER video has no RACER REFF."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(
            monkeypatch,
            dump_dir,
        )

        isr_reff = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C02_ISR.reff",
            ts(8, 10, 0),
        )
        tablet_reff = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C02_TABLET.reff",
            ts(8, 10, 10),
            source=SOURCE_REFF_2,
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C02_RACER.mp4",
            ts(8, 10, 30),
        )

        cleanup[ISR_SERIAL].append(isr_reff)
        cleanup[TABLET_SERIAL].extend(
            [
                tablet_reff,
                racer_video,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_reff],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="TABLET",
                reff_files=[tablet_reff],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                video_files=[racer_video],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1
            assert len(flights[0].reff_files) == 2
            assert len(flights[0].videos) == 1
            assert flights[0].videos[0].device_type == DeviceType.RACER
            assert len(warnings) == 1
            assert warnings[0].device_type == DeviceType.RACER
            assert warnings[0].flight_name == flights[0].name
        finally:
            cleanup_remote(cleanup)


def test_case_03_cross_device_video_creates_flight_from_standalone_reff(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """One ISR REFF + RACER video creates a new flight with warning."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_03_Standalone_Cross_Device",
        title="Standalone REFF + cross-device video",
        purpose=(
            "Verify that one standalone ISR REFF can be promoted into a flight "
            "when a time-matching RACER video is found."
        ),
        setup=("ISR REFF: 08:20:00\nRACER video: 08:20:20\nRACER REFF: intentionally missing"),
        expected=(
            "Exactly one Flight_01 folder containing ISR REFF + RACER video.\n"
            "Exactly one warning for missing RACER REFF."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        isr_reff = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C03_ISR.reff",
            ts(8, 20, 0),
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C03_RACER.mp4",
            ts(8, 20, 20),
        )

        cleanup[ISR_SERIAL].append(isr_reff)
        cleanup[TABLET_SERIAL].append(racer_video)

        try:
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_reff],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                video_files=[racer_video],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1
            assert len(warnings) == 1
            assert len(flights[0].reff_files) == 1
            assert len(flights[0].videos) == 1
            assert flights[0].reff_files[0].device_type == DeviceType.ISR
            assert flights[0].videos[0].device_type == DeviceType.RACER
        finally:
            cleanup_remote(cleanup)


def test_case_04_same_device_standalone_reff_and_video(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """One RACER REFF + RACER video creates a new flight without warning."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_04_Same_Device_Standalone",
        title="Same-device standalone REFF + video",
        purpose=(
            "Verify that a standalone RACER REFF and same-device RACER video "
            "create a new flight with no warning."
        ),
        setup=("RACER REFF: 08:30:00\nRACER video: 08:30:20"),
        expected=("Exactly one Flight_01 folder containing RACER REFF + RACER video.\nNo warning."),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        racer_reff = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C04_RACER.reff",
            ts(8, 30, 0),
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C04_RACER.mp4",
            ts(8, 30, 20),
        )

        cleanup[TABLET_SERIAL].extend(
            [
                racer_reff,
                racer_video,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_reff],
                video_files=[racer_video],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1
            assert warnings == []
            assert len(flights[0].reff_files) == 1
            assert len(flights[0].videos) == 1
        finally:
            cleanup_remote(cleanup)


def test_case_05_same_device_priority_beats_cross_device_fallback(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """Same-device Priority 2 beats cross-device Priority 1."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_05_Same_Device_Beats_Fallback",
        title="Same-device match beats cross-device fallback",
        purpose=(
            "Validate the new priority rule: a valid same-device RACER match "
            "wins even when another flight has a closer cross-device fallback."
        ),
        setup=(
            "Flight A: ISR 09:00:00 + TABLET 09:00:10\n"
            "RACER video: 09:00:40\n"
            "Flight B: ISR 09:02:30 + RACER 09:02:40\n"
            "Flight A is cross-device Priority 1. Flight B is same-device Priority 2."
        ),
        expected=(
            "Two flight folders.\n"
            "RACER video must be inside Flight B, not Flight A.\n"
            "No missing-RACER warning for the matched flight."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        isr_a = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C05_ISR_A.reff",
            ts(9, 0, 0),
        )
        tablet_a = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C05_TABLET_A.reff",
            ts(9, 0, 10),
            source=SOURCE_REFF_2,
        )
        isr_b = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C05_ISR_B.reff",
            ts(9, 2, 30),
            source=SOURCE_REFF_2,
        )
        racer_b = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C05_RACER_B.reff",
            ts(9, 2, 40),
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C05_RACER.mp4",
            ts(9, 0, 40),
        )

        cleanup[ISR_SERIAL].extend([isr_a, isr_b])
        cleanup[TABLET_SERIAL].extend(
            [
                tablet_a,
                racer_b,
                racer_video,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_a, isr_b],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="TABLET",
                reff_files=[tablet_a],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_b],
                video_files=[racer_video],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 2

            racer_flights = [
                flight
                for flight in flights
                if any(reff.device_type == DeviceType.RACER for reff in flight.reff_files)
            ]

            assert len(racer_flights) == 1
            assert len(racer_flights[0].videos) == 1
            assert racer_flights[0].videos[0].device_type == DeviceType.RACER
            assert all(warning.device_type != DeviceType.RACER for warning in warnings)
        finally:
            cleanup_remote(cleanup)


def test_case_06_priority_one_beats_priority_two_within_same_device(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """Same-device Priority 1 beats same-device Priority 2."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_06_Priority_1_Beats_Priority_2",
        title="Priority 1 beats Priority 2",
        purpose=(
            "Verify ordering inside same-device matches: a RACER flight ending "
            "before the video within 60 seconds beats a RACER flight ending later "
            "within the 8-minute Priority 2 window."
        ),
        setup=(
            "Flight A RACER REFF: 09:10:00\nRACER video: 09:10:40\nFlight B RACER REFF: 09:12:40"
        ),
        expected=("RACER video is placed in Flight A.\nFlight B remains without the video."),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        isr_a = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C06_ISR_A.reff",
            ts(9, 10, 5),
        )
        racer_a = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C06_RACER_A.reff",
            ts(9, 10, 0),
        )
        isr_b = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C06_ISR_B.reff",
            ts(9, 12, 45),
            source=SOURCE_REFF_2,
        )
        racer_b = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C06_RACER_B.reff",
            ts(9, 12, 40),
            source=SOURCE_REFF_2,
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C06_RACER.mp4",
            ts(9, 10, 40),
        )

        cleanup[ISR_SERIAL].extend([isr_a, isr_b])
        cleanup[TABLET_SERIAL].extend(
            [
                racer_a,
                racer_b,
                racer_video,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_a, isr_b],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_a, racer_b],
                video_files=[racer_video],
            )

            flights, _ = run_grouping(
                starting_flight_number=1,
            )

            assert len(flights) == 2
            flights_with_video = [flight for flight in flights if flight.videos]
            assert len(flights_with_video) == 1

            selected_racer_time = max(
                reff.mtime
                for reff in flights_with_video[0].reff_files
                if reff.device_type == DeviceType.RACER
            )
            assert selected_racer_time == ts(9, 10, 0)
        finally:
            cleanup_remote(cleanup)


def test_case_07_priority_two_used_when_no_priority_one(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """A flight five minutes after the video is a valid Priority 2 match."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_07_Priority_2",
        title="Priority 2 match",
        purpose=(
            "Verify that when no valid Priority 1 flight exists, a same-device "
            "flight ending five minutes after the video is accepted."
        ),
        setup=("RACER video: 09:20:00\nFlight RACER REFF: 09:25:00\nFlight ISR REFF: 09:25:05"),
        expected=("Exactly one flight folder.\nThe RACER video is inside that flight."),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C07_RACER.mp4",
            ts(9, 20, 0),
        )
        racer_reff = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C07_RACER.reff",
            ts(9, 25, 0),
        )
        isr_reff = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C07_ISR.reff",
            ts(9, 25, 5),
        )

        cleanup[TABLET_SERIAL].extend(
            [
                racer_video,
                racer_reff,
            ]
        )
        cleanup[ISR_SERIAL].append(isr_reff)

        try:
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_reff],
                video_files=[racer_video],
            )
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_reff],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1
            assert warnings == []
            assert len(flights[0].videos) == 1
        finally:
            cleanup_remote(cleanup)


def test_case_08_outside_eight_minute_window_stays_standalone(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """Video ten minutes before the next flight remains standalone."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_08_Outside_8_Minutes",
        title="Outside the 8-minute matching window",
        purpose=(
            "Verify that a video is not forced into a flight when the next "
            "eligible flight ends ten minutes later."
        ),
        setup=("RACER video: 09:30:00\nISR REFF: 09:40:00\nTABLET REFF: 09:40:05"),
        expected=(
            "One normal flight folder containing ISR + TABLET REFFs.\n"
            "RACER video remains as a standalone file in DUMP/.\n"
            "One warning with no flight name."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C08_RACER.mp4",
            ts(9, 30, 0),
        )
        isr_reff = push_reff(
            ISR_SERIAL,
            "RTT_TEST_C08_ISR.reff",
            ts(9, 40, 0),
        )
        tablet_reff = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C08_TABLET.reff",
            ts(9, 40, 5),
            source=SOURCE_REFF_2,
        )

        cleanup[TABLET_SERIAL].extend(
            [
                racer_video,
                tablet_reff,
            ]
        )
        cleanup[ISR_SERIAL].append(isr_reff)

        try:
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                video_files=[racer_video],
            )
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_reff],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="TABLET",
                reff_files=[tablet_reff],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1
            assert flights[0].videos == []
            assert len(warnings) == 1
            assert warnings[0].flight_name is None

            standalone = list(dump_dir.glob("VIDEO_RACER_RTT_TEST_C08_RACER.mp4"))
            assert len(standalone) == 1
        finally:
            cleanup_remote(cleanup)


def test_case_09_repeated_extraction_numbering_continuity(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """Visible output must show Flight 1, Flight 2, items 3/4, then Flight 5."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_09_Numbering_Continuity",
        title="Repeated extraction / numbering continuity",
        purpose=(
            "Verify the exact repeated-extraction numbering rule. Two existing "
            "flight folders count as items 1 and 2. One standalone REFF and one "
            "standalone video count as items 3 and 4. The next newly-created "
            "flight must therefore be Flight_05."
        ),
        setup=(
            "Step 1 -> create Flight_01 from real Android files.\n"
            "Step 2 -> create Flight_02 from real Android files.\n"
            "Step 3 -> leave one standalone REFF and one standalone video.\n"
            "           These are numbering items 3 and 4.\n"
            "Step 4 -> extract a new matching REFF/video pair."
        ),
        expected=(
            "DUMP contains Flight_01 and Flight_02.\n"
            "DUMP contains one standalone REFF (item 3).\n"
            "DUMP contains one standalone video (item 4).\n"
            "The next created folder is Flight_05, not Flight_03 or Flight_07."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        try:
            # Step 1: Flight_01.
            isr_1 = push_reff(
                ISR_SERIAL,
                "RTT_TEST_C09_ISR_1.reff",
                ts(7, 0, 0),
            )
            racer_1 = push_reff(
                TABLET_SERIAL,
                "RTT_TEST_C09_RACER_1.reff",
                ts(7, 0, 10),
            )
            cleanup[ISR_SERIAL].append(isr_1)
            cleanup[TABLET_SERIAL].append(racer_1)

            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_1],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_1],
            )
            run_grouping(
                starting_flight_number=1,
            )

            # Step 2: Flight_02.
            next_number = grouping.get_next_flight_number()
            assert next_number == 2

            isr_2 = push_reff(
                ISR_SERIAL,
                "RTT_TEST_C09_ISR_2.reff",
                ts(8, 0, 0),
                source=SOURCE_REFF_2,
            )
            racer_2 = push_reff(
                TABLET_SERIAL,
                "RTT_TEST_C09_RACER_2.reff",
                ts(8, 0, 10),
                source=SOURCE_REFF_2,
            )
            cleanup[ISR_SERIAL].append(isr_2)
            cleanup[TABLET_SERIAL].append(racer_2)

            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_2],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_2],
            )
            run_grouping(
                starting_flight_number=next_number,
            )

            # Step 3: standalone REFF and standalone video -> items 3 and 4.
            standalone_reff = push_reff(
                ISR_SERIAL,
                "RTT_TEST_C09_STANDALONE.reff",
                ts(9, 0, 0),
            )
            standalone_video = push_video(
                TABLET_SERIAL,
                "RTT_TEST_C09_STANDALONE.mp4",
                ts(9, 20, 0),
            )
            cleanup[ISR_SERIAL].append(standalone_reff)
            cleanup[TABLET_SERIAL].append(standalone_video)

            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[standalone_reff],
            )
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                video_files=[standalone_video],
            )

            run_grouping(
                starting_flight_number=3,
            )

            assert grouping.get_next_flight_number() == 5

            (case_dir / "NUMBERING_MAP.txt").write_text(
                "1 = Flight_01\n"
                "2 = Flight_02\n"
                "3 = standalone REFF\n"
                "4 = standalone video\n"
                "5 = next created flight (must be Flight_05)\n",
                encoding="utf-8",
            )

            # Step 4: compute next number BEFORE pulling new files, just like run_extraction.
            next_number = grouping.get_next_flight_number()
            assert next_number == 5

            racer_5 = push_reff(
                TABLET_SERIAL,
                "RTT_TEST_C09_RACER_5.reff",
                ts(10, 0, 0),
            )
            video_5 = push_video(
                TABLET_SERIAL,
                "RTT_TEST_C09_RACER_5.mp4",
                ts(10, 0, 20),
            )
            cleanup[TABLET_SERIAL].extend(
                [
                    racer_5,
                    video_5,
                ]
            )

            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_5],
                video_files=[video_5],
            )

            run_grouping(
                starting_flight_number=next_number,
            )

            flight_names = {
                path.name
                for path in dump_dir.iterdir()
                if path.is_dir() and path.name.startswith("Flight_")
            }

            assert any(name.startswith("Flight_01_") for name in flight_names)
            assert any(name.startswith("Flight_02_") for name in flight_names)
            assert any(name.startswith("Flight_05_") for name in flight_names)
            assert not any(name.startswith("Flight_03_") for name in flight_names)
            assert not any(name.startswith("Flight_04_") for name in flight_names)

            assert (dump_dir / "ISR_RTT_TEST_C09_STANDALONE.reff").is_file()
            assert (dump_dir / "VIDEO_RACER_RTT_TEST_C09_STANDALONE.mp4").is_file()
        finally:
            cleanup_remote(cleanup)


def test_case_10_closest_match_wins_within_same_priority(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """Two existing Priority 1 flights: closest same-device end time wins."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        ISR_SERIAL: [],
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_10_Closest_Match",
        title="Multiple matches in the same priority",
        purpose=(
            "Create two real flight folders sequentially so they can be close in "
            "time, then verify a RACER video chooses the closest Priority 1 flight."
        ),
        setup=(
            "Flight 1 RACER REFF: 10:19:10\n"
            "Flight 2 RACER REFF: 10:19:40\n"
            "RACER video: 10:20:00\n"
            "Both are Priority 1; Flight 2 is closer."
        ),
        expected=("Two flight folders remain visible.\nThe RACER video is moved into Flight_02."),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        try:
            # Create Flight_01.
            racer_1 = push_reff(
                TABLET_SERIAL,
                "RTT_TEST_C10_RACER_1.reff",
                ts(10, 19, 10),
            )
            isr_1 = push_reff(
                ISR_SERIAL,
                "RTT_TEST_C10_ISR_1.reff",
                ts(10, 19, 15),
            )
            cleanup[TABLET_SERIAL].append(racer_1)
            cleanup[ISR_SERIAL].append(isr_1)

            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_1],
            )
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_1],
            )
            flights_1, _ = run_grouping(
                starting_flight_number=1,
            )
            assert len(flights_1) == 1

            # Create Flight_02 in a separate extraction so close times stay separate.
            racer_2 = push_reff(
                TABLET_SERIAL,
                "RTT_TEST_C10_RACER_2.reff",
                ts(10, 19, 40),
                source=SOURCE_REFF_2,
            )
            isr_2 = push_reff(
                ISR_SERIAL,
                "RTT_TEST_C10_ISR_2.reff",
                ts(10, 19, 45),
                source=SOURCE_REFF_2,
            )
            cleanup[TABLET_SERIAL].append(racer_2)
            cleanup[ISR_SERIAL].append(isr_2)

            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_2],
            )
            process_role(
                monkeypatch,
                serial=ISR_SERIAL,
                device_type="ISR",
                reff_files=[isr_2],
            )
            flights_2, _ = run_grouping(
                starting_flight_number=2,
            )
            assert len(flights_2) == 1

            all_flights = [
                flights_1[0],
                flights_2[0],
            ]

            racer_video = push_video(
                TABLET_SERIAL,
                "RTT_TEST_C10_RACER.mp4",
                ts(10, 20, 0),
            )
            cleanup[TABLET_SERIAL].append(racer_video)

            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                video_files=[racer_video],
            )

            videos = grouping.get_video_files()
            assert len(videos) == 1

            matched = grouping.find_best_existing_flight_for_video(
                videos[0],
                all_flights,
            )

            assert matched is not None
            assert matched.number == 2
            assert grouping.attach_video_to_flight(
                matched,
                videos[0],
            )
            assert len(all_flights[1].videos) == 1
            assert all_flights[0].videos == []
        finally:
            cleanup_remote(cleanup)


def test_case_11_paths_update_after_real_moves(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """FlightFile.path points at actual moved files after real-device transfer."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_11_Path_Update",
        title="FlightFile path update",
        purpose=(
            "Verify that after files are transferred from the real Tablet and "
            "moved into a flight folder, each FlightFile.path points to its new "
            "real Desktop location."
        ),
        setup=("RACER REFF: 10:30:00\nRACER video: 10:30:20"),
        expected=(
            "One Flight_01 folder.\n"
            "Both FlightFile.path values point inside that folder.\n"
            "Both target files physically exist."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(monkeypatch, dump_dir)

        racer_reff = push_reff(
            TABLET_SERIAL,
            "RTT_TEST_C11_RACER.reff",
            ts(10, 30, 0),
        )
        racer_video = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C11_RACER.mp4",
            ts(10, 30, 20),
        )

        cleanup[TABLET_SERIAL].extend(
            [
                racer_reff,
                racer_video,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                reff_files=[racer_reff],
                video_files=[racer_video],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )
            write_warnings(
                case_dir,
                warnings,
            )

            assert warnings == []
            assert len(flights) == 1

            flight = flights[0]

            for file_info in flight.reff_files + flight.videos:
                assert Path(file_info.path).parent == Path(flight.path)
                assert Path(file_info.path).is_file()
        finally:
            cleanup_remote(cleanup)


def test_case_12_multiple_related_videos_without_reff_create_flight(
    monkeypatch: pytest.MonkeyPatch,
    connected_test_devices: set[str],
) -> None:
    """Three related videos with no REFF create one video-only flight."""

    del connected_test_devices
    ensure_real_remote_directories()

    cleanup = {
        TABLET_SERIAL: [],
    }

    with visible_case(
        "Case_12_Video_Only_Flight",
        title="Multiple related videos without REFF",
        purpose=(
            "Verify that related videos can create a flight even when no REFF "
            "exists, and that a later related video joins the existing video-only "
            "flight before standalone matching is considered."
        ),
        setup=(
            "RACER video 1: 11:00:00\n"
            "RACER video 2: 11:01:00\n"
            "RACER video 3: 11:02:00\n"
            "No REFF files."
        ),
        expected=(
            "Exactly one Flight_01 folder.\n"
            "The folder contains all three videos.\n"
            "The folder contains zero REFF files.\n"
            "Three missing-REFF warnings are created."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(
            monkeypatch,
            dump_dir,
        )

        video_1 = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C12_1.mp4",
            ts(11, 0, 0),
        )
        video_2 = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C12_2.mp4",
            ts(11, 1, 0),
        )
        video_3 = push_video(
            TABLET_SERIAL,
            "RTT_TEST_C12_3.mp4",
            ts(11, 2, 0),
        )

        cleanup[TABLET_SERIAL].extend(
            [
                video_1,
                video_2,
                video_3,
            ]
        )

        try:
            process_role(
                monkeypatch,
                serial=TABLET_SERIAL,
                device_type="RACER",
                video_files=[
                    video_1,
                    video_2,
                    video_3,
                ],
            )

            flights, warnings = run_grouping(
                starting_flight_number=1,
            )

            write_warnings(
                case_dir,
                warnings,
            )

            assert len(flights) == 1

            flight = flights[0]

            assert flight.reff_files == []
            assert len(flight.videos) == 3
            assert len(warnings) == 3
            assert all(warning.flight_name == flight.name for warning in warnings)

            flight_dir = Path(
                flight.path,
            )

            assert (flight_dir / "VIDEO_RACER_RTT_TEST_C12_1.mp4").is_file()
            assert (flight_dir / "VIDEO_RACER_RTT_TEST_C12_2.mp4").is_file()
            assert (flight_dir / "VIDEO_RACER_RTT_TEST_C12_3.mp4").is_file()
        finally:
            cleanup_remote(
                cleanup,
            )
