import os
from datetime import datetime
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
    get_device_datetime,
)

from tests.integration.reff_extractor.config import (
    SOURCE_REFF_1,
    SOURCE_REFF_2,
    SOURCE_VIDEO,
    TABLET_SERIAL,
    TEST_REMOTE_REFF_PATH,
    TEST_REMOTE_VIDEO_PATH,
    TIME_ADJUSTMENT_RUN_ENV_VAR,
    TIME_ADJUSTMENT_WRONG_DATE,
)
from tests.integration.reff_extractor.helpers import (
    build_test_device,
    clear_remote_test_area,
    connected_serials,
    push_named_file,
    run_adb,
)

pytestmark = [
    pytest.mark.reff_integration,
    pytest.mark.adb_integration,
]


@pytest.fixture(scope="module", autouse=True)
def require_time_adjustment_opt_in() -> None:
    """Require explicit opt-in and the fixed wrong date on the Tablet."""

    if os.getenv(TIME_ADJUSTMENT_RUN_ENV_VAR) != "1":
        pytest.skip(
            f"Set {TIME_ADJUSTMENT_RUN_ENV_VAR}=1 to run Tablet time-adjustment tests."
        )

    if TABLET_SERIAL not in connected_serials():
        pytest.fail(f"Tablet {TABLET_SERIAL} is not connected.")

    tablet = build_test_device(
        TABLET_SERIAL,
        "TABLET",
    )

    device_datetime = get_device_datetime(tablet)

    if device_datetime is None:
        pytest.fail("Could not read Tablet date/time.")

    expected_date = datetime.strptime(
        TIME_ADJUSTMENT_WRONG_DATE,
        "%Y-%m-%d",
    ).date()

    if device_datetime.date() != expected_date:
        pytest.fail(
            "Tablet must be manually set to the fixed wrong date before this suite. "
            f"Expected {expected_date}, got {device_datetime.date()}."
        )


@pytest.fixture
def clean_tablet_test_area():
    """Clean only the isolated Tablet integration-test directory."""

    clear_remote_test_area(TABLET_SERIAL)
    yield
    clear_remote_test_area(TABLET_SERIAL)


