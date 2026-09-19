import os
import subprocess
import sys
from pathlib import Path

from tests.integration.reff_extractor.config import (
    MANUAL_OUTPUT_ROOT,
    TIME_ADJUSTMENT_RUN_ENV_VAR,
    TIME_ADJUSTMENT_SERIAL,
    TIME_ADJUSTMENT_WRONG_DATE,
    TIME_ADJUSTMENT_WRONG_TIME,
)

CASES = [
    (
        "Time Adjustment rename + flight-folder timestamp",
        "test_time_adjustment_live.py::test_time_adjustment_renaming_creates_correct_flight_folder",
        "Case_01_Rename_And_Flight_Folder",
    ),
    (
        "Time Adjustment filename collision (_Number_1)",
        "test_time_adjustment_live.py::test_time_adjustment_collision_uses_number_suffix",
        "Case_02_Collision_Number_1",
    ),
]

TEST_ROOT = Path(__file__).parent
OUTPUT_ROOT = MANUAL_OUTPUT_ROOT / "Time Adjustment"


def print_instructions() -> None:
    print()
    print("TABLET TIME ADJUSTMENT TESTS")
    print("=" * 76)
    print(f"Tablet serial: {TIME_ADJUSTMENT_SERIAL}")
    print()
    print("Before running these tests, manually set ONLY the Tablet to:")
    print(f"  Date: {TIME_ADJUSTMENT_WRONG_DATE}")
    print(f"  Time: {TIME_ADJUSTMENT_WRONG_TIME}")
    print()
    print("These tests use the real Tablet paths:")
    print("  /sdcard/Records")
    print("  /sdcard/Eyesatop-Records/Screen-Videos")
    print()
    print("Do not run the normal extraction tests while the Tablet clock is wrong.")
    print("Restore automatic/current date and time when finished.")
    print("=" * 76)


def print_menu() -> None:
    print()

    for index, (title, _, _) in enumerate(
        CASES,
        start=1,
    ):
        print(f"{index}. {title}")

    print("0. Exit")


def choose_case() -> int:
    while True:
        print_menu()
        raw = input(
            "\nSelect a time-adjustment test: "
        ).strip()

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
    target: str,
    case_folder: str,
) -> int:
    output_dir = OUTPUT_ROOT / case_folder

    env = os.environ.copy()
    env[TIME_ADJUSTMENT_RUN_ENV_VAR] = "1"

    print()
    print("=" * 76)
    print(f"TIME ADJUSTMENT CASE {case_number}: {title}")
    print("=" * 76)
    print(f"Visible Desktop result: {output_dir}")
    print()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(TEST_ROOT / target),
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
    print("=" * 76)
    print()

    return result.returncode


def main() -> None:
    print_instructions()

    while True:
        choice = choose_case()

        if choice == 0:
            return

        title, target, case_folder = CASES[
            choice - 1
        ]

        run_case(
            choice,
            title,
            target,
            case_folder,
        )

        input(
            "\nPress Enter when you are finished "
            "inspecting this case..."
        )


if __name__ == "__main__":
    main()
