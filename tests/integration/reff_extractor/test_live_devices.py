from datetime import datetime, timedelta
from pathlib import Path

import pytest

from racer_team_toolkit.reff_extractor import grouping, transfer
from racer_team_toolkit.reff_extractor.grouping_dataclasses import Flight
from racer_team_toolkit.reff_extractor.time_adjustment_dataclasses import (
    FileTimeCorrection,
)
from racer_team_toolkit.reff_extractor.time_adjustment_functions import (
    apply_file_time_corrections,
    build_corrected_reff_filename,
    build_corrected_video_filename,
)

from tests.integration.reff_extractor.config import (
    ISR_SERIAL,
    SOURCE_REFF_1,
    SOURCE_REFF_2,
    SOURCE_VIDEO,
    TABLET_SERIAL,
    TEST_REMOTE_REFF_PATH,
    TEST_REMOTE_VIDEO_PATH,
)
from tests.integration.reff_extractor.helpers import (
    build_test_device,
    push_named_file,
    run_adb,
    timestamp_today,
)

pytestmark = [
    pytest.mark.reff_integration,
    pytest.mark.adb_integration,
]


def run_full_grouping(
    starting_flight_number: int = 1,
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


def patch_live_test_paths(
    monkeypatch: pytest.MonkeyPatch,
    local_dump: Path,
) -> None:
    monkeypatch.setattr(
        transfer,
        "LOCAL_DUMP_DIR",
        str(local_dump),
    )
    monkeypatch.setattr(
        transfer,
        "VIDEO_REMOTE_PATH",
        TEST_REMOTE_VIDEO_PATH,
    )
    monkeypatch.setattr(
        grouping,
        "LOCAL_DUMP_DIR",
        str(local_dump),
    )


def test_environment_has_fixed_devices_and_source_files(
    connected_test_devices: set[str],
) -> None:
    """Validate the fixed physical-device and master-file test environment."""

    assert ISR_SERIAL in connected_test_devices
    assert TABLET_SERIAL in connected_test_devices
    assert SOURCE_REFF_1.is_file()
    assert SOURCE_REFF_2.is_file()
    assert SOURCE_VIDEO.is_file()
    assert SOURCE_REFF_1.stat().st_size >= transfer.MIN_REFF_FILE_SIZE_BYTES
    assert SOURCE_REFF_2.stat().st_size >= transfer.MIN_REFF_FILE_SIZE_BYTES
    assert SOURCE_VIDEO.stat().st_size >= transfer.MIN_VIDEO_FILE_SIZE_BYTES


def test_live_two_device_transfer_and_grouping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_remote_test_devices,
) -> None:
    """Exercise ADB pull, prefixing, grouping, and video attachment end to end."""

    local_dump = tmp_path / "dump"
    local_dump.mkdir()

    staging = tmp_path / "staging"

    patch_live_test_paths(
        monkeypatch,
        local_dump,
    )

    isr = build_test_device(
        ISR_SERIAL,
        "ISR",
    )
    tablet = build_test_device(
        TABLET_SERIAL,
        "TABLET",
    )

    base_time = timestamp_today(
        8,
        0,
        0,
    )

    push_named_file(
        ISR_SERIAL,
        SOURCE_REFF_1,
        TEST_REMOTE_REFF_PATH,
        "test_isr.reff",
        base_time,
        staging,
    )

    push_named_file(
        TABLET_SERIAL,
        SOURCE_REFF_2,
        TEST_REMOTE_REFF_PATH,
        "test_tablet.reff",
        base_time + 10,
        staging,
    )

    push_named_file(
        TABLET_SERIAL,
        SOURCE_VIDEO,
        TEST_REMOTE_VIDEO_PATH,
        "ScreenRec_test.mp4",
        base_time + 40,
        staging,
    )

    isr_result = transfer.process_device(
        isr,
        include_videos=True,
    )
    tablet_result = transfer.process_device(
        tablet,
        include_videos=True,
    )

    assert isr_result.reff_files == 1
    assert isr_result.videos == 0
    assert tablet_result.reff_files == 1
    assert tablet_result.videos == 1

    flights, warnings = run_full_grouping()

    assert len(flights) == 1
    assert warnings == []
    assert len(flights[0].reff_files) == 2
    assert len(flights[0].videos) == 1


