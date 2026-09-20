import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

from racer_team_toolkit.reff_extractor import grouping, transfer
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
    REAL_REMOTE_REFF_PATH,
    REAL_REMOTE_VIDEO_PATH,
    SOURCE_REFF_1,
    SOURCE_VIDEO,
    TABLET_SERIAL,
    TIME_ADJUSTMENT_RUN_ENV_VAR,
    TIME_ADJUSTMENT_WRONG_DATE,
)
from tests.integration.reff_extractor.helpers import (
    build_test_device,
    connected_serials,
    ensure_real_remote_directories,
    push_file_direct,
    real_reff_path,
    real_video_path,
    recreate_case_directory,
    remote_file_exists,
    remove_remote_files,
    run_adb,
    write_actual_tree,
    write_case_description,
    write_status,
    write_warnings,
)

pytestmark = [
    pytest.mark.reff_integration,
    pytest.mark.adb_integration,
]


@pytest.fixture(scope="module", autouse=True)
def require_time_adjustment_opt_in() -> None:
    """Require explicit opt-in and the fixed wrong date on the Tablet."""

    if os.getenv(TIME_ADJUSTMENT_RUN_ENV_VAR) != "1":
        pytest.skip(f"Set {TIME_ADJUSTMENT_RUN_ENV_VAR}=1 to run Tablet time-adjustment tests.")

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


def process_selected_tablet_files(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reff_files: list[str] | None = None,
    video_files: list[str] | None = None,
) -> None:
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
            TABLET_SERIAL,
            "TABLET",
        ),
        include_videos=True,
    )


@contextmanager
def visible_time_case(
    case_name: str,
    *,
    title: str,
    purpose: str,
    setup: str,
    expected: str,
):
    case_dir = recreate_case_directory(f"Time Adjustment/{case_name}")
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