def patch_test_paths(
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


def run_full_grouping() -> tuple[list[Flight], list]:
    reff_result = grouping.group_files_into_flights(
        starting_flight_number=1,
    )

    video_result = grouping.group_videos_into_flights(
        flights=reff_result.flights,
        standalone_reffs=reff_result.standalone_reffs,
        starting_flight_number=reff_result.next_flight_number,
    )

    return video_result.flights, video_result.warnings


def test_time_adjustment_renaming_creates_correct_flight_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_tablet_test_area,
) -> None:
    """Corrected timestamp/name must drive the later flight-folder timestamp."""

    local_dump = tmp_path / "dump"
    local_dump.mkdir()
    staging = tmp_path / "staging"

    patch_test_paths(
        monkeypatch,
        local_dump,
    )

    tablet = build_test_device(
        TABLET_SERIAL,
        "TABLET",
    )

    corrected_datetime = datetime.now().replace(
        second=0,
        microsecond=0,
    )
    corrected_timestamp = int(
        corrected_datetime.timestamp(),
    )

    wrong_device_datetime = get_device_datetime(tablet)
    assert wrong_device_datetime is not None

    wrong_reff_timestamp = wrong_device_datetime.replace(
        hour=8,
        minute=27,
        second=0,
        microsecond=0,
    ).timestamp()

    wrong_video_timestamp = wrong_device_datetime.replace(
        hour=8,
        minute=27,
        second=20,
        microsecond=0,
    ).timestamp()

    old_reff_path = push_named_file(
        TABLET_SERIAL,
        SOURCE_REFF_1,
        TEST_REMOTE_REFF_PATH,
        "01_08_2024_08_27.reff",
        wrong_reff_timestamp,
        staging,
    )

    old_video_path = push_named_file(
        TABLET_SERIAL,
        SOURCE_VIDEO,
        TEST_REMOTE_VIDEO_PATH,
        "ScreenRec_2024-08-01_08-27.mp4",
        wrong_video_timestamp,
        staging,
    )

    reff_corrected_timestamp = corrected_timestamp
    video_corrected_timestamp = corrected_timestamp + 20

    corrected_count = apply_file_time_corrections(
        tablet,
        [
            FileTimeCorrection(
                file_path=old_reff_path,
                current_timestamp=int(wrong_reff_timestamp),
                corrected_timestamp=reff_corrected_timestamp,
            ),
            FileTimeCorrection(
                file_path=old_video_path,
                current_timestamp=int(wrong_video_timestamp),
                corrected_timestamp=video_corrected_timestamp,
            ),
        ],
    )

    assert corrected_count == 2

    corrected_reff_name = build_corrected_reff_filename(
        reff_corrected_timestamp,
    )
    corrected_video_name = build_corrected_video_filename(
        "ScreenRec_2024-08-01_08-27.mp4",
        video_corrected_timestamp,
    )

    assert corrected_video_name is not None

    corrected_reff_path = (
        f"{TEST_REMOTE_REFF_PATH}/{corrected_reff_name}"
    )
    corrected_video_path = (
        f"{TEST_REMOTE_VIDEO_PATH}/{corrected_video_name}"
    )

    assert run_adb(
        TABLET_SERIAL,
        "shell",
        "test",
        "-f",
        corrected_reff_path,
        check=False,
    ).returncode == 0

    assert run_adb(
        TABLET_SERIAL,
        "shell",
        "test",
        "-f",
        corrected_video_path,
        check=False,
    ).returncode == 0

    extraction_result = transfer.process_device(
        tablet,
        include_videos=True,
    )

    assert extraction_result.reff_files == 1
    assert extraction_result.videos == 1

    flights, warnings = run_full_grouping()

    expected_flight_name = (
        "Flight_01_"
        + corrected_datetime.strftime("%d-%m-%Y_%H-%M-%S")
    )

    assert len(flights) == 1
    assert warnings == []
    assert flights[0].name == expected_flight_name

    assert (
        local_dump
        / expected_flight_name
        / f"TABLET_{corrected_reff_name}"
    ).is_file()

    assert (
        local_dump
        / expected_flight_name
        / f"VIDEO_TABLET_{corrected_video_name}"
    ).is_file()


def test_time_adjustment_collision_uses_number_suffix(
    tmp_path: Path,
    clean_tablet_test_area,
) -> None:
    """Renaming must not overwrite an existing corrected REFF filename."""

    staging = tmp_path / "staging"

    tablet = build_test_device(
        TABLET_SERIAL,
        "TABLET",
    )

    corrected_datetime = datetime.now().replace(
        second=0,
        microsecond=0,
    )
    corrected_timestamp = int(
        corrected_datetime.timestamp(),
    )

    wrong_device_datetime = get_device_datetime(tablet)
    assert wrong_device_datetime is not None

    wrong_timestamp = wrong_device_datetime.replace(
        hour=8,
        minute=27,
        second=0,
        microsecond=0,
    ).timestamp()

    corrected_name = build_corrected_reff_filename(
        corrected_timestamp,
    )

    old_path = push_named_file(
        TABLET_SERIAL,
        SOURCE_REFF_1,
        TEST_REMOTE_REFF_PATH,
        "01_08_2024_08_27.reff",
        wrong_timestamp,
        staging,
    )

    push_named_file(
        TABLET_SERIAL,
        SOURCE_REFF_2,
        TEST_REMOTE_REFF_PATH,
        corrected_name,
        corrected_timestamp,
        staging,
    )

    corrected_count = apply_file_time_corrections(
        tablet,
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

    assert run_adb(
        TABLET_SERIAL,
        "shell",
        "test",
        "-f",
        f"{TEST_REMOTE_REFF_PATH}/{numbered_name}",
        check=False,
    ).returncode == 0