def test_time_adjustment_renaming_creates_correct_flight_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_remote_test_devices,
) -> None:
    """Corrected timestamp/name must drive the later flight-folder timestamp."""

    local_dump = tmp_path / "dump"
    local_dump.mkdir()

    staging = tmp_path / "staging"

    patch_live_test_paths(
        monkeypatch,
        local_dump,
    )

    isr = build_test_device(
        ISR_SERIAL,
        "ISR",
    )

    corrected_datetime = datetime.now().replace(
        hour=14,
        minute=22,
        second=33,
        microsecond=0,
    )

    corrected_timestamp = int(
        corrected_datetime.timestamp(),
    )

    wrong_datetime = corrected_datetime - timedelta(days=7)
    wrong_timestamp = wrong_datetime.timestamp()

    old_reff_path = push_named_file(
        ISR_SERIAL,
        SOURCE_REFF_1,
        TEST_REMOTE_REFF_PATH,
        "01_08_2024_08_27.reff",
        wrong_timestamp,
        staging,
    )

    old_video_path = push_named_file(
        ISR_SERIAL,
        SOURCE_VIDEO,
        TEST_REMOTE_VIDEO_PATH,
        "ScreenRec_2024-08-01_08-27.mp4",
        wrong_timestamp,
        staging,
    )

    corrected_count = apply_file_time_corrections(
        isr,
        [
            FileTimeCorrection(
                file_path=old_reff_path,
                current_timestamp=int(wrong_timestamp),
                corrected_timestamp=corrected_timestamp,
            ),
            FileTimeCorrection(
                file_path=old_video_path,
                current_timestamp=int(wrong_timestamp),
                corrected_timestamp=corrected_timestamp,
            ),
        ],
    )

    assert corrected_count == 2

    corrected_reff_name = build_corrected_reff_filename(
        corrected_timestamp,
    )
    corrected_video_name = build_corrected_video_filename(
        "ScreenRec_2024-08-01_08-27.mp4",
        corrected_timestamp,
    )

    assert corrected_video_name is not None

    corrected_reff_path = (
        f"{TEST_REMOTE_REFF_PATH}/{corrected_reff_name}"
    )
    corrected_video_path = (
        f"{TEST_REMOTE_VIDEO_PATH}/{corrected_video_name}"
    )

    assert (
        run_adb(
            ISR_SERIAL,
            "shell",
            "test",
            "-f",
            corrected_reff_path,
            check=False,
        ).returncode
        == 0
    )
    assert (
        run_adb(
            ISR_SERIAL,
            "shell",
            "test",
            "-f",
            corrected_video_path,
            check=False,
        ).returncode
        == 0
    )

    extraction_result = transfer.process_device(
        isr,
        include_videos=True,
    )

    assert extraction_result.reff_files == 1
    assert extraction_result.videos == 1

    flights, warnings = run_full_grouping()

    expected_flight_name = (
        "Flight_01_"
        + corrected_datetime.strftime(
            "%d-%m-%Y_%H-%M-%S"
        )
    )

    assert len(flights) == 1
    assert warnings == []
    assert flights[0].name == expected_flight_name

    expected_reff_filename = (
        f"ISR_{corrected_reff_name}"
    )
    expected_video_filename = (
        f"VIDEO_ISR_{corrected_video_name}"
    )

    assert (
        local_dump
        / expected_flight_name
        / expected_reff_filename
    ).is_file()
    assert (
        local_dump
        / expected_flight_name
        / expected_video_filename
    ).is_file()


def test_time_adjustment_collision_uses_number_suffix(
    tmp_path: Path,
    clean_remote_test_devices,
) -> None:
    """Renaming must not overwrite an existing corrected REFF filename."""

    staging = tmp_path / "staging"

    isr = build_test_device(
        ISR_SERIAL,
        "ISR",
    )

    corrected_datetime = datetime.now().replace(
        hour=15,
        minute=5,
        second=0,
        microsecond=0,
    )
    corrected_timestamp = int(
        corrected_datetime.timestamp(),
    )
    wrong_timestamp = (
        corrected_datetime - timedelta(days=7)
    ).timestamp()

    corrected_name = build_corrected_reff_filename(
        corrected_timestamp,
    )

    old_path = push_named_file(
        ISR_SERIAL,
        SOURCE_REFF_1,
        TEST_REMOTE_REFF_PATH,
        "01_08_2024_08_27.reff",
        wrong_timestamp,
        staging,
    )

    push_named_file(
        ISR_SERIAL,
        SOURCE_REFF_2,
        TEST_REMOTE_REFF_PATH,
        corrected_name,
        corrected_timestamp,
        staging,
    )

    corrected_count = apply_file_time_corrections(
        isr,
        [
            FileTimeCorrection(
                file_path=old_path,
                current_timestamp=int(wrong_timestamp),
                corrected_timestamp=corrected_timestamp,
            ),
        ],
    )

    assert corrected_count == 1

    numbered_name = (
        f"{Path(corrected_name).stem}"
        "_Number_1"
        f"{Path(corrected_name).suffix}"
    )

    numbered_path = (
        f"{TEST_REMOTE_REFF_PATH}/{numbered_name}"
    )

    assert (
        run_adb(
            ISR_SERIAL,
            "shell",
            "test",
            "-f",
            numbered_path,
            check=False,
        ).returncode
        == 0
    )