def test_time_adjustment_renaming_creates_correct_flight_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrected names and mtimes must drive the visible flight-folder name."""

    ensure_real_remote_directories((TABLET_SERIAL,))

    tablet = build_test_device(
        TABLET_SERIAL,
        "TABLET",
    )

    corrected_datetime = datetime.now().replace(
        second=0,
        microsecond=0,
    )
    corrected_reff_timestamp = int(corrected_datetime.timestamp())
    corrected_video_timestamp = corrected_reff_timestamp + 20

    wrong_reff_timestamp = datetime(
        2024,
        8,
        1,
        8,
        27,
        0,
    ).timestamp()
    wrong_video_timestamp = datetime(
        2024,
        8,
        1,
        8,
        27,
        20,
    ).timestamp()

    old_reff_path = real_reff_path("RTT_TEST_TIME_ADJUSTMENT.reff")
    old_video_name = "ScreenRec_2099-12-31_23-59-59.mp4"
    old_video_path = real_video_path(old_video_name)

    corrected_reff_name = build_corrected_reff_filename(
        corrected_reff_timestamp,
    )
    corrected_video_name = build_corrected_video_filename(
        old_video_name,
        corrected_video_timestamp,
    )

    assert corrected_video_name is not None

    corrected_reff_path = real_reff_path(corrected_reff_name)
    corrected_video_path = real_video_path(corrected_video_name)

    cleanup_paths = [
        old_reff_path,
        old_video_path,
        corrected_reff_path,
        corrected_video_path,
    ]

    # Only test-owned input names are safe to remove before setup.
    remove_remote_files(
        TABLET_SERIAL,
        [
            old_reff_path,
            old_video_path,
        ],
    )

    for generated_path in (
        corrected_reff_path,
        corrected_video_path,
    ):
        if remote_file_exists(
            TABLET_SERIAL,
            generated_path,
        ):
            pytest.fail(
                f"Time Adjustment test would collide with an existing real file: {generated_path}"
            )

    with visible_time_case(
        "Case_01_Rename_And_Flight_Folder",
        title="Time Adjustment rename + flight-folder timestamp",
        purpose=(
            "Verify the complete chain on the real Tablet and real app paths: "
            "wrong timestamps -> corrected timestamps -> renamed REFF/video -> "
            "extraction -> flight folder named from the corrected REFF timestamp."
        ),
        setup=(
            "Tablet is manually set to 2024-08-01 around 08:30.\n"
            "Test REFF mtime: 2024-08-01 08:27:00.\n"
            "Test video mtime: 2024-08-01 08:27:20.\n"
            f"Corrected REFF name: {corrected_reff_name}\n"
            f"Corrected video name: {corrected_video_name}"
        ),
        expected=(
            "DUMP/ exists.\n"
            "Exactly one Flight_01 folder is created.\n"
            "The folder timestamp matches the corrected REFF timestamp.\n"
            f"It contains TABLET_{corrected_reff_name}.\n"
            f"It contains VIDEO_TABLET_{corrected_video_name}.\n"
            "No warning."
        ),
    ) as (_, dump_dir):
        patch_dump(
            monkeypatch,
            dump_dir,
        )

        try:
            push_file_direct(
                TABLET_SERIAL,
                SOURCE_REFF_1,
                old_reff_path,
                wrong_reff_timestamp,
            )
            push_file_direct(
                TABLET_SERIAL,
                SOURCE_VIDEO,
                old_video_path,
                wrong_video_timestamp,
            )

            corrected_count = apply_file_time_corrections(
                tablet,
                [
                    FileTimeCorrection(
                        file_path=old_reff_path,
                        current_timestamp=int(wrong_reff_timestamp),
                        corrected_timestamp=corrected_reff_timestamp,
                    ),
                    FileTimeCorrection(
                        file_path=old_video_path,
                        current_timestamp=int(wrong_video_timestamp),
                        corrected_timestamp=corrected_video_timestamp,
                    ),
                ],
            )

            assert corrected_count == 2

            assert (
                run_adb(
                    TABLET_SERIAL,
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
                    TABLET_SERIAL,
                    "shell",
                    "test",
                    "-f",
                    corrected_video_path,
                    check=False,
                ).returncode
                == 0
            )

            process_selected_tablet_files(
                monkeypatch,
                reff_files=[corrected_reff_path],
                video_files=[corrected_video_path],
            )

            reff_result = grouping.group_files_into_flights(
                starting_flight_number=1,
            )
            video_result = grouping.group_videos_into_flights(
                flights=reff_result.flights,
                standalone_reffs=reff_result.standalone_reffs,
                starting_flight_number=reff_result.next_flight_number,
            )

            expected_flight_name = "Flight_01_" + corrected_datetime.strftime("%d-%m-%Y_%H-%M-%S")

            assert len(video_result.flights) == 1
            assert video_result.warnings == []
            assert video_result.flights[0].name == expected_flight_name

            assert (dump_dir / expected_flight_name / f"TABLET_{corrected_reff_name}").is_file()

            assert (
                dump_dir / expected_flight_name / f"VIDEO_TABLET_{corrected_video_name}"
            ).is_file()
        finally:
            remove_remote_files(
                TABLET_SERIAL,
                cleanup_paths,
            )


def test_time_adjustment_collision_uses_number_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Video collision rename creates _Number_1 without overwriting."""

    ensure_real_remote_directories((TABLET_SERIAL,))

    tablet = build_test_device(
        TABLET_SERIAL,
        "TABLET",
    )

    corrected_datetime = datetime.now().replace(
        second=0,
        microsecond=0,
    )
    corrected_timestamp = int(corrected_datetime.timestamp())

    wrong_timestamp = datetime(
        2024,
        8,
        1,
        8,
        28,
        0,
    ).timestamp()

    old_video_name = "ScreenRec_2024-08-01_08-28.mp4"
    old_video_path = real_video_path(old_video_name)

    corrected_name = build_corrected_video_filename(
        old_video_name,
        corrected_timestamp,
    )
    assert corrected_name is not None

    corrected_path = real_video_path(corrected_name)

    corrected_name_path = Path(corrected_name)
    numbered_name = f"{corrected_name_path.stem}_Number_1{corrected_name_path.suffix}"
    numbered_path = real_video_path(numbered_name)

    cleanup_paths = [
        old_video_path,
        corrected_path,
        numbered_path,
    ]

    # Remove only the clearly test-owned wrong-time input before setup.
    remove_remote_files(
        TABLET_SERIAL,
        [
            old_video_path,
        ],
    )

    for generated_path in (
        corrected_path,
        numbered_path,
    ):
        if remote_file_exists(
            TABLET_SERIAL,
            generated_path,
        ):
            pytest.fail(
                "Time Adjustment collision test would touch an existing real file: "
                f"{generated_path}"
            )

    with visible_time_case(
        "Case_02_Collision_Number_1",
        title="Time Adjustment video filename collision",
        purpose=(
            "Verify that two Tablet screen recordings may resolve to the same "
            "corrected filename without one overwriting the other. The second "
            "video must receive the _Number_1 suffix."
        ),
        setup=(
            "An existing video already uses the corrected target filename.\n"
            "A second video is corrected to the same timestamp.\n"
            f"Existing video: {corrected_name}\n"
            f"Expected collision video: {numbered_name}"
        ),
        expected=(
            "DUMP/ exists.\n"
            "The two related videos create exactly one Flight_01 folder.\n"
            "The flight contains both videos and zero REFF files.\n"
            f"VIDEO_TABLET_{corrected_name}\n"
            f"VIDEO_TABLET_{numbered_name}\n"
            "No video is overwritten.\n"
            "Both videos produce missing-REFF warnings."
        ),
    ) as (case_dir, dump_dir):
        patch_dump(
            monkeypatch,
            dump_dir,
        )

        try:
            # First video already occupies the corrected target name.
            push_file_direct(
                TABLET_SERIAL,
                SOURCE_VIDEO,
                corrected_path,
                corrected_timestamp,
            )

            # Second video starts with the wrong date/time name.
            push_file_direct(
                TABLET_SERIAL,
                SOURCE_VIDEO,
                old_video_path,
                wrong_timestamp,
            )

            corrected_count = apply_file_time_corrections(
                tablet,
                [
                    FileTimeCorrection(
                        file_path=old_video_path,
                        current_timestamp=int(wrong_timestamp),
                        corrected_timestamp=corrected_timestamp,
                    ),
                ],
            )

            assert corrected_count == 1

            assert (
                run_adb(
                    TABLET_SERIAL,
                    "shell",
                    "test",
                    "-f",
                    corrected_path,
                    check=False,
                ).returncode
                == 0
            )

            assert (
                run_adb(
                    TABLET_SERIAL,
                    "shell",
                    "test",
                    "-f",
                    numbered_path,
                    check=False,
                ).returncode
                == 0
            )

            process_selected_tablet_files(
                monkeypatch,
                video_files=[
                    corrected_path,
                    numbered_path,
                ],
            )

            reff_result = grouping.group_files_into_flights(
                starting_flight_number=1,
            )
            video_result = grouping.group_videos_into_flights(
                flights=reff_result.flights,
                standalone_reffs=reff_result.standalone_reffs,
                starting_flight_number=reff_result.next_flight_number,
            )

            assert len(video_result.flights) == 1

            flight = video_result.flights[0]

            assert flight.reff_files == []
            assert len(flight.videos) == 2
            assert len(video_result.warnings) == 2
            assert all(warning.flight_name == flight.name for warning in video_result.warnings)

            write_warnings(
                case_dir,
                video_result.warnings,
            )

            assert (Path(flight.path) / f"VIDEO_TABLET_{corrected_name}").is_file()
            assert (Path(flight.path) / f"VIDEO_TABLET_{numbered_name}").is_file()
        finally:
            remove_remote_files(
                TABLET_SERIAL,
                cleanup_paths,
            )
