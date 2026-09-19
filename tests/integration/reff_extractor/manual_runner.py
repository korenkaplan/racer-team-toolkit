import os
import subprocess
import sys
from pathlib import Path

from tests.integration.reff_extractor.config import (
    MANUAL_OUTPUT_ROOT,
    RUN_ENV_VAR,
)

CASES = [
    (
        "Normal multi-device flight",
        "test_grouping_cases.py::test_case_01_normal_multi_device_flight",
        "Case_01_Normal_Multi_Device",
    ),
    (
        "Missing-device REFF video joins existing flight",
        "test_grouping_cases.py::test_case_02_missing_device_reff_video_joins_existing_flight",
        "Case_02_Missing_Racer_REFF",
    ),
    (
        "Standalone REFF + cross-device video",
        "test_grouping_cases.py::test_case_03_cross_device_video_creates_flight_from_standalone_reff",
        "Case_03_Standalone_Cross_Device",
    ),
    (
        "Same-device standalone REFF + video",
        "test_grouping_cases.py::test_case_04_same_device_standalone_reff_and_video",
        "Case_04_Same_Device_Standalone",
    ),
    (
        "Same-device priority beats cross-device fallback",
        "test_grouping_cases.py::test_case_05_same_device_priority_beats_cross_device_fallback",
        "Case_05_Same_Device_Beats_Fallback",
    ),
    (
        "Priority 1 beats Priority 2",
        "test_grouping_cases.py::test_case_06_priority_one_beats_priority_two_within_same_device",
        "Case_06_Priority_1_Beats_Priority_2",
    ),
    (
        "Priority 2 when no Priority 1 exists",
        "test_grouping_cases.py::test_case_07_priority_two_used_when_no_priority_one",
        "Case_07_Priority_2",
    ),
    (
        "Outside 8-minute window",
        "test_grouping_cases.py::test_case_08_outside_eight_minute_window_stays_standalone",
        "Case_08_Outside_8_Minutes",
    ),
    (
        "Repeated extraction numbering continuity",
        "test_grouping_cases.py::test_case_09_repeated_extraction_numbering_continuity",
        "Case_09_Numbering_Continuity",
    ),
    (
        "Closest match wins",
        "test_grouping_cases.py::test_case_10_closest_match_wins_within_same_priority",
        "Case_10_Closest_Match",
    ),
    (
        "FlightFile path update after real moves",
        "test_grouping_cases.py::test_case_11_paths_update_after_real_moves",
        "Case_11_Path_Update",
    ),
]

TEST_ROOT = Path(__file__).parent


def print_menu() -> None:
    print("\nREFF Real-Device Integration Test Runner")
    print("=" * 52)

    for index, (title, _, _) in enumerate(
        CASES,
        start=1,
    ):
        print(f"{index:2}. {title}")

    print(" 0. Exit")


def choose_case() -> int:
    while True:
        print_menu()
        raw = input("\nSelect a test: ").strip()

        try:
            choice = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue

        if 0 <= choice <= len(CASES):
            return choice

        print("Invalid selection.")


def run_case(
    case_number: int,
    title: str,
    pytest_target: str,
    case_folder: str,
) -> int:
    output_dir = MANUAL_OUTPUT_ROOT / case_folder

    print()
    print("=" * 76)
    print(f"CASE {case_number}: {title}")
    print("=" * 76)
    print("This test uses the real Android devices and the real app paths:")
    print("  /sdcard/Records")
    print("  /sdcard/Eyesatop-Records/Screen-Videos")
    print()
    print(f"Visible Desktop result: {output_dir}")
    print()

    env = os.environ.copy()
    env[RUN_ENV_VAR] = "1"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_ROOT / pytest_target),
            "-vv",
            "-s",
        ],
        env=env,
        check=False,
    )

    print()
    print("=" * 76)
    print(
        "AUTOMATED RESULT: PASS"
        if result.returncode == 0
        else "AUTOMATED RESULT: FAIL"
    )
    print()
    print(f"Open this folder and compare:")
    print(f"  {output_dir}")
    print()
    print("Read:")
    print("  TEST_DESCRIPTION.txt")
    print("  ACTUAL_RESULT.txt")
    print("  AUTOMATED_RESULT.txt")

    if case_number == 9:
        print("  NUMBERING_MAP.txt")

    print("=" * 76)
    print()

    input("Press Enter when you are finished inspecting this case...")

    return result.returncode


def main() -> None:
    MANUAL_OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    while True:
        choice = choose_case()

        if choice == 0:
            return

        title, target, case_folder = CASES[choice - 1]

        run_case(
            choice,
            title,
            target,
            case_folder,
        )


if __name__ == "__main__":
    main()
